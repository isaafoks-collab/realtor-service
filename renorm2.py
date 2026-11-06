# -*- coding: utf-8 -*-
"""renorm2: перечистка всех записей — города из адресов, сводка по регионам."""
import sqlite3
from geo import normalize
con = sqlite3.connect("listings.db")
rows = con.execute("SELECT rowid, city, title FROM listings").fetchall()
changed = 0
for rid, c, title in rows:
    city, region = normalize(c, title)
    if (city, region) != (c or "", ""):
        changed += 1
    con.execute("UPDATE listings SET city=?, region=? WHERE rowid=?", (city, region, rid))
con.commit()
print("[ИТОГ] перечищено=%d из %d" % (changed, len(rows)))
q = ("SELECT region, city, COUNT(*) FROM listings WHERE is_owner=1 "
     "GROUP BY region, city ORDER BY region, COUNT(*) DESC")
cur_region = None
for reg, cit, n in con.execute(q):
    if reg != cur_region:
        cur_region = reg
        print("\n[%s]" % reg)
    print("  %s — %d" % (cit, n))
con.close()
