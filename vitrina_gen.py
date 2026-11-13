# -*- coding: utf-8 -*-
"""Генератор витрины index.html для gh-pages.

Вход: listings.db (LISTINGS_DB или cwd). Выход: index.html рядом со скриптом.
Данные только публичные: город, цена, площадь, этаж, ссылка на объявление,
счётчики. Никаких чатов, токенов и персональных данных.

Запуск: python vitrina_gen.py [--db путь] [--out путь]
"""
import argparse
import datetime
import io
import os
import sqlite3
import sys

if sys.stdout and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Свежие лоты-собственники — {date_str}</title>
<style>
 body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
        max-width: 760px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
 h1 {{ font-size: 1.4rem; }}
 .counters {{ color: #555; font-size: .95rem; margin-bottom: 1.5rem; }}
 table {{ border-collapse: collapse; width: 100%; font-size: .95rem; }}
 th, td {{ text-align: left; padding: .5rem .6rem; border-bottom: 1px solid #e5e5e5;
          vertical-align: top; }}
 th {{ border-bottom: 2px solid #999; }}
 a {{ color: #0b57d0; text-decoration: none; word-break: break-all; }}
 footer {{ margin-top: 2rem; color: #888; font-size: .85rem; }}
</style>
</head>
<body>
<h1>Свежие лоты-собственники</h1>
<div class="counters">Прогон: {date_str} &middot; Лотов в базе: {total}
 &middot; Собственников: {owners} &middot; Городов: {cities}</div>
<table>
<tr><th>Район</th><th>Цена</th><th>Площадь</th><th>Комментарий</th><th>Ссылка</th></tr>
{rows}
</table>
<footer>Обновляется после утреннего прогона парсера. Источник — открытые
объявления ЦИАН и Яндекс.Недвижимость. Ссылки ведут на исходные объявления.</footer>
</body>
</html>
"""


def fmt_price(price):
    return "{:,.0f}".format(price).replace(",", " ") + " ₽"


def fmt_area(area):
    if not area:
        return "—"
    return ("%g м²" % area).replace(".", ",")


def fmt_rooms(rooms):
    if rooms is None or rooms == 0 or rooms == "":
        return ""
    try:
        n = int(rooms)
    except (TypeError, ValueError):
        return ""
    if n == 0:
        return ""
    return "%d-комн." % n


def fmt_comment(row):
    _, city, title, price, rooms, area, author_type, is_owner, price_dropped, floor, floors_total, source = row
    parts = []
    r = fmt_rooms(rooms)
    if r:
        parts.append(r)
    if floor:
        fl = "%d" % floor if floor == int(floor) else ("%g" % floor)
        ft = "/%d" % floors_total if floors_total else ""
        parts.append(fl + ft + " эт.")
    if author_type:
        parts.append("собственник" if is_owner else str(author_type))
    if price_dropped:
        parts.append("цена снижена")
    return "; ".join(parts) or title or "—"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("LISTINGS_DB", "listings.db"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"))
    args = ap.parse_args()

    conn = sqlite3.connect("file:%s?mode=ro" % args.db, uri=True)
    try:
        total, owners, cities = conn.execute(
            "SELECT COUNT(*), SUM(is_owner=1), COUNT(DISTINCT city) FROM listings").fetchone()
        rows = conn.execute(
            "SELECT url, city, title, price, rooms, area, author_type, is_owner, "
            "price_dropped, floor, floors_total, source, detected_at FROM listings "
            "WHERE is_owner=1 AND price IS NOT NULL "
            "ORDER BY detected_at DESC LIMIT 5").fetchall()
        max_detected = conn.execute("SELECT MAX(detected_at) FROM listings").fetchone()[0]
    finally:
        conn.close()

    trs = []
    for row in rows:
        url, city, title, price, rooms, area = row[:6]
        trs.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
            "<td><a href=\"%s\">объявление</a></td></tr>"
            % (city or "—", fmt_price(price), fmt_area(area), fmt_comment(row[:12]), url))

    date_str = "—"
    if max_detected:
        try:
            dt = datetime.datetime.fromisoformat(max_detected)
            date_str = dt.strftime("%d.%m.%Y %H:%M UTC")
        except ValueError:
            date_str = max_detected[:16]

    html = PAGE.format(date_str=date_str, total=total or 0, owners=owners or 0,
                       cities=cities or 0, rows="\n".join(trs))
    with io.open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print("[ВИТРИНА] index.html сгенерирован: лотов=%s собственников=%s городов=%s"
          % (total or 0, owners or 0, cities or 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
