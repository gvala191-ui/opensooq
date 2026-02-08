import asyncio
import random
import logging
from typing import Optional, List, Dict
import curl_cffi

logger = logging.getLogger(__name__)


class ProxyManager:
    """Управление прокси с автоматической ротацией"""
    
    def __init__(self, proxy_list: List[str] = None):
        """
        Args:
            proxy_list: Список прокси в формате ["host1:port1", "host2:port2", ...]
        """
        self.proxy_list = proxy_list or []
        self.current_index = 0
        self.failed_proxies = set()
        self.proxy_stats = {}  # Статистика по каждому прокси
        
    def add_proxy(self, proxy: str):
        """Добавить прокси в список"""
        if proxy not in self.proxy_list:
            self.proxy_list.append(proxy)
            self.proxy_stats[proxy] = {"success": 0, "failed": 0, "403_errors": 0}
            logger.info(f"✅ Добавлен прокси: {proxy}")
    
    def get_next_proxy(self) -> Optional[Dict[str, str]]:
        """Получить следующий рабочий прокси"""
        if not self.proxy_list:
            return None
            
        # Фильтруем неработающие прокси
        available_proxies = [p for p in self.proxy_list if p not in self.failed_proxies]
        
        if not available_proxies:
            # Если все прокси помечены как неработающие, сбрасываем список
            logger.warning("⚠️ Все прокси неработающие, сбрасываю список")
            self.failed_proxies.clear()
            available_proxies = self.proxy_list.copy()
        
        # Берем следующий прокси по кругу
        self.current_index = (self.current_index + 1) % len(available_proxies)
        proxy_host_port = available_proxies[self.current_index]
        
        return {
            "http": f"http://{proxy_host_port}",
            "https": f"http://{proxy_host_port}",
        }
    
    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        """Получить случайный рабочий прокси"""
        if not self.proxy_list:
            return None
            
        available_proxies = [p for p in self.proxy_list if p not in self.failed_proxies]
        
        if not available_proxies:
            self.failed_proxies.clear()
            available_proxies = self.proxy_list.copy()
        
        proxy_host_port = random.choice(available_proxies)
        
        return {
            "http": f"http://{proxy_host_port}",
            "https": f"http://{proxy_host_port}",
        }
    
    def mark_proxy_failed(self, proxy: Dict[str, str]):
        """Пометить прокси как неработающий"""
        if not proxy:
            return
            
        proxy_str = proxy.get("http", "").replace("http://", "")
        if proxy_str:
            self.failed_proxies.add(proxy_str)
            logger.warning(f"❌ Прокси помечен как неработающий: {proxy_str}")
    
    def mark_403_error(self, proxy: Dict[str, str]):
        """Зафиксировать 403 ошибку для прокси"""
        if not proxy:
            return
            
        proxy_str = proxy.get("http", "").replace("http://", "")
        if proxy_str and proxy_str in self.proxy_stats:
            self.proxy_stats[proxy_str]["403_errors"] += 1
            logger.warning(f"⚠️ 403 ошибка на прокси: {proxy_str} (всего: {self.proxy_stats[proxy_str]['403_errors']})")
    
    async def test_proxy(self, proxy_host_port: str) -> bool:
        """Проверить работоспособность прокси"""
        proxy = {
            "http": f"http://{proxy_host_port}",
            "https": f"http://{proxy_host_port}",
        }
        
        try:
            async with curl_cffi.AsyncSession() as session:
                response = await session.get(
                    "https://httpbin.org/ip",
                    proxies=proxy,
                    verify=False,
                    timeout=10
                )
                
                if response.status_code == 200:
                    ip = response.json().get("origin", "неизвестно")
                    logger.info(f"✅ Прокси работает: {proxy_host_port} (IP: {ip})")
                    if proxy_host_port in self.proxy_stats:
                        self.proxy_stats[proxy_host_port]["success"] += 1
                    return True
                else:
                    logger.warning(f"⚠️ Прокси ответил кодом {response.status_code}: {proxy_host_port}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Ошибка тестирования прокси {proxy_host_port}: {e}")
            if proxy_host_port in self.proxy_stats:
                self.proxy_stats[proxy_host_port]["failed"] += 1
            return False
    
    async def test_all_proxies(self):
        """Протестировать все прокси"""
        logger.info(f"🔍 Тестирование {len(self.proxy_list)} прокси...")
        
        tasks = [self.test_proxy(proxy) for proxy in self.proxy_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        working_count = sum(1 for r in results if r is True)
        logger.info(f"✅ Рабочих прокси: {working_count}/{len(self.proxy_list)}")
        
        return working_count
    
    def get_stats(self) -> str:
        """Получить статистику по прокси"""
        if not self.proxy_stats:
            return "📊 Статистика прокси отсутствует"
        
        stats_lines = ["📊 Статистика прокси:"]
        for proxy, stats in self.proxy_stats.items():
            status = "❌" if proxy in self.failed_proxies else "✅"
            stats_lines.append(
                f"{status} {proxy}: "
                f"✓ {stats['success']} | "
                f"✗ {stats['failed']} | "
                f"🚫 403: {stats['403_errors']}"
            )
        
        return "\n".join(stats_lines)
    
    def load_from_file(self, filename: str = "proxies.txt"):
        """Загрузить прокси из файла"""
        try:
            with open(filename, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self.add_proxy(line)
            logger.info(f"✅ Загружено {len(self.proxy_list)} прокси из {filename}")
        except FileNotFoundError:
            logger.warning(f"⚠️ Файл {filename} не найден")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки прокси: {e}")


# Глобальный менеджер прокси
proxy_manager = ProxyManager()
