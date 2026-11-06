# -*- coding: utf-8 -*-
"""Сторож капчи Яндекса. Запуск: python -m unittest test_parser_yandex"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import parser_yandex


class FakeResp:
    def __init__(self, headers=None, text=""):
        self.headers = headers or {}
        self.status_code = 200
        self.text = text


def fixture(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        return f.read()


class TestCaptchaGuard(unittest.TestCase):
    def test_header_captcha_detected(self):
        self.assertTrue(parser_yandex.captcha_hit(
            FakeResp(headers={"X-Yandex-Captcha": "captcha"})))

    def test_header_captcha_absent_ok(self):
        self.assertFalse(parser_yandex.captcha_hit(
            FakeResp(headers={"X-Yandex-Captcha": ""})))

    def test_robot_title_detected(self):
        self.assertTrue(parser_yandex.captcha_hit(
            FakeResp(text="<title>Вы не робот?</title>")))

    def test_real_catalog_page_ok(self):
        self.assertFalse(parser_yandex.captcha_hit(
            FakeResp(headers={"Content-Type": "text/html"},
                     text=fixture("yandex_page.html"))))

    def test_saved_404_page_is_not_captcha(self):
        self.assertFalse(parser_yandex.captcha_hit(
            FakeResp(text=fixture("yandex_404.html"))))


if __name__ == "__main__":
    unittest.main(verbosity=2)
