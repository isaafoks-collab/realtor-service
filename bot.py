"""Бот «Прямо» v1.0 — подборка собственников для риэлторов."""
import os, sqlite3, yaml
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

def keyboard(items):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for i in items:
        kb.add(i)
    return kb

@bot.message_handler(commands=["start"])
def start(m):
    state[m.chat.id] = {"step": "consent"}
    kb = keyboard(["Согласен"])
    bot.send_message(m.chat.id, CONSENT, reply_markup=kb)

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
        "FAQ:\n— Откуда данные? ЦИАН, ежедневный сбор.\n"
        "— Законно? Да, открытые объявления + 152-ФЗ согласия.\n"
        "— Почему не агенты? Мы чистим агентские объявления.\n"
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
        bot.send_message(m.chat.id, "Неверный код. Доступ персональный, выдается по приглашению.")

@bot.message_handler(commands=["podbor"])
def podbor(m):
    if not has_access(m.from_user.id):
        limit = 3
        hint = "\n\nПолная подборка — по вечному доступу: /доступ КОД"
    else:
        limit = 100
        hint = ""
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT url, city, price, rooms, area, is_owner, price_dropped FROM listings "
        "WHERE is_owner=1 ORDER BY last_seen DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    if not rows:
        bot.send_message(m.chat.id, "База пуста — парсер ещё не запускался.")
        return
    msg = "Подборка собственников:\n"
    for url, city, price, rooms, area, is_owner, dropped in rows:
        tags = ["Собственник"]
        if dropped:
            tags.append("Цена снижена")
        msg += f"\n{city} · {rooms} · {area} м² · {price} ₽ · {', '.join(tags)}\n{url}"
    bot.send_message(m.chat.id, msg + hint)

@bot.message_handler(func=lambda m: True)
def flow(m):
    st = state.get(m.chat.id, {})
    step = st.get("step")
    if step == "consent":
        st["step"] = "city"
        bot.send_message(m.chat.id, "Ваш город?", keyboard(["Москва", "Другой"]))
    elif step == "city":
        st["step"] = "type"
        bot.send_message(m.chat.id, "Что искать?", keyboard(["квартиры", "комнаты"]))
    elif step == "type":
        st["step"] = "price"
        bot.send_message(m.chat.id, "Диапазон цены (например: 3000000-8000000)?")
    elif step == "price":
        st["step"] = "done"
        bot.send_message(m.chat.id,
            "Фильтры сохранены. Жмите /podbor — пришлю подборку собственников.\n"
            "Тарифы: /tarify, вопросы: /faq")
    else:
        bot.send_message(m.chat.id, "Жмите /podbor, /tarify, /faq или /доступ КОД")

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("BOT_TOKEN не задан. Задайте переменную окружения.")
    print("Бот запущен. Ctrl+C — остановка.")
    bot.infinity_polling()
