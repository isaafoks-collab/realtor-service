# -*- coding: utf-8 -*-
"""geo.py: нормализация города и региона из сырых значений."""
CITY_REGION = {
    "Екатеринбург": "Свердловская область",
    "Москва": "Москва",
    "Санкт-Петербург": "Санкт-Петербург",
    "Краснодар": "Краснодарский край",
    "Казань": "Республика Татарстан",
    "Новосибирск": "Новосибирская область",
}
PREFIXES = ("город ", "г. ", "посёлок городского типа ", "посёлок ",
            "село ", "деревня ", "пгт ")

def _region_like(s):
    return (s.endswith("область") or s.endswith("край")
            or s.startswith("Республика") or "автономн" in s)

def normalize(raw):
    """Возвращает (город, регион) из сырого значения поля city."""
    raw = (raw or "").strip()
    if not raw:
        return "", ""
    parts = [x.strip() for x in raw.split(",") if x.strip()]
    if len(parts) <= 1:
        return raw, CITY_REGION.get(raw, raw if _region_like(raw) else "")
    region = ""
    for p in parts[1:]:
        if _region_like(p):
            region = p
            break
    city = ""
    for p in parts[1:]:
        if _region_like(p) or "район" in p:
            continue
        low = p.lower()
        for pref in PREFIXES:
            if low.startswith(pref):
                p = p[len(pref):]
                break
        city = p
        break
    if not region and city in CITY_REGION:
        region = CITY_REGION[city]
    return city, region
