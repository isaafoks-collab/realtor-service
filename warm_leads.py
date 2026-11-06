# -*- coding: utf-8 -*-
"""Тёплые клиенты v1: согласие собственника на звонок риэлтора, карточка лида.

Хранилище: SQLite (WARM_LEADS_DB, по умолчанию warm_leads.db).
Дубли: у пользователя может быть ровно один необработанный лид.
Доставка: лог-файл + (при наличии) отправка прямо из бота (send-колбэк).
Время нажатия — МСК (UTC+3, летнего перевода нет).
"""
import json
import os
import sqlite3
import textwrap
import datetime

DB_PATH = os.getenv("WARM_LEADS_DB", "warm_leads.db")
LOG_PATH = os.getenv("WARM_LEADS_LOG", os.path.join("data", "warm_leads_log.txt"))
MSK = datetime.timezone(datetime.timedelta(hours=3))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    city TEXT,
    rooms TEXT,
    area REAL,
    floor TEXT,
    price_wish TEXT,
    deadline TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL
)
"""


def _conn(path):
    conn = sqlite3.connect(path)
    conn.execute(_SCHEMA)
    return conn


def save_lead(user_id, payload, db_path=None):
    path = db_path or DB_PATH
    now = payload.get("now") or datetime.datetime.now(MSK)
    created_at = now.isoformat(timespec="minutes")
    username = payload.get("username")
    city = payload.get("city")
    rooms = payload.get("rooms")
    area = payload.get("area")
    floor = payload.get("floor")
    price_wish = payload.get("price_wish")
    deadline = payload.get("deadline")
    conn = _conn(path)
    try:
        row = conn.execute(
            "SELECT id, status FROM leads WHERE user_id=? AND status='new'",
            (user_id,)).fetchone()
        if row:
            return "exists", row[0]
        cur = conn.execute(
            "INSERT INTO leads (user_id, username, city, rooms, area, floor, "
            "price_wish, deadline, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,'new',?)",
            (user_id, username, city, rooms, area, floor, price_wish,
             deadline, created_at))
        conn.commit()
        return "new", cur.lastrowid
    finally:
        conn.close()


def get_lead(user_id, db_path=None):
    path = db_path or DB_PATH
    conn = _conn(path)
    try:
        row = conn.execute(
            "SELECT id, username, city, rooms, area, floor, price_wish, "
            "deadline, status, created_at FROM leads "
            "WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return None, ""
    return row, build_card(row)


def build_card(row, ref=None):
    """row: (id, username, city, rooms, area, floor, price_wish, deadline,
             status, created_at-iso).
    ref: текущее время МСК (по умолчанию — сейчас)."""
    (_id, _username, city, rooms, area, floor,
     price_wish, deadline, _status, created_at) = row
    ref = ref or datetime.datetime.now(MSK)
    created = datetime.datetime.fromisoformat(created_at)
    parts = []
    if rooms:
        parts.append("%s-к" % rooms)
    if area:
        parts.append("%g м²" % area)
    if floor:
        parts.append(floor)
    if city:
        parts.append(city)
    obj = ", ".join(parts)
    lines = ["Собственник: согласен на звонок риэлтора"]
    if obj:
        lines.append("Объект: %s" % obj)
    if price_wish:
        lines.append("Ожидаемая цена: %s" % price_wish)
    if deadline:
        lines.append("Срок: продам в %s" % deadline)
    hhmm = created.strftime("%H:%M")
    if created.date() == ref.date():
        mark = "сегодня"
    elif (ref.date() - created.date()).days == 1:
        mark = "вчера"
    else:
        mark = created.strftime("%d.%m")
    lines.append("Готовность: сам нажал «нужна помощь» %s в %s" % (mark, hhmm))
    return "\n".join(lines)


def mark_handled(user_id, db_path=None):
    return _mark("user_id", user_id, db_path)


def mark_handled_id(lead_id, db_path=None):
    return _mark("id", lead_id, db_path)


def _mark(field, value, db_path):
    path = db_path or DB_PATH
    conn = _conn(path)
    try:
        cur = conn.execute(
            "UPDATE leads SET status='handled' WHERE %s=? AND status='new'"
            % field, (value,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_leads(status="new", limit=10, db_path=None):
    path = db_path or DB_PATH
    conn = _conn(path)
    try:
        return conn.execute(
            "SELECT id, user_id, username, city, rooms, area, floor, "
            "price_wish, deadline, status, created_at FROM leads "
            "WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit)
        ).fetchall()
    finally:
        conn.close()


def deliver(card, log_path=None, send=None):
    log_path = log_path or LOG_PATH
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(datetime.datetime.now(MSK).isoformat(timespec="seconds")
                + " " + card.replace("\n", " | ") + "\n")
    if send:
        send(card)
