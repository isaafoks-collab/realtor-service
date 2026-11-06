# -*- coding: utf-8 -*-
"""Разовая нормализация базы: city + новая колонка region."""
import sqlite3
from geo import normalize
con = sqlite3.connect("listings.db")
cols = [r[1] for r in con.execute("PRAGMA table_info(listings)").fetchall()]
if "region" not in cols:
    con.execute("ALTER TABLE listings ADD COLUMN region TEXT")
    print("[OK] колонка region добавлена")
rows = con.execute("SELECT rowid, city FROM listings").fetchall()
fixed_city = 0
for rid, c in rows:
    city, region = normalize(c)
    if city != (c or ""):
        fixed_city += 1
    con.execute("UPDATE listings SET city=?, region=? WHERE rowid=?", (city, region, rid))
con.commit()
n = con.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
regs = con.execute("SELECT COUNT(DISTINCT region) FROM listings WHERE is_owner=1").fetchone()[0]
con.close()
print("[ИТОГ] строк=%d, переписано городов=%d, регионов у частников=%d" % (n, fixed_city, regs))
