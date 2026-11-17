# -*- coding: utf-8 -*-
"""Установка скиллов из кураторских репозиториев.

Пайплайн (README-BIBLIOTEKA.md): клон -> карантин -> аудит -> установка.
Детерминированный, без LLM. Запуск: python tools/skills-install.py [--dry]
"""
import os
import re
import shutil
import stat
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, ".opencode", "skills")
KARANTIN = os.path.join(SKILLS, "karantin")
REPOS_DIR = os.path.join(KARANTIN, "_repos")
REPORT = os.path.join(ROOT, "tools", "skills-install-report.md")

REPOS = [
    ("anthropics-skills", "https://github.com/anthropics/skills.git"),
    ("apify-skills", "https://github.com/apify/awesome-skills.git"),
    ("kdense-scientific", "https://github.com/K-Dense-AI/claude-scientific-skills.git"),
]

# жёсткие паттерны: скилл не устанавливается, остаётся в карантине
HARD = [
    (r"curl[^|]{0,80}\|\s*(sudo\s+)?(ba)?sh", "curl|sh — скачивание и запуск кода"),
    (r"wget[^|]{0,80}\|\s*(sudo\s+)?(ba)?sh", "wget|sh — скачивание и запуск кода"),
    (r"Invoke-Expression|\biex\b", "Invoke-Expression/iex"),
    (r"shell\s*=\s*True", "subprocess shell=True"),
    (r"start-process\s+.*-verb\s+runas", "runas/права админа"),
    (r"(?i)мастер\s+приказывает", "инъекция команд мастера"),
    (r"(?i)прочитай\s+запрещ", "инъекция правил"),
    (r"Add-MpPreference|Set-MpPreference", "манипуляция защитником Windows"),
    (r"Remove-Item\s+-Recurse\s+-Force\s+[A-Za-z]:\\\\", "удаление диска"),
    (r"(?i)rm\s+-rf\s+/($|\s)", "rm -rf /"),
]
# мягкие паттерны: только отметка в отчёте
SOFT = [
    (r"eval\(", "eval()"),
    (r"exec\(", "exec()"),
    (r"http://", "незашифрованный URL"),
    (r"(?i)api[_-]?key|token|secret", "упоминание ключей"),
    (r"b64|base64", "base64"),
]
TEXT_EXT = {".md", ".py", ".js", ".ts", ".ps1", ".sh", ".json", ".yaml", ".yml",
            ".txt", ".toml", ".cfg", ".ini", ".cmd", ".bat"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv"}


def sh(args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def rmtree_persistent(path):
    def onerr(func, p, exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    shutil.rmtree(path, onerror=onerr)
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def scan_skill(folder):
    """Возврат: (жёсткие_причины, мягкие_причины, проверено_файлов)."""
    hard, soft, nfiles = [], [], 0
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() not in TEXT_EXT:
                continue
            p = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(p) > 400_000:
                    continue
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            nfiles += 1
            for pat, why in HARD:
                if re.search(pat, text):
                    hard.append(f"{os.path.relpath(p, folder)}: {why}")
            for pat, why in SOFT:
                if re.search(pat, text) and why not in soft:
                    soft.append(why)
    return hard, soft, nfiles


def has_skill_md(folder):
    for fn in ("SKILL.md", "skill.md"):
        if os.path.isfile(os.path.join(folder, fn)):
            return fn
    return None


def main():
    dry = "--dry" in sys.argv
    os.makedirs(KARANTIN, exist_ok=True)
    os.makedirs(REPOS_DIR, exist_ok=True)

    existing = set()
    for name in os.listdir(SKILLS):
        if os.path.isdir(os.path.join(SKILLS, name)) and has_skill_md(os.path.join(SKILLS, name)):
            existing.add(name.lower())
    lines = ["# Отчёт установки скиллов", ""]

    installed, quarantined = [], []
    for tag, url in REPOS:
        dst = os.path.join(REPOS_DIR, tag)
        if os.path.isdir(dst):
            rmtree_persistent(dst)
        r = sh(["git", "clone", "--depth", "1", url, dst])
        if r.returncode != 0:
            lines.append(f"## {tag}\n- КЛОН НЕ УДАЛСЯ: {r.stderr.strip()[:300]}\n")
            continue
        lines.append(f"## {tag} ({url})\n")
        for dirpath, dirnames, filenames in os.walk(dst):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            if not has_skill_md(dirpath):
                continue
            name = os.path.basename(dirpath).strip().lower().replace(" ", "-")
            name = re.sub(r"[^a-z0-9._-]", "", name)[:60]
            if not name:
                continue
            if name in existing:
                lines.append(f"- SKIP (имя занято): {name}")
                continue
            hard, soft, nfiles = scan_skill(dirpath)
            target = os.path.join(SKILLS, name)
            if hard:
                q = os.path.join(KARANTIN, name)
                if os.path.isdir(q):
                    rmtree_persistent(q)
                shutil.copytree(dirpath, q)
                quarantined.append(name)
                lines.append(f"- КАРАНТИН: {name} — {hard[0]}")
                continue
            if dry:
                lines.append(f"- DRY: {name} (файлов {nfiles}, мягкие: {', '.join(soft) or 'нет'})")
                existing.add(name)
                continue
            if os.path.isdir(target):
                rmtree_persistent(target)
            shutil.copytree(dirpath, target)
            existing.add(name)
            installed.append(name)
            lines.append(f"- УСТАНОВЛЕН: {name} (файлов {nfiles}, мягкие: {', '.join(soft) or 'нет'})")

    lines.append("")
    lines.append(f"## Итог")
    lines.append(f"- установлено: {len(installed)}")
    lines.append(f"- карантин (не прошли аудит): {len(quarantined)}")
    if installed:
        lines.append("- имена: " + ", ".join(installed))
    if quarantined:
        lines.append("- в карантине: " + ", ".join(quarantined))
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"установлено: {len(installed)}; карантин: {len(quarantined)}; отчёт: tools/skills-install-report.md")


if __name__ == "__main__":
    main()
