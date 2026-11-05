"""Парсер ЦИАН v1.0: сбор квартир/комнат, подсчёт собственников, база listings.db"""
import os, time, datetime
import sqlite3
import requests, yaml

API = "https://api.cian.ru/search-offers/v2/search-offers-body/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
           "Content-Type": "application/json"}
DB = os.getenv("LISTINGS_DB", "listings.db")

def load_cfg():
    with open("regions.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS listings ("
                 "url TEXT PRIMARY KEY, city TEXT, title TEXT, price INTEGER,"
                 "rooms TEXT, area REAL, author_type TEXT, is_owner INTEGER,"
                 "first_seen TEXT, last_seen TEXT, price_dropped INTEGER DEFAULT 0)")
    conn.commit()
    return conn

def fetch_region(region_id, pages=2):
    offers = []
    for page in range(1, pages + 1):
        payload = {"jsonQuery": {
            "engine_version": {"type": "term", "value": "2"},
            "_type": "flatrentsale", "offer_type": "offany",
            "region": {"type": "terms", "value": [region_id]},
            "page": {"type": "term", "value": page},
        }}
        try:
            r = requests.post(API, headers=HEADERS, json=payload, timeout=30)
            data = r.json().get("data", {})
            offers.extend(data.get("offersSerialized", []))
        except Exception as e:
            print(f"[WARN] регион {region_id}, страница {page}: {e}")
        time.sleep(2)
    return offers

def norm(offer):
    url = "https://www.cian.ru" + (offer.get("fullUrl") or "")
    price = int(offer.get("bargainTerms", {}).get("price", 0) or 0)
    rooms = str(offer.get("flatType") or offer.get("roomsCount") or "?")
    area = offer.get("totalArea", {})
    area = float(area.get("value") or 0)
    return url, price, rooms, area

def main():
    cfg = load_cfg()
    conn = init_db()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    total = owners = dupes = 0
    for city in cfg["cities"]:
        if not city.get("enabled"):
            continue
        for offer in fetch_region(city["cian_region_id"]):
            total += 1
            url, price, rooms, area = norm(offer)
            author = str(offer.get("authorType") or "").lower()
            is_owner = 1 if "owner" in author or "собствен" in author else 0
            owners += is_owner
            old = conn.execute("SELECT price FROM listings WHERE url=?", (url,)).fetchone()
            if old:
                dupes += 1
                dropped = 1 if old[0] and price and price < old[0] else 0
                conn.execute("UPDATE listings SET last_seen=?, price=?, is_owner=?, price_dropped=? WHERE url=?",
                             (now, price, is_owner, dropped, url))
            else:
                conn.execute("INSERT INTO listings (url, city, title, price, rooms, area, author_type,"
                             "is_owner, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (url, city["name"], offer.get("fullName", ""), price, rooms, area,
                              author, is_owner, now, now))
    conn.commit()
    conn.close()
    print(f"ИТОГ: объектов={total}, собственников={owners}, дублей={dupes}")

if __name__ == "__main__":
    main()
