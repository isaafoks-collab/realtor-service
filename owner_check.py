# -*- coding: utf-8 -*-
"""Анти-фильтр owner_check v1.1 (ключ url): один автор в 3+ объявлениях — риск агента."""
import json, sqlite3
from collections import defaultdict

MARKERS = ["торг уместен", "помощь в ипотеке", "звоните, покажу", "каждому покупателю",
           "рассмотрим любые варианты", "агентство", "риелтор", "быстрая продажа",
           "юридическая чистота", "без посредников? звоните"]

data = json.load(open("data/listings.json", encoding="utf-8"))
by_author = defaultdict(list)
text_hits = defaultdict(list)
url_of = {}
for lid, rec in data.get("listings", {}).items():
    raw = rec.get("raw") or {}
    u = raw.get("user") or {}
    aid = u.get("id") or u.get("cianUserId")
    url = raw.get("fullUrl") or ("https://www.cian.ru/sale/flat/%s/" % lid)
    url_of[lid] = url
    if aid:
        by_author[str(aid)].append((lid, rec.get("city") or ""))
    desc = (raw.get("description") or "").lower()
    hits = [mk for mk in MARKERS if mk in desc]
    if hits:
        text_hits[lid] = hits

conn = sqlite3.connect("listings.db")
try:
    conn.execute("ALTER TABLE listings ADD COLUMN agent_risk INTEGER")
except Exception:
    pass

cnt = {0: 0, 1: 0, 2: 0, "skip": 0}
for lid, rec in data.get("listings", {}).items():
    raw = rec.get("raw") or {}
    u = raw.get("user") or {}
    aid = u.get("id") or u.get("cianUserId")
    risk = 0
    if aid:
        group = by_author[str(aid)]
        cities = {c for _, c in group if c}
        if len(group) >= 5 or (len(group) >= 3 and len(cities) > 1):
            risk = 2
        elif len(group) >= 3:
            risk = 1
    if lid in text_hits and risk < 2:
        risk = max(risk, 2 if len(text_hits[lid]) >= 3 else 1)
    conn.execute("UPDATE listings SET agent_risk=? WHERE url=?", (risk, url_of[lid]))
    cnt[risk] += 1
# HTML-объявления без автора (Саратов) — не помечаем, оставляем как есть
conn.commit()
conn.close()
print("Анти-фильтр: чистых=%d, под вопросом=%d, вероятных агентов=%d (HTML-объекты не оценены)" % (cnt[0], cnt[1], cnt[2]))
