# -*- coding: utf-8 -*-
"""HTTP-клиент парсеров: curl_cffi с TLS-отпечатком Chrome.

Обход curl(77) на Windows: curl_cffi не читает CA-бандл по не-ASCII пути
(профиль пользователя может быть кирилическим) — копируем cacert.pem
в стабильный ASCII-путь (data/) и задаём CurlOpt.CAINFO явно.
"""
import os
import shutil
import ssl

from curl_cffi import requests, CurlOpt


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
