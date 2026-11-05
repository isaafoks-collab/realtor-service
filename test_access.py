"""14 тестов модуля вечного доступа. Запуск: python test_access.py"""
import os, tempfile, unittest
import access

class TestAccess(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.old_db = access.DB_PATH
        access.DB_PATH = os.path.join(self.tmpdir, "t.db")
        os.environ["ACCESS_LOG"] = os.path.join(self.tmpdir, "log.txt")

    def tearDown(self):
        access.DB_PATH = self.old_db

    def test_01_wrong_code_denied(self):
        self.assertEqual(access.grant(1, "NOPE", "PRYMO-2026"), "deny")

    def test_02_correct_code_ok(self):
        self.assertEqual(access.grant(2, "PRYMO-2026", "PRYMO-2026"), "ok")

    def test_03_second_grant_again(self):
        access.grant(3, "PRYMO-2026", "PRYMO-2026")
        self.assertEqual(access.grant(3, "PRYMO-2026", "PRYMO-2026"), "again")

    def test_04_has_access_true(self):
        access.grant(4, "PRYMO-2026", "PRYMO-2026")
        self.assertTrue(access.has_access(4))

    def test_05_has_access_false(self):
        self.assertFalse(access.has_access(5))

    def test_06_case_insensitive(self):
        self.assertEqual(access.grant(6, "prymo-2026", "PRYMO-2026"), "ok")

    def test_07_spaces_trimmed(self):
        self.assertEqual(access.grant(7, " PRYMO-2026 ", "PRYMO-2026"), "ok")

    def test_08_empty_code_denied(self):
        self.assertEqual(access.grant(8, "", "PRYMO-2026"), "deny")

    def test_09_log_written(self):
        access.grant(9, "PRYMO-2026", "PRYMO-2026")
        self.assertTrue(os.path.exists(os.environ["ACCESS_LOG"]))

    def test_10_deny_logged(self):
        access.grant(10, "XXX", "PRYMO-2026")
        with open(os.environ["ACCESS_LOG"], encoding="utf-8") as f:
            self.assertIn("DENY user=10", f.read())

    def test_11_persist_after_reopen(self):
        access.grant(11, "PRYMO-2026", "PRYMO-2026")
        self.assertTrue(access.has_access(11))

    def test_12_users_isolated(self):
        access.grant(12, "PRYMO-2026", "PRYMO-2026")
        self.assertFalse(access.has_access(13))

    def test_13_no_crash_on_repeat_deny(self):
        self.assertEqual(access.grant(1, "NOPE", "PRYMO-2026"), "deny")

    def test_14_custom_code_in_env(self):
        self.assertEqual(access.grant(14, "ZZ-0001", "ZZ-0001"), "ok")

if __name__ == "__main__":
    unittest.main(verbosity=2)
