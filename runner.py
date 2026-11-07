# -*- coding: utf-8 -*-
"""Runner скоростного контура (A1/A2/A4/A5) — бесконечный цикл для VPS.

Расписание (deploy/config.yaml, МСК):
- Одинцово: база 3 мин (диапазон 2–5), 07:00–23:00;
- Москва: 15 мин; прочие города МО: 17 мин;
- ночью (23:00–07:00): полный прогон всех городов раз в час;
- джиттер ±30 с на каждом интервале (город выходит на ход не ровно по часам).

Сбор: Яндекс (collect_cities) + ЦИАН (collect_city_html) → data/listings.json
→ json_to_db.py → конвертер заполняет detected_at/published_at (A4).
Новые частники попадают в notify_queue (db_schema): ночью копятся до утра
(A5), днём немедленную отправку включим в Части D.

Надёжность (H1-H3): ошибка одного города не роняет цикл, каждый выход
в сеть под таймаутами и повторами (сам parser_*), зависший запрос не
подвешивает цикл; БД пушится в git с pull --rebase перед push.
"""
import json
import os
import random
import sqlite3
import subprocess
import sys
import time as time_mod
from datetime import datetime, timedelta, timezone

import yaml

import db_schema
import metrics

ROOT = os.path.dirname(os.path.abspath(__file__))
MSK = timezone(timedelta(hours=3))
CONFIG_PATH = os.environ.get("REALTOR_CONFIG",
                             os.path.join(ROOT, "deploy", "config.yaml"))
DB_PATH = "listings.db"


def log(msg):
    print("[%s] %s" % (datetime.now(MSK).strftime("%d.%m %H:%M:%S"), msg),
          flush=True)


def load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def msk_now():
    return datetime.now(MSK)


def is_night(now):
    """Ночная тишина (A5): 23:00–07:00 уведомления копятся в очереди."""
    return now.hour >= 23 or now.hour < 7


def city_due(city, last_ts, now_ts, interval_minutes, jitter=30.0):
    """True, если до города дошёл ход: интервал ± джиттер; впервой раз — сразу."""
    if last_ts is None:
        return True
    target = interval_minutes * 60.0
    return (now_ts - last_ts) >= target + random.uniform(-jitter, jitter)


def pick_due(cities, last_runs, now_ts, interval_minutes, jitter=30.0):
    return [c for c in cities
            if city_due(c, last_runs.get(c), now_ts, interval_minutes, jitter)]


def cycle_plan(cfg, now, last_runs=None, jitter=30.0):
    """План цикла. Ночью — полный прогон (interval из cfg[night]),
    днём — каждая зона со своим интервалом и своими «на ход» городами."""
    last_runs = last_runs or {}
    hot_cfg = cfg["hot"]
    reg_cfg = cfg["regular"]
    moscow_cfg = cfg.get("moscow") or {"cities": [],
                                       "interval_minutes": reg_cfg["interval_minutes"]}
    now_ts = now.timestamp()
    if is_night(now):
        all_cities = list(dict.fromkeys(
            hot_cfg["cities"] + moscow_cfg["cities"] + reg_cfg["cities"]))
        return {"kind": "night", "all": all_cities,
                "interval": cfg["night"]["every_minutes"] * 60.0}
    return {
        "kind": "day",
        "hot": pick_due(hot_cfg["cities"], last_runs, now_ts,
                        hot_cfg["interval_minutes"], jitter),
        "regular": pick_due(reg_cfg["cities"], last_runs, now_ts,
                            reg_cfg["interval_minutes"], jitter),
        "moscow": pick_due(moscow_cfg["cities"], last_runs, now_ts,
                           moscow_cfg["interval_minutes"], jitter),
        "intervals": {"hot": hot_cfg["interval_minutes"] * 60.0,
                      "regular": reg_cfg["interval_minutes"] * 60.0,
                      "moscow": moscow_cfg["interval_minutes"] * 60.0},
    }


def run_convert(root):
    """Конвертер JSON → БД (заполняет detected_at/published_at у новых)."""
    proc = subprocess.run(
        [sys.executable, os.path.join(root, "json_to_db.py")], cwd=root,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=900, env=dict(os.environ, PYTHONUTF8="1"))
    ok = proc.returncode == 0
    if not ok:
        log("[ОШИБКА] json_to_db: код %s: %s" %
            (proc.returncode, ((proc.stderr or "") + (proc.stdout or ""))[-300:]))
    return ok


def category_of(rooms):
    try:
        n = int(str(rooms or ""))
    except (TypeError, ValueError):
        n = 0
    if n in (1, 2, 3):
        return "%s-комн" % n
    return "другое"


def queue_new_owners(db_path=DB_PATH, since_iso=None, period_kind="day"):
    """Новые частники за цикл → notify_queue (A5). Возвращает список."""
    conn = sqlite3.connect(db_path)
    try:
        db_schema.ensure(conn)
        rows = conn.execute(
            "SELECT url, city, rooms FROM listings "
            "WHERE is_owner=1 AND price IS NOT NULL AND detected_at >= ?",
            (since_iso,)).fetchall()
        now_iso = datetime.now(timezone.utc).isoformat()
        chat_id = os.getenv("REALTOR_CHAT_ID", "")
        for url, city, rooms in rows:
            db_schema.queue_notice(conn, url, category_of(rooms),
                                   chat_id, now_iso)
        if rows:
            log("[ОЧЕРЕДЬ] новых частников: %d (%s)" %
                (len(rows), "ночь — копим до утра" if period_kind == "night"
                 else "день — к отправке"))
    finally:
        conn.close()
    return rows


