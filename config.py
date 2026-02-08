# Конфигурация Telegram бота
import os

# ===== НАСТРОЙКИ БОТА =====
# Получи токен у @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "8392139446:AAFKa4foNUq7vU1atOJtRgLERtW-Z0_o3Vc")

# ID админа (твой Telegram ID), получи у @userinfobot
ADMIN_ID = int(os.getenv("ADMIN_ID", "8373464271"))

# ===== НАСТРОЙКИ ПАРСЕРА =====
# URL для парсинга (можешь менять через команду /seturl)
DEFAULT_URL = "https://example.com/search"

# Количество страниц для парсинга (можешь менять через /setpages)
DEFAULT_PAGES = 3

# Количество отправок на пользователя (можешь менять через /setsends)
DEFAULT_SENDS = 1

# Файл с фото для отправки
IMAGE_FILE = "pasta1.txt"

# Минимальное количество отзывов
MIN_REVIEWS = 0

# ===== ПРОКСИ (опционально) =====
# Формат: "host:port" или None
PROXY_HOST_PORT = None  # Например: "123.45.67.89:8080"

# ===== ФАЙЛЫ =====
COOKIES_FILE = "cookies.txt"
BLACKLIST_FILE = "blacklist.txt"
RESULTS_FILE = "results.txt"
