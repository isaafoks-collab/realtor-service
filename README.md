# Прямо — подборка собственников для риэлторов

## Требования
Python 3.11+, зависимости: `pip install -r requirements.txt`
(pyTelegramBotAPI, requests, beautifulsoup4, lxml, PyYAML).

## Быстрый старт
1. Токены — только из переменных окружения:
   `setx BOT_TOKEN "..."`, `setx BOT_TOKEN_OWNERS "..."` (или высокий
   локальный файл `токены.txt`, который в git не попадает — его тихо
   читают start*.bat).
2. Оркестратор: `python orchestrator.py <режим>` — режимы:
   `setup` (requirements), `test` (unittest), `parse` (полный сбор:
   parser_cian → parser_yandex → json_to_db → owner_check),
   `report` (project_report.txt), `all` (setup+test+parse+report).
3. Боты:
   - realtor: `start_realtor.bat` (BOT_ROLE=realtor)
   - owners: `start_owners.bat` (BOT_ROLE=owners)

## Статус парсеров
- ЦИАН (`parser_cian.py`): работает — API-мегаполисы (пагинация и
  фильтр `is_by_homeowner` живые, 28 офферов на страницу) + HTML-сбор
  по остальным городам; собственники находятся.
- Яндекс (`parser_yandex.py`): работает с Волны 2 — curl_cffi с
  TLS-отпечатком Chrome и `sort=DATE_DESC`; капча встречается флейпом
  (~1 запрос из 6) и снимается повтором со свежей сессией и backoff.
  Упорная капча отмечается `[БЛОК]` и пишется в сводку, данные не пишутся.
- Авито: IP-блокировка (429 и 439 «Доступ ограничен» на
  `/web/1/js/items`, Server QRATOR; и через Playwright то же).
  Легального обхода нет — парсер не пишется; варианты: официальный
  Авито API для pro-партнёров, медленный «честный» пул residential-IP,
  либо совсем исключить Авито и опираться на ЦИАН/Яндекс.

## Тёплые клиенты (флоу)
- В owners-боте (`BOT_ROLE=owners`) в меню кнопка
  «🛠 Нужна помощь риэлтору»: собственник проходит визард
  (город → комнат → площадь → этаж → цена → срок).
- Заявка в SQLite `warm_leads.db` (env `WARM_LEADS_DB`); дубли блокируются:
  активный необработанный лид у пользователя один.
- Карточка лида (объект, цена, срок, время нажатия по МСК) — в лог
  `data/warm_leads_log.txt` (env `WARM_LEADS_LOG`) и, если задан
  `REALTOR_CHAT_ID`, отправляется сообщением в чат риэлтора.
- В realtor-боте `/лиды`: список новых заявок и кнопки
  «✅ Обработать №N» — отметка «обработан»; после закрытия заявки
  собственник может создать новую.

## Правила безопасности
- Токены только в переменных окружения, в репозиторий не попадают
  (`.gitignore` покрывает `токены.txt`).
- Токены в GitHub Actions — через Secrets (`BOT_TOKEN`,
  `BOT_TOKEN_OWNERS`); не печатать их в логи.
- Репозиторий Private.
