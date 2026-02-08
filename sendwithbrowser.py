import asyncio

global _playwright_checked
from playwright.async_api import async_playwright

"""Playwright sender.
Важно:
- В обычном запуске (python) можем авто-ставить зависимости/браузер.
- В собранном EXE (PyInstaller onefile) НЕЛЬЗЯ вызывать `sys.executable -m ...`:
    это запускает exe заново и выглядит как "софт перезапустился".
    Поэтому в EXE авто-установку отключаем и используем папку `browsers/` рядом с exe.
"""
import sys
import subprocess
import os
import json

# Определение путей для работы как в скрипте, так и в скомпилированном EXE
IS_FROZEN = bool(getattr(sys, "frozen", False))
if IS_FROZEN:
    BASE_DIR = os.path.dirname(sys.executable)
    MEIPASS = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    MEIPASS = BASE_DIR


def find_browsers_path():
    """Поиск папки с браузерами в зависимости от окружения"""
    candidates = [
        os.path.join(BASE_DIR, "browsers"),
        os.path.join(BASE_DIR, "browser"),
        os.path.join(os.getcwd(), "browsers"),
        os.path.join(os.getcwd(), "browser"),
    ]
    for path in candidates:
        if os.path.exists(path) and os.path.isdir(path):
            try:
                for item in os.listdir(path):
                    if "chromium" in item.lower():
                        print(f"[DEBUG] Найден браузер: {path}")
                        return path
            except:
                pass

    # Если папка найдена, но пуста, или не найдена вовсе
    for path in candidates:
        if os.path.exists(path) and os.path.isdir(path):
            return path

    return os.path.join(BASE_DIR, "browsers")


print(f"[DEBUG] IS_FROZEN: {IS_FROZEN}")
print(f"[DEBUG] BASE_DIR: {BASE_DIR}")



_playwright_checked = False


