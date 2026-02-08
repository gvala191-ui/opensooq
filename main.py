import asyncio

from sendwithbrowser import BrowserSession
import sys
import subprocess


from sendwithbrowser import ensure_playwright


def ensure_dependencies():
    if bool(getattr(sys, "frozen", False)):
        return
    else:
        required = ["curl_cffi", "bs4"]
        for pkg in required:
            try:
                __import__(pkg)
            except ImportError:
                print(f"📦 Устанавливаю {pkg}...")
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pkg, "-q"]
                )
                print(f"✅ {pkg} установлен!")


ensure_dependencies()
import curl_cffi
from bs4 import BeautifulSoup
import os
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, unquote


async def fetch_link(link, proxy=None, cookies=None, headers=None, retries=4, proxy_manager=None) -> str:
    # ***<module>.fetch_link: Failure: Compilation Error
    request_kwargs = {
        "verify": False, 
        "timeout": 30,  # Увеличен для медленного интернета
        "allow_redirects": True,
        "max_redirects": 2
    }
    
    current_proxy = proxy
    
    if cookies:
        request_kwargs["cookies"] = cookies
    if headers:
        request_kwargs["headers"] = headers
    
    for attempt in range(retries):
        # Если есть менеджер прокси, используем его
        if proxy_manager and hasattr(proxy_manager, 'proxy_list') and proxy_manager.proxy_list:
            current_proxy = proxy_manager.get_next_proxy()
            print(f"🔄 Используем прокси: {current_proxy.get('http', 'None')}")
        
        if current_proxy:
            request_kwargs["proxies"] = current_proxy
            
        async with curl_cffi.AsyncSession() as s:
            try:
                response = await s.get(link, **request_kwargs)
                if response.status_code == 200:
                    return response.text
                    
                if response.status_code == 403:
                    print(
                        f"⚠️ 403 Forbidden на {link[:50]}... (попытка {attempt + 1}/{retries})"
                    )
                    # Помечаем прокси и меняем его
                    if proxy_manager and current_proxy:
                        proxy_manager.mark_403_error(current_proxy)
                        print("🔄 Меняю прокси из-за 403...")
                        current_proxy = proxy_manager.get_random_proxy()
                    
                    await asyncio.sleep(3)
                    continue
                    
                if response.status_code == 429:
                    print("⚠️ Rate limit 429, меняю прокси и жду 5 сек...")
                    if proxy_manager and current_proxy:
                        current_proxy = proxy_manager.get_random_proxy()
                    await asyncio.sleep(5)
                    continue
                else:
                    print(f"⚠️ HTTP {response.status_code} на {link[:50]}...")
                    return

                print(f"❌ Не удалось получить {link[:50]}... после {retries} попыток")
            except (ConnectionResetError, ConnectionAbortedError, ConnectionError) as e:
                print(f"⚠️ Разрыв соединения (попытка {attempt + 1}/{retries})")
                if proxy_manager and current_proxy:
                    print("🔄 Меняю прокси из-за разрыва соединения...")
                    current_proxy = proxy_manager.get_random_proxy()
                    
                if attempt < retries - 1:
                    await asyncio.sleep(3)
                    continue
                else:
                    return None
            except Exception as e:
                error_msg = str(e).lower()
                if "connection" in error_msg or "reset" in error_msg or "10054" in error_msg:
                    print(f"⚠️ Сетевая ошибка (попытка {attempt + 1}/{retries})")
                    if proxy_manager and current_proxy:
                        current_proxy = proxy_manager.get_random_proxy()
                else:
                    print(f"❌ Ошибка запроса (попытка {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(3)
                else:
                    return None


async def parse_main_page(main_url: str, page: str, proxy: dict) -> list:
    # ***<module>.parse_main_page: Failure: Compilation Error
    headers = {
        "accept": "text/html",
        "accept-language": "ru",
        "accept-encoding": "gzip, deflate, br",  # Добавляем сжатие
        "cache-control": "max-age=0",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    all_links = []
    errors_count = 0
    for page1 in range(1, int(page) + 1):
        try:
            if page1 == 1:
                url = main_url
            else:
                url = f"{main_url}&page={page1}"
            page_content = await fetch_link(url, proxy, None, headers)
            if not page_content:
                print(f"⚠️ Страница {page1}: не удалось загрузить, пропускаем")
                errors_count += 1
                if errors_count >= 10:
                    print("⚠️ Слишком много ошибок подряд, но продолжаем с оставшимися страницами")
                    break
                continue
            else:
                soup = BeautifulSoup(page_content, "html.parser")
                elements = soup.find_all(attrs={"data-id1": True})
                links = [elem["data-id1"] for elem in elements]
                all_links.extend(links)
                print(f"✓ Страница {page1}: найдено {len(links)} элементов.")
                errors_count = 0

        except Exception as e:
            print(f"❌ Ошибка на странице {page1}: {e}")
            errors_count += 1
            if errors_count >= 10:
                print("⚠️ Много ошибок подряд, но продолжаем")
                break
    return all_links


def parse_user_info(page_html: str) -> dict:
    user_info = {"name": None, "reviews_count": 0}
    if not page_html:
        return user_info
    else:
        try:
            soup = BeautifulSoup(page_html, "html.parser")
            owner_match = re.search(
                "[\"\\']fullName[\"\\']?\\s*:\\s*[\"\\']([^\"\\'\\\\]+)[\"\\']",
                page_html,
            )
            if not owner_match:
                owner_match = re.search(
                    '\\\\?"fullName\\\\?"\\s*:\\s*\\\\?"([^"\\\\]+)\\\\?"', page_html
                )
            if owner_match:
                user_info["name"] = owner_match.group(1)
            ratings_match = re.search(
                "[\"\\']?numberOfRatings[\"\\']?\\s*:\\s*(\\d+)", page_html
            )
            if not ratings_match:
                ratings_match = re.search(
                    '\\\\?"numberOfRatings\\\\?"\\s*:\\s*(\\d+)', page_html
                )
            if ratings_match:
                user_info["reviews_count"] = int(ratings_match.group(1))
            if user_info["reviews_count"] == 0:
                rating_label = soup.find("label", string=re.compile("التقييم"))
                if rating_label:
                    parent_div = rating_label.find_parent(
                        "div", class_=re.compile("flex")
                    )
                    if parent_div:
                        buttons = parent_div.find_all(
                            "button", class_=re.compile("text-primary")
                        )
                        for btn in buttons:
                            btn_text = btn.get_text(strip=True)
                            match = re.search("\\(\\s*(\\d+)\\s*\\)", btn_text)
                            if match:
                                user_info["reviews_count"] = int(match.group(1))
                                break
            if not user_info["name"]:
                owner_section = soup.find("section", id="ListingViewListingOwner")
                if owner_section:
                    member_link = owner_section.find(
                        "a", href=re.compile("/ar/mid/member-")
                    )
                    if member_link:
                        name_elem = owner_section.find(
                            "a", class_=re.compile("font-bold")
                        )
                        if name_elem:
                            user_info["name"] = name_elem.get_text(strip=True)
                    if user_info["reviews_count"] == 0:
                        rating_button = owner_section.find(
                            "button", class_=re.compile("text-primary")
                        )
                        if rating_button:
                            reviews_text = rating_button.get_text(strip=True)
                            match = re.search("\\(\\s*(\\d+)\\s*\\)", reviews_text)
                            if match:
                                user_info["reviews_count"] = int(match.group(1))
            return user_info
        except Exception as e:
            print(f"⚠️ Ошибка парсинга user_info: {e}")
            return user_info


def func_proxy() -> dict:
    # ***<module>.func_proxy: Failure: Compilation Error
    try:
        proxy_host_port = input(
            "Введите прокси в формате host:port (или Enter для пропуска): "
        ).strip()
        if not proxy_host_port:
            print("⚠️ Прокси не используется.")
            return
        else:
            proxy = {
                "http": f"http://{proxy_host_port}",
                "https": f"http://{proxy_host_port}",
            }

        response = curl_cffi.get(
            "https://httpbin.org/ip", proxies=proxy, verify=False, timeout=10
        )
        if response.status_code == 200:
            ip = response.json().get("origin", "неизвестно")
            print(f"✓ Прокси работает! IP: {ip}")
            return proxy
        else:
            print(f"⚠️ Прокси ответил кодом {response.status_code}")
            retry = input("Попробовать другой? (y/n): ").strip().lower()
            if retry == "y":
                return func_proxy()
            else:
                return proxy
    except Exception as e:
        print(f"❌ Ошибка прокси: {e}")
        retry = input("Попробовать другой? (y/n): ").strip().lower()
        if retry == "y":
            return func_proxy()

    return func_proxy()


def load_cookies() -> dict:
    try:
        with open("cookies.txt", "r", encoding="utf-8") as file:
            cookies_list = json.load(file)
        cookies_dict = {}
        for cookie in cookies_list:
            cookies_dict[cookie["name"]] = cookie["value"]
        return cookies_dict
    except FileNotFoundError:
        print("Файл cookies.txt не найден.")
        asd = input("Нажмите Enter для выхода...")
        os._exit(1)
    except json.JSONDecodeError:
        print("Ошибка при чтении cookies.txt. Проверьте формат JSON.")
        asd = input("Нажмите Enter для выхода...")
        os._exit(1)


def load_blacklist() -> set:
    try:
        with open("blacklist.txt", "r", encoding="utf-8") as file:
            blacklist = set(
                (
                    line.strip().lower()
                    for line in file
                    if line.strip() and (not line.startswith("#"))
                )
            )
        print(f"✓ Загружено {len(blacklist)} записей из блеклиста")
        return blacklist
    except FileNotFoundError:
        print("⚠ Файл blacklist.txt не найден. Создаю новый...")
        with open("blacklist.txt", "w", encoding="utf-8") as file:
            file.write(
                "# Блеклист - отправленные пользователи (каждый с новой строки)\n"
            )
        return set()


def add_to_blacklist(identifier: str):
    # ***<module>.add_to_blacklist: Failure: Compilation Error
    if not identifier:
        return
    existing = load_blacklist()
    if identifier.lower() in existing:
        return
    try:
        with open("blacklist.txt", "a", encoding="utf-8") as file:
            file.write(f"{identifier}\n")
    except Exception as e:
        print(f"⚠️ Ошибка добавления в блеклист: {e}")
        return None


def is_in_blacklist(identifier: str, blacklist: set) -> bool:
    if not identifier:
        return False
    else:
        return identifier.lower() in blacklist


async def parse_link(link: str, proxy: dict, cookies: str) -> dict:
    headers = {
        "accept": "text/html",
        "accept-language": "ru-RU,ru;q=0.9",
        "accept-encoding": "gzip, deflate, br",  # Добавляем сжатие для экономии трафика
        "cache-control": "max-age=0",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    try:
        page_content = await fetch_link(link, proxy, cookies, headers)
        if not page_content:
            return {"name": None, "reviews_count": 0}

        # Убираем вывод размера для ускорения
        # print(f"Размер страницы: {len(page_content)}")

        user_info = parse_user_info(page_content)
        if user_info["name"]:
            print(f"✓ Найден: {user_info['name']}, отзывов: {user_info['reviews_count']}")
        return user_info
    except Exception as e:
        print(f"❌ Ошибка parse_link: {e}")
        return {"name": None, "reviews_count": 0}


async def parse_user_thread(
    id: str,
    proxy: dict,
    cookies: dict,
    max_reviews: int,
    blacklist: set,
    base_domain: str,
) -> dict:
    # ***<module>.parse_user_thread: Failure: Compilation Error
    link = f"https://{base_domain}/ar/search/{id}"
    try:
        if is_in_blacklist(id, blacklist):
            return
        user_data = await parse_link(link, proxy, cookies)
        if not user_data or not user_data.get("name"):
            return None
        if is_in_blacklist(user_data["name"], blacklist):
            return None
        if user_data["reviews_count"] <= max_reviews:
            # Автоматически добавляем в блеклист сразу после парсинга
            add_to_blacklist(id)
            add_to_blacklist(user_data["name"])
            return {
                "id": id,
                "name": user_data["name"],
                "reviews_count": user_data["reviews_count"],
                "link": link,
            }

    except Exception as e:
        print(e)
        return None


async def send_messages_to_user_with_session(
    browser_session, user: dict, image_path: str, sends_count: int = 5
):
    chat_link = user.get("chat_link")
    if not chat_link or chat_link in ("Не доступен", "Ошибка"):
        return False
    else:
        print(f"→ {user['name']}")
        success_count = 0
        for i in range(sends_count):
            try:
                result = await browser_session.send_image(chat_link, image_path)
                if result:
                    success_count += 1
                    print(f"  ✓ [{i + 1}/{sends_count}]")
                else:
                    print(f"  ✗ [{i + 1}/{sends_count}]")
                if i < sends_count - 1:
                    await asyncio.sleep(1.5)
            except Exception as e:
                print(f"  ✗ Ошибка: {e}")
        if success_count > 0:
            add_to_blacklist(user["name"])
            add_to_blacklist(user["id"])
        return success_count > 0


from datetime import datetime


async def parse_for_message(link: str, proxy: dict, cookies: str) -> str:
    try:
        headers = {
            "accept": "text/html",
            "accept-encoding": "gzip, deflate, br",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        page_content = await fetch_link(link, proxy, cookies, headers)
        if not page_content:
            return None

        # 1. Достаем listing_id (postId)
        listing_id = None
        l_match = re.search(r'\\"postId\\":(\d+)', page_content)
        if l_match: listing_id = l_match.group(1)

        # 2. Достаем member_id (ID владельца в ownerData)
        member_id = None
        m_match = re.search(r'\\"ownerData\\":\{\\"id\\":(\d+)', page_content)
        if m_match: member_id = m_match.group(1)

        # 3. Достаем member_data_id (это id внутри memberData в блоке listings)
        # В твоем дампе он часто совпадает с member_id, но мы ищем его отдельно
        member_data_id = member_id  # По умолчанию берем этот, если не найдем другой
        md_match = re.search(r'\\"member_id\\":\\"(\d+)\\"', page_content)
        user_info_cookie = cookies.get('userInfo')
        if user_info_cookie:
            try:
                # Декодируем %7B%22id... в {"id":...
                decoded_str = unquote(user_info_cookie)
                user_data = json.loads(decoded_str)
                if 'id' in user_data:
                    my_id = str(user_data['id'])
            except Exception as e:
                print(f"⚠️ Не удалось распарсить userInfo: {e}")

        if listing_id and member_id and member_data_id:
            today = datetime.now().strftime("%Y-%m-%d")
            # Собираем ту самую ссылку

            chat_url = (
                f"https://my.opensooq.com/chats/open/{listing_id}/{member_id}/{my_id}"
                f"?cSource=opensooq&cMedium=none&cName=direct_web_open&v={today}&selectedRoom={listing_id}-{member_id}-{my_id}"
            )
            print(f"✓ Ссылка собрана: {listing_id}")
            return chat_url

        print(f"⚠️ Не удалось собрать все ID для ссылки: L:{listing_id} M:{member_id} MD:{member_data_id}")
        return None

    except Exception as e:
        print(f"❌ Ошибка сборки ссылки: {e}")
        return None


async def get_chat_link_thread(user: dict, proxy: dict, cookies: dict) -> dict:
    try:
        chat_link = await parse_for_message(user["link"], proxy, cookies)
        user["chat_link"] = chat_link if chat_link else "Не доступен"
        return user
    except Exception:
        user["chat_link"] = "Ошибка"
        return user


async def parser() -> list:
    await ensure_playwright()
    # ***<module>.parser: Failure: Different control flow
    cookie_dict = load_cookies()
    blacklist = load_blacklist()


    main_link = input('Введи ссылку: ')
    #main_link = "https://ae.opensooq.com/en/find?search=true&sort_code=recent"
    max_reviews = int(input('Введи макс отзывов: '))
    #max_reviews = 10
    while True:
        try:
            page, sends = input('Введите номер страницы и количество отправок через запятую (например, 1,10): ').split(',')
            #page, sends = 1, 4
            sends = int(sends.strip())
            page = int(page.strip())
        except:
            print("Неверный формат ввода. Попробуйте снова.")
        else:
            print(f"\n=== Загрузка фото ===")
            # Ищем файл изображения в папке
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
            image_file = None
            for file in os.listdir('.'):
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    image_file = os.path.abspath(file)
                    break
            
            if not image_file:
                print(f"\n❌ Ошибка: фото не найдено!")
                print(f"Добавьте изображение (.jpg, .png и т.д.) в папку с программой.")
                asd = input("Нажмите Enter для выхода...")
                os._exit(1)
            
            if os.path.exists(image_file):
                file_size = os.path.getsize(image_file) / 1024  # в KB
                print(f"✓ Найдено фото: {os.path.basename(image_file)} ({file_size:.1f} KB)")
            else:
                print(f"\n❌ Ошибка: файл {image_file} не существует!")
                asd = input("Нажмите Enter для выхода...")
                os._exit(1)
            
            # Адаптивное количество потоков для оптимальной работы при множественном запуске
            threads_count = 40  # Оптимально для 20 Мбит/с при 2-4 софтах
            proxy = None
            print(f"Используем прокси: {proxy}" if proxy else "Прокси не используется.")

            print(f"\n{'============================================================'}")
            print("Настройки парсинга:")
            print(f"  Ссылка: {main_link}")
            print(f"  Страниц: {page}")
            print(f"  Макс отзывов: {max_reviews}")
            print(f"  Сообщений на пользователя: {sends}")
            print(f"  Потоков: {threads_count}")
            print(f"{'============================================================'}\n")
            parsed_url = urlparse(main_link)
            base_domain = parsed_url.netloc
            print(f"🌍 Гео домен: {base_domain}")
            print("\n=== Парсинг объявлений ===")
            ids = await parse_main_page(main_link, page, proxy)
            print(f"Всего найдено объявлений: {len(ids)}")
            print(f"\n=== Парсинг пользователей ({threads_count} потоков) ===")
            all_users_data = []
            semaphore = asyncio.Semaphore(threads_count)
            all_users_data = []

            async def sem_task(user_id):
                async with semaphore:
                    await asyncio.sleep(0.15)  # Увеличенная задержка для медленного интернета
                    result = await parse_user_thread(
                        user_id, proxy, cookie_dict, max_reviews, blacklist, base_domain
                    )
                    if result:
                        all_users_data.append(result)

            # Создаем список задач
            tasks = [sem_task(user_id) for user_id in ids]

            # Запускаем всё параллельно
            await asyncio.gather(*tasks)
            tasks.clear()
            print("\n✓ Парсинг завершён!")
            print(
                f"Всего пользователей с отзывами ≤ {max_reviews}: {len(all_users_data)}"
            )
            print(f"\n=== Получение ссылок на чаты ({threads_count} потоков) ===")
            updated_users = []
            completed = 0
            total = len(all_users_data)
            async def worker(user):
                async with semaphore:
                    await asyncio.sleep(0.15)  # Увеличенная задержка
                    result = await get_chat_link_thread(user, proxy, cookie_dict)
                    if result:
                        updated_users.append(result)

            # Создаем список всех задач
            tasks = [worker(user) for user in all_users_data]

            # Запускаем всё параллельно и ждем завершения
            await asyncio.gather(*tasks)
            
            print(f"\n✓ Получено {len(updated_users)} чат-ссылок")
            with open("results.txt", "w", encoding="utf-8") as f:
                for user in updated_users:
                    f.write(
                        f"ID: {user['id']} | Имя: {user['name']} | Отзывов: {user['reviews_count']}\n"
                    )
                    f.write(f"Объявление: {user['link']}\n")
                    f.write(f"Чат: {user.get('chat_link', 'Не доступен')}\n")
                    f.write(
                        "--------------------------------------------------------------------------------\n"
                    )
            print("\n✓ Результаты сохранены в results.txt")
            print(f"Всего записей: {len(updated_users)}")
            send_messages = "y"
            if send_messages in ["yes", "y", "да", "д"]:
                print(
                    f"\n=== Отправка фото ({len(updated_users)} пользователей) ==="
                )
                print(f"Будет отправлено по {sends} фото каждому")
                print("🚀 Запускаю браузер...")
                browser = await BrowserSession(proxy=proxy).start()
                sent_count = 0
                failed_count = 0
                try:
                    for i, user in enumerate(updated_users, 1):
                        print(f"\n[{i}/{len(updated_users)}] Обработка: {user['name']}")
                        result = await send_messages_to_user_with_session(
                            browser, user, image_file, sends
                        )
                        if result:
                            sent_count += 1
                        else:
                            failed_count += 1
                finally:
                   await browser.close()
                print(
                    f"\n{'============================================================'}"
                )
                print("Отправка завершена!")
                print(f"Успешно: {sent_count}/{len(updated_users)}")
                print(f"Неудачно: {failed_count}/{len(updated_users)}")
                return updated_users
            else:
                print("\n⊗ Отправка сообщений пропущена.")
                return updated_users


if __name__ == '__main__':
    asyncio.run(parser())