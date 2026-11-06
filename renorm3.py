# -*- coding: utf-8 -*-
"""renorm3: дозаполнение регионов и городов поверх v3-справочника."""
import sqlite3
from geo import normalize
con = sqlite3.connect("listings.db")
rows = con.execute("SELECT rowid, city, title FROM listings").fetchall()
fixed_city = fixed_region = 0
for rid, c, title in rows:
    city, region = normalize(c, title)
    if city and not c:
        fixed_city += 1
    if region and not (c and region):
        pass
    con.execute("UPDATE listings SET city=?, region=? WHERE rowid=?", (city, region, rid))
con.commit()
print("[ИТОГ] строк=%d, дозаполнено городов=%d" % (len(rows), fixed_city))
q = ("SELECT region, city, COUNT(*) FROM listings WHERE is_owner=1 "
     "GROUP BY region, city ORDER BY region, COUNT(*) DESC")
cur = None
for reg, cit, n in con.execute(q):
    if reg != cur:
        cur = reg
        print("\n[%s]" % reg)
    print("  %s — %d" % (cit, n))
con.close()
