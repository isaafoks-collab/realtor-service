# -*- coding: utf-8 -*-
"""Парсер ЦИАН v9: рабочий API-эндпоинт, HTML с deal_type=sale, диагностика."""
import json, os, random, re, time
from collections import OrderedDict
import requests

try:
    import yaml
except ImportError:
    yaml = None

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
BASE_HEADERS = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"}
API_URL = "https://api.cian.ru/search-offers/v2/search-offers/"
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
            data = None
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
        if not found and isinstance(data, dict):
            for k, v in data.items():
                if isinstance(k, str) and isinstance(v, int):
                    found[k.strip()] = v
    if not found:
        cities = list(BUILTIN)
        print("[INFO] regions.yaml не распознан — встроенный список городов")
    else:
        cities = list(found.items())
        print("[INFO] Города: " + ", ".join("%s(%d)" % (n, i) for n, i in cities))
    return cities


def api_body(region, page):
    return {
        "category": {"dealType": "sale", "objectType": ["flat"]},
        "engineVersion": {"engineVersion": "v2"},
        "geo": {"locations": [{"type": "location", "id": region}],
                "selectedEarthCheck": [], "selectedExpressCheck": [],
                "selectedHomesCount": []},
        "page": {"currentPage": page, "pageSize": 28,
                 "offersSelected": [], "sort": ["default"]},
        "pagination": {"currentPage": page, "pageSize": 28, "sort": []},
        "term": {"ensureMortgageCommunicationOption": False,
                 "isNoFurniture": False, "isRentByDaily": False},
        "isAgentOwner": None, "showForAgentOnly": False,
        "specialOffers": False, "promotionTypes": [],
        "withNewbies": False, "onlyInNoNoGreySchema": False, "lotIds": [],
    }


def fetch(session, url, method="get", json_body=None, label=""):
    last_body = ""
    for attempt in range(3):
        try:
            if method == "post":
                r = session.post(url, json=json_body, timeout=20)
            else:
                r = session.get(url, timeout=20)
            if r.status_code == 200:
                if "aptcha" in r.text[:600]:
                    print("[WARN] %s: капча; повтор %d/3" % (label, attempt + 1))
                    time.sleep(4 + attempt * 3)
                    continue
                return r
            last_body = r.text[:300]
            print("[WARN] %s: HTTP %d; повтор %d/3" % (label, r.status_code, attempt + 1))
        except Exception as e:
            print("[WARN] %s: %s; повтор %d/3" % (label, type(e).__name__, attempt + 1))
        time.sleep(3 + attempt * 2)
    if last_body:
        print("[DIAG] %s, начало ответа: %r" % (label, last_body))
    return None


def parse_api_items(r):
    try:
        data = r.json()
    except Exception:
        return None
    offers = []
    if isinstance(data, dict):
        od = data.get("offersData")
        if isinstance(od, dict):
            raw = od.get("itemsSerialized")
            if isinstance(raw, str):
                try:
                    offers = json.loads(raw)
                except Exception:
                    offers = []
            else:
                offers = od.get("items") or []
        elif data.get("items"):
            offers = data["items"]
        elif data.get("offers"):
            offers = data["offers"]
    if not isinstance(offers, list):
        return None
    out = []
    for it in offers:
        if isinstance(it, dict) and (it.get("id") or it.get("offerId")):
            out.append({"id": str(it.get("id") or it.get("offerId")), "raw": it})
    return out or None


def parse_html_items(r):
    ids = re.findall(r"/sale/flat/(\d+)/", r.text)
    if not ids:
        print("[WARN] html 200, но ссылок на объявления не найдено")
        return None
    return [{"id": i, "raw": {}} for i in OrderedDict.fromkeys(ids)]


def is_owner(raw):
    if not raw:
        return False
    ut = str(raw.get("userType") or raw.get("user_type") or "").lower()
    if ut in ("owner", "собственник"):
        return True
    return bool(raw.get("isByHomeowner") or raw.get("is_owner"))


def main():
    print("[INFO] Парсер v9 стартует")
    cities = load_cities()
    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    listings, owners, seen = OrderedDict(), OrderedDict(), set()
    total_dups = failed = 0
    for name, rid in cities:
        for page in range(1, PAGES + 1):
            label = "%s, стр.%d" % (name, page)
            items = None
            r = fetch(session, API_URL, "post", api_body(rid, page), label + " api")
            if r is not None:
                items = parse_api_items(r)
                if items is None:
                    print("[WARN] %s: api без данных; пробую html" % label)
            if items is None:
                url = "%s?deal_type=sale&engine_version=2&region=%d&p=%d" % (HTML_URL, rid, page)
                session.headers["Accept"] = "text/html,application/xhtml+xml,*/*"
                rh = fetch(session, url, label=label + " html")
                session.headers["Accept"] = "application/json, text/plain, */*"
                if rh is not None:
                    items = parse_html_items(rh)
            if items is None:
                print("[WARN] %s: не удалось (капча/404) — регион пропущен" % label)
                failed += 1
                continue
            new = 0
            for it in items:
                if it["id"] in seen:
                    total_dups += 1
                    continue
                seen.add(it["id"])
                new += 1
                listings[it["id"]] = {"city": name, "raw": it["raw"]}
                if is_owner(it["raw"]):
                    owners[it["id"]] = name
            print("[OK] %s: найдено=%d, новых=%d" % (label, len(items), new))
            time.sleep(random.uniform(3, 6))
    print("ИТОГ: объектов=%d, собственников=%d, дублей=%d" % (len(listings), len(owners), total_dups))
    if failed:
        print("ПРИМЕЧАНИЕ: %d запросов не прошли (капча/сеть) — частичный сбор" % failed)
    os.makedirs("data", exist_ok=True)
    path = os.path.join("data", "listings.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"listings": listings, "owners": list(owners.keys())},
                  f, ensure_ascii=False, indent=1)
    print("Сохранено: " + os.path.abspath(path))


if __name__ == "__main__":
    main()
