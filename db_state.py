# -*- coding: utf-8 -*-
"""db_state: текущее распределение регион -> города по частникам."""
import sqlite3
con = sqlite3.connect("listings.db")
print("=== РЕГИОНЫ (is_owner=1) ===")
for r, n in con.execute(
    "SELECT region, COUNT(*) FROM listings WHERE is_owner=1 "
    "AND region!='' GROUP BY region ORDER BY COUNT(*) DESC"):
    print("  %r — %d" % (r, n))
print()
print("=== РЕГИОН -> ГОРОДА ===")
q = ("SELECT region, city, COUNT(*) FROM listings WHERE is_owner=1 "
     "GROUP BY region, city ORDER BY region, COUNT(*) DESC")
cur = None
for reg, cit, n in con.execute(q):
    if reg != cur:
        cur = reg
        print("\n[%r]" % reg)
    print("  %r — %d" % (cit, n))
print()
print("=== БЕЗ РЕГИОНА (топ-10 городов) ===")
for c, n in con.execute(
    "SELECT city, COUNT(*) FROM listings WHERE is_owner=1 "
    "AND (region='' OR region IS NULL) GROUP BY city ORDER BY COUNT(*) DESC LIMIT 10"):
    print("  %r — %d" % (c, n))
print()
print("=== ПРИМЕРЫ записей с city='Москва' (source, title) ===")
for s, t in con.execute(
    "SELECT source, title FROM listings WHERE is_owner=1 AND city='Москва' LIMIT 8"):
    print("  [%s] %r" % (s, t))
con.close()
