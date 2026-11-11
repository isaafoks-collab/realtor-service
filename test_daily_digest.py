# -*- coding: utf-8 -*-
"""Тесты daily_digest (план 2026-11-10-daily-digest-telegram, 6 тестов)."""
import datetime
import os
import sqlite3
import tempfile
import unittest

import db_schema
import daily_digest


def insert_listing(conn, url, is_owner=1, price=7900000, city="Голицыно",
                   rooms="2-комн.", area=54.0, hours_ago=1, sent_at=None):
    now = datetime.datetime.now(datetime.timezone.utc)
    detected = (now - datetime.timedelta(hours=hours_ago)).isoformat()
    conn.execute(
        "INSERT INTO listings (url, city, title, price, rooms, area, "
        " is_owner, first_seen, last_seen, detected_at, sent_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (url, city, "t", price, rooms, area, is_owner,
         detected, detected, detected, sent_at))
    conn.commit()


def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    db_schema.ensure(conn)
    return conn, path


class TestSelectNewFilters(unittest.TestCase):
    def test_select_new_filters(self):
        conn, _ = temp_db()
        insert_listing(conn, "https://cian.ru/good", is_owner=1,
                       price=1000000, hours_ago=1)
        insert_listing(conn, "https://cian.ru/agent", is_owner=0,
                       price=2000000, hours_ago=1)
        insert_listing(conn, "https://cian.ru/sent", is_owner=1,
                       price=3000000, hours_ago=1, sent_at="t")
        insert_listing(conn, "https://cian.ru/old", is_owner=1,
                       price=4000000, hours_ago=48)
        insert_listing(conn, "https://cian.ru/noprice", is_owner=1,
                       price=None, hours_ago=1)
        since = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.timedelta(hours=24)).isoformat()
        rows, total = daily_digest.select_new(conn, since)
        urls = [r[0] for r in rows]
        self.assertEqual(urls, ["https://cian.ru/good"])
        self.assertEqual(total, 1)
        conn.close()


class TestBuildText(unittest.TestCase):
    def test_build_text(self):
        rows = [("https://x.ru/1", "Абхазия", "t", 7900000, "2-комн.", 54.0),
                ("https://x.ru/2", "Боброво", "t", 1234567, None, None),
                ("https://x.ru/3", "Абхазия", "t", None, "1-комн.", 30.0)]
        texts, chunks_urls = daily_digest.build_text(rows)
        self.assertEqual(len(texts), 1)
        self.assertIn("https://x.ru/1", texts[0])
        self.assertIn("7 900 000 ₽", texts[0])
        self.assertNotIn("None", texts[0])
        self.assertEqual(chunks_urls, [["https://x.ru/1",
                                        "https://x.ru/3",
                                        "https://x.ru/2"]])
        # города сгруппированы: оба «Абхазия» подряд (1 и 3), потом Боброво
        i1, i2, i3 = (texts[0].index("https://x.ru/%d" % i) for i in (1, 2, 3))
        self.assertTrue(i1 < i3 < i2)
        self.assertLessEqual(len(texts[0]), daily_digest.CHUNK_LIMIT)

    def test_chunking_limit(self):
        long_url = "https://cian.ru/lot/" + "x" * 90
        rows = [(long_url + str(i), "Город%d" % (i % 7), "t", 1000000 + i,
                 "2-комн.", 50.0) for i in range(60)]
        texts, chunks_urls = daily_digest.build_text(rows)
        self.assertGreater(len(texts), 1)
        for text in texts:
            self.assertLessEqual(len(text), daily_digest.CHUNK_LIMIT)
            self.assertTrue(text.startswith("Свежие собственники"))
        self.assertEqual(sum(len(u) for u in chunks_urls), 60)


class TestNoCreds(unittest.TestCase):
    def test_no_creds_exit_0(self):
        old_tok, old_chat = daily_digest.BOT_TOKEN, daily_digest.CHAT_ID
        daily_digest.BOT_TOKEN, daily_digest.CHAT_ID = "", ""
        sent = []
        old_send = daily_digest.send_text
        daily_digest.send_text = lambda text: sent.append(text)
        try:
            self.assertEqual(daily_digest.main([]), 0)
            self.assertEqual(sent, [])
        finally:
            daily_digest.BOT_TOKEN, daily_digest.CHAT_ID = old_tok, old_chat
            daily_digest.send_text = old_send


class TestSendFail(unittest.TestCase):
    def test_send_fail_exit_1_and_message(self):
        old_tok, old_chat = daily_digest.BOT_TOKEN, daily_digest.CHAT_ID
        daily_digest.BOT_TOKEN, daily_digest.CHAT_ID = "tok", "chat"
        conn, path = temp_db()
        insert_listing(conn, "https://cian.ru/fail")
        old_db, old_send, old_fb = (daily_digest.DB_PATH,
                                    daily_digest.send_text,
                                    daily_digest.send_fallback)
        daily_digest.DB_PATH = path
        daily_digest.send_text = lambda text: (_ for _ in ()).throw(
            RuntimeError("Telegram 400"))
        fallbacks = []
        daily_digest.send_fallback = lambda text: fallbacks.append(text)
        try:
            self.assertEqual(daily_digest.main([]), 1)
            self.assertEqual(len(fallbacks), 1)
            self.assertIn("СБОЙ", fallbacks[0])
            n = conn.execute(
                "SELECT COUNT(*) FROM listings WHERE sent_at IS NOT NULL"
            ).fetchone()[0]
            self.assertEqual(n, 0)
        finally:
            daily_digest.BOT_TOKEN, daily_digest.CHAT_ID = old_tok, old_chat
            daily_digest.DB_PATH, daily_digest.send_text, \
                daily_digest.send_fallback = old_db, old_send, old_fb
            conn.close()
            os.remove(path)


class TestMarkSentAndQueue(unittest.TestCase):
    def test_mark_sent_and_queue(self):
        old_tok, old_chat = daily_digest.BOT_TOKEN, daily_digest.CHAT_ID
        daily_digest.BOT_TOKEN, daily_digest.CHAT_ID = "tok", "chat"
        conn, path = temp_db()
        insert_listing(conn, "https://cian.ru/one")
        insert_listing(conn, "https://cian.ru/two", city="Боброво")
        conn.execute("INSERT INTO notify_queue (url, category, chat_id, "
                     "created_at) VALUES ('https://cian.ru/one','2-комн.',"
                     "'1','t1')")
        conn.commit()
        old_db, old_send = daily_digest.DB_PATH, daily_digest.send_text
        daily_digest.DB_PATH = path
        daily_digest.send_text = lambda text: None
        try:
            self.assertEqual(daily_digest.main([]), 0)
            for url in ("https://cian.ru/one", "https://cian.ru/two"):
                sent = conn.execute(
                    "SELECT sent_at FROM listings WHERE url=?",
                    (url,)).fetchone()[0]
                self.assertIsNotNone(sent)
            self.assertEqual(len(db_schema.pending(conn)), 0)
        finally:
            daily_digest.BOT_TOKEN, daily_digest.CHAT_ID = old_tok, old_chat
            daily_digest.DB_PATH, daily_digest.send_text = old_db, old_send
            conn.close()
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
