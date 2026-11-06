# -*- coding: utf-8 -*-
"""Планировщик: раз в N часов — ЦИАН, Яндекс, конвертер, анти-фильтр, отчёт."""
import subprocess, sys, time, random
from datetime import datetime

INTERVAL_HOURS = 6

def run(script):
    print("[%s] >> %s" % (datetime.now().strftime("%H:%M:%S"), script))
    try:
        r = subprocess.run([sys.executable, script], timeout=7200,
                           capture_output=True, text=True, errors="replace")
        tail = (r.stdout or "").strip().splitlines()
        for line in tail[-3:]:
            print("   ", line)
        if r.returncode != 0:
            err = (r.stderr or "").strip().splitlines()
            print("   [ERR]", err[-1] if err else "код %d" % r.returncode)
            return False
        return True
    except Exception as e:
        print("   [ERR]", type(e).__name__, e)
        return False

def report():
    try:
        import sqlite3
        conn = sqlite3.connect("listings.db")
        total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        owners = conn.execute("SELECT COUNT(*) FROM listings WHERE is_owner=1").fetchone()[0]
        fresh = conn.execute(
            "SELECT COUNT(*) FROM listings WHERE last_seen >= datetime('now', '-1 day')"
        ).fetchone()[0]
        conn.close()
        line = "[%s] база: всего=%d, частников=%d, видны за сутки=%d" % (
            datetime.now().strftime("%d.%m %H:%M"), total, owners, fresh)
        print(line)
        with open("scheduler.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print("[ERR] отчёт:", e)

print("планировщик запущен, цикл каждые %d ч. Ctrl+C — стоп." % INTERVAL_HOURS)
while True:
    print("=" * 50)
    for script in ("parser_cian.py", "parser_yandex.py", "json_to_db.py"):
        run(script)
        time.sleep(random.uniform(20, 60))
    report()
    time.sleep(INTERVAL_HOURS * 3600)
