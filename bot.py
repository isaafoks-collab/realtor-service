# -*- coding: utf-8 -*-
"""Бот «Прямо» v3.2 — выбор региона, затем города; метки риска и этажа."""
import os, sqlite3
import telebot
from telebot import types
from access import grant, has_access

TOKEN = os.getenv("BOT_TOKEN")
FREE_CODE = os.getenv("FREE_CODE", "PRYMO-2026")
DB = os.getenv("LISTINGS_DB", "listings.db")
bot = telebot.TeleBot(TOKEN)
state = {}

CONSENT = ("Прежде чем продолжить: мы обрабатываем ваши данные по 152-ФЗ. "
           "Оферта и политика — по ссылкам в меню. Продолжая, вы соглашаетесь.")


def cols():
    conn = sqlite3.connect(DB)
    c = [r[1] for r in conn.execute("PRAGMA table_info(listings)").fetchall()]
    conn.close()
    return c


def regions_from_db():
    try:
        conn = sqlite3.connect(DB)
        rows = conn.execute(
            "SELECT region, COUNT(*) AS n FROM listings WHERE is_owner=1 "
            "AND region IS NOT NULL AND region != '' "
            "GROUP BY region ORDER BY n DESC").fetchall()
        conn.close()
        return [r[0] for r in rows if r[0]][:15]
    except Exception:
        return []


def cities_in_region(region):
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT city, COUNT(*) AS n FROM listings WHERE is_owner=1 AND region=? "
        "AND city IS NOT NULL AND city != '' "
        "GROUP BY city ORDER BY n DESC LIMIT 11", (region,)).fetchall()
    conn.close()
    return [r[0] for r in rows]


def pairs_kb(items, current=None):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for c in items:
        row.append(("> " if c == current else "") + c)
        if len(row) == 2:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    return kb


def main_kb(region=None):
    return pairs_kb(regions_from_db(), region) if False else pairs_kb(["Все регионы"] + regions_from_db()[:7])


def onetime_kb(items):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row(*items)
    return kb


@bot.message_handler(commands=["start"])
def start(m):
    state[m.chat.id] = {"step": "consent"}
    bot.send_message(m.chat.id, CONSENT, reply_markup=onetime_kb(["Согласен"]))


@bot.message_handler(commands=["tarify"])
def tarify(m):
    bot.send_message(m.chat.id,
        "Тарифы:\n"
        "Подборки: Москва 990 ₽/мес, крупные города 690 ₽, прочие 490 ₽\n"
        "Лиды: 600 ₽ за контакт или 2990 ₽/мес (гарантия возврата)\n"
        "Отчёт по объекту: 590 ₽ разово\n"
        "Пакет «Подготовка к сделке»: 1490 ₽")


@bot.message_handler(commands=["faq"])
def faq(m):
    bot.send_message(m.chat.id,
        "FAQ:\n— Откуда данные? ЦИАН и Яндекс, ежедневный сбор.\n"
        "— Законно? Да, открытые объявления + 152-ФЗ согласия.\n"
        "— Почему не агенты? Фильтр чистит агентские объявления, спорные помечает.\n"
        "— Не дозвонился по лиду? Вернём деньги.\n"
        "— Отписка: /stop")


@bot.message_handler(commands=["доступ", "access"])
def access_cmd(m):
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(m.chat.id, "Формат: /доступ КОД")
        return
    res = grant(m.from_user.id, parts[1], FREE_CODE)
    if res == "ok":
        bot.send_message(m.chat.id, "Доступ выдан. Вечный.")
    elif res == "again":
        bot.send_message(m.chat.id, "У вас уже есть вечный доступ.")
    else:
        bot.send_message(m.chat.id, "Неверный код. Доступ персональный, выдаётся по приглашению.")


def parse_price(text):
    try:
        a, b = text.replace(" ", "").split("-")
        return float(a), float(b)
    except Exception:
        return None


