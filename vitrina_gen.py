# -*- coding: utf-8 -*-
"""Генератор витрины index.html для gh-pages (Фаза 1 — Людмила).

Требования:
- Один экран = одна мысль, крупный текст (база 18–20px), крупные кнопки-ссылки
- Сверху: «Обновлено сегодня в 07:02» (реальная дата последнего прогона)
- Два блока: «Собственники напрямую» и «Через агентов» — чётко разделены,
  собственники всегда первыми
- Каждый лот: фото (если есть в источнике), цена, адрес/район, площадь,
  ссылка «Открыть объявление» на исходник (одна ссылка, без редирект-цепочек)
- Телефоны собственников на публичной странице НЕ показывать
- Никакой рекламы, аналитики, cookie-баннеров, форм подписки
- Работает в стандартном браузере Android и на слабом интернете
- Светлая тема по умолчанию (лучше для пожилого пользователя) + кнопка тёмной
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
<title>Свежие лоты — {date_str}</title>
<style>
  :root {{
    --bg: #ffffff; --text: #1a1a1a; --muted: #555; --card-bg: #f7f7f7;
    --card-border: #e0e0e0; --accent: #0b57d0; --accent-bg: #eef4ff;
    --owner-bg: #f0fdf4; --agent-bg: #fffbeb;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #121212; --text: #e0e0e0; --muted: #999; --card-bg: #1e1e1e;
      --card-border: #333; --accent: #66b3ff; --accent-bg: #1a2a44;
      --owner-bg: #1a2e1a; --agent-bg: #2a2a1a;
    }}
  }}
  html.dark {{
    --bg: #121212; --text: #e0e0e0; --muted: #999; --card-bg: #1e1e1e;
    --card-border: #333; --accent: #66b3ff; --accent-bg: #1a2a44;
    --owner-bg: #1a2e1a; --agent-bg: #2a2a1a;
  }}
  body {{
    font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
    max-width: 800px; margin: 0 auto; padding: 1rem;
    background: var(--bg); color: var(--text); font-size: 18px; line-height: 1.5;
  }}
  h1 {{ font-size: 1.6rem; margin: 1rem 0 0.5rem; }}
  .updated {{ color: var(--muted); font-size: 1rem; margin-bottom: 1.5rem; }}
  .section {{ margin: 2rem 0; }}
  .section h2 {{
    font-size: 1.3rem; padding: 0.75rem 1rem; border-radius: 8px;
    background: var(--owner-bg); margin-bottom: 1rem;
  }}
  .section.agents h2 {{ background: var(--agent-bg); }}
  .card {{
    background: var(--card-bg); border: 1px solid var(--card-border);
    border-radius: 12px; padding: 1rem; margin-bottom: 1rem;
  }}
  .card img {{
    width: 100%; max-height: 200px; object-fit: cover; border-radius: 8px;
    margin-bottom: 0.75rem;
  }}
  .card .price {{ font-size: 1.4rem; font-weight: 700; color: var(--accent); }}
  .card .address {{ color: var(--muted); margin: 0.5rem 0; }}
  .card .area {{ font-size: 0.95rem; color: var(--muted); }}
  .card a.btn {{
    display: inline-block; margin-top: 0.75rem; padding: 0.75rem 1.5rem;
    font-size: 1.1rem; font-weight: 600; color: #fff;
    background: var(--accent); border-radius: 8px; text-decoration: none;
  }}
  .card a.btn:active {{ opacity: 0.8; }}
  .theme-toggle {{
    position: fixed; top: 1rem; right: 1rem; padding: 0.5rem 1rem;
    font-size: 0.9rem; background: var(--card-bg); color: var(--text);
    border: 1px solid var(--card-border); border-radius: 8px; cursor: pointer;
  }}
  footer {{ margin-top: 2rem; padding: 1rem 0; color: var(--muted); font-size: 0.9rem;
    border-top: 1px solid var(--card-border); }}
</style>
</head>
<body>
<button class="theme-toggle" onclick="toggleTheme()">🌙 / ☀️</button>
<h1>Свежие лоты</h1>
<div class="updated">Обновлено: {date_str}</div>

<div class="section owners">
<h2>🏠 Собственники напрямую</h2>
{owner_rows}
</div>

<div class="section agents">
<h2>📋 Через агентов</h2>
{agent_rows}
</div>

<footer>
Источник: ЦИАН, Яндекс.Недвижимость. Обновляется каждое утро в 07:02.
</footer>
<script>
function toggleTheme() {{
  document.documentElement.classList.toggle('dark');
  localStorage.setItem('dark', document.documentElement.classList.contains('dark'));
}}
if (localStorage.getItem('dark') === 'true') {{
  document.documentElement.classList.add('dark');
}}
</script>
</body>
</html>
"""

