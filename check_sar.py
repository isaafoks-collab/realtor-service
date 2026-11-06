# -*- coding: utf-8 -*-
"""check_sar: текущее распределение городов в Саратовской области."""
import sqlite3
con = sqlite3.connect("listings.db")
print("Распределение городов (is_owner=1, Саратовская область):")
for c, n in con.execute(
    "SELECT city, COUNT(*) FROM listings WHERE is_owner=1 "
    "AND region='Саратовская область' GROUP BY city ORDER BY COUNT(*) DESC"):
    print("  %r — %d" % (c, n))
print()
print("Примеры заголовков (первые 10):")
for t, in con.execute(
    "SELECT title FROM listings WHERE is_owner=1 "
    "AND region='Саратовская область' LIMIT 10"):
    print(repr(t))
con.close()
