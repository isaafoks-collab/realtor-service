# -*- coding: utf-8 -*-
"""Тесты Скоростного контура Волны 3 (A2/A4/A5 + миграция + сбор города).
Запуск: python -m unittest test_wave3_speed"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import db_schema
import metrics
import parser_cian
import runner
import watchdog_db

MSK = timezone(timedelta(hours=3))


class TestNightWindow(unittest.TestCase):
    def test_boundaries_23_and_07(self):
        self.assertTrue(runner.is_night(datetime(2026, 11, 7, 23, 0, tzinfo=MSK)))
        self.assertTrue(runner.is_night(datetime(2026, 11, 7, 6, 59, tzinfo=MSK)))
        self.assertFalse(runner.is_night(datetime(2026, 11, 7, 7, 0, tzinfo=MSK)))
        self.assertFalse(runner.is_night(datetime(2026, 11, 7, 22, 59, tzinfo=MSK)))


class TestSchedule(unittest.TestCase):
    def test_first_due_immediately(self):
        self.assertTrue(runner.city_due("Одинцово", None, 1000.0, 3))

    def test_due_after_interval_with_zero_jitter(self):
        now = 10_000.0
        self.assertFalse(runner.city_due("X", now - 10, now, 3, jitter=0.0))
        self.assertTrue(runner.city_due("X", now - 3 * 60, now, 3, jitter=0.0))
        self.assertTrue(runner.city_due("X", now - 4 * 60, now, 3, jitter=0.0))

    def test_pick_due_checks_each_city(self):
        now = 1000.0
        last_runs = {"Одинцово": now - 10, "Химки": now - 4000}
        due = runner.pick_due(["Одинцово", "Химки"], last_runs, now, 3,
                              jitter=0.0)
        self.assertEqual(due, ["Химки"])


class TestConvergencePlan(unittest.TestCase):
    def test_cycle_plan_day_uses_groups(self):
        cfg = {"hot": {"cities": ["Одинцово"], "interval_minutes": 3},
               "regular": {"cities": ["Химки"], "interval_minutes": 17},
               "moscow": {"cities": ["Москва"], "interval_minutes": 15},
               "night": {"every_minutes": 60}}
        now = datetime(2026, 11, 7, 12, 0, tzinfo=MSK)
        plan = runner.cycle_plan(cfg, now, jitter=0.0)
        self.assertEqual(plan["kind"], "day")
        self.assertEqual(plan["hot"], ["Одинцово"])
        self.assertEqual(plan["regular"] + plan["moscow"], ["Химки", "Москва"])
        self.assertEqual(plan["intervals"]["hot"], 180.0)

    def test_cycle_plan_night_is_full(self):
        cfg = {"hot": {"cities": ["Одинцово"], "interval_minutes": 3},
               "regular": {"cities": ["Химки"], "interval_minutes": 17},
               "moscow": {"cities": ["Москва"], "interval_minutes": 15},
               "night": {"every_minutes": 60}}
        now = datetime(2026, 11, 7, 23, 30, tzinfo=MSK)
        plan = runner.cycle_plan(cfg, now, jitter=0.0)
        self.assertEqual(plan["kind"], "night")
        self.assertEqual(plan["all"], ["Одинцово", "Москва", "Химки"])
        self.assertEqual(plan["interval"], 3600.0)


class TestMoneyMetrics(unittest.TestCase):
    def test_to_utc_both_formats(self):
        self.assertIsNotNone(metrics.to_utc("2026-11-06T07:59:19.453464+00:00"))
        self.assertIsNotNone(metrics.to_utc("2026-11-05 10:13:49"))

    def test_summarize_avg_p95(self):
        vals = list(range(1, 21))  # p95: nearest-rank, 19-е значение из 20
        s = metrics.summarize(vals)
        self.assertEqual(s["n"], 20)
        self.assertEqual(s["avg"], 10.5)
        self.assertEqual(s["p95"], 19)

    def test_summarize_skips_none_and_empty(self):
        self.assertEqual(metrics.summarize([None, None])["n"], 0)
        self.assertEqual(metrics.summarize([])["p95"], None)

    def test_collect_from_db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            con = sqlite3.connect(path)
            con.execute("CREATE TABLE listings (published_at TEXT, "
                        "detected_at TEXT, sent_at TEXT)")
            con.executemany(
                "INSERT INTO listings VALUES (?,?,?)", [
                    ("2026-11-07T10:00:00+00:00", "2026-11-07T10:05:00+00:00",
                     "2026-11-07T10:06:00+00:00"),
                    ("2026-11-07T11:00:00+00:00", "2026-11-07T11:20:00+00:00",
                     None)])
            con.commit()
            pub, sent = metrics.collect(con)
            self.assertEqual(pub, [300.0, 1200.0])
            self.assertEqual(sent, [60.0])
            con.close()
        finally:
            os.remove(path)


class TestSchemaMigration(unittest.TestCase):
    def _make_base(self, path):
        con = sqlite3.connect(path)
        con.execute(
            "CREATE TABLE listings (url TEXT PRIMARY KEY, city TEXT, "
            "price INTEGER, is_owner INTEGER)")
        return con

    def test_creates_table_on_fresh_db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            con = sqlite3.connect(path)
            db_schema.ensure(con)  # пустая БД — таблица создаётся с нуля
            cols = [r[1] for r in con.execute("PRAGMA table_info(listings)")]
            for name in ("url", "city", "price", "is_owner", "source",
                         "region", "last_seen") + db_schema.LISTINGS_METRICS:
                self.assertIn(name, cols)
            con.close()
        finally:
            os.remove(path)

    def test_metrics_columns_and_queue_idempotent(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            con = self._make_base(path)
            db_schema.ensure(con)
            db_schema.ensure(con)  # дважды — идемпотентно
            cols = [r[1] for r in con.execute("PRAGMA table_info(listings)")]
            for name in db_schema.LISTINGS_METRICS:
                self.assertIn(name, cols)
            r = con.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertEqual(r.lower(), "wal")
            pend = db_schema.pending(con)
            self.assertEqual(pend, [])
            con.close()
        finally:
            os.remove(path)

    def test_queue_notice_dedup_and_mark(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            con = self._make_base(path)
            db_schema.ensure(con)
            first = db_schema.queue_notice(con, "u1", "2-комн", "12", "t1")
            again = db_schema.queue_notice(con, "u1", "2-комн", "12", "t2")
            self.assertTrue(first)
            self.assertFalse(again)  # дубль не пишется
            other = db_schema.queue_notice(con, "u2", "1-комн", "12", "t1")
            self.assertTrue(other)
            self.assertEqual(len(db_schema.pending(con)), 2)
            db_schema.mark_delivered(con, [1], "t1")
            ids = [p[0] for p in db_schema.pending(con)]
            self.assertEqual(ids, [2])
            con.close()
        finally:
            os.remove(path)


class TestWatchdog(unittest.TestCase):
    def test_fresh_db_returns_zero_age(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            con = sqlite3.connect(path)
            con.execute("CREATE TABLE listings (last_seen TEXT)")
            con.execute("INSERT INTO listings VALUES (?)",
                        (datetime.now(timezone.utc).isoformat(),))
            con.commit(); con.close()
            minutes = watchdog_db.freshness_minutes(path)
            self.assertLess(minutes, 40)
        finally:
            os.remove(path)

    def test_stale_db_detected(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            con = sqlite3.connect(path)
            old = datetime.now(timezone.utc) - timedelta(minutes=90)
            con.execute("CREATE TABLE listings (last_seen TEXT)")
            con.execute("INSERT INTO listings VALUES (?)",
                        (old.isoformat(),))
            con.commit(); con.close()
            minutes = watchdog_db.freshness_minutes(path)
            self.assertGreaterEqual(minutes, 40)
        finally:
            os.remove(path)


class FakeCianResp:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class TestCollectCityHtmlOffline(unittest.TestCase):
    def test_merge_into_shared_state(self):
        def fake_fetch(sess, slug, page, label):
            assert slug == "odintsovo"
            html = ('/sale/flat/111/ ... Собственник ... /sale/flat/222/')
            return (["111", "222"] and
                    [{"id": str(i), "raw": {}} for i in ("111", "222")],
                    {"111"})
        listings, owners, seen = {}, {}, set()
        parser_cian.collect_city_html(
            None, "Одинцово", listings, owners, seen, log=lambda *_: None,
            fetch=fake_fetch)
        self.assertEqual(list(listings), ["111", "222"])
        self.assertEqual(listings["111"]["city"], "Одинцово")
        self.assertIn("111", owners)
        self.assertNotIn("222", owners)

    def test_unavailable_city_skipped(self):
        def fake_fetch(sess, slug, page, label):
            return None, set()
        listings, owners, seen = {}, {}, set()
        parser_cian.collect_city_html(
            None, "Нет-города", listings, owners, seen,
            log=lambda *_: None, fetch=fake_fetch)
        self.assertEqual((listings, owners), ({}, {}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
