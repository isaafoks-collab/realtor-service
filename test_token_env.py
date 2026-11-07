# -*- coding: utf-8 -*-
"""Токены только из окружения. Запуск: python -m unittest test_token_env"""
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
TG_TOKEN_RE = re.compile(r"\b\d{9,10}:A[0-9A-Za-z_-]{30,}")


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


class TestBotReadsEnv(unittest.TestCase):
    def test_bot_tokens_come_from_env_var(self):
        self.assertIn('os.getenv("BOT_TOKEN")', read("bot.py"))

    def test_bot_does_not_reference_token_file(self):
        self.assertNotIn("токены", read("bot.py"))

    def test_bot_exits_with_clear_message_without_token(self):
        env = dict(os.environ)
        env.pop("BOT_TOKEN", None)
        env["PYTHONUTF8"] = "1"
        proc = subprocess.run(
            [sys.executable, "bot.py"], cwd=ROOT, env=env,
            capture_output=True, text=True, timeout=120)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("BOT_TOKEN", (proc.stdout + proc.stderr))


class TestNoSecretsInScripts(unittest.TestCase):
    def test_bot_sources_have_no_hardcoded_tokens(self):
        for name in ("bot.py", "parser_cian.py", "parser_yandex.py"):
            self.assertIsNone(TG_TOKEN_RE.search(read(name)), name)

    def test_start_bats_have_no_hardcoded_tokens(self):
        for name in ("start.bat", "start_owners.bat", "start_realtor.bat",
                     "start_scheduler.bat"):
            if not os.path.exists(os.path.join(ROOT, name)):
                continue
            self.assertIsNone(TG_TOKEN_RE.search(read(name)), name)

    def test_gitignore_covers_token_file(self):
        proc = subprocess.run(
            ["git", "check-ignore", "токены.txt"], cwd=ROOT,
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, ".gitignore не покрывает токены.txt")

    def test_workflows_pull_bot_tokens_from_github_secrets(self):
        text = read(os.path.join(".github", "workflows", "daily-parse.yml"))
        self.assertIn("${{ secrets.BOT_TOKEN }}", text)
        self.assertIsNone(TG_TOKEN_RE.search(text))


if __name__ == "__main__":
    unittest.main(verbosity=2)
