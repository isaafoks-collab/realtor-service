# План: daily_digest.py — утренняя сводка новых лотов в Telegram

Дата: 2026-11-10. Автор: слон (автономно, этап B-следствие/подготовка этапа F).

## Цель

В коде проекта НЕТ отправки новых лотов/сводки риэлтору в Telegram:
notify_queue наполняется runner-ом (runner.queue_new_owners →
db_schema.queue_notice), но никем не рассылается; sent_at никем не
проставляется (только metrics.py читает его для метрик). В realtor-боте
только меню и тёплые клиенты. А критерий готовности директивы №5 —
«объявления собственников доходят до Telegram-канала риэлтора».
Нужен компонент: ежедневный утренний скрипт, который после прогона
парсеров выбирает свежие частниковые лоты, отправляет сводку риэлтору
в Telegram и отмечает их sent_at + снимает очередь.

## Что меняется

Новый файл: `daily_digest.py` (корень проекта) + `test_daily_digest.py`.
Затрагиваемые существующие модули: только ЧТЕНИЕ — db_schema (pending/
mark_delivered), db (listings). Ничего в существующих файлах не правится.

### daily_digest.py (структура)

```python
# -*- coding: utf-8 -*-
"""Утренняя сводка: новые лоты-собственники → Telegram риэлтору.

Правила:
- выборка: is_owner=1, sent_at IS NULL, price IS NOT NULL,
  detected_at >= (UTC сейчас - 24ч);
- не отправлять, если новых 0 (без спама);
- сводка чанками ≤3500 символов (лимит Telegram 4096, круг 1);
- после успешной отправки: sent_at=now_utc для url из ОТПРАВЛЕННЫХ
  чанков (partial success) + db_schema.mark_delivered для их записей
  в notify_queue (pending);
- нет BOT_TOKEN или REALTOR_CHAT_ID → exit 0, лог «сводка выключена»;
- при неудаче отправки: попытка отправить короткое сообщение
  «[СБОЙ] сводка: <ошибка>» на тот же chat_id (для человека), exit 1.
Запуск: python daily_digest.py [--limit N]
"""
import os, sqlite3, sys, time, datetime, requests

DB_PATH = os.environ.get("LISTINGS_DB", "listings.db")  # как bot.py:32
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("REALTOR_CHAT_ID", "")
MAX_ITEMS = 40
WINDOW_HOURS = 24
CHUNK_LIMIT = 3500
PAUSE_BETWEEN = 3.0  # сек между сообщениями

def select_new(conn, since_iso, limit=MAX_ITEMS): ...
def build_text(rows): ...       # → (chunks, chunks_urls)
def send_text(text, timeout=30): ...   # requests.post api.telegram.org sendMessage
def mark_sent(conn, urls, now_iso): ...  # UPDATE listings SET sent_at=...
def clear_queue(conn, urls, now_iso): ... # db_schema.pending → mark_delivered по url
def main(argv): ...
```

- `select_new` SQL:
  `SELECT url, city, title, price, rooms, area FROM listings
   WHERE is_owner=1 AND sent_at IS NULL AND price IS NOT NULL
   AND detected_at >= ?
   ORDER BY detected_at DESC LIMIT ?`
  (используются только существующие колонки — факт схемы db_schema.py
  строки 17–39; фильтр price IS NOT NULL — выравнивание с
  runner.queue_new_owners (runner.py:130), замечание круга 1).
- build_text(rows): заголовок «🌅 Свежие собственники за 24ч: N», далее
  строки «— [Город] 2-комн., 54 м², 7 900 000 ₽ — url»; неполные поля
  пропускаются (price None → без цены; rooms None → без комнат); url
  обязателен. Сортировка по городу для читаемости.
  ЦЕНА: формат без запятых — пробелы-разделители тысяч
  (`"{:,.0f}".format(p).replace(",", " ")`).
  ВОЗВРАТ (круг 2): кортеж (chunks, chunks_urls) — chunks: список
  текстов ≤CHUNK_LIMIT (по границам строк, образец bot.py:173–181,
  но у КАЖДОГО чанка свой короткий заголовок «Свежие собственники
  (часть k/M): X шт.»); chunks_urls: параллельный список списков url,
  попавших в каждый чанк — так partial success знает, кому ставить
  sent_at.
  ЛИМИТ 4096 (круг 1, блокирующее → устранено): текст разбивается на
  ЧАНКИ ≤3500 символов.
- `send_text`: POST https://api.telegram.org/bot<TOKEN>/sendMessage
  (chat_id, text, disable_web_page_preview=True, parse_mode не задаём —
  url не размаркирован). 3 попытки с backoff 2/4/8 сек на сетевые ошибки
  и 429/500+ (по образцу httpclient.fetch_with_backoff, но обычным
  requests — т.к. curl_cffi для Telegram API не нужен; решение
  уменьшает зависимости на VPS). Отправка ПОСЛЕДОВАТЕЛЬНАЯ по чанкам:
  если чанк k упал — чанки k..N не отправляются, exit 1 (fallback);
  чанки 1..k-1 уже отправлены — их лоты ПОМЕЧАЮТСЯ sent_at (partial
  success: sent_at ставится только по url, реально ушедшим в тексте
  отправленных чанков; неснятые лоты уйдут в следующем прогоне — но
  окно 24ч по detected_at сохраняется, since_iso фиксирован на старте
  прогона, а не на времени чанка).