async def _find_playwright_bundled_node() -> str or None:
    """Поиск встроенного Node.js для работы Playwright в EXE"""
    try:
        if IS_FROZEN:
            meipass_candidates = [
                os.path.join(MEIPASS, "playwright", "driver", "node.exe"),
                os.path.join(MEIPASS, "playwright", "driver", "node"),
            ]
            for path in meipass_candidates:
                if os.path.exists(path):
                    return path

        import playwright

        pkg_dir = os.path.dirname(playwright.__file__)
        candidates = [
            os.path.join(pkg_dir, "driver", "node.exe"),
            os.path.join(pkg_dir, "driver", "node"),
            os.path.join(pkg_dir, "driver", "package", "node.exe"),
            os.path.join(pkg_dir, "driver", "package", "node"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
    except Exception:
        return None
    return None


async def _run_playwright_install_chromium(env: dict) -> None:
    """Запуск процесса установки браузера"""
    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode == 0:
        return
    else:
        bundled_node = _find_playwright_bundled_node()
        if bundled_node:
            env2 = env.copy()
            env2["PLAYWRIGHT_NODEJS_PATH"] = bundled_node
            proc2 = subprocess.run(cmd, env=env2, capture_output=True, text=True)
            if proc2.returncode == 0:
                return
            else:
                stderr = (proc2.stderr or proc.stderr or "").strip()
                stdout = (proc2.stdout or proc.stdout or "").strip()
                raise RuntimeError(
                    f"Playwright install failed.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
                )
        else:
            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            raise RuntimeError(
                f"Playwright install failed. Node not found.\nSTDERR:\n{stderr}"
            )


async def ensure_playwright():
    """Проверка наличия всех компонентов Playwright"""

    global _playwright_checked
 
    _playwright_checked = True


class BrowserSession:
    """Класс для управления постоянной сессией браузера"""

    def __init__(self, proxy: dict = None):
        self.proxy = proxy
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self, retries: int = 3):
        for attempt in range(1, retries + 1):
            try:
                print(f"[DEBUG] Запуск playwright (попытка {attempt})...")
                self.playwright = await async_playwright().start()

                chromium_exe = None
                if os.path.exists("browsers"):
                    for item in os.listdir("browsers"):
                        if "chromium" in item.lower():
                            chromium_dir = os.path.join("browsers", item)
                            for root, dirs, files in os.walk(chromium_dir):
                                for f in files:
                                    if f.lower() in ["chrome.exe", "chromium.exe"]:
                                        chromium_exe = os.path.join(root, f)
                                        break
                                if chromium_exe:
                                    break
                        if chromium_exe:
                            break

                browser_args = {
                    "headless": False,
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                    ],
                }
                if chromium_exe:
                    browser_args["executable_path"] = chromium_exe

                context_args = {
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                    "viewport": {"width": 1920, "height": 1080},
                }
                if self.proxy:
                    proxy_url = self.proxy.get("http") or self.proxy.get("https", "")
                    if proxy_url:
                        context_args["proxy"] = {"server": proxy_url}

                self.browser = await self.playwright.chromium.launch(**browser_args)
                self.context = await self.browser.new_context(**context_args)

                # Загрузка куки
                if os.path.exists("cookies.txt"):
                    try:
                        with open("cookies.txt", "r", encoding="utf-8") as f:
                            cookies_list = json.load(f)
                        pw_cookies = []
                        for c in cookies_list:
                            pc = {
                                "name": c["name"],
                                "value": c["value"],
                                "domain": c.get("domain", ".opensooq.com"),
                                "path": c.get("path", "/"),
                            }
                            if "expirationDate" in c:
                                pc["expires"] = c["expirationDate"]
                            if "secure" in c:
                                pc["secure"] = c["secure"]
                            pw_cookies.append(pc)

                        await self.context.add_cookies(pw_cookies)
                        print(f"✓ Cookies загружены ({len(pw_cookies)} шт.)")
                    except Exception as e:
                        print(f"⚠️ Ошибка cookies: {e}")

                self.page = await self.context.new_page()
                
                # Блокируем только тяжелые ресурсы (не CSS/JS!), чтобы чат работал
                await self.page.route("**/*", lambda route: (
                    route.abort() if route.request.resource_type in ["image", "media"]
                    else route.continue_()
                ))
                
                await self.page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )
                return self
            except Exception as e:
                print(f"❌ Ошибка старта: {e}")
                await self.close()
                if attempt < retries:
                    await asyncio.sleep(2)
                else:
                    raise
        return self

    async def send_message(self, link: str, message: str, retries: int = 2) -> bool:
        for attempt in range(1, retries + 1):
            try:
                # Используем domcontentloaded + задержка (networkidle не работает - чат делает постоянные запросы)
                await self.page.goto(link, wait_until="domcontentloaded", timeout=10000)
                
                # Проверяем, что не редиректнуло на главную
                current_url = self.page.url
                if "chats/open" not in current_url:
                    print(f"⚠️ Попытка {attempt}: Редирект на {current_url[:50]}... Пропускаем.")
                    return False
                
                await asyncio.sleep(4)  # Даем время скриптам чата инициализироваться

                # Ждем textarea и проверяем, что она видима
                textarea_selector = "textarea"
                try:
                    await self.page.wait_for_selector(textarea_selector, state="visible", timeout=8000)
                except:
                    print(f"⚠️ Попытка {attempt}: Поле ввода не найдено или не видимо.")
                    if attempt < retries:
                        await asyncio.sleep(2)
                        continue
                    return False

                textarea = await self.page.query_selector(textarea_selector)
                if not textarea:
                    print(f"⚠️ Попытка {attempt}: textarea не найдена в DOM.")
                    continue
                
                # Проверяем, что элемент интерактивен
                is_visible = await textarea.is_visible()
                is_enabled = await textarea.is_enabled()
                if not is_visible or not is_enabled:
                    print(f"⚠️ Попытка {attempt}: textarea не готова (visible={is_visible}, enabled={is_enabled}).")
                    await asyncio.sleep(1)
                    continue

                # Очищаем и заполняем
                await textarea.click()  # Сначала клик для фокуса
                await textarea.fill("")  # На всякий случай чистим
                await textarea.fill(message)
                await asyncio.sleep(0.5)

                # Пробуем нажать Enter — это самый надежный способ на OpenSooq
                await textarea.press("Enter")

                # На всякий случай ищем кнопку, если Enter не сработал
                # Ищем кнопку именно по атрибутам или тексту, а не только по иконке
                send_button = await self.page.query_selector(
                    'button[type="submit"], button:has(.fa-paper-plane), .send-message-btn')
                if send_button:
                    await send_button.click()

                await asyncio.sleep(1.5)  # Даем время на отправку запроса в сеть
                return True

            except Exception as e:
                print(f"⚠️ Попытка {attempt}: Ошибка в send_message: {e}")
                if attempt < retries:
                    await asyncio.sleep(2)

        return False

    async def send_image(self, link: str, image_path: str, retries: int = 2) -> bool:
        """Отправка изображения в чат"""
        for attempt in range(1, retries + 1):
            try:
                # Переходим на страницу чата
                await self.page.goto(link, wait_until="domcontentloaded", timeout=10000)
                
                # Проверяем, что не редиректнуло на главную
                current_url = self.page.url
                if "chats/open" not in current_url:
                    print(f"⚠️ Попытка {attempt}: Редирект на {current_url[:50]}... Пропускаем.")
                    return False
                
                await asyncio.sleep(4)  # Даем время на инициализацию

                # Ищем input для загрузки файла (обычно скрыт)
                file_input_selectors = [
                    'input[type="file"]',
                    'input[accept*="image"]',
                    '.file-input',
                    '[data-upload]'
                ]
                
                file_input = None
                for selector in file_input_selectors:
                    file_input = await self.page.query_selector(selector)
                    if file_input:
                        break
                
                if not file_input:
                    print(f"⚠️ Попытка {attempt}: input для загрузки файла не найден.")
                    if attempt < retries:
                        await asyncio.sleep(2)
                        continue
                    return False

                # Загружаем файл
                await file_input.set_input_files(image_path)
                await asyncio.sleep(1)  # Даем время на обработку загрузки

                # Ищем кнопку отправки (она может появиться после загрузки фото)
                send_button_selectors = [
                    'button[type="submit"]',
                    'button:has(.fa-paper-plane)',
                    '.send-message-btn',
                    'button.send-btn',
                    '[data-send]'
                ]
                
                send_button = None
                for selector in send_button_selectors:
                    send_button = await self.page.query_selector(selector)
                    if send_button:
                        is_visible = await send_button.is_visible()
                        is_enabled = await send_button.is_enabled()
                        if is_visible and is_enabled:
                            break
                
                if send_button:
                    await send_button.click()
                    await asyncio.sleep(2)  # Даем время на отправку
                    return True
                else:
                    print(f"⚠️ Попытка {attempt}: Кнопка отправки не найдена или не активна.")
                    if attempt < retries:
                        await asyncio.sleep(2)
                        continue
                    return False

            except Exception as e:
                print(f"⚠️ Попытка {attempt}: Ошибка в send_image: {e}")
                if attempt < retries:
                    await asyncio.sleep(2)

        return False

    async def close(self):
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except:
            pass
        finally:
            self.page = self.context = self.browser = self.playwright = None


