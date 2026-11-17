# -*- coding: utf-8 -*-
# Сбор каталога скиллов-кандидатов из открытых источников (без LLM).
# Запуск: python tools/skills-harvest.py
# Результат: .opencode/skills/kandidaty.md
import json
import re
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".opencode" / "skills" / "kandidaty.md"
UA = {"User-Agent": "skills-harvester/1.0 (agent army library build)"}
TIMEOUT = 15
unavailable = []


def get(url: str):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001 - любая ошибка сети = пометка, не падение
        unavailable.append(f"{url} — {type(e).__name__}: {e}")
        return None


def fetch_json(url: str):
    raw = get(url)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        unavailable.append(f"{url} — не JSON ({e})")
        return None


candidates = {}  # ключ (имя в нижнем регистре) -> (имя, источник, примечание)


def add(name: str, source: str, note: str):
    name = name.strip().strip("-* ").strip()
    if not name or len(name) > 80:
        return
    key = name.lower()
    if key not in candidates:
        candidates[key] = (name, source, note.strip()[:100])


# 1) Официальный репозиторий anthropics/skills — всё дерево за один запрос
tree = fetch_json("https://api.github.com/repos/anthropics/skills/git/trees/main?recursive=1")
if tree and isinstance(tree.get("tree"), list):
    for item in tree["tree"]:
        path = item.get("path", "")
        if path.endswith("SKILL.md"):
            folder = path.rsplit("/SKILL.md", 1)[0]
            name = folder.rsplit("/", 1)[-1]
            add(name, "github.com/anthropics/skills", f"путь: {folder}")
else:
    unavailable.append("anthropics/skills tree — дерево не получено")

time.sleep(0.5)

# 2) Коллекции awesome-* на GitHub
search = fetch_json("https://api.github.com/search/repositories?q=awesome+claude+skills&per_page=20")
repos = []
if search and isinstance(search.get("items"), list):
    repos = [it["full_name"] for it in search["items"] if it.get("full_name")]
else:
    unavailable.append("github search awesome-claude-skills — не получил список")

md_link = re.compile(r"\[([^\]\[]{1,80})\]\((https?://[^\)\s]+)\)")
for repo in repos[:20]:  # экономим rate limit
    for branch in ("HEAD",):
        raw = get(f"https://raw.githubusercontent.com/{repo}/{branch}/README.md")
        time.sleep(0.5)
        if raw:
            for label, url in md_link.findall(raw)[:200]:
                low = url.lower()
                if any(skip in low for skip in (".png", ".jpg", ".svg", ".gif", "badge", "license", "contributing")):
                    continue
                add(label, repo, url)
            break

# 3) skills.sh — попытка
sh = get("https://skills.sh")
if sh:
    for m in re.findall(r'href="/([A-Za-z0-9_\-\.]+)/([A-Za-z0-9_\-\.]+)"', sh)[:300]:
        add(m[1], "skills.sh", f"{m[0]}/{m[1]}")

# 4) Дополнительный поиск коллекций по агентским скиллам
search2 = fetch_json("https://api.github.com/search/repositories?q=agent+skills+collection&per_page=20")
if search2 and isinstance(search2.get("items"), list):
    for it in search2["items"][:20]:
        add(it.get("name", ""), f"github.com/{it['full_name']}", it.get("description", ""))

# Запись результата
lines = []
by_source = {}
for name, source, note in candidates.values():
    host = source.split("/")[0] if "/" in source else source
    by_source.setdefault(source, []).append((name, note))

lines.append("# Каталог кандидатов в библиотеку скиллов")
lines.append(f"Собран: {date.today().isoformat()} скриптом tools/skills-harvest.py. "
             f"Итого кандидатов: {len(candidates)} (без дубликатов)")
for source, items in sorted(by_source.items()):
    lines.append(f"\n## {source}")
    for name, note in sorted(items, key=lambda x: x[0].lower()):
        suffix = f" — {note}" if note else ""
        lines.append(f"- {name} — {source}{suffix}")
if unavailable:
    lines.append("\n## Недоступные источники")
    for u in unavailable:
        lines.append(f"- {u}")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"кандидатов собрано: {len(candidates)}")
print(f"файл: {OUT}")
if unavailable:
    print("недоступные источники:")
    for u in unavailable:
        print(f"  - {u}")
