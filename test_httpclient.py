# -*- coding: utf-8 -*-
"""httpclient: CA-обход curl(77) и сессия. Запуск: python -m unittest test_httpclient"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import httpclient


class TestHttpclient(unittest.TestCase):
    def test_makes_ca_copy_at_ascii_path(self):
        ca = httpclient._ca_path()
        self.assertTrue(ca, "CA не найден")
        self.assertTrue(os.path.exists(ca))
        try:
            ca.encode("ascii")
        except UnicodeEncodeError:
            self.fail("CA-путь не-ASCII — curl(77) вернётся")

    def test_session_has_chrome_impersonation(self):
        s = httpclient.session()
        self.assertTrue(hasattr(s, "get"))
        self.assertTrue(hasattr(s, "post"))
        self.assertEqual(getattr(s, "impersonate", None), "chrome",
                         "Session без impersonate=chrome")


if __name__ == "__main__":
    unittest.main(verbosity=2)
