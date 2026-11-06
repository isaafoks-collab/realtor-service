# -*- coding: utf-8 -*-
"""renorm4: перечистка под v4-справочник."""
import sqlite3
from geo import normalize
con = sqlite3.connect("listings.db")
rows = con.execute("SELECT rowid, city, title FROM listings").fetchall()
n_city = n_reg = 0
for rid, c, title in rows:
    city, region = normalize(c, title)
    if city and not c:
        n_city += 1
    if region and not region and c:
        n_reg += 1
    con.execute("UPDATE listings SET city=?, region=? WHERE rowid=?", (city, region, rid))
con.commit()
print("[ИТОГ] строк=%d, добавлено городов=%d, добавлено регионов=%d" % (len(rows), n_city, n_reg))
cur = None
for reg, cit, n in con.execute(
    "SELECT region, city, COUNT(*) FROM listings WHERE is_owner=1 "
    "GROUP BY region, city ORDER BY region, COUNT(*) DESC"):
    if reg != cur:
        cur = reg
        print("\n[%s]" % reg)
    print("  %s — %d" % (cit, n))
con.close()
