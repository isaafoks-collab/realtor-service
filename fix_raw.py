# -*- coding: utf-8 -*-
"""Надёжный фикс raw: заменяем строку явно, с проверкой."""
src = open("parser_cian.py", encoding="utf-8").read()
old = '"raw": it.get("raw") or {}'
if old in src:
    open("parser_cian.py", "w", encoding="utf-8").write(src.replace(old, '"raw": it'))
    print("[FIX] строка заменена: raw теперь сохраняет объект целиком")
elif '"raw": it,' in src or '"raw": it}' in src:
    print("[INFO] уже исправлено")
else:
    print("[ОШИБКА] целевая строка не найдена — сообщу, пришлю файл целиком")