def fmt_price(price):
    if price is None:
        return "—"
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
    if price_dropped:
        parts.append("цена снижена")
    return "; ".join(parts) or title or ""

def make_card(row):
    """Один лот → HTML-карточка."""
    url, city, title, price, rooms, area, author_type, is_owner, price_dropped, floor, floors_total, source, detected_at = row
    photo = ""
    # Если в источнике есть фото — показываем (пока нет, оставляем пусто)
    if source:
        photo = '<img src="%s" alt="%s" loading="lazy">' % (source, title or "фото")
    
    address = city or "—"
    if title and title != address:
        address += " — " + title
    
    comment = fmt_comment(row[:12])
    
    card = """
<div class="card">
  {photo}
  <div class="price">{price}</div>
  <div class="address">{address}</div>
  <div class="area">{area}{comment}</div>
  <a class="btn" href="{url}">Открыть объявление</a>
</div>
""".format(
        photo=photo,
        price=fmt_price(price),
        address=address,
        area=fmt_area(area) + (" — " + comment if comment else ""),
        url=url
    )
    return card.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("LISTINGS_DB", "listings.db"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"))
    args = ap.parse_args()

    conn = sqlite3.connect("file:%s?mode=ro" % args.db, uri=True)
    try:
        # Собственники — первые 20
        owner_rows = conn.execute(
            "SELECT url, city, title, price, rooms, area, author_type, is_owner, "
            "price_dropped, floor, floors_total, source, detected_at FROM listings "
            "WHERE is_owner=1 AND price IS NOT NULL "
            "ORDER BY detected_at DESC LIMIT 20").fetchall()
        
        # Агенты — первые 20
        agent_rows = conn.execute(
            "SELECT url, city, title, price, rooms, area, author_type, is_owner, "
            "price_dropped, floor, floors_total, source, detected_at FROM listings "
            "WHERE is_owner=0 AND price IS NOT NULL "
            "ORDER BY detected_at DESC LIMIT 20").fetchall()
        
        total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        max_detected = conn.execute("SELECT MAX(detected_at) FROM listings").fetchone()[0]
    finally:
        conn.close()

    owner_html = "\n".join(make_card(r) for r in owner_rows) or "<p>Пока нет данных</p>"
    agent_html = "\n".join(make_card(r) for r in agent_rows) or "<p>Пока нет данных</p>"

    # Дата обновления
    date_str = "—"
    if max_detected:
        try:
            dt = datetime.datetime.fromisoformat(max_detected)
            # Показываем как "сегодня в 07:02" если прогон был сегодня
            now = datetime.datetime.now(datetime.timezone.utc)
            if dt.date() == now.date():
                date_str = "сегодня в %s" % dt.strftime("%H:%M")
            else:
                date_str = dt.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            date_str = max_detected[:16]

    html = PAGE.format(date_str=date_str, owner_rows=owner_html, agent_rows=agent_html)
    with io.open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    
    print("[ВИТРИНА] index.html сгенерирован: собственников=%d, агентов=%d, всего в базе=%d"
          % (len(owner_rows), len(agent_rows), total))
    return 0

if __name__ == "__main__":
    sys.exit(main())
