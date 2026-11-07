# План: волна 2 — схемы Miraines (Яндекс-спасение, Авито)

**Фокус:** проверка живости эндпоинтов ДО реализации; реализация только там,
где доказан живой ответ. Поля — только публичные (цена, комнаты, площадь,
этаж, город, время публикации). Телефоны/имена — никогда.

## Задача 2.1 — پروба живости (до кода)
- Probe A (Яндекс): GET realty.yandex.ru/<город>/kupit/kvartira/?sort=DATE_DESC
  через httpclient (chrome TLS). Фиксировать: HTTP, `X-Yandex-Captcha`,
  наличие `window.INITIAL_STATE`, число `offerId`, размер.
- Probe B (Авито): GET https://www.avito.ru/web/1/js/items с рабочим
  набором параметров (locationId=Москва 637640, categoryId из README,
  s=104, updateListOnly=true). Фиксировать HTTP, JSON/HTML, блок-маркеры.
- Вердикты фиксируются в отчёте: жив/капча/параметр устарел.

## Задача 2.2 — приёмы Miraines в httpclient (куда бы ни встраивали)
- `pause(base, jitter=0.3)`: ±30% на паузы (замена равномерных sleep).
- `fetch_retry(session, url, method, ... )`: exponential backoff на
  403/429/439 (+сетевые ошибки), инъекционные часы/sleep для тестов.
- Тесты: jitter в границах, backoff по кодам, тьфу培训班: чисто.

## Задача 2.3 — реализация (только по живым протоколам)
- Яндекс жив (probe OK) → спасение parser_yandex: уже на curl_cffi;
  добавить `sort=DATE_DESC` к URL, джиттер/бэкф офф из 2.2; данные через
  INITIAL_STATE; «[БЛОК]» остаётся.
- Авито жив → parser_avito.py (поля: id, цена, комнаты, площадь, этаж,
  город, время публикации; is_owner по маркеру, если есть в JSON);
  тест на сохранённой фикстуре из probe-ответа; PARSE_STEPS в
  orchestrator.
- Не жив → только отчёт об результатах с фактами (пункты — как в Phase 3).

## Коммит
`wave2: miraines endpoints — [заполнить по фактам]`
