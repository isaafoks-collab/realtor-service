# -*- coding: utf-8 -*-
"""Проверка: заполнился ли raw."""
import json
d = json.load(open("data/listings.json", encoding="utf-8"))
filled = sum(1 for r in d["listings"].values() if r.get("raw"))
print("объявлений=%d, с данными raw=%d" % (len(d["listings"]), filled))
sample = next((r["raw"] for r in d["listings"].values() if r.get("raw")), None)
if sample:
    print("пример ключей:", sorted(sample.keys())[:25])
