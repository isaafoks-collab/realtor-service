#!/usr/bin/env bash
# Настройка VPS (вызывается из deploy-vps.yml). Идемпотентна:
# безопасно запускать многократно — доводит сервер до рабочего состояния.
set -euo pipefail
cd /opt/realtor-service

# 1) Секреты приходят файлом /tmp/realtor.env (передаёт deploy-vps.yml).
#    Значения никогда не печатаются.
sudo mkdir -p /etc/realtor
sudo mv /tmp/realtor.env /etc/realtor/env
sudo chmod 600 /etc/realtor/env

# 2) Изолированное окружение и зависимости.
sudo apt-get update -qq || true
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv || true
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt

# 2б) Git: runner (root) коммитит базу из каталога деплой-юзера
# — без safe.directory git падает «dubious ownership».
sudo git config --global --add safe.directory /opt/realtor-service || true

# 3) Схема БД (идемпотентная миграция Волны 3).
./venv/bin/python db_schema.py

# 4) Постоянная работа: сервис стартует сам и сам поднимается после сбоя
#    (Автоперезапуск настроен в unit-файле).
sudo cp deploy/realtor-runner.service /etc/systemd/system/realtor-runner.service
sudo systemctl daemon-reload
sudo systemctl enable --now realtor-runner

sleep 10
sudo systemctl is-active realtor-runner
echo "--- последние строки работы (без секретов) ---"
sudo journalctl -u realtor-runner -n 40 --no-pager || true
