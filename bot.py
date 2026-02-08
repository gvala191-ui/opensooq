import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BotCommand
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import config
from main import (
    parse_main_page,
    parse_user_info,
    fetch_link,
    load_cookies,
    load_blacklist,
)
from sendwithbrowser import BrowserSession
from proxy_rotator import ProxyRotator
from proxy_manager import ProxyManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Глобальные переменные для управления парсером
parser_task = None
is_running = False
proxy_manager = ProxyManager()  # Менеджер прокси
current_settings = {
    "url": config.DEFAULT_URL,
    "pages": config.DEFAULT_PAGES,
    "sends": config.DEFAULT_SENDS,
    "image": config.IMAGE_FILE,
    "min_reviews": config.MIN_REVIEWS,
}


class Settings(StatesGroup):
    waiting_for_url = State()
    waiting_for_pages = State()
    waiting_for_sends = State()
    waiting_for_image = State()
    waiting_for_reviews = State()


# Инициализация бота
bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


def check_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом"""
    return user_id == config.ADMIN_ID


async def parse_and_send():
    """Основная функция парсинга и отправки"""
    global is_running
    try:
        logger.info("🚀 Начинаю парсинг...")
        
        # Загрузка прокси
        if config.USE_PROXY_ROTATION:
            proxy_manager.load_from_file(config.PROXY_FILE)
            if proxy_manager.proxy_list:
                await bot.send_message(
                    config.ADMIN_ID,
                    f"🔄 Загружено {len(proxy_manager.proxy_list)} прокси\n"
                    f"Тестирую их работоспособность..."
                )
                working = await proxy_manager.test_all_proxies()
                await bot.send_message(
                    config.ADMIN_ID,
                    f"✅ Рабочих прокси: {working}/{len(proxy_manager.proxy_list)}"
                )
        
        await bot.send_message(
            config.ADMIN_ID, "🚀 Парсинг запущен!\n\nСобираю данные..."
        )

        # Загрузка куки и blacklist
        cookies = load_cookies()
        blacklist = load_blacklist()

        # Настройка прокси
        proxy = None
        if config.PROXY_HOST_PORT and not config.USE_PROXY_ROTATION:
            proxy = {
                "http": f"http://{config.PROXY_HOST_PORT}",
                "https": f"http://{config.PROXY_HOST_PORT}",
            }
        elif proxy_manager.proxy_list:
            proxy = proxy_manager.get_next_proxy()

        # Парсинг главной страницы (передаем proxy_manager)
        # Нужно обновить parse_main_page чтобы принимала proxy_manager
        all_links = await parse_main_page(
            current_settings["url"], current_settings["pages"], proxy
        )
        await bot.send_message(
            config.ADMIN_ID, f"✅ Найдено {len(all_links)} объявлений"
        )

        # Фильтрация по blacklist
        filtered_links = [link for link in all_links if link not in blacklist]
        await bot.send_message(
            config.ADMIN_ID,
            f"📋 После фильтрации: {len(filtered_links)} объявлений",
        )

        # Сбор данных пользователей
        all_users_data = []
        await bot.send_message(config.ADMIN_ID, "📊 Собираю данные пользователей...")

        for idx, link in enumerate(filtered_links, 1):
            if not is_running:
                await bot.send_message(config.ADMIN_ID, "⏸️ Парсинг остановлен")
                return

            try:
                page_html = await fetch_link(link, proxy, cookies)
                if page_html:
                    user_info = parse_user_info(page_html)
                    if user_info["reviews_count"] >= current_settings["min_reviews"]:
                        all_users_data.append(
                            {
                                "id": link,
                                "link": link,
                                "name": user_info["name"] or "Неизвестно",
                                "reviews_count": user_info["reviews_count"],
                            }
                        )
                if idx % 10 == 0:
                    await bot.send_message(
                        config.ADMIN_ID,
                        f"⏳ Обработано {idx}/{len(filtered_links)}",
                    )
            except Exception as e:
                logger.error(f"Ошибка при обработке {link}: {e}")

        await bot.send_message(
            config.ADMIN_ID,
            f"✅ Собрано {len(all_users_data)} пользователей\n\nНачинаю получение чат-ссылок...",
        )

        # Получение чат-ссылок через браузер
        browser = None
        try:
            browser = await BrowserSession(proxy=proxy).start()
            updated_users = []

            for idx, user in enumerate(all_users_data, 1):
                if not is_running:
                    await bot.send_message(config.ADMIN_ID, "⏸️ Парсинг остановлен")
                    break

                try:
                    chat_link = await browser.get_chat_link(user["link"])
                    if chat_link:
                        user["chat_link"] = chat_link
                        updated_users.append(user)

                    if idx % 5 == 0:
                        await bot.send_message(
                            config.ADMIN_ID,
                            f"💬 Получено ссылок: {idx}/{len(all_users_data)}",
                        )
                except Exception as e:
                    logger.error(f"Ошибка получения чат-ссылки: {e}")

            # Сохранение результатов
            with open(config.RESULTS_FILE, "w", encoding="utf-8") as f:
                for user in updated_users:
                    f.write(
                        f"ID: {user['id']} | Имя: {user['name']} | Отзывов: {user['reviews_count']}\n"
                    )
                    f.write(f"Объявление: {user['link']}\n")
                    f.write(f"Чат: {user.get('chat_link', 'Не доступен')}\n")
                    f.write("-" * 80 + "\n")

            await bot.send_message(
                config.ADMIN_ID,
                f"💾 Результаты сохранены в {config.RESULTS_FILE}\n"
                f"Всего пользователей: {len(updated_users)}\n\n"
                f"Начинаю отправку фото...",
            )

            # Отправка фото
            sent_count = 0
            failed_count = 0

            for idx, user in enumerate(updated_users, 1):
                if not is_running:
                    await bot.send_message(config.ADMIN_ID, "⏸️ Отправка остановлена")
                    break

                try:
                    from main import send_messages_to_user_with_session

                    result = await send_messages_to_user_with_session(
                        browser, user, current_settings["image"], current_settings["sends"]
                    )
                    if result:
                        sent_count += 1
                    else:
                        failed_count += 1

                    if idx % 5 == 0:
                        await bot.send_message(
                            config.ADMIN_ID,
                            f"📤 Отправлено: {sent_count}, Ошибок: {failed_count} ({idx}/{len(updated_users)})",
                        )
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Ошибка отправки сообщения: {e}")

            # Финальный отчет
            await bot.send_message(
                config.ADMIN_ID,
                f"✅ Отправка завершена!\n\n"
                f"📊 Статистика:\n"
                f"✓ Успешно: {sent_count}\n"
                f"✗ Неудачно: {failed_count}\n"
                f"📝 Всего: {len(updated_users)}",
            )

        finally:
            if browser:
                await browser.close()

    except Exception as e:
        logger.error(f"Критическая ошибка в парсере: {e}")
        await bot.send_message(config.ADMIN_ID, f"❌ Ошибка: {e}")
    finally:
        is_running = False


# ===== КОМАНДЫ БОТА =====


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Приветствие"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этому боту")
        return

    await message.answer(
        "👋 Привет! Я бот для управления парсером.\n\n"
        "📋 Доступные команды:\n"
        "/run - Запустить парсинг и отправку\n"
        "/stop - Остановить работу\n"
        "/status - Текущий статус\n"
        "/settings - Показать настройки\n"
        "/seturl - Изменить URL\n"
        "/setpages - Изменить кол-во страниц\n"
        "/setsends - Изменить кол-во отправок\n"
        "/setimage - Изменить файл с фото\n"
        "/setreviews - Мин. количество отзывов\n"
        "/help - Помощь"
    )


@dp.message(Command("run"))
async def cmd_run(message: types.Message):
    """Запуск парсера"""
    global parser_task, is_running

    if not check_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    if is_running:
        await message.answer("⚠️ Парсер уже запущен!")
        return

    is_running = True
    parser_task = asyncio.create_task(parse_and_send())
    await message.answer("✅ Парсер запущен!")


@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    """Остановка парсера"""
    global is_running, parser_task

    if not check_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    if not is_running:
        await message.answer("⚠️ Парсер не запущен")
        return

    is_running = False
    if parser_task:
        parser_task.cancel()
    await message.answer("🛑 Парсер остановлен")


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Статус работы"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    status = "🟢 Запущен" if is_running else "🔴 Остановлен"
    await message.answer(
        f"📊 Статус: {status}\n\n"
        f"⚙️ Текущие настройки:\n"
        f"🔗 URL: {current_settings['url'][:50]}...\n"
        f"📄 Страниц: {current_settings['pages']}\n"
        f"📤 Отправок: {current_settings['sends']}\n"
        f"🖼️ Файл: {current_settings['image']}\n"
        f"⭐ Мин. отзывов: {current_settings['min_reviews']}"
    )


@dp.message(Command("settings"))
async def cmd_settings(message: types.Message):
    """Показать все настройки"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    await message.answer(
        f"⚙️ Настройки парсера:\n\n"
        f"🔗 URL: {current_settings['url']}\n"
        f"📄 Страниц: {current_settings['pages']}\n"
        f"📤 Отправок на юзера: {current_settings['sends']}\n"
        f"🖼️ Файл с фото: {current_settings['image']}\n"
        f"⭐ Мин. отзывов: {current_settings['min_reviews']}\n\n"
        f"Используйте команды /set* для изменения"
    )


