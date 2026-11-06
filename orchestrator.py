# -*- coding: utf-8 -*-
"""orchestrator.py — единый оркестратор проекта realtor-service.

Режимы: setup, test, parse, report, all.
Запуск: python orchestrator.py <режим>
"""
import datetime
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
REPORT_FILE = "project_report.txt"

TEST_TIMEOUT = int(os.environ.get("ORCH_TEST_TIMEOUT", "900"))
SETUP_TIMEOUT = int(os.environ.get("ORCH_SETUP_TIMEOUT", "1800"))
PARSE_TIMEOUT = int(os.environ.get("ORCH_PARSE_TIMEOUT", "1800"))

MODES = ("setup", "test", "parse", "report", "all")

MIN_REQUIREMENTS = """pyTelegramBotAPI==4.14.0
requests==2.31.0
beautifulsoup4==4.12.3
lxml==5.1.0
PyYAML==6.0.1
"""

PARSE_STEPS = (
    ("check_cities.py", "проверка городов из regions.yaml"),
    ("parser_cian.py", "основной сбор объявлений ЦИАН (создаёт listings.db)"),
    ("parser_yandex.py", "сбор объявлений Яндекс.Недвижимости"),
    ("json_to_db.py", "загрузка data/listings.json в БД",
     "data/listings.json"),
)

SENSITIVE_NAME_RE = re.compile(r"(токен|token|secret|парол|password|api[_-]?key|ключ)", re.IGNORECASE)

TAIL_LINES = 30


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg))


def main(argv, root=None):
    root = root or ROOT
    if not argv or argv[0] not in MODES:
        print("orchestrator.py — оркестратор проекта realtor-service")
        print("Использование: python orchestrator.py <режим>")
        print("Доступные режимы:")
        for mode, desc in MODE_DESCRIPTIONS.items():
            print("  %-7s %s" % (mode, desc))
        if argv:
            print("Неизвестный режим: %s" % argv[0])
        return 1
    mode = argv[0]
    try:
        rc = MODE_HANDLERS[mode](root)
    except Exception as e:
        log("Ошибка в режиме '%s': %s: %s" % (mode, type(e).__name__, e))
        return 1
    return rc


MODE_DESCRIPTIONS = {
    "setup": " — установить зависимости и проверить окружение",
    "test": " — запустить все тесты проекта",
    "parse": " — выполнить основной разбор данных",
    "report": " — сводный отчёт в project_report.txt",
    "all": " — setup, затем test, parse, report",
}

MODE_HANDLERS = {}


def ensure_requirements(root):
    path = os.path.join(root, "requirements.txt")
    if os.path.exists(path):
        log("requirements.txt уже существует: %s" % path)
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(MIN_REQUIREMENTS)
    log("requirements.txt отсутствовал — создан минимальный файл")
    return True


def check_environment(root):
    log("Python: %s" % sys.version.split()[0])
    if sys.version_info < (3, 10):
        log("ПРЕДУПРЕЖДЕНИЕ: требуется Python 3.10+")
    for mod in ("telebot", "requests", "bs4", "lxml", "yaml"):
        if importlib.util.find_spec(mod) is not None:
            log("Модуль %s: OK" % mod)
        else:
            log("Модуль %s: НЕ установлен" % mod)


