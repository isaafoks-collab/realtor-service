# -*- coding: utf-8 -*-
"""Конвертер v3: ЦИАН через owners+raw, Яндекс через поля записи, метки не понижаются."""
import json, sqlite3

data = json.load(open("data/listings.json", encoding="utf-8"))
listings = data.get("listings", data)
owners = set(data.get("owners", []))
print("owners в json: %d" % len(owners))

conn = sqlite3.connect("listings.db")
cols = [r[1] for r in conn.execute("PRAGMA table_info(listings)")]
for extra in ("floors_total", "source"):
    if extra not in cols:
        conn.execute("ALTER TABLE listings ADD COLUMN %s" % extra)

def dig(d, path):
    cur = d
    for p in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur

def num(v, cast=int):
    try:
        return cast(v) if v is not None else None
    except (TypeError, ValueError):
        return None

# образец ключей raw цian-записи — сверим имена полей
for lid, rec in listings.items():
    if not str(lid).startswith("y_"):
        print("цian raw ключи:", sorted((rec.get("raw") or {}).keys())[:40])
        break

new_cnt = upd_cnt = own_cnt = 0
for lid, rec in listings.items():
    rec = rec or {}
    raw = rec.get("raw") or {}
    url = rec.get("url") or ("https://www.cian.ru/sale/flat/%s/" % lid)
    old = conn.execute(
        "SELECT price, first_seen, price_dropped, is_owner, agent_risk "
        "FROM listings WHERE url=?", (url,)).fetchone()

    price = num(rec.get("price") or dig(raw, "price") or dig(raw, "bargainTerms.price"))
    rooms = num(rec.get("rooms") or rec.get("roomsTotal") or raw.get("roomsCount"))
    area = num(rec.get("area") or raw.get("totalArea"), float)
    floor = num(rec.get("floor") or raw.get("floorNumber"))
    ftot = num(rec.get("floors_total") or raw.get("floorsTotal"))

    if str(lid).startswith("y_"):
        computed_owner = 1 if rec.get("is_owner") else 0
    else:
        computed_owner = 1 if lid in owners else 0
    is_owner = 1 if (computed_owner or (old and old[3])) else 0

    risk = max(num(rec.get("agent_risk")) or 0, (old[4] or 0) if old else 0)
    author_type = (raw.get("userType") or rec.get("author_type")
                   or ("собственник" if is_owner else "") or None)
    source = rec.get("source") or ("yandex" if str(lid).startswith("y_") else "cian")

    dropped = 0
    if old:
        if old[0] and price and price < old[0]:
            dropped = 1
        elif old[2]:
            dropped = old[2]
    first_seen = old[1] if old else rec.get("first_seen")

    conn.execute(
        "INSERT OR REPLACE INTO listings "
        "(url, city, title, price, rooms, area, author_type, is_owner, "
        " first_seen, last_seen, price_dropped, agent_risk, floor, floors_total, source) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (url, rec.get("city") or "",
         (rec.get("address") or (rec.get("description") or "")[:80] or "")[:120],
         price, rooms, area, author_type, is_owner,
         first_seen, rec.get("last_seen"), dropped, risk, floor, ftot, source))
    if old:
        upd_cnt += 1
    else:
        new_cnt += 1
    if is_owner:
        own_cnt += 1

conn.commit()
total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
own_total = conn.execute("SELECT COUNT(*) FROM listings WHERE is_owner=1").fetchone()[0]
fl_total = conn.execute("SELECT COUNT(*) FROM listings WHERE floor IS NOT NULL").fetchone()[0]
print("ИТОГ: новых=%d, обновлено=%d, всего=%d, is_owner=1=%d, с этажом=%d" %
      (new_cnt, upd_cnt, total, own_total, fl_total))

for src in ("yandex", "cian"):
    r = conn.execute(
        "SELECT COUNT(*), SUM(price IS NOT NULL), SUM(rooms IS NOT NULL), "
        "SUM(floor IS NOT NULL), SUM(is_owner=1) FROM listings WHERE source=?", (src,)).fetchone()
    print("%s: всего=%s, с ценой=%s, с комнатами=%s, с этажом=%s, частников=%s" %
          (src, r[0], r[1], r[2], r[3], r[4]))
conn.close()
