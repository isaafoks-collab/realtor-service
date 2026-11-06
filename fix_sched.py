# -*- coding: utf-8 -*-
"""Патч scheduler.py: чтение вывода в кодировке консоли без падений."""
src = open("scheduler.py", encoding="utf-8").read()
old = '''        r = subprocess.run([sys.executable, script], timeout=1800,
                           capture_output=True, text=True, encoding="utf-8")'''
new = '''        r = subprocess.run([sys.executable, script], timeout=1800,
                           capture_output=True, text=True, errors="replace")'''
if old in src:
    open("scheduler.py", "w", encoding="utf-8").write(src.replace(old, new))
    print("[FIX] кодировка вывода починена")
else:
    print("[ОШИБКА] блок не найден")
