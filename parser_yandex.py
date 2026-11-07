# -*- coding: utf-8 -*-
"""Парсер Яндекс.Недвижимости v2.0: сбор по каждому городу отдельно."""
import json, re, time, random, sys
from datetime import datetime, timezone
from httpclient import fetch_with_backoff, pause, session as make_session
from cities import cities_to_collect

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CAT_MAP = {"OWNER": (True, 0), "AGENT": (False, 2),
           "PRIVATE_AGENT": (False, 1), "DEVELOPER": (False, 0)}

MAJOR_SLUGS = {
    "Москва": "moskva", "Санкт-Петербург": "sankt-peterburg",
    "Екатеринбург": "ekaterinburg", "Казань": "kazan",
    "Новосибирск": "novosibirsk", "Краснодар": "krasnodar",
    "Саратов": "saratov", "Энгельс": "engels",
}
TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

def slug_for(city):
    if city in MAJOR_SLUGS:
        return MAJOR_SLUGS[city]
    out = ""
    for ch in city.lower():
        if ch == " " or ch == "-":
            out += "-"
        else:
            out += TRANSLIT.get(ch, "")
    return out

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
    rooms = o.get("roomsTotal")
    if isinstance(rooms, str):
        rooms = rooms.strip()
        if rooms.isdigit():
            rooms = int(rooms)
        elif "туди" in rooms.lower():
            rooms = 0
        else:
            rooms = None
    fo = o.get("floorsOffered")
    floor = fo[0] if isinstance(fo, list) and fo else None
    if isinstance(floor, str) and floor.isdigit():
        floor = int(floor)
    ftot = o.get("floorsTotal")
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

def captcha_hit(resp):
    """True: Яндекс отдаёт страницу капчи вместо каталога (HTTP 200!)."""
    if resp.headers.get("X-Yandex-Captcha", "").lower() == "captcha":
        return True
    m = re.search(r"<title[^>]*>(.*?)</title>", resp.text[:2000], re.S)
    return bool(m and m.group(1).strip().startswith("Вы не робот"))


def collect_cities(targets, data, log=print):
    total, owners, blocked = 0, 0, []
    for city in targets:
        slug = slug_for(city)
        for tag, suffix in (("обычные", ""), ("без-посредников", "bez-posrednikov/")):
            url = "https://realty.yandex.ru/%s/kupit/kvartira/%s?sort=DATE_DESC" % (slug, suffix)
            r, skip = None, False
            for attempt in (1, 2):
                # Яндекс вешает капчу примерно на 1 запрос из 6 (флейп) и
                # после первого запроса той же сессии — свежая сессия + 1
                # повтор спасают; упорная капча → [БЛОК]
                s = make_session()
                s.headers.update({"Accept-Language": "ru-RU,ru;q=0.9"})
                try:
                    r = fetch_with_backoff(s.get, url, timeout=25)
                except Exception as e:
                    log("[ПРОПУСК] %s (%s): %s: %s" % (city, tag, type(e).__name__, e))
                    r, skip = None, True
                    break
                if captcha_hit(r) and attempt == 1:
                    time.sleep(random.uniform(2, 4))
                    continue
                break
            if skip or r is None:
                continue
            if r.status_code != 200:
                log("[ПРОПУСК] %s (%s): HTTP %d" % (city, tag, r.status_code))
                pause(6)
                continue
            if captcha_hit(r):
                log("[БЛОК] %s (%s): Яндекс отдал капчу вместо каталога" % (city, tag))
                if city not in blocked:
                    blocked.append(city)
                pause(6)
                continue
            offers = parse_state(r.text)
            uniq = {}
            for o in offers or []:
                rec = extract(o, city)
                if rec and rec["id"] not in uniq:
                    uniq[rec["id"]] = rec
            new = 0
            for rid, rec in uniq.items():
                if rid not in data["listings"]:
                    rec["first_seen"] = datetime.now(timezone.utc).isoformat()
                    new += 1
                rec["last_seen"] = datetime.now(timezone.utc).isoformat()
                data["listings"][rid] = rec
            cnt_owner = sum(1 for rec in uniq.values() if rec["is_owner"])
            total += len(uniq)
            owners += cnt_owner
            log("[OK] %s (%s): найдено=%d, новых=%d, частников=%d" %
                (city, tag, len(uniq), new, cnt_owner))
            pause(6)
    return total, owners, blocked


def main():
    data = json.load(open("data/listings.json", encoding="utf-8"))
    if "listings" not in data:
        data = {"listings": data}

    test = len(sys.argv) > 1 and sys.argv[1].startswith("тест")
    if test:
        targets = ["Саратов", "Энгельс", "Одинцово"]
    else:
        targets = []
        for c in list(MAJOR_SLUGS) + cities_to_collect():
            if c not in targets:
                targets.append(c)

    total, owners, blocked = collect_cities(targets, data)
    json.dump(data, open("data/listings.json", "w", encoding="utf-8"),
              ensure_ascii=False)
    print("ИТОГ: объектов=%d, частников=%d, всего в хранилище=%d" %
          (total, owners, len(data["listings"])))
    if blocked:
        print("ВНИМАНИЕ: Яндекс заблокировал %d городов капчей: %s" %
              (len(blocked), ", ".join(blocked)))


if __name__ == "__main__":
    main()
