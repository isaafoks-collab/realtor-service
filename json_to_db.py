# -*- coding: utf-8 -*-
"""Конвертер v3: data/listings.json -> listings.db. Сохраняет first_seen, добавляет floor и agent_risk."""
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
n = n_own = 0
for lid, rec in data.get("listings", {}).items():
    raw = rec.get("raw") or {}
    bt = raw.get("bargainTerms") or {}
    fl = raw.get("floorNumber")
    fc = raw.get("floorsCount")
    floor = "%s/%s" % (fl, fc) if fl and fc else (str(fl) if fl else None)
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
        "floor": floor,
    }
    if "id" in cols:
        pass
    use = [c for c in cols if c in row]
    vals = [row[c] for c in use]
    cols_sql = ", ".join(use) if "id" in cols else "id, " + ", ".join(use)
    ph = ", ".join(["?"] * (len(use) + (0 if "id" in cols else 1)))
    set_sql = ", ".join("%s=?" % c for c in use if c != "id")
    try:
        if "id" in cols:
            conn.execute("INSERT OR IGNORE INTO listings (id, first_seen) VALUES (?,?)", (lid, now))
            conn.execute("UPDATE listings SET %s WHERE id=?" % set_sql, vals + [lid])
        else:
            conn.execute("INSERT OR REPLACE INTO listings (%s) VALUES (%s)" % (cols_sql, ph), [lid] + vals)
    except Exception as e:
        print("[WARN] %s: %s" % (lid, e))
        continue
    n += 1
    if row["is_owner"]:
        n_own += 1
conn.commit()
total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
own = conn.execute("SELECT COUNT(*) FROM listings WHERE is_owner=1").fetchone()[0]
conn.close()
print("ИТОГ: записей=%d (собственников=%d), всего в базе=%d, is_owner=1 в базе=%d" % (n, n_own, total, own))
