# -*- coding: utf-8 -*-
"""geo.py v2: нормализация города и региона + извлечение города из адреса."""
CITY_REGION = {
    "Екатеринбург": "Свердловская область",
    "Москва": "Москва",
    "Санкт-Петербург": "Санкт-Петербург",
    "Краснодар": "Краснодарский край",
    "Казань": "Республика Татарстан",
    "Новосибирск": "Новосибирская область",
    "Саратов": "Саратовская область",
}
PREFIXES = ("город ", "г. ", "посёлок городского типа ", "посёлок ",
            "село ", "деревня ", "пгт ")
STREET_WORDS = ("улиц", "проспект", "проезд", "переулок", "микрорайон",
                "бульвар", "шоссе", "набережная", "площадь", "снт", "садовод")

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
        if c and not _street_like(c):
            return c
        break
    return ""

def normalize(raw, addr=""):
    """Возвращает (город, регион) из сырого значения и адреса-подстраховки."""
    raw = (raw or "").strip()
    if not raw:
        c = from_address(addr)
        return c, CITY_REGION.get(c, "")
    parts = [x.strip() for x in raw.split(",") if x.strip()]
    if len(parts) <= 1:
        if _region_like(raw):
            c = from_address(addr)
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
        if c:
            city = c
        break
    if not city:
        city = from_address(addr)
    if not region and city in CITY_REGION:
        region = CITY_REGION[city]
    return city, region
