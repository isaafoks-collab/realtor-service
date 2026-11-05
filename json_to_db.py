# -*- coding: utf-8 -*-
"""Конвертер v3.1: data/listings.json -> listings.db (ключ url). Сохраняет first_seen, добавляет floor."""
import json, sqlite3, datetime

data = json.load(open("data/listings.json", encoding="utf-8"))
owners = set(data.get("owners", []))
conn = sqlite3.connect("listings.db")
for col in ("agent_risk", "floor"):
    try:
        conn.execute("ALTER TABLE listings ADD COLUMN %s" % col)
    except Exception:
        pass
cols = [r[1] for r in conn.execute("PRAGMA table_info(listings)").fetchall()]
now = datetime.datetime.now().isoformat(timespec="seconds")
n = n_own = n_upd = 0
for lid, rec in data.get("listings", {}).items():
    raw = rec.get("raw") or {}
    bt = raw.get("bargainTerms") or {}
    fl = raw.get("floorNumber")
    fc = raw.get("floorsCount")
    floor = "%s/%s" % (fl, fc) if fl and fc else (str(fl) if fl else None)
    url = raw.get("fullUrl") or ("https://www.cian.ru/sale/flat/%s/" % lid)
    row = {
        "city": (raw.get("geo") or {}).get("userInput") or rec.get("city"),
        "title": raw.get("fullName") or raw.get("name"),
        "price": bt.get("priceRur") or bt.get("price"),
        "rooms": raw.get("roomsCount"),
        "area": raw.get("totalArea"),
        "author_type": raw.get("userType") or ("собственник" if lid in owners else None),
        "is_owner": 1 if lid in owners else 0,
        "floor": floor,
        "last_seen": now,
    }
    updatable = [c for c in cols if c in row]
    try:
        cur = conn.execute("SELECT 1 FROM listings WHERE url=?", (url,)).fetchone()
        if cur is None:
            base = ["url", "first_seen"] + updatable
            vals = [url, now] + [row[c] for c in updatable]
            conn.execute("INSERT INTO listings (%s) VALUES (%s)" % (", ".join(base), ", ".join(["?"] * len(base))), vals)
            n += 1
        else:
            set_sql = ", ".join("%s=?" % c for c in updatable)
            conn.execute("UPDATE listings SET %s WHERE url=?" % set_sql,
                         [row[c] for c in updatable] + [url])
            n_upd += 1
        if row["is_owner"]:
            n_own += 1
    except Exception as e:
        print("[WARN] %s: %s" % (lid, e))
        continue
conn.commit()
total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
own = conn.execute("SELECT COUNT(*) FROM listings WHERE is_owner=1").fetchone()[0]
fl_cnt = conn.execute("SELECT COUNT(*) FROM listings WHERE floor IS NOT NULL").fetchone()[0]
conn.close()
print("ИТОГ: новых=%d, обновлено=%d, собственников=%d, всего в базе=%d, is_owner=1=%d, с этажом=%d" % (n, n_upd, n_own, total, own, fl_cnt))
