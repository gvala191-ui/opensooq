import random
import asyncio
from typing import Optional, List


class ProxyRotator:
    """Ротация прокси при ошибках 403"""
    
    def __init__(self, proxy_file: str = "proxies.txt"):
        self.proxies = []
        self.current_index = 0
        self.failed_proxies = set()
        self.load_proxies(proxy_file)
    
    def load_proxies(self, filename: str):
        """Загрузка прокси из файла"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Пропускаем комментарии и пустые строки
                    if line and not line.startswith('#'):
                        self.proxies.append(line)
            print(f"✅ Загружено {len(self.proxies)} прокси")
        except FileNotFoundError:
            print("⚠️ Файл proxies.txt не найден, работаем без прокси")
            self.proxies = []
    
    def get_current_proxy(self) -> Optional[dict]:
        """Получить текущий прокси"""
        if not self.proxies:
            return None
        
        # Пропускаем проваленные прокси
        attempts = 0
        while attempts < len(self.proxies):
            proxy_string = self.proxies[self.current_index]
            
            if proxy_string not in self.failed_proxies:
                return self._format_proxy(proxy_string)
            
            self.current_index = (self.current_index + 1) % len(self.proxies)
            attempts += 1
        
        # Все прокси провалились - сбрасываем failed и пробуем снова
        print("⚠️ Все прокси провалились, сбрасываем список неудач")
        self.failed_proxies.clear()
        return self._format_proxy(self.proxies[self.current_index])
    
    def _format_proxy(self, proxy_string: str) -> dict:
        """Форматирование прокси строки в dict"""
        # Проверяем наличие авторизации
        if '@' in proxy_string:
            # user:pass@host:port
            auth_part, host_port = proxy_string.split('@')
            proxy_url = f"http://{auth_part}@{host_port}"
        else:
            # host:port
            proxy_url = f"http://{proxy_string}"
        
        return {
            "http": proxy_url,
            "https": proxy_url
        }
    
    def rotate(self):
        """Переключиться на следующий прокси"""
        if not self.proxies:
            return
        
        old_proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        new_proxy = self.proxies[self.current_index]
        
        print(f"🔄 Смена прокси: {old_proxy} → {new_proxy}")
    
    def mark_failed(self):
        """Отметить текущий прокси как проваленный"""
        if not self.proxies:
            return
        
        failed_proxy = self.proxies[self.current_index]
        self.failed_proxies.add(failed_proxy)
        print(f"❌ Прокси провалился: {failed_proxy}")
        self.rotate()
    
    def get_random_proxy(self) -> Optional[dict]:
        """Получить случайный прокси"""
        if not self.proxies:
            return None
        
        available = [p for p in self.proxies if p not in self.failed_proxies]
        if not available:
            # Сбрасываем failed если все провалились
            self.failed_proxies.clear()
            available = self.proxies
        
        proxy_string = random.choice(available)
        return self._format_proxy(proxy_string)
    
    def reset_failures(self):
        """Сбросить список проваленных прокси"""
        self.failed_proxies.clear()
        print("♻️ Список проваленных прокси сброшен")


# Пример использования
if __name__ == "__main__":
    rotator = ProxyRotator()
    
    # Получить текущий прокси
    proxy = rotator.get_current_proxy()
    print(f"Текущий прокси: {proxy}")
    
    # Сменить прокси
    rotator.rotate()
    
    # Отметить как проваленный
    rotator.mark_failed()
    
    # Получить случайный
    random_proxy = rotator.get_random_proxy()
    print(f"Случайный прокси: {random_proxy}")