def run_script(name, root, timeout=PARSE_TIMEOUT, echo=True):
    path = os.path.join(root, name)
    step = {"name": name, "skipped": False, "ok": False, "returncode": None,
            "timed_out": False, "output": "", "duration": None, "reason": ""}
    if not os.path.exists(path):
        step["skipped"] = True
        step["reason"] = "файл не найден"
        log("%s: пропущен (%s)" % (name, step["reason"]))
        return step
    log("Запуск %s..." % name)
    start = time.monotonic()
    chunks = []
    timed_out = [False]

    def _kill():
        timed_out[0] = True
        try:
            proc.kill()
        except OSError:
            pass

    try:
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
                   PYTHONUNBUFFERED="1")
        proc = subprocess.Popen(
            [sys.executable, path], cwd=root, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1)
        timer = threading.Timer(timeout, _kill)
        timer.start()
        try:
            for line in proc.stdout:
                line = line.rstrip("\r\n")
                chunks.append(line)
                if echo:
                    print("    | %s" % line)
            proc.wait()
        finally:
            timer.cancel()
            proc.stdout.close()
    except Exception as e:
        log("%s: не удалось запустить: %s: %s" % (name, type(e).__name__, e))
        step["reason"] = "%s: %s" % (type(e).__name__, e)
        return step
    step["duration"] = round(time.monotonic() - start, 1)
    step["output"] = "\n".join(chunks)
    step["returncode"] = proc.returncode
    step["timed_out"] = timed_out[0]
    step["ok"] = proc.returncode == 0 and not timed_out[0]
    if timed_out[0]:
        log("%s: ПРЕРВАН по таймауту (%s сек)" % (name, step["duration"]))
    elif proc.returncode == 0:
        log("%s: OK (%s сек)" % (name, step["duration"]))
    else:
        log("%s: ОШИБКА, код возврата %s" % (name, proc.returncode))
    return step


