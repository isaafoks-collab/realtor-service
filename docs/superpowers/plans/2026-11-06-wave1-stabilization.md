# План: волна 1 — стабилизация (curl_cffi, бэкап БД, защита уведомлений)

> Исполнитель — эта сессия. После волны — отчёт и пауза до подтверждения.

**Сверка контекста промта с реальностью** (важно перед реализацией):
- Тестов 51 (unittest), не 39/pytest — счётчик ниже фиксируем, драйвер остаётся unittest.
- Стек бота — pyTelegramBotAPI; aiogram в проекте нет → limited-aiogram (библиотека
  для aiogram) прямой пользы не даёт; проверим существование пакета и применим
  эквивалентный механизм под telebot (свой тротлер + tenacity), иначе «установка ради
  установки».
- `requests` живёт в parser_cian.py, parser_yandex.py, check_cities.py.
- Кода бэкапа listings.db нет (файл listings_backup.db — старый артефакт) →
  делаем db_backup.py (sqlite3.Connection.backup + restore-проверка) и вписываем
  шаг в daily-parse.yml (единственное разрешённое изменение yml).

## Задача 1A — curl_cffi (+tenacity)
- requirements.txt: + curl_cffi, tenacity (requests остаётся: owned by JSON? нет
  — только если ещё используется; check_cities переводим тоже).
- parser_cian.py, parser_yandex.py, check_cities.py: `from curl_cffi import requests`
  + `impersonate="chrome"` на Session.
- Проверка: 51 тест OK; живой GET одного города ЦИАН (как в 1-й фазе) — HTTP 200.

## Задача 1B — бэкап БД
- Модуль `db_backup.py`: backup(src, dst) через sqlite3 backup API;
  verify(dst, src): integrity_check == ok, count(src)==count(dst),
  max(rowid) совпадает, последняя строка content-сравнима.
- Тест test_db_backup.py (временные файлы, WAL-режим).
- daily-parse.yml: шаг «backup + restore-проверка» до шага Commit database.
- Проверка вручную на listings.db.

## Задача 1C — защита отправки
- Проверить пакеты: limited-aiogram (PyPI) — применимость.
- Свой мини-тротлер `notify.py`: 1/сек на чат, 20/мин на группу,
  30/сек глобально, tenacity retry (exponential, 4 попытки) на исключения
  отправителя; инъекционные часы для тестов.
- Тест test_notify.py; подключение в bot.py одним местом
  (`bot.send_message = notify.wrap(bot.send_message)`).
- запись в БД: tenacity-обёртка для финальной записи json_to_db (точечно).

## Коммит
`chore: wave1 — curl_cffi (chrome TLS), db backup+restore drill, notify guard`
