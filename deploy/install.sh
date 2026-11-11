#!/usr/bin/env bash
# ONE-TOUCH установка realtor-service на VPS (Ubuntu, root).
# Человек заполняет /tmp/realtor.env по deploy/env.template и запускает:
#   sudo bash deploy/install.sh
# Скрипт сам: окружение, клон (по токену из env, если репо нет), venv, схему,
# systemd unit + timer (07:00 МСК), первый прогон, отчёт в консоль.
set -euo pipefail

REPO_DIR=/opt/realtor-service
ENV_SRC=/tmp/realtor.env
ENV_DST=/etc/realtor/env

[ -f "$ENV_SRC" ] || { echo "нет $ENV_SRC — заполни deploy/env.template и положи в /tmp/realtor.env"; exit 1; }
source <(grep -E '^[A-Z_]+=' "$ENV_SRC")
: "${GITHUB_REPO_TOKEN:?в env нет GITHUB_REPO_TOKEN}"

# 1) Пакеты
apt-get update -qq || true
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv git python3 || true

# 2) Репозиторий (клон по токену, если нет)
if [ ! -d "$REPO_DIR/.git" ]; then
  git clone --depth 1 "https://x-access-token:${GITHUB_REPO_TOKEN}@github.com/isaafoks-collab/realtor-service.git" "$REPO_DIR"
fi
cd "$REPO_DIR"
git config --global --add safe.directory "$REPO_DIR" || true

# 3) venv + зависимости
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt

# 4) Секреты: /tmp/realtor.env → /etc/realtor/env (600), /tmp копия удаляется
mkdir -p /etc/realtor
install -m 600 "$ENV_SRC" "$ENV_DST"
shred -u "$ENV_SRC" 2>/dev/null || rm -f "$ENV_SRC"

# 5) Схема БД
./venv/bin/python db_schema.py

# 6) systemd: unit + timer
cp deploy/realtor-morning.service /etc/systemd/system/
cp deploy/realtor-morning.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now realtor-morning.timer

# 7) Первый прогон сейчас (утро не ждать)
systemctl start realtor-morning.service || true

echo "=== Статус таймера ==="
systemctl list-timers realtor-morning.timer --no-pager || true
echo "=== Последний лог прогона ==="
journalctl -u realtor-morning -n 40 --no-pager || true
echo "Готово. Утренний прогон — каждый день в 07:00 МСК (Persistent — нагонит пропущенное)."
