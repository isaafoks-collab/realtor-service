# -*- coding: utf-8 -*-
"""Тёплые клиенты: согласие, карточка лида, дубли, обработан. Запуск:
python -m unittest test_warm_leads"""
import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import warm_leads


def msk(y=2026, m=11, d=6, hh=14, mm=30):
    tz = datetime.timezone(datetime.timedelta(hours=3))
    return datetime.datetime(y, m, d, hh, mm, tzinfo=tz)


class WarmLeadsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "warm_leads.db")
        self.log = os.path.join(self.tmp.name, "leads_log.txt")
        self.lead = {
            "rooms": "2", "area": 54, "floor": "5/9", "city": "Одинцово",
            "price_wish": "7,2 млн", "deadline": "ближайшие 1–3 месяца",
            "username": "andrey", "now": msk(),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_then_card_matches_template(self):
        _, row = warm_leads.save_lead(101, self.lead, db_path=self.db)
        self.assertIsInstance(row, int)
        row, _ = warm_leads.get_lead(101, db_path=self.db)
        card = warm_leads.build_card(row, ref=self.lead["now"])
        self.assertEqual(card,
            "Собственник: согласен на звонок риэлтора\n"
            "Объект: 2-к, 54 м², 5/9, Одинцово\n"
            "Ожидаемая цена: 7,2 млн\n"
            "Срок: продам в ближайшие 1–3 месяца\n"
            "Готовность: сам нажал «нужна помощь» сегодня в 14:30")

    def test_dup_protection(self):
        warm_leads.save_lead(101, self.lead, db_path=self.db)
        res, _ = warm_leads.save_lead(101, self.lead, db_path=self.db)
        self.assertEqual(res, "exists")

    def test_mark_handled_and_new_lead_allowed(self):
        warm_leads.save_lead(101, self.lead, db_path=self.db)
        self.assertTrue(warm_leads.mark_handled(101, db_path=self.db))
        res, _ = warm_leads.save_lead(101, self.lead, db_path=self.db)
        self.assertEqual(res, "new")

    def test_list_and_mark_by_id(self):
        warm_leads.save_lead(201, self.lead, db_path=self.db)
        warm_leads.save_lead(202, self.lead, db_path=self.db)
        rows = warm_leads.list_leads(db_path=self.db)
        self.assertEqual(len(rows), 2)
        self.assertTrue(warm_leads.mark_handled_id(rows[0][0], db_path=self.db))
        self.assertEqual(len(warm_leads.list_leads(db_path=self.db)), 1)

    def test_deliver_writes_log_and_calls_sender(self):
        warm_leads.save_lead(101, self.lead, db_path=self.db)
        _, card = warm_leads.get_lead(101, db_path=self.db)
        sent = []
        warm_leads.deliver(card, log_path=self.log,
                           send=sent.append)
        self.assertIn("5/9, Одинцово", open(self.log, encoding="utf-8").read())
        self.assertEqual(card, sent[0])

    def test_card_skips_missing_optional_fields(self):
        lead = {"rooms": "2", "city": "Одинцово", "username": "a",
                "deadline": "ближайшие 1–3 месяца", "now": msk()}
        warm_leads.save_lead(102, lead, db_path=self.db)
        _, card = warm_leads.get_lead(102, db_path=self.db)
        self.assertNotIn("м²", card)
        self.assertNotIn("Ожидаемая цена", card)
        self.assertIn("Объект: 2-к, Одинцово", card)

    def test_yesterday_wording(self):
        lead = dict(self.lead, now=msk(m=11, d=5))
        warm_leads.save_lead(103, lead, db_path=self.db)
        row, _ = warm_leads.get_lead(103, db_path=self.db)
        card = warm_leads.build_card(row, ref=msk(m=11, d=6))
        self.assertIn("вчера в 14:30", card)


if __name__ == "__main__":
    unittest.main(verbosity=2)
