# -*- coding: utf-8 -*-
"""HTTP-клиент парсеров: curl_cffi с TLS-отпечатком Chrome.

Обход curl(77) на Windows: curl_cffi не читает CA-бандл по не-ASCII пути
(профиль пользователя может быть кирилическим) — копируем cacert.pem
в стабильный ASCII-путь (data/) и задаём CurlOpt.CAINFO явно.

Приёмы Miraines/real-estate-parser (перенос схем, не код):
- pause(): пауза с джиттером ±30%;
- fetch_with_backoff(): exponential backoff на 403/429/439 и сетевые ошибки.
"""
import os
import random
import shutil
import ssl
import time

from curl_cffi import requests, CurlOpt

RETRY_STATUS = {403, 429, 439}


def _ca_path():
    ca = os.path.join("data", "ca.pem")
    if not os.path.exists(ca):
        try:
            source = certifi_where()
            if source:
                os.makedirs("data", exist_ok=True)
                shutil.copy(source, ca)
        except Exception:
            return None
    return ca


def certifi_where():
    try:
        import certifi
        return certifi.where()
    except ImportError:
        return ssl.get_default_verify_paths().cafile


def session(impersonate="chrome"):
    opts = {}
    ca = _ca_path()
    if ca:
        opts[CurlOpt.CAINFO] = ca.encode()
    try:
        return requests.Session(impersonate=impersonate, curl_options=opts or None)
    except Exception:
        return requests.Session(impersonate=impersonate)


def pause(base, jitter=0.3, sleep=time.sleep):
    """Пауза base секунд с джиттером ±jitter (по умолчанию ±30%)."""
    low, high = base * (1 - jitter), base * (1 + jitter)
    sleep(random.uniform(low, high))


def fetch_with_backoff(send, *args, retry_statuses=None,
                       attempts=3, fallback_sleep=2.0, sleep=time.sleep, **kwargs):
    """send(*args, **kwargs) — вызов session.get/post.
    Повторяет exponential (fallback_sleep 2/4/8...) на 403/429/439 и сетевых
    ошибках; возвращает последний ответ или бросает, если сеть так и не жила.
    """
    send_at = None
    statuses = retry_statuses or RETRY_STATUS
    for attempt in range(attempts):
        try:
            resp = send(*args, **kwargs)
            if getattr(resp, "status_code", 200) not in statuses:
                return resp
        except Exception as e:
            if attempt == attempts - 1:
                raise
            send_at = fallback_sleep * (2 ** attempt)
            sleep(send_at)
            continue
        if attempt < attempts - 1:
            sleep(fallback_sleep * (2 ** attempt))
    return resp
