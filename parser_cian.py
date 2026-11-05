# -*- coding: utf-8 -*-
"""Парсер ЦИАН v13.1: API-города + Саратов (бейдж data-type=homeowner, полная пагинация)."""
import json, os, random, re, time
from collections import OrderedDict
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
BASE_HEADERS = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Content-Type": "application/json"}
API_URL = "https://api.cian.ru/search-offers/v2/search-offers-desktop/"
PAGES = 2
CITIES = [("Москва", 1), ("Санкт-Петербург", 2), ("Екатеринбург", 4777),
          ("Казань", 4659), ("Новосибирск", 4821), ("Краснодар", 4820),
          ("Саратовская область", None)]
SLUGS = {"Саратовская область": "saratov"}


def json_query(rid, page, owners_only=False):
    q = {"_type": "flatsale",
         "engine_version": {"type": "term", "value": 2},
         "region": {"type": "terms", "value": [rid]},
         "page": {"type": "term", "value": page}}
    if owners_only:
        q["is_by_homeowner"] = {"type": "term", "value": True}
    return {"jsonQuery": q}


def fetch_api(session, body, label):
    for attempt in range(5):
        try:
            r = session.post(API_URL, json=body, timeout=25)
            if r.status_code == 200:
                data = r.json()
                offers = (data.get("data") or {}).get("offersSerialized") or []
                if isinstance(offers, list) and offers:
                    return offers
                return []
            print("[WARN] %s: HTTP %d; попытка %d/5" % (label, r.status_code, attempt + 1))
        except Exception as e:
            print("[WARN] %s: %s; попытка %d/5" % (label, type(e).__name__, attempt + 1))
        time.sleep(10 + attempt * 8 + random.uniform(0, 5))
    return None


def owner_ids_from_html(text):
    """ID объявлений, у которых в карточке есть метка data-type="homeowner"."""
    matches = list(re.finditer(r"/sale/flat/(\d+)/", text))
    owners = set()
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else min(len(text), start + 6000)
        segment = text[start:end]
        if 'data-type="homeowner"' in segment or re.search(r">Собственник<", segment):
            owners.add(match.group(1))
    return owners


def fetch_saratov_html(session, slug, page, label):
    urls = ["https://%s.cian.ru/kupit-kvartiru-saratovskaya-oblast/?p=%d" % (slug, page),
            "https://%s.cian.ru/kupit-kvartiru/?p=%d" % (slug, page)]
    for url in urls:
        for attempt in range(2):
            try:
                r = session.get(url, timeout=25)
                if r.status_code == 200:
                    ids = re.findall(r"/sale/flat/(\d+)/", r.text)
                    if ids:
                        owners = owner_ids_from_html(r.text)
                        items = [{"id": str(i), "raw": {}} for i in OrderedDict.fromkeys(ids)]
                        return items, owners
                    print("[WARN] %s: страница без объявлений (%s)" % (label, url))
                else:
                    print("[WARN] %s: HTTP %d (%s)" % (label, r.status_code, url))
            except Exception as e:
                print("[WARN] %s: %s (%s)" % (label, type(e).__name__, url))
            time.sleep(10 + attempt * 8)
    return None, set()


def main():
    print("[INFO] Парсер v13.1 стартует")
    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    listings, owners, seen = OrderedDict(), OrderedDict(), set()
    failed = 0
    for owners_only in (False, True):
        for name, rid in CITIES:
            for page in range(1, PAGES + 1):
                slug = SLUGS.get(name)
                if slug and owners_only:
                    continue  # HTML-город: собственники размечаются бейджами в первом проходе
                label = "%s%s стр.%d" % (name, " (собственники)" if owners_only else "", page)
                offers, owner_ids, from_api = None, set(), False
                if rid is not None:
                    offers = fetch_api(session, json_query(rid, page, owners_only), label)
                    if offers is not None:
                        from_api = True
                if not offers:
                    if slug:
                        offers, owner_ids = fetch_saratov_html(session, slug, page, label)
                    if offers is None:
                        print("[WARN] %s: не удалось — пропущено" % label)
                        failed += 1
                        continue
                new = 0
                for it in offers:
                    if not isinstance(it, dict) or not it.get("id"):
                        continue
                    lid = str(it["id"])
                    if lid not in seen:
                        seen.add(lid)
                        listings[lid] = {"city": name, "raw": it.get("raw") or {}}
                        new += 1
                    if (owners_only and from_api) or (lid in owner_ids):
                        owners[lid] = name
                print("[OK] %s: найдено=%d, новых=%d, собственников=%d" % (label, len(offers), new, len(owners)))
                time.sleep(random.uniform(10, 18))
    print("ИТОГ: объектов=%d, собственников=%d, пропущено запросов=%d" % (len(listings), len(owners), failed))
    os.makedirs("data", exist_ok=True)
    with open(os.path.join("data", "listings.json"), "w", encoding="utf-8") as f:
        json.dump({"listings": listings, "owners": list(owners.keys())}, f, ensure_ascii=False, indent=1)
    print("Сохранено: " + os.path.abspath(os.path.join("data", "listings.json")))


if __name__ == "__main__":
    main()

