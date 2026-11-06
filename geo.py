# -*- coding: utf-8 -*-
"""geo.py v3: справочник городов, поиск города по заголовку, мусор-фильтр."""
CITY_REGION = {
    "Екатеринбург": "Свердловская область",
    "Асбест": "Свердловская область",
    "Малышева": "Свердловская область",
    "Рефтинский": "Свердловская область",
    "Москва": "Москва",
    "Санкт-Петербург": "Санкт-Петербург",
    "Краснодар": "Краснодарский край",
    "Яблоновский": "Республика Адыгея",
    "Казань": "Республика Татарстан",
    "Новосибирск": "Новосибирская область",
    "Саратов": "Саратовская область",
    "Энгельс": "Саратовская область",
    "Балаково": "Саратовская область",
    "Вольск": "Саратовская область",
    "Маркс": "Саратовская область",
    "Аткарск": "Саратовская область",
    "Балашов": "Саратовская область",
    "Энгельсское": "Саратовская область",
}
REGION_CITIES = {}
for c, r in CITY_REGION.items():
    REGION_CITIES.setdefault(r, []).append(c)

PREFIXES = ("город ", "г. ", "посёлок городского типа ", "посёлок ",
            "село ", "деревня ", "пгт ", "микрорайон ")
STREET_WORDS = ("улиц", "проспект", "проезд", "переулок",
                "бульвар", "шоссе", "набережная", "площадь", "снт", "садовод")
JUNK_WORDS = ("купить", "продам", "продаётся", "квартира", "комнат", "цена", "млн")

def _region_like(s):
    return (s.endswith("область") or s.endswith("край")
            or s.startswith("Республика") or "автономн" in s)

def _clean_city(p):
    low = p.lower()
    for pref in PREFIXES:
        if low.startswith(pref):
            return p[len(pref):].strip()
    return p

def _street_like(s):
    low = s.lower()
    return any(w in low for w in STREET_WORDS) or s[:1].isdigit()

def _junk_like(s):
    low = s.lower()
    return any(w in low for w in JUNK_WORDS) or len(s) > 40

def from_address(addr):
    """Город из начала адреса: «Саратов, улица …» -> «Саратов»."""
    addr = (addr or "").strip()
    if not addr:
        return ""
    parts = [x.strip() for x in addr.split(",") if x.strip()]
    if parts and parts[0] == "Россия":
        parts = parts[1:]
    for p in parts:
        if _region_like(p) or "район" in p.lower():
            continue
        c = _clean_city(p)
        if c and not _street_like(c) and not _junk_like(c):
            return c
        break
    return ""

def find_known_city(text):
    """Ищет известный город справочника прямо в тексте: «… — Саратов, улица…»."""
    text = text or ""
    for city in CITY_REGION:
        if city in text:
            return city
    return ""

def normalize(raw, addr=""):
    """Возвращает (город, регион) из сырого значения и адреса/заголовка."""
    raw = (raw or "").strip()
    if not raw:
        c = from_address(addr)
        return c, CITY_REGION.get(c, "")
    parts = [x.strip() for x in raw.split(",") if x.strip()]
    if len(parts) <= 1:
        if _region_like(raw):
            c = from_address(addr) or find_known_city(addr)
            return c, raw
        return raw, CITY_REGION.get(raw, "")
    region = ""
    for p in parts[1:]:
        if _region_like(p):
            region = p
            break
    city = ""
    for p in parts[1:]:
        if _region_like(p) or "район" in p.lower():
            continue
        c = _clean_city(p)
        if c and not _junk_like(c):
            city = c
        break
    if not city:
        city = from_address(addr) or find_known_city(addr)
    if not region:
        region = CITY_REGION.get(city, "") or find_known_city(city) and CITY_REGION.get(find_known_city(city), "")
    return city, region