def collect_test_results(root, timeout=TEST_TIMEOUT):
    has_pytest = importlib.util.find_spec("pytest") is not None
    if has_pytest:
        tool = "pytest"
        args = ["-m", "pytest", "--tb=short", "-q", "-p", "no:cacheprovider"]
    else:
        tool = "unittest"
        args = ["-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"]
    log("Запуск тестов (%s)..." % tool)
    start = time.monotonic()
    try:
        proc = subprocess.run([sys.executable] + args, cwd=root,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        log("Тесты: ПРЕРВАНЫ по таймауту %s сек" % timeout)
        return {"tool": tool, "ran": None, "passed": 0, "failed": 0, "errors": 0,
                "ok": False, "output": "timeout %s сек" % timeout}
    output = (proc.stdout or "") + (proc.stderr or "")
    res = _parse_test_summary(tool, output, proc.returncode)
    res["output"] = output
    log("Тесты: прошло %s, упало %s, ошибок %s (%s сек)" %
        (res["passed"], res["failed"], res["errors"], round(time.monotonic() - start, 1)))
    if not res["ok"]:
        log("ВНИМАНИЕ: тесты завершились неудачей (код %s)" % proc.returncode)
    return res


def _parse_test_summary(tool, output, returncode):
    if tool == "pytest":
        passed = _int_group(output, r"(\d+) passed")
        failed = _int_group(output, r"(\d+) failed")
        errors = _int_group(output, r"(\d+) errors?")
        return {"tool": tool, "ran": None, "passed": passed, "failed": failed,
                "errors": errors, "ok": returncode == 0}
    ran = _int_group(output, r"Ran (\d+) tests? in")
    failed = _int_group(output, r"failures=(\d+)")
    errors = _int_group(output, r"errors=(\d+)")
    if ran is None and returncode in (0, 1):
        ran, failed, errors = 0, 0, 0
    passed = max(0, ran - failed - errors)
    return {"tool": tool, "ran": ran, "passed": passed, "failed": failed,
            "errors": errors, "ok": returncode == 0 and (ran is None or ran > 0)}


def _int_group(text, pattern):
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0


def run_parse_steps(root, timeout=PARSE_TIMEOUT, echo=True):
    steps = []
    for entry in PARSE_STEPS:
        name, desc = entry[0], entry[1]
        required_file = entry[2] if len(entry) > 2 else None
        if required_file and not os.path.exists(os.path.join(root, *required_file.split("/"))):
            log("%s: пропущен (%s — %s)" % (name, desc, "нет " + required_file))
            steps.append({"name": name, "desc": desc, "skipped": True, "ok": False,
                          "returncode": None, "timed_out": False,
                          "output": "", "duration": None,
                          "reason": "нет " + required_file})
            continue
        log("%s — %s" % (name, desc))
        step = run_script(name, root, timeout=timeout, echo=echo)
        step["desc"] = desc
        steps.append(step)
    return steps


def find_issues(root, test_res, steps):
    issues = []
    if test_res:
        if test_res["ok"] and test_res["passed"] == test_res["failed"] == test_res["errors"] == 0:
            issues.append("Не найдено ни одного теста (тестовый запуск ничего не обнаружил)")
        for key in ("failed", "errors"):
            if test_res[key]:
                issues.append("Тесты (%s): %s %s" %
                              (test_res["tool"], test_res[key],
                               "падений" if key == "failed" else "ошибок"))
    for step in steps:
        if step["skipped"]:
            issues.append("%s пропущен: %s" % (step["name"], step["reason"]))
        elif step["timed_out"]:
            issues.append("%s прерван по таймауту" % step["name"])
        elif not step["ok"]:
            issues.append("%s завершился с ошибкой (код %s)" % (step["name"], step["returncode"]))
    if os.path.isdir(root):
        suspicious = sorted(n for n in os.listdir(root)
                            if os.path.isfile(os.path.join(root, n))
                            and SENSITIVE_NAME_RE.search(n))
        for name in suspicious:
            issues.append("В корне репозитория лежит файл '%s' — судя по имени, там могут быть "
                          "токены/секреты. README требует хранить токены только в переменных "
                          "окружения: уберите секреты и удалите файл из репозитория" % name)
    return issues


def build_report(root, test_res, steps, issues):
    lines = []
    total_failed = test_res["failed"] + test_res["errors"] if test_res else 0
    if test_res:
        status = "OK (%s прошло)" % test_res["passed"] if test_res["ok"] else \
            "ПРОВАЛ: %s падений/ошибок" % total_failed
    else:
        status = "не запускались"
    now = datetime.datetime.now()

    lines.append("СВОДНЫЙ ОТЧЁТ ПРОЕКТА realtor-service")
    lines.append("Сгенерирован orchestrator.py: %s" % now.strftime("%d.%m.%Y %H:%M:%S"))
    lines.append("Python: %s | ОС: %s" % (sys.version.split()[0], sys.platform))
    lines.append("")
    lines.append("=== СТРУКТУРА ФАЙЛОВ ===")
    lines += _file_structure_lines(root)
    lines.append("")
    lines.append("=== ТЕСТЫ ===")
    if test_res:
        lines.append("Инструмент: %s; статус: %s" % (test_res["tool"], status))
        lines.append("Прошло: %s | Падений: %s | Ошибок: %s" %
                     (test_res["passed"], test_res["failed"], test_res["errors"]))
        if not test_res["ok"]:
            lines.append("Хвост вывода тестов:")
            lines += _tail(test_res["output"])
    lines.append("")
    lines.append("=== РАЗБОР ДАННЫХ ===")
    if steps:
        for s in steps:
            st = "ПРОПУСК (%s)" % s["reason"] if s["skipped"] else \
                "ТАЙМАУТ" if s["timed_out"] else \
                "ПАДЕНИЕ (код %s)" % s["returncode"] if not s["ok"] else "OK"
            tail = " (%s сек)" % s.get("duration") if s.get("duration") is not None else ""
            lines.append("%s — %s: %s%s" % (s["name"], s.get("desc", ""), st, tail))
            if not s["ok"] and not s["skipped"]:
                lines.append("  Хвост вывода %s:" % s["name"])
                lines += _tail(s["output"], prefix="    ")
    else:
        lines.append("не выполнялся")
    lines.append("")
    lines.append("=== ВЫЯВЛЕННЫЕ ПРОБЛЕМЫ ===")
    if issues:
        for i, issue in enumerate(issues, 1):
            lines.append("%s. %s" % (i, issue))
    else:
        lines.append("не обнаружено")
    return "\n".join(lines) + "\n"


def _file_structure_lines(root):
    out = []
    py_files = 0
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if os.path.isdir(path) or name == REPORT_FILE:
            continue
        if name.endswith(".py"):
            py_files += 1
        out.append("  %-30s %8s" % (name, _human_size(os.path.getsize(path))))
    data_dir = os.path.join(root, "data")
    if os.path.isdir(data_dir):
        out.append("  data/")
        for name in sorted(os.listdir(data_dir)):
            path = os.path.join(data_dir, name)
            out.append("    %-28s %8s" % (name, _human_size(os.path.getsize(path))))
    out.append("Всего python-файлов в корне: %d" % py_files)
    return out


def _human_size(n):
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024:
            return "%.0f%s" % (n, unit) if unit == "Б" else "%.1f%s" % (n, unit)
        n /= 1024
    return "%.1fТБ" % n


def _tail(text, prefix="    "):
    lines = [l for l in text.splitlines() if l.strip()]
    return [prefix + l for l in lines[-TAIL_LINES:]]


def write_report(root, text):
    path = os.path.join(root, REPORT_FILE)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    log("Отчёт записан: %s" % path)
    return path


def setup_mode(root):
    log("Режим setup")
    ensure_requirements(root)
    check_environment(root)
    log("Установка зависимостей: python -m pip install -r requirements.txt")
    start = time.monotonic()
    try:
        proc = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                              cwd=root, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=SETUP_TIMEOUT)
    except subprocess.TimeoutExpired:
        log("pip install прерван по таймауту")
        return 1
    except Exception as e:
        log("pip install не удалось запустить: %s: %s" % (type(e).__name__, e))
        return 1
    tail = _tail((proc.stdout or "") + (proc.stderr or ""))
    for line in tail:
        print("  | %s" % line)
    if proc.returncode == 0:
        log("Зависимости установлены (%s сек)" % round(time.monotonic() - start, 1))
        return 0
    log("pip install завершился с кодом %s" % proc.returncode)
    return 1


