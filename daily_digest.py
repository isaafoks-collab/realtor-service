# -*- coding: utf-8 -*-
"""Утренняя сводка: новые лоты-собственники → Telegram риэлтору.

Правила (план plany/2026-11-10-daily-digest-telegram.md, 2 круга рыбок):
- выборка: is_owner=1, sent_at IS NULL, price IS NOT NULL,
  detected_at >= (UTC сейчас - 24ч);
- пустая выборка → exit 0 без сообщения (анти-спам);
- сводка чанками <=3500 символов (лимит Telegram 4096);
- после успешной отправки: sent_at=now_utc для url из отправленных
  чанков (partial success) + снятие их записей из notify_queue;
- нет BOT_TOKEN или REALTOR_CHAT_ID → exit 0, лог «сводка выключена»;
- при неудаче отправки: попытка короткого «[СБОЙ] сводка: ...» на тот
  же chat_id, exit 1.
Запуск: python daily_digest.py [--limit N]
"""
import datetime
import os
import sqlite3
import sys
import time

import requests

import db_schema

DB_PATH = os.environ.get("LISTINGS_DB", "listings.db")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("REALTOR_CHAT_ID", "")
MAX_ITEMS = 40
WINDOW_HOURS = 24
CHUNK_LIMIT = 3500
PAUSE_BETWEEN = 3.0
API_URL = "https://api.telegram.org/bot%s/sendMessage"


def utc_now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def log(msg):
    print(msg, flush=True)


def select_new(conn, since_iso, limit=MAX_ITEMS):
    """(rows, total) — строки и полный счёт выборки (для лога переполнения)."""
    where = ("WHERE is_owner=1 AND sent_at IS NULL AND price IS NOT NULL "
             "AND detected_at >= ?")
    total = conn.execute("SELECT COUNT(*) FROM listings %s" % where,
                         (since_iso,)).fetchone()[0]
    rows = conn.execute(
        "SELECT url, city, title, price, rooms, area FROM listings %s "
        "ORDER BY detected_at DESC LIMIT ?" % where,
        (since_iso, limit)).fetchall()
    return rows, total


def fmt_price(price):
    return "{:,.0f}".format(price).replace(",", " ") + " ₽"


def fmt_row(row):
    url, city, title, price, rooms, area = row
    parts = []
    if city:
        parts.append("[%s]" % city)
    if rooms:
        parts.append(str(rooms))
    if area:
        parts.append("%g м²" % area)
    if price:
        parts.append(fmt_price(price))
    return "— %s — %s" % (" ".join(parts) if parts else "лот", url)


def build_text(rows):
    """→ (chunks, chunks_urls): тексты чанков <=CHUNK_LIMIT и список url
    на каждый чанк (partial success знает, кому ставить sent_at)."""
    ordered = sorted(rows, key=lambda r: (r[1] or "",))
    lines = [(r[0], fmt_row(r)) for r in ordered]
    chunks, chunks_urls = [], []
    cur_lines, cur_urls, cur_len = [], [], 0
    for url, line in lines:
        extra = len(line) + 1
        if cur_lines and cur_len + extra > CHUNK_LIMIT - 80:
            chunks.append(cur_lines)
            chunks_urls.append(cur_urls)
            cur_lines, cur_urls, cur_len = [], [], 0
        cur_lines.append(line)
        cur_urls.append(url)
        cur_len += extra
    if cur_lines:
        chunks.append(cur_lines)
        chunks_urls.append(cur_urls)
    texts = []
    for i, (chunk_lines, chunk_urls) in enumerate(zip(chunks, chunks_urls)):
        header = "Свежие собственники за 24ч (часть %d/%d): %d шт." % (
            i + 1, len(chunks), len(chunk_urls))
        texts.append(header + "\n" + "\n".join(chunk_lines))
    return texts, chunks_urls


def send_text(text, timeout=30):
    """3 попытки с backoff 2/4/8 на сетевые ошибки и 429/500+. Бросает
    последнюю ошибку, если так и не отправили."""
    last = None
    for attempt in range(3):
        try:
            resp = requests.post(
                API_URL % BOT_TOKEN,
                json={"chat_id": CHAT_ID, "text": text,
                      "disable_web_page_preview": True},
                timeout=timeout)
            code = resp.status_code
            if code in (429,) or code >= 500:
                last = RuntimeError("Telegram %s" % code)
            elif code != 200:
                raise RuntimeError("Telegram %s: %s" % (code, resp.text[:200]))
            else:
                return
        except RuntimeError as e:
            raise
        except Exception as e:
            last = e
        if attempt < 2:
            time.sleep(2 * (2 ** attempt))
    raise last


def send_fallback(text, timeout=15):
    """Одна попытка сообщить человеку о сбое; тихо глотает свою ошибку."""
    try:
        requests.post(API_URL % BOT_TOKEN,
                      json={"chat_id": CHAT_ID, "text": text},
                      timeout=timeout)
    except Exception:
        pass


def mark_sent(conn, sent_urls, now_iso):
    for url in sent_urls:
        conn.execute("UPDATE listings SET sent_at=? WHERE url=?",
                     (now_iso, url))
    conn.commit()


def clear_queue(conn, sent_urls, now_iso):
    """Снять из notify_queue записи, чей url реально отправлен."""
    wanted = set(sent_urls)
    ids = [r[0] for r in db_schema.pending(conn) if r[1] in wanted]
    if ids:
        db_schema.mark_delivered(conn, ids, now_iso)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    limit = MAX_ITEMS
    if "--limit" in argv:
        i = argv.index("--limit")
        limit = int(argv[i + 1])

    if not BOT_TOKEN or not CHAT_ID:
        log("[СВОДКА] выключена: нет BOT_TOKEN или REALTOR_CHAT_ID")
        return 0

    conn = sqlite3.connect(DB_PATH)
    try:
        db_schema.ensure(conn)
        since = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.timedelta(hours=WINDOW_HOURS)).isoformat()
        rows, total = select_new(conn, since, limit=limit)
        if total == 0:
            log("[СВОДКА] новых собственников за 24ч: 0 — не отправляю")
            return 0
        if total > len(rows):
            log("[СВОДКА] не влезло: %d лотов сверх лимита %d" %
                (total - len(rows), limit))
        now_iso = utc_now_iso()
        texts, chunks_urls = build_text(rows)
        sent_urls = []
        for text, urls in zip(texts, chunks_urls):
            try:
                send_text(text)
            except Exception as e:
                log("[СВОДКА] сбой отправки: %s: %s" % (type(e).__name__, e))
                send_fallback("[СБОЙ] сводка собственников: %s: %s" %
                              (type(e).__name__, e))
                if sent_urls:
                    mark_sent(conn, sent_urls, now_iso)
                    clear_queue(conn, sent_urls, now_iso)
                return 1
            sent_urls.extend(urls)
            if text is not texts[-1]:
                time.sleep(PAUSE_BETWEEN)
        mark_sent(conn, sent_urls, now_iso)
        clear_queue(conn, sent_urls, now_iso)
        log("[СВОДКА] отправлено: %d лотов, %d сообщений" %
            (len(sent_urls), len(texts)))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
