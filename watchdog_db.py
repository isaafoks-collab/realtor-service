# -*- coding: utf-8 -*-
"""A3: проверка свежести БД для watchdog-воркфлоу.

Ручной запуск: python watchdog_db.py
Код возврата: 0 — БД отмечалась за последние FRESH_MINUTES минут,
2 — тишина дольше (в Actions запускается резервный прогон).
"""
import sqlite3
import sys
from datetime import datetime, timezone

import metrics

FRESH_MINUTES = 40
DB_PATH = "listings.db"


def freshness_minutes(path=DB_PATH):
    """Сколько минут назад БД «видела» объявления; None — данных нет."""
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            "SELECT last_seen FROM listings WHERE last_seen IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()
    newest = None
    for (value,) in rows:
        dt = metrics.to_utc(value)
        if dt is None:
            continue
        if newest is None or dt > newest:
            newest = dt
    if newest is None:
        return None
    now = datetime.now(timezone.utc)
    return max(0.0, (now - newest).total_seconds() / 60.0)


def main():
    age = freshness_minutes()
    if age is None:
        print("freshness: данных о свежести нет")
        return 2
    status = "СВЕЖАЯ" if age <= FRESH_MINUTES else "ЧУЖАЯ-ТИШИНА"
    print("freshness: %s — %.1f мин назад" % (status, age))
    return 0 if age <= FRESH_MINUTES else 2


if __name__ == "__main__":
    sys.exit(main())
