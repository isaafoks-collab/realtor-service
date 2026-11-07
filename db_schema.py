# -*- coding: utf-8 -*-
"""Схема БД Волны 3: метрики скорости (A4) и ночная очередь уведомлений (A5).

- listings: published_at (со площадки), detected_at (увидели мы),
  sent_at (отправили риэлтору) — считаются конвертером и отправкой;
- notify_queue: уведомления между 23:00 и 07:00 МСК копятся до утра,
  одно объявление — одна запись (partial unique index по URL);
- journal_mode=WAL — безопасная запись при параллельных процессах.
Миграция идемпотентна. Перед первой миграцией — бэкап (F2):
python db_backup.py listings.db data/listings_backup.sqlite
На пустом сервере создаёт таблицу listings с полной текущей схемой.
"""
import sqlite3

LISTINGS_METRICS = ("published_at", "detected_at", "sent_at")

_TABLE_SQL = (
    "CREATE TABLE IF NOT EXISTS listings ("
    " url TEXT PRIMARY KEY,"
    " city TEXT,"
    " title TEXT,"
    " price INTEGER,"
    " rooms TEXT,"
    " area REAL,"
    " author_type TEXT,"
    " is_owner INTEGER,"
    " first_seen TEXT,"
    " last_seen TEXT,"
    " price_dropped INTEGER DEFAULT 0,"
    " agent_risk INTEGER,"
    " floor INTEGER,"
    " floors_total INTEGER,"
    " source TEXT,"
    " region TEXT,"
    " published_at TEXT,"
    " detected_at TEXT,"
    " sent_at TEXT"
    ")"
)


def ensure(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(listings)")]
    if not cols:
        conn.execute(_TABLE_SQL)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(listings)")]
    for name in LISTINGS_METRICS:
        if name not in cols:
            conn.execute("ALTER TABLE listings ADD COLUMN %s TEXT" % name)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS notify_queue ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " url TEXT NOT NULL,"
        " category TEXT,"
        " chat_id TEXT,"
        " created_at TEXT NOT NULL,"
        " delivered_at TEXT"
        ")")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_notify_queue_pending "
        "ON notify_queue (url) WHERE delivered_at IS NULL")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.commit()
    return True


def queue_notice(conn, url, category, chat_id, created_at):
    """В очередь ночных уведомлений. Дубль (тот же URL жив в очереди) —
    молча пропускается. Возвращает True, если запись добавлена."""
    try:
        conn.execute(
            "INSERT INTO notify_queue (url, category, chat_id, created_at) "
            "VALUES (?,?,?,?)", (url, category, chat_id, created_at))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def pending(conn, limit=200):
    return conn.execute(
        "SELECT id, url, category, chat_id, created_at FROM notify_queue "
        "WHERE delivered_at IS NULL ORDER BY id LIMIT ?", (limit,)).fetchall()


def mark_delivered(conn, ids, delivered_at):
    for qid in ids:
        conn.execute(
            "UPDATE notify_queue SET delivered_at=? WHERE id=?",
            (delivered_at, qid))
    conn.commit()


if __name__ == "__main__":
    con = sqlite3.connect("listings.db")
    ensure(con)
    print("схема актуальна: метрики + очередь, journal=%s" %
          con.execute("PRAGMA journal_mode").fetchone()[0])
    con.close()
