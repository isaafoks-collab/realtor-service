"""Модуль вечного доступа: пароль-код, один бесплатник навсегда."""
import os
import sqlite3
import datetime

DB_PATH = os.getenv("ACCESS_DB", "access.db")

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS granted ("
        "user_id INTEGER PRIMARY KEY, granted_at TEXT, code TEXT)"
    )
    return conn

def log_event(text):
    with open(os.getenv("ACCESS_LOG", "access_log.txt"), "a", encoding="utf-8") as f:
        f.write(datetime.datetime.now().isoformat(timespec="seconds") + " " + text + "\n")

def grant(user_id: int, code: str, free_code: str) -> str:
    if code.strip().upper() != free_code.strip().upper():
        log_event(f"DENY user={user_id} wrong code")
        return "deny"
    conn = _conn()
    if conn.execute("SELECT 1 FROM granted WHERE user_id=?", (user_id,)).fetchone():
        conn.close()
        log_event(f"GRANT-AGAIN user={user_id}")
        return "again"
    conn.execute("INSERT INTO granted (user_id, granted_at, code) VALUES (?,?,?)",
                 (user_id, datetime.datetime.now().isoformat(timespec="seconds"), code))
    conn.commit()
    conn.close()
    log_event(f"GRANT user={user_id} permanent access")
    return "ok"

def has_access(user_id: int) -> bool:
    conn = _conn()
    row = conn.execute("SELECT 1 FROM granted WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return bool(row)
