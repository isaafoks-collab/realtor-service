# -*- coding: utf-8 -*-
"""db_backup: WAL-безопасный бэкап и restore-проверка.
Запуск: python -m unittest test_db_backup"""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db_backup


def make_src(path):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE listings "
                 "(rowid_ INTEGER PRIMARY KEY, city TEXT, price REAL)")
    conn.executemany("INSERT INTO listings (city, price) VALUES (?,?)",
                     [("Одинцово", 7_200_000), ("Саратов", 3_500_000)])
    conn.commit()
    conn.close()


class DbBackupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, "listings.db")
        self.dst = os.path.join(self.tmp.name, "backup.sqlite")
        make_src(self.src)

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_via_backup_api_preserves_last_row(self):
        db_backup.backup(self.src, self.dst)
        self.assertTrue(db_backup.verify(self.src, self.dst))

    def test_verify_detects_corrupted_backup(self):
        db_backup.backup(self.src, self.dst)
        conn = sqlite3.connect(self.dst)
        conn.execute("DELETE FROM listings WHERE rowid=(SELECT MAX(rowid) FROM listings)")
        conn.commit()
        conn.close()
        self.assertFalse(db_backup.verify(self.src, self.dst))

    def test_verify_detects_missing_table(self):
        conn = sqlite3.connect(self.dst)
        conn.execute("CREATE TABLE other (x)")
        conn.close()
        self.assertFalse(db_backup.verify(self.src, self.dst))

    def test_cli_exit_codes(self):
        self.assertEqual(db_backup.main(["db_backup.py", self.src, self.dst]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