def send_podbor(m):
    if not has_access(m.from_user.id):
        limit, hint = 3, "\n\nПолная подборка — по вечному доступу: /доступ КОД"
    else:
        limit, hint = 30, ""
    st = state.get(m.chat.id, {})
    c = cols()
    risk_col = "agent_risk" if "agent_risk" in c else "0"
    sel = ("SELECT url, city, price, rooms, area, price_dropped, floor, %s "
           "FROM listings WHERE is_owner=1 AND price IS NOT NULL" % risk_col)
    args = []
    if st.get("city"):
        sel += " AND city=?"
        args.append(st["city"])
    elif st.get("region"):
        sel += " AND region=?"
        args.append(st["region"])
    rooms = st.get("rooms")
    if rooms == "4+":
        sel += " AND CAST(rooms AS INTEGER)>=4"
    elif rooms and rooms != "любое":
        sel += " AND CAST(rooms AS INTEGER)=?"
        args.append(rooms)
    pr = st.get("price")
    if pr:
        sel += " AND price>=? AND price<=?"
        args += [pr[0], pr[1]]
    sel += " ORDER BY last_seen DESC LIMIT ?"
    args.append(limit)
    conn = sqlite3.connect(DB)
    rows = conn.execute(sel, args).fetchall()
    conn.close()
    label = st.get("city") or st.get("region") or "все регионы"
    if not rows:
        bot.send_message(m.chat.id,
            "По фильтрам «%s» ничего нет. Ослабьте фильтры (например, «любое» "
            "по комнатности) или выберите весь регион." % label,
            reply_markup=main_kb(st.get("region")))
        return
    items = []
    for url, ct, price, rooms_, area, dropped, floor, risk in rows:
        tags = []
        if risk == 2:
            tags.append("⚠ вероятный агент")
        elif risk == 1:
            tags.append("⚠ требует проверки")
        else:
            tags.append("Собственник")
        if dropped:
            tags.append("Цена снижена")
        fl = (" · этаж %s" % floor) if floor else ""
        ar = ("%g м²" % area) if area else ""
        rm = ("%sк" % rooms_) if rooms_ is not None else ""
        head = " · ".join(x for x in (ct, rm, ar) if x)
        items.append("\n%s · %d ₽%s · %s\n%s" % (head, price, fl, ", ".join(tags), url))
    chunks, cur = [], ""
    for it in items:
        if len(cur) + len(it) > 3500 and cur:
            chunks.append(cur)
            cur = it
        else:
            cur += it
    if cur:
        chunks.append(cur)
    first = True
    for ch in chunks:
        text = ("Подборка: %s — %d объектов от собственников\n" % (label, len(rows)) + ch
                + hint) if first else ch
        bot.send_message(m.chat.id, text,
                         reply_markup=main_kb(st.get("region")) if first else None)
        first = False


@bot.message_handler(commands=["podbor"])
def podbor(m):
    send_podbor(m)


@bot.message_handler(func=lambda m: True)
def flow(m):
    st = state.setdefault(m.chat.id, {})
    text = (m.text or "").strip()
    regions = regions_from_db()

    if text == "Все регионы" or text in regions:
        st["region"] = None if text == "Все регионы" else text
        st["city"] = None
        st["step"] = "type"
        if st["region"]:
            cities = cities_in_region(st["region"])
            if len(cities) > 1:
                st["step"] = "city"
                bot.send_message(m.chat.id, "Регион: %s. Выберите город или весь регион." % st["region"],
                                 reply_markup=pairs_kb(["Весь регион"] + cities))
                return
        bot.send_message(m.chat.id, "Регион: %s. Что искать?" % (st["region"] or "все регионы"),
                         reply_markup=onetime_kb(["квартиры", "комнаты", "дома", "участки"]))
        return
    if st.get("step") == "city" and text == "Весь регион":
        st["city"] = None
        st["step"] = "type"
        bot.send_message(m.chat.id, "Регион: %s (весь). Что искать?" % st.get("region", ""),
                         reply_markup=onetime_kb(["квартиры", "комнаты", "дома", "участки"]))
        return
    if st.get("step") == "consent" and text == "Согласен":
        st["step"] = "region"
        bot.send_message(m.chat.id, "Где ищете?", reply_markup=main_kb(None))
        return

    step = st.get("step")
    if step == "consent":
        bot.send_message(m.chat.id, CONSENT, reply_markup=onetime_kb(["Согласен"]))
    elif step == "region":
        st["region"] = text or None
        st["city"] = None
        st["step"] = "type"
        bot.send_message(m.chat.id, "Что искать?", reply_markup=onetime_kb(["квартиры", "комнаты", "дома", "участки"]))
    elif step == "city":
        st["city"] = None if text == "Весь регион" else (text or None)
        st["step"] = "type"
        bot.send_message(m.chat.id, "Что искать?", reply_markup=onetime_kb(["квартиры", "комнаты", "дома", "участки"]))
    elif step == "type":
        if text in ("комнаты", "дома", "участки"):
            bot.send_message(m.chat.id, "Пока собираем только квартиры. Комнаты, дома и участки подключим следом. Продолжаем с квартирами.")
        st["otype"] = "квартиры"
        st["step"] = "rooms"
        bot.send_message(m.chat.id, "Сколько комнат?", reply_markup=onetime_kb(["любое", "1", "2", "3", "4+"]))
    elif step == "rooms":
        st["rooms"] = text if text in ("любое", "1", "2", "3", "4+") else "любое"
        st["step"] = "price"
        bot.send_message(m.chat.id, "Диапазон цены (например: 3000000-8000000, либо «любая»):")
    elif step == "price":
        st["price"] = parse_price(text) if text not in ("любая", "") else None
        st["step"] = "done"
        bot.send_message(m.chat.id,
            "Фильтры сохранены: регион=%s, город=%s, комнат=%s, цена=%s.\nЖмите /podbor. Всё меняется в любой момент."
            % (st.get("region") or "любой", st.get("city") or "весь регион",
               st.get("rooms") or "любое", st.get("price") or "любая"))
        send_podbor(m)
    else:
        bot.send_message(m.chat.id, "Жмите /podbor, /tarify, /faq или /доступ КОД", reply_markup=main_kb(st.get("region")))


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("BOT_TOKEN не задан.")
    print("Бот запущен. Ctrl+C — остановка.")
    bot.infinity_polling()
