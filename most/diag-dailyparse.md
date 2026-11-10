# Диагностика форс-прогона daily-parse (run 42747049021)

- Запущен workflow_dispatch: 2026-11-10 06:04:53 местного (03:04 UTC)
- Результат: **failure**; job «parse» (id 129601550061) 03:04:54 – 03:04:57 UTC
- Лог `gh run view --log`: «log not found: 129601550061» — шаги не стартовали,
  логов физически нет (step-список пуст). Секреты тут ни при чём: код job
  не выполнился ни на шаге.

## Аннотации чек-рана (дословно)

1. failure:
"The job was not started because recent account payments have failed or
your spending limit needs to be increased. Please check the 'Billing &
plans' section in your settings"

2. notice (не влияет):
"The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19,
2026. For more information, see [runner-images issue 14748](
https://github.com/actions/runner-images/issues/14748)"

## Вывод

Джоба не запускается из-за состояния биллинга аккаунта GitHub
(неоплаченный платёж или достигнут лимит расходов). Согласуется с вчерашним
быстропадением — failure за 5-10 секунд (run 42569644137 от
2026-11-09 05:51 UTC): джоба тоже не стартовала, а не падала на секретах.

Ссылки:
- run: https://github.com/isaafoks-collab/realtor-service/actions/runs/42747049021
- job: https://github.com/isaafoks-collab/realtor-service/actions/runs/42747049021/job/129601550061

Деньги/биллинг трогать на себя не беру (жёсткий стоп + протокол «Деньги»):
нужно действие человека в браузере → Settings → Billing and plans.