def test_mode(root):
    log("Режим test")
    res = collect_test_results(root)
    return 0 if res["ok"] else 1


def parse_mode(root):
    log("Режим parse")
    steps = run_parse_steps(root, echo=True)
    failed = [s for s in steps if not s["skipped"] and not s["ok"]]
    if failed:
        log("Разбор данных завершён с ошибками: %s" % ", ".join(s["name"] for s in failed))
        return 1
    log("Разбор данных завершён")
    return 0


def report_mode(root, test_res=None, parse_steps=None):
    log("Режим report")
    test_res = test_res if test_res is not None else collect_test_results(root)
    steps = parse_steps if parse_steps is not None else run_parse_steps(root, echo=False)
    issues = find_issues(root, test_res, steps)
    text = build_report(root, test_res, steps, issues)
    write_report(root, text)
    if issues:
        print("Обнаружено проблем: %d (см. %s)" % (len(issues), REPORT_FILE))
    else:
        print("Проблем не обнаружено (см. %s)" % REPORT_FILE)
    return 0


def all_mode(root):
    log("Режим all: setup -> test -> parse -> report")
    rc = setup_mode(root)
    if rc != 0:
        log("Продолжаю, несмотря на сбой setup")
    test_res = collect_test_results(root)
    rc_test = 0 if test_res["ok"] else 1
    if rc_test != 0:
        log("Продолжаю, несмотря на провал тестов")
    log("Режим parse")
    steps = run_parse_steps(root, echo=True)
    rc_parse = 0
    failed = [s for s in steps if not s["skipped"] and not s["ok"]]
    if failed:
        log("Разбор данных завершён с ошибками: %s" % ", ".join(s["name"] for s in failed))
        rc_parse = 1
    else:
        log("Разбор данных завершён")
    report_mode(root, test_res=test_res, parse_steps=steps)
    return max(rc, rc_test, rc_parse)


MODE_HANDLERS.update({
    "setup": setup_mode,
    "test": test_mode,
    "parse": parse_mode,
    "report": report_mode,
    "all": all_mode,
})


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