async def send_message_with_browser(
    link: str, message: str, proxy: dict = None, retries: int = 2
) -> bool:
    """
    Автономная функция: открывает НОВЫЙ браузер для каждой отправки.
    Используется, когда не нужна одна долгая сессия.
    """
    await ensure_playwright()

    # Моя информация от января 2025 года — в последних версиях Playwright
    # логика запуска в EXE требует четкого указания путей.
    for attempt in range(1, retries + 1):
        browser = None
        try:
            async with async_playwright() as p:
                print(
                    f"[DEBUG] Попытка {attempt}/{retries}: Запуск браузера для {link}"
                )

                # Настройка параметров запуска
                browser_args = {
                    "headless": False,
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                }

                # Если мы в EXE, пытаемся найти вложенный chromium
                chromium_exe = None
                if os.path.exists("browsers"):
                    for root, dirs, files in os.walk("browsers"):
                        for f in files:
                            if f.lower() in ["chrome.exe", "chromium.exe"]:
                                chromium_exe = os.path.join(root, f)
                                break
                        if chromium_exe:
                            break

                if chromium_exe:
                    browser_args["executable_path"] = chromium_exe

                # Контекст (UA и Прокси)
                context_args = {
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                    "viewport": {"width": 1920, "height": 1080},
                }

                if proxy:
                    proxy_url = proxy.get("http") or proxy.get("https")
                    if proxy_url:
                        context_args["proxy"] = {"server": proxy_url}

                # Старт
                browser = await p.chromium.launch(**browser_args)
                context = await browser.new_context(**context_args)

                # Загрузка куки
                if os.path.exists("cookies.txt"):
                    try:
                        with open("cookies.txt", "r", encoding="utf-8") as f:
                            cookies_data = json.load(f)
                        valid_cookies = []
                        for c in cookies_data:
                            valid_cookies.append(
                                {
                                    "name": c["name"],
                                    "value": c["value"],
                                    "domain": c.get("domain", ".opensooq.com"),
                                    "path": c.get("path", "/"),
                                }
                            )
                        await context.add_cookies(valid_cookies)
                    except Exception as e:
                        print(f"[DEBUG] Ошибка куки: {e}")

                page = await context.new_page()
                
                # Блокируем только тяжелые ресурсы (не CSS/JS!)
                await page.route("**/*", lambda route: (
                    route.abort() if route.request.resource_type in ["image", "media"]
                    else route.continue_()
                ))
                
                await page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )

                # Действия на странице - domcontentloaded + задержка (networkidle таймаутит)
                await page.goto(link, wait_until="domcontentloaded", timeout=10000)
                
                # Проверяем, что не редиректнуло
                current_url = page.url
                if "chats/open" not in current_url:
                    print(f"[DEBUG] Редирект на {current_url[:50]}... Попытка {attempt}")
                    await browser.close()
                    if attempt < retries:
                        await asyncio.sleep(2)
                        continue
                    return False
                
                await asyncio.sleep(4)  # Даем время скриптам чата инициализироваться

                # Ждем textarea и проверяем видимость
                try:
                    await page.wait_for_selector("textarea", state="visible", timeout=6000)
                    textarea = await page.query_selector(
                        "#chatForm > div > textarea"
                    ) or await page.query_selector("textarea")
                except:
                    textarea = None

                if not textarea:
                    print(f"[DEBUG] Textarea не найдена на попытке {attempt}")
                    await browser.close()
                    if attempt < retries:
                        await asyncio.sleep(1)
                        continue
                    return False
                
                # Проверяем готовность элемента
                is_visible = await textarea.is_visible()
                is_enabled = await textarea.is_enabled()
                if not is_visible or not is_enabled:
                    print(f"[DEBUG] Textarea не готова (visible={is_visible}, enabled={is_enabled})")
                    await browser.close()
                    if attempt < retries:
                        await asyncio.sleep(1)
                        continue
                    return False

                # Ввод и отправка
                await textarea.fill(message)
                await asyncio.sleep(0.3)

                send_button = (
                    await page.query_selector(".fa-paper-plane")
                    or await page.query_selector(".fa-solid.fs-1.fa-paper-plane")
                    or await page.query_selector('button[type="submit"]')
                )

                if send_button:
                    await send_button.click()
                else:
                    await textarea.press("Enter")

                print(f"[+] Сообщение отправлено на {link}")
                await asyncio.sleep(1.5)  # Ждем, чтобы запрос улетел

                await browser.close()
                return True

        except Exception as e:
            print(f"[DEBUG] Ошибка в автономной функции: {e}")
            if browser:
                try:
                    await browser.close()
                except:
                    pass
            if attempt < retries:
                await asyncio.sleep(1)
            else:
                return False

    return False


