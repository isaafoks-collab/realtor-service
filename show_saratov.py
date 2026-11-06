# -*- coding: utf-8 -*-
"""show_saratov: заголовки записей без города в Саратовской области."""
import sqlite3
con = sqlite3.connect("listings.db")
rows = con.execute(
    "SELECT rowid, title, city FROM listings "
    "WHERE is_owner=1 AND region='Саратовская область' "
    "AND (city='' OR city IS NULL) LIMIT 20").fetchall()
print("Всего записей без города: %d, показываю первые %d" % (
    con.execute("SELECT COUNT(*) FROM listings WHERE is_owner=1 "
                "AND region='Саратовская область' AND (city='' OR city IS NULL)"
                ).fetchone()[0], len(rows)))
for rid, title, city in rows:
    print("--- rowid=%s city=%r" % (rid, city))
    print(repr(title))
con.close()
