# -*- coding: utf-8 -*-
"""Тесты оркестратора. Запуск: python -m unittest test_orchestrator"""
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import orchestrator


def run_raw(func, *args, **kwargs):
    """Запускает func, возвращает (результат, stdout)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = func(*args, **kwargs)
    return result, buf.getvalue()


class TestMain(unittest.TestCase):
    def test_no_args_returns_1(self):
        rc, out = run_raw(orchestrator.main, [])
        self.assertEqual(rc, 1)

    def test_unknown_mode_returns_1(self):
        rc, out = run_raw(orchestrator.main, ["bogus"])
        self.assertEqual(rc, 1)

    def test_no_args_prints_available_modes(self):
        rc, out = run_raw(orchestrator.main, [])
        for mode in orchestrator.MODES:
            self.assertIn(mode, out)

    def test_unknown_mode_prints_available_modes(self):
        rc, out = run_raw(orchestrator.main, ["bogus"])
        for mode in orchestrator.MODES:
            self.assertIn(mode, out)


class TestEnsureRequirements(unittest.TestCase):
    def test_creates_minimal_file_when_missing(self):
        with tempfile.TemporaryDirectory() as root:
            created = orchestrator.ensure_requirements(root)
            path = os.path.join(root, "requirements.txt")
            self.assertTrue(created)
            self.assertTrue(os.path.exists(path))
            with open(path, encoding="utf-8") as f:
                content = f.read()
            for pkg in ("pyTelegramBotAPI", "requests", "beautifulsoup4", "PyYAML"):
                self.assertIn(pkg, content)

    def test_keeps_existing_file_untouched(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "requirements.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("myownpkg==1.0.0\n")
            created = orchestrator.ensure_requirements(root)
            self.assertFalse(created)
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "myownpkg==1.0.0\n")


class TestRunScript(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_captures_success(self):
        script = os.path.join(self.root, "ok.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write('print("Всё хорошо")\n')
        step, _ = run_raw(orchestrator.run_script, "ok.py", self.root)
        self.assertFalse(step["skipped"])
        self.assertEqual(step["returncode"], 0)
        self.assertTrue(step["ok"])
        self.assertIn("Всё хорошо", step["output"])

    def test_reports_failure(self):
        script = os.path.join(self.root, "fail.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write("import sys; sys.exit(3)\n")
        step, _ = run_raw(orchestrator.run_script, "fail.py", self.root)
        self.assertEqual(step["returncode"], 3)
        self.assertFalse(step["ok"])

    def test_reports_timeout(self):
        script = os.path.join(self.root, "slow.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write("import time; time.sleep(5)\n")
        step, _ = run_raw(orchestrator.run_script, "slow.py", self.root, timeout=1)
        self.assertTrue(step["timed_out"])
        self.assertFalse(step["ok"])

    def test_missing_script_is_skipped_with_reason(self):
        step, _ = run_raw(orchestrator.run_script, "nope.py", self.root)
        self.assertTrue(step["skipped"])
        self.assertIn("не найден", step["reason"])


class TestCollectTestResults(unittest.TestCase):
    def test_counts_passed_and_failed(self):
        root = tempfile.mkdtemp()
        with open(os.path.join(root, "test_good.py"), "w", encoding="utf-8") as f:
            f.write(
                "import unittest\n"
                "class TestGood(unittest.TestCase):\n"
                "    def test_a(self):\n"
                "        self.assertTrue(True)\n"
                "    def test_b(self):\n"
                "        self.assertTrue(True)\n"
            )
        with open(os.path.join(root, "test_bad.py"), "w", encoding="utf-8") as f:
            f.write(
                "import unittest\n"
                "class TestBad(unittest.TestCase):\n"
                "    def test_c(self):\n"
                "        self.fail('ожидаемо падает')\n"
            )
        res, _ = run_raw(orchestrator.collect_test_results, root)
        self.assertEqual(res["tool"], "unittest")
        self.assertEqual(res["failed"], 1)
        self.assertEqual(res["passed"], 2)
        self.assertFalse(res["ok"])


class TestRunParseSteps(unittest.TestCase):
    def test_marks_missing_scripts_and_data_as_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            steps, _ = run_raw(orchestrator.run_parse_steps, root)
            self.assertEqual(len(steps), len(orchestrator.PARSE_STEPS))
            self.assertTrue(all(s["skipped"] for s in steps))
            reasons = " | ".join(s["reason"] for s in steps)
            self.assertIn("listings.json", reasons)

    def test_json_to_db_skipped_without_data(self):
        with tempfile.TemporaryDirectory() as root:
            steps, _ = run_raw(orchestrator.run_parse_steps, root)
            self.assertEqual(len(steps), len(orchestrator.PARSE_STEPS))
            self.assertTrue(all(s["skipped"] for s in steps))
            reasons = " | ".join(s["reason"] for s in steps)
            self.assertIn("listings.json", reasons)


class TestFindIssues(unittest.TestCase):
    def test_flags_failed_parse_step(self):
        step = {"name": "parser_cian.py", "skipped": False, "ok": False,
                "returncode": 2, "timed_out": False, "reason": ""}
        issues, _ = run_raw(orchestrator.find_issues, tempfile.mkdtemp(),
                            {"tool": "unittest", "ok": True, "passed": 3, "failed": 0, "errors": 0},
                            [step])
        self.assertTrue(any("parser_cian.py" in i for i in issues))

    def test_flags_failed_tests(self):
        test_res = {"tool": "unittest", "ok": False, "passed": 1, "failed": 2, "errors": 0}
        issues, _ = run_raw(orchestrator.find_issues, tempfile.mkdtemp(), test_res, [])
        self.assertTrue(any("2" in i for i in issues))

    def test_flags_token_named_file_in_root(self):
        root = tempfile.mkdtemp()
        with open(os.path.join(root, "токены.txt"), "w", encoding="utf-8") as f:
            f.write("x")
        issues, _ = run_raw(orchestrator.find_issues, root,
                            {"tool": "unittest", "ok": True, "passed": 1, "failed": 0, "errors": 0}, [])
        self.assertTrue(any("токены.txt" in i for i in issues))


class TestReport(unittest.TestCase):
    def test_build_report_contains_all_sections(self):
        root = tempfile.mkdtemp()
        with open(os.path.join(root, "parser_cian.py"), "w", encoding="utf-8") as f:
            f.write("# скрипт\n")
        test_res = {"tool": "unittest", "ok": True, "passed": 3, "failed": 0, "errors": 0}
        step = {"name": "check_cities.py", "skipped": True, "reason": "файл не найден",
                "ok": False, "returncode": None, "timed_out": False}
        issues = ["тестовая проблема"]
        text, _ = run_raw(orchestrator.build_report, root, test_res, [step], issues)
        for section in ("СТРУКТУРА", "ТЕСТЫ", "РАЗБОР ДАННЫХ", "ПРОБЛЕМЫ", "parser_cian.py", "тестовая проблема"):
            self.assertIn(section, text)

    def test_report_mode_writes_file(self):
        root = tempfile.mkdtemp()
        rc, _ = run_raw(orchestrator.report_mode, root)
        self.assertEqual(rc, 0)
        path = os.path.join(root, "project_report.txt")
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("ПРОБЛЕМЫ", content)


class TestSetupUnicodeCrash(unittest.TestCase):
    def test_setup_mode_does_not_crash_on_unencodable_output(self):
        fake = subprocess.CompletedProcess(args=[], returncode=0)
        fake.stdout = "\ufffd " * 5
        fake.stderr = ""
        real_run = orchestrator.subprocess.run
        old_out, old_err = sys.stdout, sys.stderr
        buf = io.TextIOWrapper(io.BytesIO(), encoding="cp1251", errors="strict")
        buf_err = io.TextIOWrapper(io.BytesIO(), encoding="cp1251", errors="strict")
        try:
            orchestrator.subprocess.run = lambda *a, **k: fake
            sys.stdout = buf
            sys.stderr = buf_err
            with tempfile.TemporaryDirectory() as tmpdir:
                rc = orchestrator.main(["setup"], root=tmpdir)
            self.assertEqual(rc, 0)
        finally:
            orchestrator.subprocess.run = real_run
            sys.stdout, sys.stderr = old_out, old_err
            buf.close()
            buf_err.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