async def send_multiple_messages(proxy: dict = None):
    """Интерактивный цикл рассылки"""
    await ensure_playwright()
    async with async_playwright() as p:
        # Инициализация браузера внутри контекста
        browser_args = {
            "headless": False,
            "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        }
        context_args = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
        }

        if proxy:
            proxy_url = proxy.get("http") or proxy.get("https", "")
            if proxy_url:
                context_args["proxy"] = {"server": proxy_url}

        browser = await p.chromium.launch(**browser_args)
        context = await browser.new_context(**context_args)

        # Загрузка куки
        try:
            if os.path.exists("cookies.txt"):
                with open("cookies.txt", "r", encoding="utf-8") as f:
                    c_list = json.load(f)
                await context.add_cookies(
                    [
                        {
                            "name": c["name"],
                            "value": c["value"],
                            "domain": c.get("domain", ".opensooq.com"),
                            "path": c.get("path", "/"),
                        }
                        for c in c_list
                    ]
                )
                print("✓ Cookies загружены")
        except Exception as e:
            print(f"⚠ Ошибка загрузки cookies: {e}")

        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        print('\n=== Браузер открыт. Введите "exit" для выхода ===')
        while True:
            try:
                print("\n" + "=" * 50)
                link = input('Введите ссылку на чат (или "exit"): ').strip()
                if link.lower() == "exit":
                    break
                if not link:
                    continue

                message = input("Введите текст сообщения: ").strip()
                if not message:
                    continue

                print(f"Открываю: {link}")
                await page.goto(link, wait_until="networkidle", timeout=15000)

                try:
                    await page.wait_for_selector("textarea", timeout=10000)
                    textarea = await page.query_selector(
                        "#chatForm > div > textarea"
                    ) or await page.query_selector("textarea")

                    if textarea:
                        await textarea.fill(message)
                        await asyncio.sleep(1)
                        btn = await page.query_selector(
                            ".fa-solid.fs-1.fa-paper-plane"
                        ) or await page.query_selector('button[type="submit"]')

                        if btn:
                            await btn.click()
                            print("✓ Сообщение отправлено!")
                        else:
                            await textarea.press("Enter")
                            print("✓ Отправлено через Enter")
                        await asyncio.sleep(2)
                    else:
                        print("✗ Поле ввода не найдено")
                except Exception as e:
                    print(f"✗ Ошибка на странице: {e}")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"✗ Критическая ошибка: {e}")

        await browser.close()
        print("Браузер закрыт.")


if __name__ == "__main__":
    proxy = {"http": "http://127.0.0.1:60000", "https": "http://127.0.0.1:60000"}
    asyncio.run(send_multiple_messages(proxy=proxy))
