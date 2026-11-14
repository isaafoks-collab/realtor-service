# Карта окружения ноутбука (поддерживается актуальной слоном)

ОБНОВЛЕНО: 2026-11-14

## Железо и ОС
- ОС: Windows 11 (build 26200), пользователь Андрей
- CPU/RAM: 16 ГБ RAM (10+ ГБ обычно свободно), графика Intel UHD iGPU (без дискретной памяти)
- Диск C: ~237 ГБ, свободно ~137 ГБ
- Сон: тайм-аут сна 0 минут (AC и батарея) — ноутбук не засыпает сам; гибернация доступна, но не запускается по таймеру

## Инструменты разработки
- Node.js v26.13.0, npm 11.20.0 (C:\Program Files\nodejs)
- Python 3.14 (C:\Users\Андрей\AppData\Local\Programs\Python\Python314) + Python312 (Program Files)
- Git, GitHub CLI (gh), Ollama 0.40.16
- PowerShell 5.1; bash/rg отдельно не установлены (ripgrep нет — использовать Select-String/наш grep-инструмент)
- Docker — НЕ установлен (Strix и полигоны в Docker требуют установки Docker Desktop — отдельный шаг)

## Установленные программы (крупное)
Adobe (Acrobat), AmneziaVPN/AmneziaWG, MetaTrader 5, Microsoft Office, OpenOffice, VS Code, Opera, Firefox, OneDrive, WinRAR, 360, Yandex (браузер/музыка)

## Наши службы и шлюзы (эшелоны каскада)
| Что | Как запущено | Порт | Проверка |
|---|---|---|---|
| OmniRoute v3.8.53 (эшелон 2a) | npm global `omniroute serve --headless`, cmd-процесс с автоперезапуском через стража | 20128 (только 127.0.0.1) | /healthz |
| freellmapi v0.2.1 (эшелон 2b) | node server/dist/index.js из C:\Users\Андрей\Documents\agent-tools\freellmapi | 3001 | /v1/models с единым ключом |
| Ollama qwen2.5-coder:3b (эшелон 3) | приложение Ollama (Programs\Ollama) | 11434 | /v1/chat/completions |
| claude-mem v15.18.3 (память) | воркер claude-mem, автостарт при установке; страж поднимает через `npx claude-mem start` | 37792 (не 37777!) | /health |
- supermemory снят (supermemory.json удалён из ~\.config\opencode) — два движка памяти держать нельзя
- claude-mem: настройка провайдера саммари ждёт первого захода мастера в веб-GUI: http://127.0.0.1:37792/?setup=1; до этого статус «degraded (Claude CLI setup required)» — это не поломка
- Логи OmniRoute: ~\.omniroute\logs\stdout.log / stderr.log; конфиг ~\.omniroute\.env (REQUIRE_API_KEY=false, OMNIROUTE_SERVER_HOST=127.0.0.1)
- freellmapi: единый ключ в БД server\data\freeapi.db (таблица settings, unified_api_key); ключ прописан в конфиге OpenCode
- Конфиг OpenCode: ~\.config\opencode\opencode.jsonc (permissions allow: edit/bash/webfetch; провайдеры freellmapi/omniroute/ollama)

## Планировщик задач (не системные)
- strazh-realtor: most\strazh.ps1 (realtor-service)
- strazh-trading: C:\Users\Андрей\Documents\trading-agent\most\strazh.ps1
- StrazhMosta: most\strazh.ps1 (скрыто, раз в минуту)
- Прочие: обновления Adobe/OneDrive/Opera, «Скрытие реальных данных» (hide_owners.vbs — рабочий механизм проекта)
- Задач для клона-стража freellmapi/omniroute пока НЕТ — добавит страж (раздел 13 правок strazh.ps1)

## Службы (значимые)
AmneziaVPN-service (VPN), ClickToRunSvc (Office), OneDrive, стандартный набор Windows

## Ограничения ноутбука
- 16 ГБ RAM: модель Ollama держим 3b (1.9 ГБ); 7b можно, но с распетом по CPU — медленно
- Docker нет: Strix/полигоны — после установки Docker Desktop (жёсткий стоп не требуется, установка бесплатная)
