# -*- coding: utf-8 -*-
"""Парсер ЦИАН v10: search-offers-desktop + фильтр is_by_homeowner."""
import json, os, random, re, time
from collections import OrderedDict
import requests

try:
    import yaml
except ImportError:
    yaml = None

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
BASE_HEADERS = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Content-Type": "application/json"}
API_URL = "https://api.cian.ru/search-offers/v2/search-offers-desktop/"
HTML_URL = "https://www.cian.ru/cat.php"
PAGES = 2
BUILTIN = [("Москва", 1), ("Санкт-Петербург", 2), ("Екатеринбург", 4777),
           ("Казань", 4659), ("Новосибирск", 4821), ("Краснодар", 4820)]


def load_cities():
    data = None
    if yaml is not None:
        try:
            with open("regions.yaml", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print("[WARN] regions.yaml не прочитан (%s)" % e)
    found = OrderedDict()

    def walk(node, hint=None):
        if isinstance(node, dict):
            rid, nm = None, None
            for k in ("region_id", "id"):
                if isinstance(node.get(k), int):
                    rid = node[k]
                    break
            for k in ("name", "city", "title"):
                if isinstance(node.get(k), str):
                    nm = node[k]
                    break
            if rid is not None and (nm or hint):
                found[(nm or hint).strip()] = rid
            for k, v in node.items():
                walk(v, k if isinstance(k, str) else hint)
        elif isinstance(node, list):
            for it in node:
                walk(it, hint)

    if data is not None:
        walk(data)
    if not found:
        cities = list(BUILTIN)
        print("[INFO] regions.yaml не распознан — встроенный список городов")
    else:
        cities = list(found.items())
        print("[INFO] Города: " + ", ".join("%s(%d)" % (n, i) for n, i in cities))
    return cities


def json_query(rid, page, owners_only=False):
    q = {"_type": "flatsale",
         "engine_version": {"type": "term", "value": 2},
         "region": {"type": "terms", "value": [rid]},
         "page": {"type": "term", "value": page}}
    if owners_only:
        q["is_by_homeowner"] = {"type": "term", "value": True}
    return {"jsonQuery": q}


def fetch(session, url, json_body=None, label=""):
    for attempt in range(3):
        try:
            r = session.post(url, json=json_body, timeout=20) if json_body is not None else session.get(url, timeout=20)
            if r.status_code == 200:
                return r
            print("[WARN] %s: HTTP %d; повтор %d/3" % (label, r.status_code, attempt + 1))
        except Exception as e:
            print("[WARN] %s: %s; повтор %d/3" % (label, type(e).__name__, attempt + 1))
        time.sleep(3 + attempt * 2)
    return None


def parse_items(r):
    try:
        data = r.json()
    except Exception:
        return None
    offers = (data.get("data") or {}).get("offersSerialized") or []
    if not isinstance(offers, list):
        return None
    out = []
    for it in offers:
        if isinstance(it, dict) and it.get("id"):
            out.append({"id": str(it["id"]), "raw": it})
    return out or None


def parse_html_items(r):
    ids = re.findall(r"/sale/flat/(\d+)/", r.text)
    if not ids:
        return None
    return [{"id": i, "raw": {}} for i in OrderedDict.fromkeys(ids)]


def main():
    print("[INFO] Парсер v10 стартует")
    cities = load_cities()
    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    listings, owners, seen = OrderedDict(), OrderedDict(), set()
    failed = dups = 0
    for name, rid in cities:
        for page in range(1, PAGES + 1):
            label = "%s, стр.%d" % (name, page)
            r = fetch(session, API_URL, json_query(rid, page), label)
            items = parse_items(r) if r is not None else None
            if items is None:
                url = "%s?deal_type=sale&engine_version=2&region=%d&p=%d" % (HTML_URL, rid, page)
                rh = fetch(session, url, label=label + " html")
                items = parse_html_items(rh) if rh is not None else None
            if items is None:
                print("[WARN] %s: не удалось — пропущено" % label)
                failed += 1
                continue
            new = 0
            for it in items:
                if it["id"] in seen:
                    dups += 1
                    continue
                seen.add(it["id"])
                new += 1
                listings[it["id"]] = {"city": name, "raw": it["raw"]}
            print("[OK] %s: найдено=%d, новых=%d" % (label, len(items), new))
            time.sleep(random.uniform(3, 6))
        for page in range(1, PAGES + 1):
            label = "%s собственники, стр.%d" % (name, page)
            r = fetch(session, API_URL, json_query(rid, page, owners_only=True), label)
            items = parse_items(r) if r is not None else None
            if items is None:
                failed += 1
                continue
            for it in items:
                if it["id"] not in seen:
                    listings[it["id"]] = {"city": name, "raw": it["raw"]}
                seen.add(it["id"])
                owners[it["id"]] = name
            print("[OK] %s: собственников=%d" % (label, len(items)))
            time.sleep(random.uniform(3, 6))
    print("ИТОГ: объектов=%d, собственников=%d, дублей=%d" % (len(listings), len(owners), dups))
    if failed:
        print("ПРИМЕЧАНИЕ: %d запросов не прошли" % failed)
    os.makedirs("data", exist_ok=True)
    path = os.path.join("data", "listings.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"listings": listings, "owners": list(owners.keys())}, f, ensure_ascii=False, indent=1)
    print("Сохранено: " + os.path.abspath(path))


if __name__ == "__main__":
    main()
