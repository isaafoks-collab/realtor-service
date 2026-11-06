# -*- coding: utf-8 -*-
"""Проверка: города из дым-теста должны лежать в базе под своими именами."""
import sqlite3
con = sqlite3.connect("listings.db")
for reg in ("Саратовская область", "Московская область"):
    print("\n[%s]" % reg)
    rows = con.execute(
        "SELECT city, COUNT(*) FROM listings WHERE is_owner=1 AND region=? "
        "GROUP BY city ORDER BY COUNT(*) DESC", (reg,)).fetchall()
    if rows:
        for c, n in rows:
            print("  %s — %d" % (c, n))
    else:
        print("  пусто")
con.close()
