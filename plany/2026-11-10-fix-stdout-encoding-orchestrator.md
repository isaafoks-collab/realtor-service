# План: фикс UnicodeEncodeError в orchestrator.py (консоль Windows cp1251)

Дата: 2026-11-10. Круги рыбок: 1 (novichok 4 блок. — закрыты), 2 (3 блок.
— закрыты: тест стал репродуцировать дефект, потоки восстанавливаются),
3 (sverka 1 блок. — shutil; novichok 2 блок. — контракты), ЭКСТРЕННЫЙ
КРУГ (маленькая правка по кругу 3: TemporaryDirectory вместо mkdtemp+
shutil, факты-контракты добавлены). Автор: слон (автономно, этап B).

## Цель

Прогон `python orchestrator.py all` 19:37:38 сломался на шаге setup:
`UnicodeEncodeError: 'charmap' codec can't encode characters`. Точная
механика (подтверждена рыбками кругов 1–2): `setup_mode` запускает pip
БЕЗ `PYTHONUTF8/PYTHONIOENCODING`, декодирует вывод как UTF-8 с
`errors="replace"` (не-UTF-8 байты pip → U+FFFD), а затем печатает
`  | %s` в собственный stdout (cp1251-пайп/консоль) — U+FFFD в cp1251
не представим → исключение. Исключение ловится в `main()` (строки 64–68,
`except Exception`) → журнал «Ошибка в режиме 'setup'» и rc=1, а не
traceback (уточнено рыбкой-сверкой, круг 2). Цель: прогон не должен
падать из-за кодировки строк вывода orchestrator на любом шаге печати.

## Что меняется (точный список)

Файл: `orchestrator.py`, три точки.

**1. `main(argv, root=None)` (строки 52–69)** — в начале тела:

```python
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
```

Аргументация: `import sys` есть (стр. 13); AttributeError — StringIO
(нет reconfigure), ValueError — `io.UnsupportedOperation`/закрытый,
OSError — обрыв канала при flush. После правки U+FFFD заменяется
символом замены прямо при печати — краша нет.

**2. `setup_mode(root)` (строки 350–373, print хвоста — строка 368)** —
передавать ребёнку-env; точный вид у run_script (строка 127):
`env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
PYTHONUNBUFFERED="1")`; `os` импортирован (строка 10). Для pip-ребёнка
kwarg в `subprocess.run` (строка 357):
`env=dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")`.
Следствие: pip начнёт отдавать честный UTF-8, декодирование без U+FFFD,
нечитаемый хвост уходит (причина корня, замечание 3 рыбки-скептика
круга 2, взято в границы правки как лучший вариант).
Правка узкая: только env kwarg; timeout/errors/capture_output/text
уже есть (контракт для теста-фейка: используется только
`(proc.stdout or "")+(proc.stderr or "")` и `proc.returncode`).

**3. `test_orchestrator.py` — новый регрессионный тест (в существующем
   файле, отдельный класс, изолированный, без setUp/tearDown — чистка
   через tempfile.TemporaryDirectory, чтобы не нужен был shutil
   (импорта shutil в файле нет — факт сверки, круг 3); замечания
   новичка круга 3 закрыты фактами):

```python
class TestSetupUnicodeCrash(unittest.TestCase):
    def test_setup_mode_does_not_crash_on_unencodable_output(self):
        # contract: orchestrator.main(argv, root=None) -> int (return rc;
        # sys.exit только в __main__, строка 439). Реальный вызов в
        # setup_mode: subprocess.run([sys.executable, "-m", "pip",
        # "install", "-r", "requirements.txt"], cwd=root,
        # capture_output=True, text=True, encoding="utf-8",
        # errors="replace", timeout=SETUP_TIMEOUT, env=<см. п.2>)
        # -> CompletedProcess; читается только
        # (proc.stdout or "")+(proc.stderr or "") и proc.returncode.
        fake = subprocess.CompletedProcess(args=[], returncode=0)
        fake.stdout = "\ufffd " * 5   # U+FFFD не кодируется в cp1251
        fake.stderr = ""
        real_run = orchestrator.subprocess.run
        old_out, old_err = sys.stdout, sys.stderr
        buf = io.TextIOWrapper(io.BytesIO(), encoding="cp1251", errors="strict")
        buf_err = io.TextIOWrapper(io.BytesIO(), encoding="cp1251", errors="strict")
        try:
            orchestrator.subprocess.run = lambda *a, **k: fake
            sys.stdout = buf
            sys.stderr = buf_err
            with tempfile.TemporaryDirectory() as tmpdir:
                rc = orchestrator.main(["setup"], root=tmpdir)
            self.assertEqual(rc, 0)
        finally:
            orchestrator.subprocess.run = real_run
            sys.stdout, sys.stderr = old_out, old_err
            buf.close(); buf_err.close()
```

