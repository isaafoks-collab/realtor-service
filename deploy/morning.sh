#!/usr/bin/env bash
# Утренний прогон realtor на VPS (unit realtor-morning.service, таймер 07:00 МСК):
# parse → daily_digest → git push базы. Любое падение — сообщение человеку в Telegram.
set -u
cd /opt/realtor-service
PY=/opt/realtor-service/venv/bin/python3
export PYTHONUTF8=1 PYTHONUNBUFFERED=1

notify_fail() {
  # Одна попытка сообщить в Telegram; её собственная ошибка глотается.
  $PY -c "import os, daily_digest as d
d.BOT_TOKEN = os.getenv('BOT_TOKEN', '')
d.CHAT_ID = os.getenv('REALTOR_CHAT_ID', '')
d.send_fallback('[СБОЙ] утренний прогон на VPS: $1. Лог: journalctl -u realtor-morning')" || true
}

$PY orchestrator.py parse
rc=$?
if [ "$rc" -ne 0 ]; then
  notify_fail "parse rc=$rc"
  exit "$rc"
fi

$PY daily_digest.py
rc_digest=$?
if [ "$rc_digest" -ne 0 ]; then
  exit "$rc_digest"   # digest сам сообщил человеку
fi

$PY -c "from runner import git_push_db; git_push_db('/opt/realtor-service', 0, None)" || true
echo "morning: прогон завершён"
