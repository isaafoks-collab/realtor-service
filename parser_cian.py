# -*- coding: utf-8 -*-
"""Парсер ЦИАН v14: API-мегаполисы + HTML-сбор по каждому городу отдельно."""
import json, os, random, re, time, sys
from collections import OrderedDict
from httpclient import session
from cities import cities_to_collect

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
BASE_HEADERS = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Content-Type": "application/json"}
API_URL = "https://api.cian.ru/search-offers/v2/search-offers-desktop/"
API_CITIES = [("Москва", 1), ("Санкт-Петербург", 2), ("Екатеринбург", 4777),
              ("Казань", 4659), ("Новосибирск", 4821), ("Краснодар", 4820)]
TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}
CIAN_EXCEPT = {"Химки": "khimki", "Немчиновка": "nemchinovka",
               "Старая Купавна": "staraya-kupavna",
               "Ртищево": "rtishchevo", "Мытищи": "mytishchi"}

def cian_slug_for(city):
    if city in CIAN_EXCEPT:
        return CIAN_EXCEPT[city]
    out = ""
    for ch in city.lower():
        if ch == " " or ch == "-":
            out += "-"
        else:
            out += TRANSLIT.get(ch, "")
    return out

def json_query(rid, page, owners_only=False):
    q = {"_type": "flatsale",
         "engine_version": {"type": "term", "value": 2},
         "region": {"type": "terms", "value": [rid]},
         "page": {"type": "term", "value": page}}
    if owners_only:
        q["is_by_homeowner"] = {"type": "term", "value": True}
    return {"jsonQuery": q}

def fetch_api(sess, body, label):
    for attempt in range(3):
        try:
            r = sess.post(API_URL, json=body, timeout=25)
            if r.status_code == 200:
                data = r.json()
                offers = (data.get("data") or {}).get("offersSerialized") or []
                return offers if isinstance(offers, list) else []
            print("[WARN] %s: HTTP %d; попытка %d/3" % (label, r.status_code, attempt + 1))
        except Exception as e:
            print("[WARN] %s: %s; попытка %d/3" % (label, type(e).__name__, attempt + 1))
        time.sleep(10 + attempt * 8 + random.uniform(0, 5))
    return None

def owner_ids_from_html(text):
    matches = list(re.finditer(r"/sale/flat/(\d+)/", text))
    owners = set()
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else min(len(text), start + 6000)
        segment = text[start:end]
        if 'data-type="homeowner"' in segment or re.search(r">Собственник<", segment):
            owners.add(match.group(1))
    return owners

def fetch_city_html(sess, slug, page, label):
    url = "https://%s.cian.ru/kupit-kvartiru/?p=%d" % (slug, page)
    for attempt in range(2):
        try:
            r = sess.get(url, timeout=25)
            if r.status_code == 200:
                ids = re.findall(r"/sale/flat/(\d+)/", r.text)
                if ids:
                    owners = owner_ids_from_html(r.text)
                    items = [{"id": str(i), "raw": {}} for i in OrderedDict.fromkeys(ids)]
                    return items, owners
                print("[ПРОПУСК] %s: страниц нет (%s)" % (label, url))
                return [], set()
            print("[WARN] %s: HTTP %d (%s)" % (label, r.status_code, url))
        except Exception as e:
            print("[WARN] %s: %s (%s)" % (label, type(e).__name__, url))
        time.sleep(10 + attempt * 8)
    return None, set()

def main():
    print("[INFO] Парсер ЦИАН v14 стартует")
    sess = session()
    sess.headers.update(BASE_HEADERS)
    listings, owners, seen = OrderedDict(), OrderedDict(), set()

    test = len(sys.argv) > 1 and sys.argv[1].startswith("тест")
    per_city = ["Саратов", "Энгельс", "Одинцово"] if test else cities_to_collect()

    # 1) API-мегаполисы: два прохода (все, потом только собственники)
    for owners_only in (False, True):
        for name, rid in API_CITIES:
            for page in (1, 2):
                label = "%s%s стр.%d" % (name, " (собственники)" if owners_only else "", page)
                offers = fetch_api(sess, json_query(rid, page, owners_only), label)
                if offers is None:
                    continue
                for it in offers:
                    if not isinstance(it, dict) or not it.get("id"):
                        continue
                    lid = str(it["id"])
                    if lid not in seen:
                        seen.add(lid)
                        listings[lid] = {"city": name, "raw": it}
                    if owners_only:
                        owners[lid] = name
                print("[OK] %s: найдено=%d, накоплено собственников=%d" % (label, len(offers), len(owners)))
                pause(14)

    # 2) HTML-сбор по каждому городу отдельно (1 страница на город)
    for city in per_city:
        slug = cian_slug_for(city)
        label = "%s (html)" % city
        items, owner_ids = fetch_city_html(sess, slug, 1, label)
        if items is None:
            print("[ПРОПУСК] %s: поддомен недоступен" % city)
            continue
        new = 0
        for it in items:
            lid = it["id"]
            if lid not in seen:
                seen.add(lid)
                listings[lid] = {"city": city, "raw": it}
                new += 1
            if lid in owner_ids:
                owners[lid] = city
        print("[OK] %s: найдено=%d, новых=%d, собственников=%d" % (city, len(items), new, len(owner_ids)))
        pause(21)

    print("ИТОГ: объектов=%d, собственников=%d" % (len(listings), len(owners)))
    # слияние с существующим хранилищем: не выбрасывать данные Яндекса и прежние записи
    store_path = os.path.join("data", "listings.json")
    if os.path.exists(store_path):
        try:
            prev = json.load(open(store_path, encoding="utf-8"))
            if "listings" not in prev:
                prev = {"listings": prev}
            kept = 0
            for lid, val in (prev.get("listings") or {}).items():
                if lid not in listings:
                    listings[lid] = val
                    kept += 1
            for oid in prev.get("owners") or []:
                if oid not in owners and oid in listings:
                    owners[oid] = (listings[oid].get("city") or "")
            print("[OK] слияние: сохранено прежних записей=%d" % kept)
        except Exception as e:
            print("[WARN] слияние не удалось: %s" % e)
    os.makedirs("data", exist_ok=True)
    with open(os.path.join("data", "listings.json"), "w", encoding="utf-8") as f:
        json.dump({"listings": listings, "owners": list(owners.keys())}, f, ensure_ascii=False, indent=1)
    print("Сохранено: " + os.path.abspath(os.path.join("data", "listings.json")))

if __name__ == "__main__":
    main()
