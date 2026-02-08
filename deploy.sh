#!/bin/bash

# 🚀 Скрипт автоматического деплоя на VPS

set -e

echo "=========================================="
echo "🚀 Деплой Parser Bot на VPS"
echo "=========================================="
echo ""

# Проверка переменных окружения
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ Ошибка: переменная BOT_TOKEN не установлена"
    echo "Выполни: export BOT_TOKEN='твой_токен'"
    exit 1
fi

if [ -z "$ADMIN_ID" ]; then
    echo "❌ Ошибка: переменная ADMIN_ID не установлена"
    echo "Выполни: export ADMIN_ID='твой_id'"
    exit 1
fi

echo "✅ Переменные окружения настроены"
echo ""

# Обновление системы
echo "📦 Обновление системы..."
sudo apt update && sudo apt upgrade -y

# Установка зависимостей
echo "📦 Установка Python и Git..."
sudo apt install -y python3 python3-pip git

# Установка Python зависимостей
echo "📦 Установка Python пакетов..."
pip3 install -r requirements.txt

# Установка Playwright
echo "🌐 Установка Playwright и браузеров..."
playwright install chromium
playwright install-deps chromium

echo ""
echo "✅ Зависимости установлены!"
echo ""

# Создание systemd сервиса
echo "⚙️ Настройка systemd сервиса..."
sudo tee /etc/systemd/system/parser-bot.service > /dev/null <<EOF
[Unit]
Description=Parser Telegram Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment="BOT_TOKEN=$BOT_TOKEN"
Environment="ADMIN_ID=$ADMIN_ID"
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Перезагрузка systemd
echo "🔄 Перезагрузка systemd..."
sudo systemctl daemon-reload

# Включение автозапуска
echo "🔧 Включение автозапуска..."
sudo systemctl enable parser-bot

# Запуск бота
echo "🚀 Запуск бота..."
sudo systemctl start parser-bot

echo ""
echo "=========================================="
echo "✅ Деплой завершен успешно!"
echo "=========================================="
echo ""
echo "📊 Проверка статуса:"
echo "   sudo systemctl status parser-bot"
echo ""
echo "📋 Просмотр логов:"
echo "   sudo journalctl -u parser-bot -f"
echo ""
echo "🔄 Перезапуск:"
echo "   sudo systemctl restart parser-bot"
echo ""
echo "🛑 Остановка:"
echo "   sudo systemctl stop parser-bot"
echo ""
echo "=========================================="
echo "🎉 Бот работает 24/7!"
echo "=========================================="

# Показать статус
sleep 2
sudo systemctl status parser-bot
