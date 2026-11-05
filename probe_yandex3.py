# -*- coding: utf-8 -*-
"""Разведка Яндекса 3: вытаскиваем настоящие ссылки из ответа сайта."""
import re, requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
s = requests.Session()
s.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
r = s.get("https://realty.yandex.ru/moskva/kupit/kvartiru/", timeout=20)
print("статус=%d, байт=%d" % (r.status_code, len(r.content)))
hrefs = re.findall(r'href="([^"]+)"', r.text)
cand = [h for h in hrefs if re.search(r"\d{6,}", h)]
for h in list(dict.fromkeys(cand))[:15]:
    print("ссылка:", h)
canon = re.search(r'<link rel="canonical" href="([^"]+)"', r.text)
print("canonical:", canon.group(1) if canon else "нет")
with open("data/yandex_404.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("страница сохранена: data/yandex_404.html")
