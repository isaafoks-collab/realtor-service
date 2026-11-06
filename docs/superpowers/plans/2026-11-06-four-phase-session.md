# План сессии: сторож Яндекса + is_owner ЦИАН, тёплые клиенты, Авито, уборка

> **Для агентов:** выполняется нативно в этой сессии, фаза за фазой.
> После каждой фазы — `git commit` и одна строка статуса.

**Глобальные ограничения:** секреты не печатать в чат; токены уже из окружения
(не переделывать); unittest, стиль репо (русские сообщения, корневые тесты
`test_*.py`); не трогать перечисленные в Фазе 4 файлы.

---

## ФАЗА 1 — Яндекс-сторож + is_owner ЦИАН

**Задача 1.1 Сторож капчи.**
- Modify: `parser_yandex.py`, Test: `test_parser_yandex.py`.
- Контракт: `def captcha_hit(resp) -> bool` — True при `X-Yandex-Captcha: captcha`
  ИЛИ `<title>` начинается с «Вы не робот» (проверялось 06.11: живой ответ
  200/14.6КБ/`X-Yandex-Captcha: captcha`/«Вы не робот?»).
- Тест: капча-минификстура (респ-стаб с заголовком) → True; нормальный ответ
  (данные `yandex_page.html` через стаб) → False; `data/yandex_404.html` → False
  (это честная 404, не капча).
- В цикле сбора: при капче `[БЛОК] <город> (<tag>)`, `continue`, без записи в БД;
  в ИТОГ — строка `заблокировано=<N городов>`.

**Задача 1.2 is_owner ЦИАН.**
- Modify (при подтверждении дефекта): `parser_cian.py`, Test: `test_parser_cian.py`.
- Шаги: статичный прогон `parse` на `data/saratov_page1.html` → счётчик
  `author.category` (`userType`), сравнить с `CAT_MAP`; если все категории
  пустые/неверно извлекаются — править извлечение, тест на фикстуре.

**Commit:** `parser_yandex: guard against Yandex captcha page` + cian fix.

## ФАЗА 2 — Тёплые клиенты

- Read: `bot.py` (owners-бот), `owner_check.py`, `access.py`,
  `soglasie_peredacha_rieltoru.md`, `soglasie_obrabotka.md`, README.
- Реализовать по TDD (тест `test_warm_leads.py`): константа кнопки/шага,
  запись согласия (город, объект, цена, срок, время МСК, дедупликация),
  сборка карточки лида (4 строки по образцу), доставка карточки (файл
  параллельно с потенциальной межботовой доставкой), отметка `handled`,
  защита от повторов.
- Сквозной прогон на тестовых данных (без ботов) — вывод карточки в чат.
- README: раздел «Тёплые клиенты».
- **Commit:** `bot: warm-lead flow (need-help call consent, lead card, dedup)`.

## ФАЗА 3 — Авито (systematic-debugging)

- Read: `probe_avito2.py`, `probe_avito3.py`, `data/avito_probe.html`.
- Один живой GET (город из `cities_to_collect()`) с логом: HTTP, размер,
  заголовки (`Content-Type`, `Server`, `Retry-After`), маркеры капчи/бана,
  счётчик объявлений в HTML.
- Исходы а/б/в: а) парсер `parser_avito.py` + тест на сохранённой странице +
  `PARSE_STEPS` в `orchestrator.py`; б) только факты + варианты без обхода
  защиты; в) JS-only → факты + варианты (мобильная версия/API).
- **Commit:** `avito: diagnostics + (parser | report-only)`.

## ФАЗА 4 — Уборка и полный прогон

- Проверить ссылки main-модулей/README на временные скрипты; ценные диагност-
  скрипты → `tools/`, остальное удалить (включая `found_regions*.txt`).
- README: запуск с токенами из окружения, статус парсеров, orchestrator-режимы,
  флоу тёплых клиентов.
- Прогон: `ORCH_PARSE_TIMEOUT=3600 python orchestrator.py all`; результаты и
  финальный `project_report.txt` (актуальный, без устаревших пунктов).
- **Commit:** `chore: cleanup temp scripts, README refresh, report`.

## Финальное резюме

На каждый фаз: сделано/протестировано; статус Яндекс/ЦИАН/Авито; полный прогон;
project_report.txt; ручные остатки (GitHub Secrets, ротация токенов через
@BotFather).
