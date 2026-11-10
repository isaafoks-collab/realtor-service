# -*- coding: utf-8 -*-
"""setup.ps1: источники токенов и защита от печати значений.
Запуск: python -m unittest test_setup_script"""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(ROOT, "setup.ps1")


def run_setup(env, stdin_text=None, token_file=None):
    cmd = ("[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
           "[Console]::InputEncoding = [System.Text.Encoding]::UTF8; "
           "& '%s' -SkipGitHub" % SCRIPT)
    if token_file:
        cmd += " -TokenFile '%s'" % token_file
    args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-Command", cmd]
    return subprocess.run(args, capture_output=True, input=stdin_text,
                          text=True, encoding="utf-8", errors="replace",
                          env=env, cwd=ROOT, timeout=120)


class TestSetupScript(unittest.TestCase):
    def base_env(self):
        env = dict(os.environ)
        env.pop("BOT_TOKEN", None)
        env.pop("BOT_TOKEN_OWNERS", None)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def test_from_environment_source_named(self):
        env = self.base_env()
        env["BOT_TOKEN"] = "111AAA:secretvalue"
        env["BOT_TOKEN_OWNERS"] = "222BBB:secretvalue"
        tmp = os.path.join(tempfile.gettempdir(), "tok_setup_env.txt")
        r = run_setup(env, token_file=tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("BOT_TOKEN: заполнен (источник: окружение)", r.stdout)
        self.assertIn("BOT_TOKEN_OWNERS: заполнен (источник: окружение)", r.stdout)

    def test_values_never_printed(self):
        env = self.base_env()
        env["BOT_TOKEN"] = "111AAA:supersecret111"
        env["BOT_TOKEN_OWNERS"] = "222BBB:supersecret222"
        tmp = os.path.join(tempfile.gettempdir(), "tok_setup_env.txt")
        r = run_setup(env, token_file=tmp)
        self.assertNotIn("supersecret111", r.stdout)
        self.assertNotIn("supersecret222", r.stdout)
        self.assertNotIn("supersecret111", r.stderr)
        self.assertNotIn("supersecret222", r.stderr)

    def test_from_token_file(self):
        env = self.base_env()
        fd, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("# комментарий\nBOT_TOKEN=333CCC:filesecret\n")
        try:
            r = run_setup(env, token_file=path)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("BOT_TOKEN: заполнен (источник: токены.txt)", r.stdout)
            self.assertIn("BOT_TOKEN_OWNERS: не задан", r.stdout)
            self.assertNotIn("filesecret", r.stdout)
        finally:
            os.remove(path)

    def test_manual_prompt_success_moves_to_file(self):
        env = self.base_env()
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            r = run_setup(env, stdin_text="444DDD:typedsecret\n555EEE:typedsecret2\n",
                          token_file=path)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("источник: ручной ввод", r.stdout)
            self.assertNotIn("typedsecret", r.stdout)
            content = open(path, encoding="utf-8").read()
            self.assertIn("BOT_TOKEN=444DDD:typedsecret", content)
            self.assertIn("BOT_TOKEN_OWNERS=555EEE:typedsecret2", content)
        finally:
            os.remove(path)

    def test_missing_report(self):
        env = self.base_env()
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            r = run_setup(env, stdin_text="\n", token_file=path)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("не задан", r.stdout)
            self.assertIn("нет ни локально, ни в GitHub Secrets", r.stdout)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
