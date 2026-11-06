# -*- coding: utf-8 -*-
"""Бэкап listings.db через sqlite3.Connection.backup (WAL-безопасный)
+ restore-проверка «учебной тревоги»: бэкап валиден только если из него
восстанавливаются данные (integrity_check + сравнение count/last row).
Запуск: python db_backup.py <src> <dst>
"""
import os
import sqlite3
import sys


def backup_strict(src, dst):
    """Копия через backup API (не файл-копия: WAL полностью сворачивается)."""
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    src_conn = sqlite3.connect(src)
    dst_conn = sqlite3.connect(dst)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()


try:
    from tenacity import retry, stop_after_attempt, wait_exponential
    backup = retry(stop=stop_after_attempt(3),
                   wait=wait_exponential(min=1, max=30))(backup_strict)
except ImportError:  # tenacity недоступна — без retry
    backup = backup_strict


def tables(conn):
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]


def verify(src, dst):
    """True: копия восстанавливает данные и целостна."""
    src_conn = sqlite3.connect(src)
    dst_conn = sqlite3.connect(dst)
    try:
        if dst_conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            return False
        src_tables = set(tables(src_conn))
        if not src_tables:
            return True
        dst_tables = set(tables(dst_conn))
        if src_tables - dst_tables:
            return False
        for name in src_tables:
            src_count = src_conn.execute("SELECT COUNT(*) FROM %s" % name).fetchone()[0]
            dst_count = dst_conn.execute("SELECT COUNT(*) FROM %s" % name).fetchone()[0]
            if src_count != dst_count:
                return False
            last_src = src_conn.execute(
                "SELECT * FROM %s WHERE rowid=(SELECT MAX(rowid) FROM %s)" % (name, name)).fetchone()
            last_dst = dst_conn.execute(
                "SELECT * FROM %s WHERE rowid=(SELECT MAX(rowid) FROM %s)" % (name, name)).fetchone()
            if last_src != last_dst:
                return False
        return True
    finally:
        dst_conn.close()
        src_conn.close()


def main(argv):
    if len(argv) != 3:
        print("Использование: python db_backup.py <listings.db> <копия>")
        return 2
    src, dst = argv[1], argv[2]
    backup(src, dst)
    ok = verify(src, dst)
    print("бэкап: %s -> %s; restore-проверка: %s" % (src, dst, "OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
