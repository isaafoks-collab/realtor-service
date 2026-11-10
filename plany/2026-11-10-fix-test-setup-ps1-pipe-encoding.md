# План: зелёный test_setup_script (кодировка пайпа PowerShell 5.1)

Дата: 2026-11-10. Автор: слон (автономно, этап B).
План-компаньон к plany/2026-11-10-fix-stdout-encoding-orchestrator.md.

## Цель

`python -m unittest discover` даёт 4 фейла в test_setup_script.py.
БАЗА-ЛИНИЯ (проверено через git stash: те же 4 фейла без правок
orchestrator):
setup.ps1 вызывается как `powershell -File ...`, PowerShell 5.1 пишет
в пайп stdout консольной кодировкой (cp866 — видно mojibake
`"????: ???????"` = `(источник: окружение)`), тест декодирует с
encoding="utf-8" (test_setup_script.py, строка 20) → не совпадают:
- «BOT_TOKEN: заполнен (источник: окружение)»;
- «BOT_TOKEN: заполнен (источник: токены.txt)»;
- «источник: ручной ввод»;
- «не задан».
Цель: test_setup_script.py зелёный. setup.ps1 сам не меняется.

## Что меняется

Файл: `test_setup_script.py`, одна функция `run_setup(env, stdin_text,
token_file)` (строки 14–21).

Вместо `-File` — запуск через `-Command`, который ставит
Console.OutputEncoding в UTF-8 до вызова скрипта:

```python
def run_setup(env, stdin_text=None, token_file=None):
    cmd = ("[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
           "[Console]::InputEncoding = [System.Text.Encoding]::UTF8; "
           "& '%s' -SkipGitHub" % SCRIPT)
    if token_file:
        cmd += " -TokenFile '%s'" % token_file
    args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-Command", cmd]
    return subprocess.run(args, capture_output=True, input=stdin_text,
                          text=True, encoding="utf-8", errors="replace",
                          env=env, cwd=ROOT, timeout=120)
```

- Пути: SCRIPT — реальный путь с кириллицей
  (`C:\Users\Андрей\Documents\realtor-service\setup.ps1`). В PS
  одинарные кавычки `'...'` литеральные; в путях проекта одинарных
  кавычек нет — подстановка безопасна.
- `& '<путь>' -SkipGitHub [-TokenFile '<путь>']` — то же поведение,
  что -File: скрипт линейный с `param(...)` (факт: строки setup.ps1
  1–10 задают параметры/функции; именованные параметры вызова).
- Write-Host в пайп PS 5.1 кодируется OutputEncoding; после установки
  UTF-8 тестовый decode utf-8 совпадает.
- Скрипт setup.ps1 не трогается вообще.

## Крайние значения

- Входной текст теста ASCII (`444DDD:typedsecret\n`) — одинаков в любой
  кодировке; `InputEncoding=UTF8` дополнительно ставится (безвредно).
- Секретная гигиена: ASCII-подстроки `supersecretNNN`/`typedsecret`/
  `filesecret` — ищутся посимвольно, кодировка не влияет; существующий
  test_values_never_printed остаётся зелёным.
- PowerShell 5.1 — целевая среда (В Windows по умолчанию);
  `[System.Text.Encoding]::UTF8` доступен в 5.1.
- Пути с кириллицей в выводе-setup-скрипта тест не парсит — только
  русские фразы-фрагменты.

## Критерии приёмки

1. `python -m unittest test_setup_script -v` — 5 тестов OK.
2. `python -m unittest discover -s . -p "test_*.py"` — rc==0
   (вместе с новым тестом оркестратора; полный проект — все
   test_*.py). До правки — 4 фейла, после — ноль.
3. test_values_never_printed остаётся зелёным (гигиена секретов).

## Риски

- `-Command`: строка-командa одна; в PS 5.1 `-Command` доступен
  (это стандартный ключ); порядок: сначала OutputEncoding, потом
  InputEncoding, потом вызов скрипта — последовательные statements
  внутри одной -Command строки разделены `;` — работоспособно в
  PowerShell 5.1.
- Изоляция: правка только в тестовой обвязке тестов; прод-запуск
  setup.ps1 человеком не меняется.

## Что НЕ меняется

setup.ps1 (скрипт целиком), все прочие тесты, orchestrator.py (правки
плана-компаньона уже внесены и проверены), мост, .ps1 моста.
