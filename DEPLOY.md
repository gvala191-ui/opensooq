# ☁️ Деплой бота на сервер - Независимая работа 24/7

## 🎯 Зачем это нужно?

✅ Бот работает **24/7** без твоего участия  
✅ Не зависит от **твоего ПК и интернета**  
✅ Можно **запускать/останавливать** из любой точки мира через Telegram  
✅ Все запросы идут **напрямую с сервера**  

---

## 🆓 Вариант 1: Render.com (БЕСПЛАТНО)

**Плюсы:** Полностью бесплатно, простая настройка  
**Минусы:** Засыпает после 15 мин неактивности (но легко обходится)

### Шаг 1: Подготовка проекта

1. Создай файл `requirements.txt`:
```bash
aiogram>=3.15.0
bs4>=0.0.2
curl-cffi>=0.14.0
playwright>=1.58.0
```

2. Создай файл `render.yaml` (для автодеплоя):
```yaml
services:
  - type: web
    name: parser-bot
    runtime: python
    buildCommand: pip install -r requirements.txt && playwright install chromium
    startCommand: python bot.py
    envVars:
      - key: BOT_TOKEN
        sync: false
      - key: ADMIN_ID
        sync: false
```

### Шаг 2: Регистрация на Render

1. Иди на [render.com](https://render.com)
2. Зарегистрируйся через GitHub
3. Подключи свой репозиторий (или создай новый)

### Шаг 3: Создание сервиса

1. Нажми **New +** → **Web Service**
2. Выбери свой репозиторий
3. Настрой:
   - **Name:** parser-bot
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt && playwright install chromium`
   - **Start Command:** `python bot.py`
4. Добавь **Environment Variables:**
   - `BOT_TOKEN` = твой токен
   - `ADMIN_ID` = твой ID

### Шаг 4: Деплой

Нажми **Create Web Service** - и готово! Бот развернется автоматически.

---

## 🔥 Вариант 2: VPS (Самый мощный)

**Плюсы:** Полный контроль, всегда онлайн  
**Минусы:** От $3-5/месяц  

Рекомендую: [Hetzner](https://www.hetzner.com) (€3.79/мес), [DigitalOcean](https://www.digitalocean.com) ($4/мес)

### Быстрая установка на Ubuntu

```bash
# 1. Подключись к серверу
ssh root@твой_ip

# 2. Установи Python и зависимости
apt update
apt install python3 python3-pip git -y

# 3. Клонируй проект
git clone <твой_репозиторий>
cd opensoq

# 4. Установи зависимости
pip3 install -r requirements.txt
playwright install chromium
playwright install-deps

# 5. Настрой переменные окружения
export BOT_TOKEN="твой_токен"
export ADMIN_ID="твой_id"

# 6. Запусти бота в фоне
nohup python3 bot.py > bot.log 2>&1 &

# 7. Проверь логи
tail -f bot.log
```

### Автозапуск через systemd

Создай файл `/etc/systemd/system/parser-bot.service`:

```ini
[Unit]
Description=Parser Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/opensoq
Environment="BOT_TOKEN=8392139446:AAFKa4foNUq7vU1atOJtRgLERtW-Z0_o3Vc"
Environment="ADMIN_ID=8373464271"
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
systemctl daemon-reload
systemctl enable parser-bot
systemctl start parser-bot

# Проверка статуса
systemctl status parser-bot

# Просмотр логов
journalctl -u parser-bot -f
```

---

## 🐳 Вариант 3: Railway.app (БЕСПЛАТНО $5 кредитов)

1. Регистрация на [railway.app](https://railway.app)
2. **New Project** → **Deploy from GitHub**
3. Выбери репозиторий
4. Добавь переменные `BOT_TOKEN` и `ADMIN_ID`
5. Деплой!

---

## 🚀 Вариант 4: PythonAnywhere (БЕСПЛАТНО)

**Плюсы:** Полностью бесплатный тариф  
**Минусы:** Ограничения по CPU

1. Регистрация на [pythonanywhere.com](https://www.pythonanywhere.com)
2. Bash консоль → загрузи проект
3. Настрой `Always-On Task` для bot.py

---

## 🔄 Автоматический деплой через GitHub Actions

Создай `.github/workflows/deploy.yml`:

```yaml
name: Deploy Bot

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Deploy to VPS
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /root/opensoq
            git pull
            systemctl restart parser-bot
```

---

## 📊 Мониторинг и управление

### Проверка работы бота

```bash
# На VPS
systemctl status parser-bot
journalctl -u parser-bot -f

# Процессы
ps aux | grep bot.py

# Использование ресурсов
htop
```

### Остановка/Перезапуск

```bash
# Systemd
systemctl stop parser-bot
systemctl restart parser-bot

# Вручную
killall python3
nohup python3 bot.py > bot.log 2>&1 &
```

---

## 🛡️ Безопасность

### 1. Не храни токены в коде!

Используй переменные окружения или `.env` файл:

```bash
# На сервере
export BOT_TOKEN="..."
export ADMIN_ID="..."
```

### 2. Настрой firewall

```bash
# Разреши только SSH и HTTPS
ufw allow 22/tcp
ufw allow 443/tcp
ufw enable
```

### 3. Регулярные обновления

```bash
apt update && apt upgrade -y
```

---

## 💡 Советы по оптимизации

### 1. Webhook вместо Polling (быстрее)

Если у тебя есть домен и SSL:

```python
# В bot.py
async def main():
    await bot.delete_webhook()
    await bot.set_webhook(
        url=f"https://твой-домен.com/{config.BOT_TOKEN}",
        drop_pending_updates=True
    )
```

### 2. Использование Redis для хранения состояний

```python
from aiogram.fsm.storage.redis import RedisStorage

storage = RedisStorage.from_url("redis://localhost:6379")
dp = Dispatcher(storage=storage)
```

### 3. Логирование в файл

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
```

---

## 🎓 Рекомендуемый вариант для новичков

**Render.com** - самый простой старт:
1. ✅ Полностью бесплатно
2. ✅ Автоматический деплой из GitHub
3. ✅ Не нужно возиться с серверами
4. ✅ 750 часов в месяц бесплатно

Когда проект вырастет → переходи на VPS для полного контроля.

---

## 📞 Поддержка

После деплоя бот будет работать 24/7 и ты сможешь управлять им через Telegram откуда угодно! 🚀
