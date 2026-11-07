# -*- coding: utf-8 -*-
"""Workflow daily-parse.yml: должен жить в .github/workflows с env из Secrets.
Запуск: python -m unittest test_workflow_location"""
import os
import unittest

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
WF = os.path.join(ROOT, ".github", "workflows", "daily-parse.yml")


class TestWorkflowLocation(unittest.TestCase):
    def test_file_in_github_workflows(self):
        self.assertTrue(os.path.exists(WF), "workflow должен лежать в .github/workflows/")

    def test_valid_yaml_with_name(self):
        doc = yaml.safe_load(open(WF, encoding="utf-8"))
        self.assertEqual(doc["name"], "daily-parse")

    def test_job_env_from_secrets(self):
        doc = yaml.safe_load(open(WF, encoding="utf-8"))
        job = doc["jobs"]["parse"]
        self.assertEqual(job["env"]["BOT_TOKEN"], "${{ secrets.BOT_TOKEN }}")
        self.assertEqual(job["env"]["BOT_TOKEN_OWNERS"], "${{ secrets.BOT_TOKEN_OWNERS }}")

    def test_secrets_check_step(self):
        doc = yaml.safe_load(open(WF, encoding="utf-8"))
        steps = doc["jobs"]["parse"]["steps"]
        names = [s.get("name") or s.get("uses") or "?" for s in steps]
        check = next(s for s in steps if s.get("name") == "Проверка секретов")
        self.assertIn("BOT_TOKEN_OWNERS", check["run"])

    def test_dispatch_and_cron(self):
        doc = yaml.safe_load(open(WF, encoding="utf-8"))
        self.assertIn("workflow_dispatch", doc[True])  # ключ True: `on:` в yaml
        self.assertIn("cron", doc[True]["schedule"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
