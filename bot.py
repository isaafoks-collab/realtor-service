# -*- coding: utf-8 -*-
"""Бот «Прямо» v4 — меню всегда на экране, шаги с подсказками, старт всё сбрасывает."""
import os, time, sqlite3
import telebot
from telebot import types
from access import grant, has_access
from geo import REGION_CITIES
import warm_leads

ROLE = os.getenv("BOT_ROLE", "realtor")  # realtor | owners
REALTOR_CHAT_ID = os.getenv("REALTOR_CHAT_ID")
HELP_BTN = "🛠 Нужна помощь риэлтору"
DEADLINES = ["ближайшие 1–3 месяца", "3–6 месяцев", "6–12 месяцев", "больше года"]

def full_cities_in_region(region):
    """Все города региона: сначала те, где есть данные, затем весь справочник."""
    db_cities = cities_in_region(region) or []
    out = list(db_cities)
    for c in REGION_CITIES.get(region, []):
        if c not in out:
            out.append(c)
    return out

from geo import REGION_CITIES

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise SystemExit(
        "Не задана переменная окружения BOT_TOKEN.\n"
        "Задайте её перед запуском (см. README): setx BOT_TOKEN \"...\" "
        "или запускайте через start*.bat.")
FREE_CODE = os.getenv("FREE_CODE", "PRYMO-2026")
DB = os.getenv("LISTINGS_DB", "listings.db")
bot = telebot.TeleBot(TOKEN)
state = {}

WELCOME = ("👋 Привет! Это «Прямо» — подборка квартир напрямую от собственников, "
           "без агентов и посредников.\n\n"
           "Нажмите «🔍 Подбор жилья» — и за четыре шага получите подборку: "
           "регион → город → сколько комнат → цена.\n\n"
           "Всё можно менять в любой момент, а «🔄 Начать сначала» всегда вернёт в начало.")

CONSENT = ("Прежде чем продолжить: мы обрабатываем ваши данные по 152-ФЗ. "
           "Оферта и политика — по ссылкам в меню. Продолжая, вы соглашаетесь.")

PRICE_PRESETS = {
    "Любая цена": None,
    "до 5 млн": (0, 5_000_000),
    "5-10 млн": (5_000_000, 10_000_000),
    "10-20 млн": (10_000_000, 20_000_000),
    "20+ млн": (20_000_000, 10**12),
}


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
        "AND city IS NOT NULL AND city != '' AND city != ? "
        "GROUP BY city ORDER BY n DESC LIMIT 16", (region, region)).fetchall()
    conn.close()
    return [r[0] for r in rows]


def pairs_kb(items, current=None):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for c in items:
        row.append(("→ " if c == current else "") + c)
        if len(row) == 2:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    return kb


def consent_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("✅ Согласен")
    return kb


def menu_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🔍 Подбор жилья")
    if ROLE == "owners":
        kb.row(HELP_BTN)
    kb.row("💰 Тарифы", "❓ Вопросы и ответы")
    kb.row("🔑 Ввести код", "🔄 Начать сначала")
    return kb


def strip_arrow(text):
    return text[2:] if text.startswith("→ ") else text


def send_menu(m, text):
    state[m.chat.id] = {"step": "menu", "ts": time.time()}
    bot.send_message(m.chat.id, text, reply_markup=menu_kb())


def send_podbor(m):
    st = state.get(m.chat.id, {})
    if not has_access(m.from_user.id):
        limit, hint = 3, "\n\n🔑 Полная подборка — по вечному доступу. Нажмите «🔑 Ввести код»."
    else:
        limit, hint = 30, ""
    sel = ("SELECT url, city, price, rooms, area, price_dropped, floor, "
           "COALESCE(agent_risk, 0) FROM listings "
           "WHERE is_owner=1 AND price IS NOT NULL")
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
    elif rooms and rooms != "Любое":
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
    after_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    after_kb.row("🔍 Изменить параметры", "🔄 Начать сначала")
    after_kb.row("💰 Тарифы", "❓ Вопросы и ответы")
    if not rows:
        bot.send_message(m.chat.id,
            "По фильтрам «%s» ничего не нашлось. Попробуйте «Любое» по комнатности "
            "или «Любая цена» — или расширйте географию." % label,
            reply_markup=after_kb)
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
        bot.send_message(m.chat.id, text, reply_markup=after_kb if first else None)
        first = False


def parse_price(text):
    try:
        a, b = text.replace(" ", "").split("-")
        return float(a), float(b)
    except Exception:
        return None


def show_tarify(m):
    bot.send_message(m.chat.id,
        "💰 Тарифы:\n\n"
        "Подборки: Москва 990 ₽/мес, крупные города 690 ₽, прочие 490 ₽\n\n"
        "Лиды: 600 ₽ за контакт или 2990 ₽/мес (не дозвонились — вернём деньги)\n\n"
        "Отчёт по объекту: 590 ₽ разово\n\n"
        "Пакет «Подготовка к сделке»: 1490 ₽",
        reply_markup=menu_kb())


