# -*- coding: utf-8 -*-
"""slug_report: какие города собрали данные, какие пропустили."""
import sqlite3
con = sqlite3.connect("listings.db")
print("=== ВСЕ РЕГИОНЫ -> ГОРОДА (is_owner=1) ===")
cur = None
for reg, cit, n in con.execute(
    "SELECT region, city, COUNT(*) FROM listings WHERE is_owner=1 "
    "GROUP BY region, city ORDER BY region, COUNT(*) DESC"):
    if reg != cur:
        cur = reg
        print("\n[%s]" % reg)
    print("  %s — %d" % (cit, n))
con.close()