- `clear_queue`: из db_schema.pending(conn) выбираем записи, чей url
  в отправленном множестве, mark_delivered(conn, ids, now_iso).
  (pending читает LIMIT 200 — при переполнении очереди часть снимется
  на следующем прогоне; самовыравнивание, замечание круга 1.)
- `mark_sent`: `UPDATE listings SET sent_at=? WHERE url=?` поштучно
  (объёмы ≤40 — ок), commit один раз в конце. now_iso — всегда UTC ISO
  через `datetime.now(timezone.utc).isoformat()` (тот же формат, что
  runner.py:132 и json_to_db — замечание круга 1).
- Лимит сообщений: до N чанков ≤3500 символов (не одно сообщение —
  правка круга 1).

### test_daily_digest.py

Тесты (без сети, без реального Telegram):
1. test_select_new_filters: temp-БД (полная схема через db_schema.ensure)
   + строки: is_owner=1/sent_at NULL/detected свежий → выбирается;
   is_owner=0 → нет; sent_at заполнен → нет; detected старше 24ч → нет.
2. test_build_text: url присутствует, город группируется, None-поля
   не ломают; лимит MAX_ITEMS не превышен.
3. test_no_creds_exit_0: пустые env → main возвращает 0, отправки не было.
4. test_send_fail_exit_1_and_message: подмена send_text (падает на
   первом чанке) → main возвращает 1; дёргался send_fallback
   (сообщение человеку); ни один sent_at не проставлен (при упавшем
   первом чанке).
5. test_mark_sent_and_queue: фейк-отправка → sent_at заполнен у
   отправленных чанков; notify_queue pending по их url пуст.
6. test_chunking_limit: 60 лотов с длинными url → количество чанков
   >1; каждый чанк ≤3500 символов; на каждом чанке заголовок.
   (запускается без сети: main принимает параметры через injectable
   функции — select_new/send_text — так же, как test_orchestrator
   подменяет subprocess.run.)

## Правила расчёта и крайние значения

- Пустая выборка → exit 0 без сообщения (анти-спам; правило ночного
  окна из db_schema.py строк 6–7: ночные накопленные
  лоты уходят утром — это соответствует одному утреннему запуску).
- ПЕРЕПОЛНЕНИЕ (круг 2): лотов за окно >MAX_ITEMS → в лог
  «не влезло: K лотов» (K = полный счёт выборки минус LIMIT); хвост
  остаётся sent_at=NULL и может выйти за окно — осознанно (окно 24ч
  жёсткое, свежесть ценна), правило фиксируется в журнале решений.
- Дубликаты: url PRIMARY KEY — дубль невозможен; в сводку не дублируем.
- price INTEGER (копейки? факт: в бот-тестах «600 ?  2990 ?/м²» — цена
  в рублях целым числом) → формат «{:,.0f} ₽» с пробелами-разделителями.
- Секреты: token только из env, никогда не печатается и не попадает в
  логи/статус (используется только в URL запроса — и это стандартное
  место; в лог печатается только код ответа и text-ошибка API).
- exit-коды: 0 = ок или выключено; 1 = сбой отправки (systemd увидит,
  человек получит сообщение, если Telegram жив).

## Ручная проверка (пересчитываемая)

1. Юнит: python -m unittest test_daily_digest -v — 6 тестов OK.
2. Полный discover: python -m unittest discover -s . -p "test_*.py"
   rc==0 (95+6=101 тест).
3. Пересчёт по числам текущей базы: в локальной listings.db сейчас
   (20:52 прогон) is_owner=1 всего 2209, из них sent_at IS NULL —
   почти все (отправок ещё не было); окно 24ч отфильтрует старые —
   ручной SQL до прогона: SELECT COUNT(*) FROM listings WHERE
   is_owner=1 AND sent_at IS NULL AND detected_at >= date('now','-1 day')
   — число N войдёт в сводку (на VPS, после первого прогона).
4. Dry-run локально: python daily_digest.py без BOT_TOKEN → «сводка
   выключена», rc 0, БЕЗ сообщений (реальный Telegram не дёргается).

## Риски

- Telegram API блокировка chat_id (бот не состоит в канале) → 403 от
  API: send_text вернёт ошибку, fallback-сообщение тоже упадёт →
  exit 1, systemd-лог. Отчёт в статус.
- Реальная отправка сообщений риэлтору — ПОЛЬЗОВАТЕЛЬСКОЕ событие, но
  это и есть цель проекта (README); первую реальную отправку выполняет
  этап F на VPS.
- rate limit Telegram: чанки с паузой 3 сек между сообщениями
  (~20/мин — на границе лимита группы, при большем числе чанков
  backoff на 429 сработает).

## Что НЕ меняется

db_schema.py, runner.py, bot.py, json_to_db.py, metrics.py, парсеры,
orchestrator.py, мост, deploy/* (деплой-составка — отдельная задача),
файл токенов (локальный), база данных (только поля sent_at/delivered_at
в рантайме прогона).