def show_faq(m):
    bot.send_message(m.chat.id,
        "❓ Частые вопросы:\n\n"
        "— Откуда данные? Из открытых объявлений ЦИАН и Яндекса, обновляем каждый день.\n"
        "— Это законно? Да: открытые объявления + согласия по 152-ФЗ.\n"
        "— Почему нет агентов? Фильтр отсеивает агентские объявления, спорные помечает.\n"
        "— Не дозвонился по лиду? Вернём деньги.\n"
        "— Контакты владельца? По тарифу «Лиды» или вечному доступу.",
        reply_markup=menu_kb())


@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(m.chat.id, WELCOME, reply_markup=menu_kb())
    state[m.chat.id] = {"step": "consent", "ts": time.time()}
    bot.send_message(m.chat.id, CONSENT, reply_markup=consent_kb())


@bot.message_handler(commands=["tarify"])
def tarify_cmd(m):
    show_tarify(m)


@bot.message_handler(commands=["faq"])
def faq_cmd(m):
    show_faq(m)


@bot.message_handler(commands=["podbor"])
def podbor_cmd(m):
    st = state.setdefault(m.chat.id, {})
    if st.get("city") or st.get("region"):
        send_podbor(m)
    else:
        send_menu(m, "Сначала выберите регион — нажмите «🔍 Подбор жилья».")


@bot.message_handler(commands=["доступ", "access"])
def access_cmd(m):
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(m.chat.id, "🔑 Отправьте код одной строкой: «🔑 Ввести код» в меню, затем сам код.")
        return
    res = grant(m.from_user.id, parts[1], FREE_CODE)
    if res == "ok":
        send_menu(m, "✅ Готово! Доступ выдан — он вечный. Жмите «🔍 Подбор жилья».")
    elif res == "again":
        send_menu(m, "У вас уже есть вечный доступ. Жмите «🔍 Подбор жилья».")
    else:
        send_menu(m, "Код не подошёл. Доступ персональный, выдаётся по приглашению.")


@bot.message_handler(commands=["лиды", "leads"])
def leads_cmd(m):
    rows = warm_leads.list_leads()
    if not rows:
        bot.send_message(m.chat.id, "Новых заявок нет.", reply_markup=menu_kb())
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for row in rows:
        card = warm_leads.build_card(row)
        bot.send_message(m.chat.id, card)
        kb.row("✅ Обработать №%d" % row[0])
    kb.row("🔄 Начать сначала")
    bot.send_message(m.chat.id, "Новых заявок: %d" % len(rows), reply_markup=kb)


