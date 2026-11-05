# -*- coding: utf-8 -*-
"""Конвертер: data/listings.json -> listings.db (формат bot.py)."""
import json, sqlite3, datetime

data = json.load(open("data/listings.json", encoding="utf-8"))
owners = set(data.get("owners", []))
conn = sqlite3.connect("listings.db")
cols = [r[1] for r in conn.execute("PRAGMA table_info(listings)").fetchall()]
now = datetime.datetime.now().isoformat(timespec="seconds")
n = n_own = 0
for lid, rec in data.get("listings", {}).items():
    raw = rec.get("raw") or {}
    bt = raw.get("bargainTerms") or {}
    row = {
        "url": raw.get("fullUrl") or ("https://www.cian.ru/sale/flat/%s/" % lid),
        "city": (raw.get("geo") or {}).get("userInput") or rec.get("city"),
        "title": raw.get("fullName") or raw.get("name"),
        "price": bt.get("priceRur") or bt.get("price"),
        "rooms": raw.get("roomsCount"),
        "area": raw.get("totalArea"),
        "author_type": raw.get("userType") or ("собственник" if lid in owners else None),
        "is_owner": 1 if lid in owners else 0,
        "price_dropped": 0,
        "last_seen": now,
    }
    use = [c for c in cols if c in row]
    vals = [row[c] for c in use]
    conn.execute("INSERT OR REPLACE INTO listings (%s) VALUES (%s)" % (", ".join(use), ", ".join(["?"] * len(use))), vals)
    n += 1
    if row["is_owner"]:
        n_own += 1
conn.commit()
total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
own = conn.execute("SELECT COUNT(*) FROM listings WHERE is_owner=1").fetchone()[0]
conn.close()
print("ИТОГ: записей=%d (собственников=%d), всего в базе=%d, is_owner=1 в базе=%d" % (n, n_own, total, own))
