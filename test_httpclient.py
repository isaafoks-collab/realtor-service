# -*- coding: utf-8 -*-
"""Приёмы Miraines в httpclient: pause() и fetch_with_backoff().
Запуск: python -m unittest test_httpclient"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import httpclient


def fake_send(seq):
    """seq: список (response|Exception) — выдаётся по одному за вызов."""
    state = {"i": 0}

    def sender(url, **kw):
        item = seq[state["i"]]
        state["i"] += 1
        if isinstance(item, Exception):
            raise item
        return item

    sender.count = lambda: state["i"]
    return sender


class Resp:
    def __init__(self, code=200):
        self.status_code = code


class TestPause(unittest.TestCase):
    def test_pause_within_jitter_bounds(self):
        sleeps = []
        httpclient.pause(10, jitter=0.3, sleep=sleeps.append)
        for _ in range(50):
            httpclient.pause(10, jitter=0.3, sleep=sleeps.append)
        self.assertTrue(all(7.0 <= s <= 13.0 for s in sleeps), sleeps[:5])


class TestFetchWithBackoff(unittest.TestCase):
    def test_retries_429_then_200(self):
        sleeps = []
        send = fake_send([Resp(429), Resp(429), Resp(200)])
        r = httpclient.fetch_with_backoff(send, "http://x",
                                          sleep=sleeps.append, fallback_sleep=2.0)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(sleeps, [2.0, 4.0])

    def test_ok_immediate(self):
        sleeps = []
        send = fake_send([Resp(200)])
        httpclient.fetch_with_backoff(send, "http://x", sleep=sleeps.append)
        self.assertEqual(sleeps, [])

    def test_retries_on_439_and_403(self):
        for code in (439, 403):
            sleeps = []
            send = fake_send([Resp(code), Resp(200)])
            r = httpclient.fetch_with_backoff(send, "http://x", sleep=sleeps.append)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(sleeps, [2.0])

    def test_network_error_retried_then_success(self):
        sleeps = []
        send = fake_send([ConnectionError("битый сокет"), Resp(200)])
        r = httpclient.fetch_with_backoff(send, "http://x", sleep=sleeps.append)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(send.count(), 2)

    def test_exhausted_all_429_returns_last(self):
        send = fake_send([Resp(429), Resp(429), Resp(429)])
        r = httpclient.fetch_with_backoff(send, "http://x",
                                          sleep=lambda d: None, attempts=3)
        self.assertEqual(r.status_code, 429)

    def test_network_error_last_attempt_raises(self):
        send = fake_send([ConnectionError("x"), ConnectionError("y")])
        with self.assertRaises(ConnectionError):
            httpclient.fetch_with_backoff(send, "http://x",
                                          sleep=lambda d: None, attempts=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
