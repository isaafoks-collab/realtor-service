# Запуск на VPS (по-человечески)

Дальше всё выполняется на сервере (VPS). Инструкция написана так, чтобы её
можно было сделать копированием команд, не разбираясь в деталях.

## 1. Скопировать проект

```bash
git clone https://github.com/isaafoks-collab/realtor-service.git /opt/realtor-service
cd /opt/realtor-service
python3 -m pip install --no-cache-dir -r requirements.txt
```

## 2. Секреты

Скопировать шаблон и заполнить (значения не показывать никому):

```bash
mkdir -p /etc/realtor
cp /opt/realtor-service/deploy/env.example /etc/realtor/env
nano /etc/realtor/env   # заполнить BOT_TOKEN, REALTOR_CHAT_ID, GITHUB_REPO_TOKEN
chmod 600 /etc/realtor/env
```

## 3. Включить постоянную работу

```bash
cp /opt/realtor-service/deploy/realtor-runner.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now realtor-runner
```

Теперь программа сама стартует при загрузке сервера и сама
поднимается, если зависнет. Отчёт о работе в логах:

```bash
journalctl -u realtor-runner -f
```