@bot.message_handler(func=lambda m: True)
def flow(m):
    st = state.setdefault(m.chat.id, {})
    text = strip_arrow((m.text or "").strip())

    # сброс после долгого молчания — диалог начинается заново
    if st.get("ts") and time.time() - st["ts"] > 3 * 3600:
        st = state[m.chat.id] = {"step": "menu", "ts": time.time()}
        bot.send_message(m.chat.id, WELCOME, reply_markup=menu_kb())

    # глобальные кнопки меню работают с любого шага
    if text == "🔄 Начать сначала":
        bot.send_message(m.chat.id, WELCOME, reply_markup=menu_kb())
        st.clear(); st.update({"step": "consent", "ts": time.time()})
        bot.send_message(m.chat.id, CONSENT, reply_markup=consent_kb())
        return
    if text == "🔍 Подбор жилья":
        keep = st.get("consent_ok")
        st.clear(); st["consent_ok"] = keep; st["ts"] = time.time()
        if not st.get("consent_ok"):
            st["step"] = "consent"
            bot.send_message(m.chat.id, CONSENT, reply_markup=consent_kb())
            return
        st["step"] = "region"
        bot.send_message(m.chat.id, "Шаг 1 из 4. В каком регионе ищете?",
                         reply_markup=pairs_kb(["Все регионы"] + regions_from_db()))
        return
    if text == "💰 Тарифы":
        show_tarify(m); return
    if text == "❓ Вопросы и ответы":
        show_faq(m); return
    if text == "🔑 Ввести код":
        st.clear(); st["step"] = "code"; st["ts"] = time.time()
        bot.send_message(m.chat.id,
            "🔑 Отправьте код доступа одной строкой. Его выдают по приглашению.",
            reply_markup=types.ReplyKeyboardRemove())
        return
    if text.startswith("✅ Обработать №"):
        try:
            ok = warm_leads.mark_handled_id(int(text[len("✅ Обработать №"):]))
        except ValueError:
            ok = False
        send_menu(m, "Отмечено как обработанное." if ok else "Заявка не найдена.")
        return
    if text == "🔍 Изменить параметры":
        st["step"] = "region"
        bot.send_message(m.chat.id, "Шаг 1 из 4. В каком регионе ищете?",
                         reply_markup=pairs_kb(["Все регионы"] + regions_from_db()))
        return
    if text == HELP_BTN:
        st.clear(); st["step"] = "hlp_city"; st["ts"] = time.time()
        bot.send_message(m.chat.id,
            "🛠 Давайте подготовим заявку. Вы подпишете согласие (152-ФЗ), "
            "и риэлтор-партнёр вашего города сам свяжется с вами.\n\n"
            "В каком городе продаёте?",
            reply_markup=types.ReplyKeyboardRemove())
        return

    step = st.get("step")

    if step == "consent":
        if text in ("Согласен", "✅ Согласен"):
            st["consent_ok"] = True
            st["step"] = "region"
            st["ts"] = time.time()
            bot.send_message(m.chat.id, "Шаг 1 из 4. В каком регионе ищете?",
                             reply_markup=pairs_kb(["Все регионы"] + regions_from_db()))
        else:
            bot.send_message(m.chat.id, CONSENT, reply_markup=consent_kb())
        return

    if step == "code":
        res = grant(m.from_user.id, text, FREE_CODE)
        if res == "ok":
            send_menu(m, "✅ Готово! Доступ выдан — он вечный. Жмите «🔍 Подбор жилья».")
        elif res == "again":
            send_menu(m, "У вас уже есть вечный доступ. Жмите «🔍 Подбор жилья».")
        else:
            send_menu(m, "Код не подошёл. Доступ персональный, выдаётся по приглашению.")
        return

    if step == "region":
        if text == "Все регионы":
            st["region"] = None; st["city"] = None
        else:
            st["region"] = text; st["city"] = None
        cities = full_cities_in_region(st["region"]) if st["region"] else []
        st["ts"] = time.time()
        if cities:
            st["step"] = "city"
            kb = pairs_kb(["Весь регион"] + cities)
            bot.send_message(m.chat.id,
                "Шаг 2 из 4. Регион: %s. Выберите город или весь регион:" % st["region"],
                reply_markup=kb)
        elif st["region"]:
            st["step"] = "type"
            bot.send_message(m.chat.id,
                "Регион: %s. Разбивки по городам пока нет — покажем весь регион. Что ищем?" % st["region"],
                reply_markup=pairs_kb(["Квартиры", "Комнаты", "Дома", "Участки"]))
        else:
            st["step"] = "type"
            bot.send_message(m.chat.id, "Ищем по всем регионам. Что ищем?",
                             reply_markup=pairs_kb(["Квартиры", "Комнаты", "Дома", "Участки"]))
        return

    if step == "city":
        if text == "Весь регион":
            st["city"] = None
        else:
            conn = sqlite3.connect("listings.db")
            n_city = conn.execute(
                "SELECT COUNT(*) FROM listings WHERE is_owner=1 AND city=?",
                (text,)).fetchone()[0]
            conn.close()
            if n_city == 0:
                st["city"] = None
                st["step"] = "type"
                st["ts"] = time.time()
                bot.send_message(m.chat.id,
                    "В %s пока нет объявлений от собственников — покажу весь регион «%s». Что ищем?" % (text, st.get("region") or "выбранном"),
                    reply_markup=pairs_kb(["Квартиры", "Комнаты", "Дома", "Участки"]))
                return
            st["city"] = text
        st["step"] = "type"
        st["ts"] = time.time()
        label = st.get("city") or st.get("region") or "все регионы"
        bot.send_message(m.chat.id, "Шаг 3 из 4. «%s». Что ищем?" % label,
                         reply_markup=pairs_kb(["Квартиры", "Комнаты", "Дома", "Участки"]))
        return

    if step == "type":
        if text in ("Комнаты", "Дома", "Участки"):
            bot.send_message(m.chat.id,
                "Комнаты, дома и участки подключаем следом. Пока покажем квартиры — "
                "продолжаем.")
        st["otype"] = "квартиры"
        st["step"] = "rooms"
        st["ts"] = time.time()
        bot.send_message(m.chat.id, "Сколько комнат?",
                         reply_markup=pairs_kb(["Любое", "1", "2", "3", "4+"]))
        return

    if step == "rooms":
        st["rooms"] = text if text in ("Любое", "1", "2", "3", "4+") else "Любое"
        st["step"] = "price"
        st["ts"] = time.time()
        bot.send_message(m.chat.id,
            "Шаг 4 из 4. Какой диапазон цены?\nВыберите кнопку или напишите свой диапазон, "
            "например: 3500000-8000000",
            reply_markup=pairs_kb(list(PRICE_PRESETS) + ["Написать свою"]))
        return

    if step == "price":
        if text == "Написать свою":
            st["step"] = "price_free"
            bot.send_message(m.chat.id,
                "Напишите диапазон одной строкой, например: 3500000-8000000\n"
                "Или «любая», чтобы снять ограничение.",
                reply_markup=types.ReplyKeyboardRemove())
            return
        if text in PRICE_PRESETS:
            st["price"] = PRICE_PRESETS[text]
        else:
            st["price"] = parse_price(text)
            if st["price"] is None:
                bot.send_message(m.chat.id,
                    "Не понял диапазон. Формат: 3500000-8000000 — или выберите кнопку выше.")
                return
        st["step"] = "done"
        st["ts"] = time.time()
        p = st["price"]
        plabel = ("от %d до %d" % (p[0], p[1])) if p else "любая"
        if p and p[0] == 0:
            plabel = "до %d" % p[1]
        elif p and p[1] >= 10**11:
            plabel = "от %d" % p[0]
        bot.send_message(m.chat.id,
            "Отлично! Ищем: %s, %s, комнат: %s, цена: %s.\nСобираю подборку…"
            % (st.get("city") or st.get("region") or "все регионы",
               "квартиры", (st.get("rooms") or "Любое").lower(), plabel),
            reply_markup=types.ReplyKeyboardRemove())
        send_podbor(m)
        return

    if step == "price_free":
        if text in ("любая", "Любая"):
            st["price"] = None
        else:
            st["price"] = parse_price(text)
            if st["price"] is None:
                bot.send_message(m.chat.id,
                    "Не понял диапазон. Пример: 3500000-8000000, либо «любая».")
                return
        st["step"] = "done"
        st["ts"] = time.time()
        send_podbor(m)
        return

    if step == "hlp_city":
        st["h_city"] = text; st["step"] = "hlp_rooms"; st["ts"] = time.time()
        bot.send_message(m.chat.id, "Сколько комнат?", reply_markup=pairs_kb(
            ["Студия", "1", "2", "3", "4+"]))
        return

    if step == "hlp_rooms":
        st["h_rooms"] = text if text in ("Студия", "1", "2", "3", "4+") else ""
        st["step"] = "hlp_area"; st["ts"] = time.time()
        bot.send_message(m.chat.id,
            "Какая площадь? Например: 54. Или «нет», чтобы не указывать.",
            reply_markup=types.ReplyKeyboardRemove())
        return

    if step == "hlp_area":
        if text.lower() in ("нет", "не указывать"):
            st["h_area"] = None
        else:
            try:
                st["h_area"] = float(text.replace(",", ".").replace("м²", "").strip())
            except ValueError:
                bot.send_message(m.chat.id, "Площадь — числом, например 54 (или «нет»).")
                return
        st["step"] = "hlp_floor"; st["ts"] = time.time()
        bot.send_message(m.chat.id, "Этаж? Например: 5/9 (или «нет»).")
        return

    if step == "hlp_floor":
        st["h_floor"] = None if text.lower() in ("нет", "не указывать") else text
        st["step"] = "hlp_price"; st["ts"] = time.time()
        bot.send_message(m.chat.id, "На какую цену рассчитываете? Например: 7,2 млн (или «нет»).")
        return

    if step == "hlp_price":
        st["h_price"] = None if text.lower() in ("нет", "не указывать") else text
        st["step"] = "hlp_deadline"; st["ts"] = time.time()
        bot.send_message(m.chat.id, "В какие сроки планируете продать?", reply_markup=pairs_kb(DEADLINES))
        return

    if step == "hlp_deadline":
        deadline = text if text in DEADLINES else "ближайшие 1–3 месяца"
        payload = {
            "username": m.from_user.username,
            "city": st.get("h_city"), "rooms": st.get("h_rooms"),
            "area": st.get("h_area"), "floor": st.get("h_floor"),
            "price_wish": st.get("h_price"), "deadline": deadline,
        }
        res, lead_id = warm_leads.save_lead(m.from_user.id, payload)
        send_menu(m, "Отлично, принёс заявку №%d. Если риэлтор не позвонил — "
                     "нажмите ещё раз." % lead_id if res == "new" else
                 "У вас уже есть активная заявка №%d — риэлтор свяжется, "
                 "новую создавать не нужно." % lead_id)
        if res == "new":
            _, card = warm_leads.get_lead(m.from_user.id)
            warm_leads.deliver(card, send=(
                lambda c: bot.send_message(REALTOR_CHAT_ID, c)
            ) if REALTOR_CHAT_ID else None)
        return

    # шаг done и все прочие: неизвестный текст — подсказка
    send_menu(m, "Не понял сообщение 🙂 Выберите кнопку из меню внизу — "
                 "или «🔄 Начать сначала», чтобы начать подбор с нуля.")


if __name__ == "__main__":
    print("Бот запущен. Ctrl+C — остановка.")
    bot.infinity_polling()
