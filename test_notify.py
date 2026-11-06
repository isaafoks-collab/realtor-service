# -*- coding: utf-8 -*-
"""notify: тротлер+ретраи. Запуск: python -m unittest test_notify"""
import sys
import unittest

sys.path.insert(0, ".")
import notify


def make_notifier():
    class FakeClock:
        t = 0.0

        def monotonic(self):
            return self.t

        def sleep(self, d):
            self.t += d
            self.sleeps.append(d)

    FakeClock.sleeps = []
    return FakeClock()


SENT = []


def fake_sender(chat_id, text, **kw):
    SENT.append((chat_id, text))
    return "ok"


class TestNotifier(unittest.TestCase):
    def test_private_chat_min_one_sec(self):
        c = make_notifier()
        n = notify.Notifier(clock=c.monotonic, sleep=c.sleep)
        s = n.wrap(fake_sender)
        skept = s(100, "привет")
        s(100, "ещё")  # сразу же — обязан уснуть ~1 сек
        self.assertEqual(skept, "ok")
        self.assertGreaterEqual([x for x in c.sleeps if x > 0][0], 0.9)

    def test_group_chat_throttled_harder(self):
        c = make_notifier()
        n = notify.Notifier(clock=c.monotonic, sleep=c.sleep)
        s = n.wrap(fake_sender)
        s(-500, "в группу")
        c.sleeps.clear()
        s(-500, "в группу второй")
        self.assertGreaterEqual(max(c.sleeps), notify.GROUP_INTERVAL - 0.5)

    def test_global_limit_30_per_second(self):
        c = make_notifier()
        n = notify.Notifier(clock=c.monotonic, sleep=c.sleep)
        s = n.wrap(fake_sender)
        for i in range(31):
            s(1000 + i, "x")
        # 31-я отправка за 1 сек: глобальный лимит принудил паузу
        self.assertGreater(max(c.sleeps), 0)

    def test_retry_three_attempts_then_success(self):
        c = make_notifier()
        n = notify.Notifier(clock=c.monotonic, sleep=c.sleep)
        calls = []

        def flaky(chat_id, text, **kw):
            calls.append(1)
            if len(calls) < 3:
                raise TimeoutError("сеть мигнула")
            return "ok"

        self.assertEqual(n.call(flaky, 5, "текст"), "ok")
        self.assertEqual(len(calls), 3)

    def test_retry_raises_after_attempts_exhausted(self):
        c = make_notifier()
        n = notify.Notifier(clock=c.monotonic, sleep=c.sleep)

        def always_fail(chat_id, text, **kw):
            raise TimeoutError("бессрочный сбой")

        with self.assertRaises(Exception):
            n.call(always_fail, 5, "текст")


if __name__ == "__main__":
    unittest.main(verbosity=2)
