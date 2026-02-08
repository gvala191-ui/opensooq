@echo off
chcp 65001 >nul
echo ========================================
echo 🤖 Telegram Bot - Парсер
echo ========================================
echo.

REM Проверка установки aiogram
python -c "import aiogram" 2>nul
if errorlevel 1 (
    echo ⚠️  aiogram не установлен!
    echo 📦 Устанавливаю зависимости...
    echo.
    python -m pip install aiogram -q
    if errorlevel 1 (
        echo ❌ Ошибка установки!
        pause
        exit /b 1
    )
    echo ✅ Зависимости установлены!
    echo.
)

REM Проверка конфигурации
python -c "import config; assert config.BOT_TOKEN != 'YOUR_BOT_TOKEN_HERE', 'Настрой BOT_TOKEN в config.py'; assert config.ADMIN_ID != 0, 'Настрой ADMIN_ID в config.py'" 2>nul
if errorlevel 1 (
    echo ❌ ОШИБКА: Не настроен config.py
    echo.
    echo 📝 Нужно отредактировать config.py:
    echo    1. Получи токен у @BotFather
    echo    2. Узнай свой ID у @userinfobot
    echo    3. Заполни BOT_TOKEN и ADMIN_ID
    echo.
    pause
    exit /b 1
)

echo ✅ Конфигурация проверена
echo 🚀 Запускаю бота...
echo.
echo Нажми Ctrl+C для остановки
echo ========================================
echo.

python bot.py

if errorlevel 1 (
    echo.
    echo ❌ Бот завершился с ошибкой!
    pause
    exit /b 1
)

echo.
echo 👋 Бот остановлен
pause
