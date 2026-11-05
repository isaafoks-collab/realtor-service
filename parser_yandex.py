# -*- coding: utf-8 -*-
"""Парсер Яндекс.Недвижимости v1.0 — структура через INITIAL_STATE."""
import json, re, time, random, requests
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CITIES = {
    "Москва": "moskva", "Санкт-Петербург": "sankt-peterburg",
    "Екатеринбург": "ekaterinburg", "Казань": "kazan",
    "Новосибирск": "novosibirsk", "Краснодар": "krasnodar",
    "Саратовская область": "saratov",
}
CAT_MAP = {"OWNER": (True, 0), "AGENT": (False, 2),
           "PRIVATE_AGENT": (False, 1), "DEVELOPER": (False, 0)}

def parse_state(html):
    pos = html.find("window.INITIAL_STATE = ")
    if pos < 0:
        pos = html.find("window.INITIAL_STATE=")
    if pos < 0:
        return None
    start = html.find("=", pos) + 1
    while html[start] in " \t":
        start += 1
    obj, _ = json.JSONDecoder().raw_decode(html[start:])
    found = []
    def walk(node, depth=0):
        if depth > 14 or len(found) >= 300:
            return
        if isinstance(node, dict):
            if "offerId" in node and isinstance(node.get("offerId"), str) and len(node) > 8:
                found.append(node)
            for v in node.values():
                walk(v, depth + 1)
        elif isinstance(node, list):
            for v in node:
                walk(v, depth + 1)
    walk(obj)
    return found

def dig(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d

def extract(o, city):
    oid = o.get("offerId")
    if not oid:
        return None
    price = dig(o, "price", "value")
    area = dig(o, "area", "value")
    ap = o.get("apartment") or {}
    rooms = ap.get("roomsCount") or o.get("roomsCount")
    floor = ap.get("floorNumber") or o.get("floorNumber")
    ftot = ap.get("floorsTotal") or dig(o, "building", "floorsTotal")
    if floor is None and o.get("floorsOffered"):
        try:
            floor = int(str(o["floorsOffered"]).split("/")[0])
        except Exception:
            floor = None
    addr = dig(o, "location", "address") or dig(o, "location", "street")
    a = o.get("author") or {}
    cat = a.get("category")
    is_owner, risk = CAT_MAP.get(cat, (False, 0))
    return {
        "id": "y_" + oid,
        "url": "https://realty.yandex.ru/offer/%s/" % oid,
        "city": city,
        "type": "flat",
        "rooms": rooms,
        "price": price,
        "area": area,
        "floor": floor,
        "floors_total": ftot,
        "address": addr,
        "description": (o.get("description") or "")[:4000],
        "is_owner": 1 if is_owner else 0,
        "agent_risk": risk,
        "published": o.get("creationDate"),
        "source": "yandex",
        "raw": {
            "offerId": oid, "price": price, "area": area,
            "roomsCount": rooms, "floorNumber": floor, "floorsCount": ftot,
            "address": addr, "description": o.get("description"),
            "creationDate": o.get("creationDate"),
            "cianUserId": None, "userType": cat,
            "origUrl": o.get("url"), "agentName": a.get("agentName"),
        },
    }

s = requests.Session()
s.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
data = json.load(open("data/listings.json", encoding="utf-8"))
if "listings" not in data:
    data = {"listings": data}

total, owners = 0, 0
for city, slug in CITIES.items():
    for tag, suffix in (("обычные", ""), ("без-посредников", "bez-posrednikov/")):
        url = "https://realty.yandex.ru/%s/kupit/kvartira/%s" % (slug, suffix)
        try:
            r = s.get(url, timeout=25)
            if r.status_code != 200:
                print("[WARN] %s (%s): HTTP %d" % (city, tag, r.status_code))
                continue
            offers = parse_state(r.text)
            uniq, new = {}, 0
            for o in offers or []:
                rec = extract(o, city)
                if rec and rec["id"] not in uniq:
                    uniq[rec["id"]] = rec
            for rid, rec in uniq.items():
                if rid not in data["listings"]:
                    rec["first_seen"] = datetime.now(timezone.utc).isoformat()
                    new += 1
                rec["last_seen"] = datetime.now(timezone.utc).isoformat()
                data["listings"][rid] = rec
            cnt_owner = sum(1 for rec in uniq.values() if rec["is_owner"])
            total += len(uniq)
            owners += cnt_owner
            print("[OK] %s (%s): найдено=%d, новых=%d, частников=%d" %
                  (city, tag, len(uniq), new, cnt_owner))
            time.sleep(random.uniform(4, 8))
        except Exception as e:
            print("[WARN] %s (%s): %s: %s" % (city, tag, type(e).__name__, e))

json.dump(data, open("data/listings.json", "w", encoding="utf-8"),
          ensure_ascii=False)
print("ИТОГ: объектов=%d, частников=%d, всего в хранилище=%d" %
      (total, owners, len(data["listings"])))
