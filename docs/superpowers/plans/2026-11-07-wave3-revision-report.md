# Ревизионный отчёт (Часть 0, форма 0.4) — 07.11.2026

## 1. Карта проекта (файл → назначение → зависимости)

| Файл | Назначение | Зависимости |
|---|---|---|
| parser_cian.py | Сбор ЦИАН: API-мегаполисы (2 прохода, is_by_homeowner) + HTML-сбор по городам; пишет data/listings.json | httpclient, cities |
| parser_yandex.py | Сбор Яндекса по городам, fresh-session + sort=DATE_DESC + ретрай капчи; добавляет y_* записи в тот же JSON | httpclient, cities |
| json_to_db.py | Конвертер JSON → listings.db (схема listings: 16 колонок, keys: url PK) | geo |
| owner_check.py | Анти-фильтр агентов (COUNT по автору, лексика) → agent_risk | data/listings.json, listings.db |
| geo.py | Справочники городов/регионов + normalize() города из строки/адреса | — |
| cities.py | Список городов сбора (Саратовская + Московская области) | geo? нет |
| check_cities.py | Разовая диагностика городов из regions.yaml (live-проверки cian.ru/cat.php) | httpclient, regions.yaml |
| httpclient.py | curl_cffi-сессия с Chrome-TLS + CA-обход (data/ca.pem), pause() ±30%, fetch_with_backoff(403/429/439) | curl_cffi |
| notify.py | Тротлер Telegram (1/с чат, 20/мин группа, 30/с глобально) + tenacity-рetreaт | telebot (динамически), tenacity |
| bot.py | Боты realtor/owners: подборка, доступ по коду, тёплые заявки | access, geo, warm_leads, notify, SQLite listings.db |
| access.py | Вечный доступ (access.db granted, лог) | SQLite |
| warm_leads.py | Тёплые клиенты: leads-таблица, карточка, дубли, доставка | SQLite |
| db_backup.py | WAL-safe бэкап + restore-проверка (verify: integrity + last row) | tenacity (опц.) |
| orchestrator.py | Режимы setup/test/parse/report/all; PARSE_STEPS | все шаги |
| scheduler.py | Старый локальный 6h-цикл (ЦИАН, Яндекс, конвертер) | — |
| normalize_db.py | Разовая миграция (region) — уже применена | geo |
| start*.bat + hide_*.vbs | Локальные запуски ботов и планировщика (Windows) | — |
| .github/workflows/daily-parse.yml | Суточный Actions-прогон (05:00 UTC), коммит listings.db | Secrets BOT_TOKEN, BOT_TOKEN_OWNERS |
| setup.ps1 | Скрипт настройки токенов (окружение → токены.txt → скрытый ввод; синхронизация gh secret) | gh (опц.) |
| regions.yaml | Города + Cian region_id + тарифы | check_cites |
| data/ (gitignored) | listings.json (20 МБ), fixtures HTML, ca.pem, listings_backup.sqlite | — |
| oferta/politika/soglasie | Юридические документы 152-ФЗ | — |

Поток данных: parsers → data/listings.json → json_to_db → listings.db → bot (подборка), owner_check → agent_risk.

## 2. Удалено / исправлено / улучшено

Исправлено до ревизии (в рамках прошлой задачи): test_token_env путь к workflow (.github/workflows); шаблон тестов warm_leads со сдвигом полуночи.

Удалено:
- listings_backup.db (устаревшая в корне копия БД, актуальная — data/listings_backup.sqlite_new после нового бэкапа);
- project_report.txt и scheduler.log из git (генерируемые артефакты, локально остаются) — добавлены в .gitignore, вместе с access_log.txt и access.db (личные user_id не для репозитория).

Исправлено/улучшено:
- json_to_db.py: убран отладочный print «cian raw ключи» из каждого ежедневного прогона;
- orchestrator.py: PARSE_STEPS — check_cities.py исключён из ежедневного контура (он делал live-сетевые проверки при каждом прогоне); зато owner_check.py добавлен в контур (его отсутствие означало, что agent_risk не обновлялся после последнего ручного прогона);
- bot.py: удалён дублирующий импорт REGION_CITIES;
- README: статус Яндекса обновлён (работает с Волны 2), у Авито добавлен 439, состав parse-контура обновлён;
- БД: миграции прошлых волн сверены (region/floors_total/source добавляются idempolarmente; owner_status/price_history появится в Волне 3 — конфликтов нет). journal_mode=delete — для волны 3 (VPS, многопроцессность) включу WAL при миграции.

## 3. Проблемы прошлых волн, которые НЕ трогаю

- Жёсткая привязка парсеров к «Саратовская + Московская области», хотя зона — Москва и МО: города уедут в конфиг персонализации (E5) в Волне 3, сейчас не трогаю, чтобы не ломать накопленные данные по Саратову.
- listings.db коммитится в репозиторий из Actions (схема «БД — артефакт версионирования»); на VPS ист распояв несоответствие (Действия коммитят БД, а runner локально её же меняет) — рассинхрон возможен; решение — перенос расписания на VPS (A1) и сохранение БД только на VPS + бэкапы; перенюс без согласования.
- access.db с личными user_id лежал в git (ранее «было»); вынесен из git только сейчас — уже перечислено выше; существующие коммиты git содержат копию (историческая утечка: часть данных о выдаче доступа уже в история — предложить владельцу фильтр (`git filter-repo`) НЕ делаю сам).

## 4. Риски для Волны 3

- Р1. VPS-доступы (секреты) ещё не выданы владельцем: A1-перенос фактически не стартует без ssh; код можно готовить локально (runner-цикл, systemd-файлы, EnvironmentFile).
- Р2. pytest в F1 не установлен (в окружении проблемы кэша pip — ставить с --no-cache-dir); тестовый стек сейчас unittest, 77 тестов; добавляющие фичи пишутся в unittest до явного включения pytest.
- Р3. WhatsApp/VK-каналы и Telethon (B3) потребуют personal API-ключи Telegram — это секреты, договорённость с владельцем обязательна.
- Р4. Ночная очередь (A5) и каналы (D1) потребуют отдельной таблицы событий и конфига channels — их нет сегодня; миграции бэкапить (F2).
- Р5. ЦИАН околочасовая пауза (pause 14/21 с) при учащённом опросе Одинцово (2–5 мин) может вызывать рост мягких 402-блокировок; замерить на Волна 2 тест-прогоне и далее на VPS.
- Р6. ЕГРН/выписки — снято владельцем: не реализовывать (см. промт).