@dp.message(Command("seturl"))
async def cmd_seturl(message: types.Message, state: FSMContext):
    """Установка URL"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    await message.answer("Отправьте новый URL для парсинга:")
    await state.set_state(Settings.waiting_for_url)


@dp.message(Settings.waiting_for_url)
async def process_url(message: types.Message, state: FSMContext):
    current_settings["url"] = message.text
    await message.answer(f"✅ URL обновлен: {message.text}")
    await state.clear()


@dp.message(Command("setpages"))
async def cmd_setpages(message: types.Message, state: FSMContext):
    """Установка количества страниц"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    await message.answer("Введите количество страниц для парсинга:")
    await state.set_state(Settings.waiting_for_pages)


@dp.message(Settings.waiting_for_pages)
async def process_pages(message: types.Message, state: FSMContext):
    try:
        pages = int(message.text)
        current_settings["pages"] = pages
        await message.answer(f"✅ Количество страниц обновлено: {pages}")
    except ValueError:
        await message.answer("❌ Введите число!")
    await state.clear()


@dp.message(Command("setsends"))
async def cmd_setsends(message: types.Message, state: FSMContext):
    """Установка количества отправок"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    await message.answer("Введите количество отправок на пользователя:")
    await state.set_state(Settings.waiting_for_sends)


@dp.message(Settings.waiting_for_sends)
async def process_sends(message: types.Message, state: FSMContext):
    try:
        sends = int(message.text)
        current_settings["sends"] = sends
        await message.answer(f"✅ Количество отправок обновлено: {sends}")
    except ValueError:
        await message.answer("❌ Введите число!")
    await state.clear()


@dp.message(Command("setimage"))
async def cmd_setimage(message: types.Message, state: FSMContext):
    """Установка файла с фото"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    await message.answer("Введите имя файла с фото (например: pasta1.txt):")
    await state.set_state(Settings.waiting_for_image)