- Подмена/подмены ставятся ВНУТРИ try (восстановление в finally —
  исключение до finally не унесёт подмену; замечание 3 скептика круга 3).
- Требуется в test_orchestrator.py: `import subprocess` (отсутствует —
  факт сверки), io/os/sys/tempfile — уже есть (io стр. 3, tempfile
  стр. 6 — факт сверки).
- root=tmpdir: `ensure_requirements` в tmpdir создаст requirements.txt
  (tmp — допустимо), `check_environment` печатает в (подменённый) stdout.
- До правки: rc==1 с логом «Ошибка в режиме 'setup'»; после: rc==0
  (когда-то проверено эмуляцией рыбки-сверки круга 3: 1→0).
- Тест не проверяет п.2 (env) — покрыто ручным критерием 2 (замечание
  3 скептика круга 3, зафиксировано).

### Факты, закрывающие вопросы рыбки-новичка экстренного круга
(эмпирически подтверждены рыбкой-сверкой в живой симуляции на реальных
файлах, круг 3 и экстренный круг):
- `main(argv, root=None)` ожидает argv БЕЗ имени скрипта (элементы —
  имена режимов из MODES); вызов вида
  `orchestrator.main(["setup"], root=tmpdir)` корректен.
- `main` возвращает int rc, не sys.exit (sys.exit только в
  `__main__`, строка 439); успех — rc==0.
- В чистом tmpdir путь setup_mode гарантированно доходит до
  subprocess.run/print: ensure_requirements создаёт requirements.txt
  в root, ранних return нет (кроме отсутствия файла — это обработано
  созданием); симуляция сверкой показала ровно заявленную ошибку
  `UnicodeEncodeError: 'charmap' ... '\ufffd'` до фикса и rc=0 после.
- setup_mode ссылается на `subprocess.run` через модуль
  (`orchestrator.subprocess.run`) — патч лямбдой валиден.
- test_orchestrator.py уже импортирует orchestrator и unittest (строки
  8–10, факт сверки).

## Правила и крайние значения

- `sys.stdout`/`sys.stderr` None (pythonw) → AttributeError пойман,
  поведение прежнее.
- `sys.stdout is sys.stderr` → двойной reconfigure безвреден.
- Консоль уже UTF-8 (Linux/VPS) → безвредна, поведение прежнее.
- cp1251-консоль: вывод станет UTF-8 (mojibake осознан и принят; краш
  хуже mojibake). Факт: никто в проекте не парсит вывод orchestrator — start*.bat запускают, runner.py не вызывает.
- Наблюдаемый признак дефекта (уточнение круга 2): не traceback, а
  лог-строка `Ошибка в режиме 'setup': UnicodeEncodeError...` и rc=1
  (исключение ловится в `main`, строки 64–68).
- Факт: `log()` печатает в stdout (строки 48–49), файлового лога у
  orchestrator нет; `write_report` пишет файл явно UTF-8 (342–346).

## Критерии приёмки

1. После правки юнит-тест из п.3 зелёный, `python -m unittest discover
   -s . -p "test_*.py"` rc==0 (старые тесты не сломаны — установка
   подмен в finally).
2. `python orchestrator.py setup` (реальный pip): пройдена печать
   хвоста без `Ошибка в режиме 'setup'`/UnicodeEncodeError в логе
   (rc может быть != 0 из-за сети — НЕ задерживается; критерий —
   отсутствие краша).
3. `python orchestrator.py all` — полный прогон без краша на печати
   (продолжение ядра этапа B; отдельные задачи прогонов отслеживаются
   отдельно от этой правки).

## Риски

- pytest capsys: подменённый stdout без reconfigure → AttributeError
  пойман; тесты не ломаются.
- `errors="replace"` становится настройкой процесса постоянной —
  точка контроля записана в журнал решений (замечание 5 скептика,
  круг 2); фикс-наблюдение в журнале решений.
- Thread-safety: run_parse_steps вызывает run_script (same process) —
  все печати оттуда перенаправляются на перенастроенный stdout — ок;
  мутаций внутренних dict не делаем.

## Что НЕ меняется

- run_script, collect_test_results, report_mode, файлы отчётов (уже
  UTF-8); парсеры, боты, база, мост, .ps1, другие тесты.