def git_push_db(root, interval_minutes=15, last_push=None):
    """Пушит listings.db в git не чаще interval; перед push — pull --rebase.
    Токен — из env (deploy/env.example). Отвалившийся push не роняет цикл."""
    now_ts = time_mod.time()
    if last_push is not None and now_ts - last_push < interval_minutes * 60:
        return last_push
    token = os.getenv("GITHUB_REPO_TOKEN")
    if not token:
        return last_push or now_ts
    remote = "https://x-access-token:%s@github.com/isaafoks-collab/realtor-service.git" % token
    env = dict(os.environ, PYTHONUTF8="1", GIT_TERMINAL_PROMPT="0")

    def git(*args):
        proc = subprocess.run(["git", *args], cwd=root, env=env,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
        if proc.returncode != 0:
            log("[GIT] %s: не удалось (%s)" %
                (args[0], ((proc.stdout or "") + (proc.stderr or ""))[-200:]))
        return proc.returncode == 0

    try:
        if not git("add", DB_PATH):
            return now_ts
        dirty_proc = subprocess.run(["git", "diff", "--cached", "--quiet"],
                                    cwd=root, env=env, capture_output=True)
        if dirty_proc.returncode == 0:
            return now_ts
        if git("-c", "user.name=realtor-runner",
               "-c", "user.email=runner@realtor.service",
               "commit", "-m", "runner: база объявлений"):
            git("pull", "--rebase", remote, "main")
            git("push", remote, "main")
            log("[GIT] база обновлена в git")
    except Exception as e:
        log("[GIT] сбой: %s: %s" % (type(e).__name__, e))
    return now_ts


def collect(cities, data, root, seen):
    """Сбор по городам: Яндекс + ЦИАН-HTML. Ошибка города не роняет цикл."""
    import parser_cian
    import parser_yandex
    from httpclient import session as make_session

    # Яндекс: уже сам проходит города с ретраями и паузами
    parser_yandex.collect_cities(cities, data)

    sess = make_session()
    sess.headers.update({"User-Agent": parser_cian.UA,
                         "Accept-Language": "ru-RU,ru;q=0.9"})
    owner_map = {str(lid): "" for lid in data["owners"]}
    listings = data["listings"]
    owners_dict = data.setdefault("_owners_io", owner_map)
    for city in cities:
        try:
            parser_cian.collect_city_html(sess, city, listings, owners_dict, seen)
            parser_yandex.pause(6)
        except Exception as e:
            log("[ОШИБКА] ЦИАН %s: %s: %s" % (city, type(e).__name__, e))
    data.pop("_owners_io", None)
    data["owners"] = list(owners_dict)


def run_cycle(cfg, root):
    """Один проход: сбор по расписанию → JSON → конвертация → очередь."""
    data_path = os.path.join(root, "data", "listings.json")
    data = {"listings": {}, "owners": []}
    if os.path.exists(data_path):
        raw = json.load(open(data_path, encoding="utf-8"))
        if "listings" in raw:
            data = {"listings": raw["listings"], "owners": raw.get("owners", [])}
    seen = set(data["listings"])
    start_iso = datetime.now(timezone.utc).isoformat()

    plan = cycle_plan(cfg, msk_now(), runner_get_last(root))
    if plan["kind"] == "night":
        cities = plan["all"]
        if not cities:
            return False
        log("[НОЧЬ] полный прогон: %d городов" % len(cities))
    else:
        cities = plan["hot"] + plan["regular"] + plan["moscow"]
        if not cities:
            return False
        log("[ДЕНЬ] на ход: %s" % ", ".join(cities))
        if "{hot}" in plan.get("intervals") or False:
            pass  # страховка от забытых хвостов — не должна появляться

    collect(cities, data, root, seen)
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    json.dump({"listings": data["listings"], "owners": data["owners"]},
              open(data_path, "w", encoding="utf-8"), ensure_ascii=False)
    if run_convert(root):
        queue_new_owners(DB_PATH, since_iso=start_iso, period_kind=plan["kind"])

    now_ts = datetime.now(timezone.utc).timestamp()
    new_last = dict(runner_get_last(root))
    for c in cities:
        new_last[c] = now_ts
    runner_set_last(root, new_last)
    return True


_STATE_CACHE = {}


def _state_path(root):
    return os.environ.get("REALTOR_RUNNER_STATE",
                          os.path.join(root, "data", "runner_state.json"))


def runner_get_last(root):
    path = _state_path(root)
    if path in _STATE_CACHE:
        return dict(_STATE_CACHE[path])
    if os.path.exists(path):
        try:
            _STATE_CACHE[path] = json.load(open(path, encoding="utf-8"))
        except Exception:
            _STATE_CACHE[path] = {}
    else:
        _STATE_CACHE[path] = {}
    return dict(_STATE_CACHE[path])


def runner_set_last(root, state):
    path = _state_path(root)
    _STATE_CACHE[path] = dict(state)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    json.dump(state, open(path, "w", encoding="utf-8"), ensure_ascii=False,
              indent=1)


def summary_metrics():
    try:
        conn = sqlite3.connect(DB_PATH)
        text = metrics.report_text(conn)
        conn.close()
        print(text)
    except Exception as e:
        log("[ОШИБКА] метрики: %s: %s" % (type(e).__name__, e))


def main():
    cfg = load_config()
    log("Runner стартует; конфиг: %s" % CONFIG_PATH)
    tick = int(cfg.get("tick_seconds", 30))
    push_every = int((cfg.get("push") or {}).get("every_minutes", 15))
    last_push = None
    while True:
        try:
            run_cycle(cfg, ROOT)
        except Exception as e:  # H2: любое падение — с контекстом в лог
            log("[ОШИБКА] цикл: %s: %s" % (type(e).__name__, e))
        last_push = git_push_db(ROOT, push_every, last_push)
        time_mod.sleep(tick)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "метрики":
        summary_metrics()
    else:
        main()