@dp.message(Settings.waiting_for_image)
async def process_image(message: types.Message, state: FSMContext):
    current_settings["image"] = message.text
    await message.answer(f"✅ Файл с фото обновлен: {message.text}")
    await state.clear()


@dp.message(Command("setreviews"))
async def cmd_setreviews(message: types.Message, state: FSMContext):
    """Установка минимального количества отзывов"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    await message.answer("Введите минимальное количество отзывов:")
    await state.set_state(Settings.waiting_for_reviews)


@dp.message(Settings.waiting_for_reviews)
async def process_reviews(message: types.Message, state: FSMContext):
    try:
        reviews = int(message.text)
        current_settings["min_reviews"] = reviews
        await message.answer(f"✅ Минимальное количество отзывов обновлено: {reviews}")
    except ValueError:
        await message.answer("❌ Введите число!")
    await state.clear()


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Помощь"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    await message.answer(
        "📖 Инструкция по использованию:\n\n"
        "1️⃣ Настройте параметры командами /set*\n"
        "2️⃣ Запустите парсер - /run\n"
        "3️⃣ Следите за статусом - /status\n"
        "4️⃣ При необходимости остановите - /stop\n\n"
        "⚠️ Важно:\n"
        "- Убедитесь, что cookies.txt заполнен\n"
        "- Файл с фото должен существовать\n"
        "- Парсинг может занять много времени\n\n"
        "🔄 Прокси:\n"
        "- /proxies - Статистика прокси\n"
        "- /testproxies - Проверить все прокси"
    )


@dp.message(Command("proxies"))
async def cmd_proxies(message: types.Message):
    """Статистика прокси"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    if not proxy_manager.proxy_list:
        await message.answer(
            "⚠️ Прокси не настроены\n\n"
            "Добавьте прокси в файл proxies.txt\n"
            "Формат: host:port (по одному на строку)"
        )
        return

    stats = proxy_manager.get_stats()
    await message.answer(stats)


@dp.message(Command("testproxies"))
async def cmd_test_proxies(message: types.Message):
    """Тестирование всех прокси"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    if not proxy_manager.proxy_list:
        await message.answer("⚠️ Прокси не настроены")
        return

    await message.answer(f"🔍 Тестирую {len(proxy_manager.proxy_list)} прокси...")
    
    working_count = await proxy_manager.test_all_proxies()
    
    await message.answer(
        f"✅ Тестирование завершено!\n\n"
        f"Рабочих: {working_count}/{len(proxy_manager.proxy_list)}\n\n"
        f"Используйте /proxies для подробной статистики"
    )


async def set_commands():
    """Установка команд бота"""
    commands = [
        BotCommand(command="start", description="Начать работу"),
        BotCommand(command="run", description="Запустить парсинг"),
        BotCommand(command="stop", description="Остановить парсинг"),
        BotCommand(command="status", description="Показать статус"),
        BotCommand(command="settings", description="Показать настройки"),
        BotCommand(command="help", description="Помощь"),
    ]
    await bot.set_my_commands(commands)


async def main():
    """Запуск бота"""
    logger.info("🤖 Запуск бота...")
    
    # Проверка конфигурации
    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ BOT_TOKEN не настроен в config.py!")
        print("\n" + "="*50)
        print("❌ ОШИБКА: Токен бота не настроен!")
        print("="*50)
        print("\n📝 Инструкция:")
        print("1. Найди @BotFather в Telegram")
        print("2. Отправь /newbot и создай бота")
        print("3. Скопируй токен")
        print("4. Открой config.py и вставь токен в BOT_TOKEN")
        print("\nПример:")
        print('BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"')
        print("\n" + "="*50 + "\n")
        return
    
    if config.ADMIN_ID == 0:
        logger.error("❌ ADMIN_ID не настроен в config.py!")
        print("\n" + "="*50)
        print("❌ ОШИБКА: ADMIN_ID не настроен!")
        print("="*50)
        print("\n📝 Инструкция:")
        print("1. Найди @userinfobot в Telegram")
        print("2. Отправь /start")
        print("3. Скопируй свой ID")
        print("4. Открой config.py и вставь ID в ADMIN_ID")
        print("\nПример:")
        print('ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))')
        print("\n" + "="*50 + "\n")
        return
    
    try:
        await set_commands()
        logger.info("✅ Бот запущен! Жду команды в Telegram...")
        print("\n" + "="*50)
        print("✅ Бот успешно запущен!")
        print("="*50)
        print(f"📱 Найди своего бота в Telegram и напиши /start")
        print(f"🔑 Твой ID админа: {config.ADMIN_ID}")
        print("📋 Нажми Ctrl+C для остановки")
        print("="*50 + "\n")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        print(f"\n❌ Ошибка: {e}\n")
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
        print("\n👋 Бот остановлен\n")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        print(f"\n💥 Критическая ошибка: {e}\n")
        import traceback
        traceback.print_exc()
