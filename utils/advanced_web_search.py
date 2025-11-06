"""
Продвинутая система веб-поиска с TF-IDF ранжированием и кэшированием
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin, urlparse
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.metrics.pairwise import cosine_similarity
import hashlib
import os
import time
import logging
from typing import List, Dict, Any
import re
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Создаем директорию для кэша
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

class AdvancedWebSearch:
    """Продвинутая система веб-поиска с интеллектуальным ранжированием"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        
        # Configure proxy if enabled
        proxy_enabled = os.getenv("PROXY_ENABLED", "false").lower() == "true"
        if proxy_enabled:
            proxy_host = os.getenv("PROXY_HOST")
            proxy_port = os.getenv("PROXY_PORT")
            proxy_username = os.getenv("PROXY_USERNAME")
            proxy_password = os.getenv("PROXY_PASSWORD")
            
            if proxy_host and proxy_port:
                if proxy_username and proxy_password:
                    proxy_url = f"http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}"
                else:
                    proxy_url = f"http://{proxy_host}:{proxy_port}"
                
                self.session.proxies = {
                    "http": proxy_url,
                    "https": proxy_url,
                }
                logger.info(f"🌐 AdvancedWebSearch: Proxy enabled {proxy_host}:{proxy_port}")
    
    def duck_search(self, query: str, max_results: int = 5) -> List[str]:
        """Поиск через DuckDuckGo с fallback"""
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            logger.info(f"Поиск DuckDuckGo: {query}")
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Ищем ссылки в результатах поиска (разные селекторы)
            links = []
            
            # Пробуем разные селекторы для DuckDuckGo
            selectors = [
                ".result__url",
                ".result__a",
                ".result__title a",
                ".result a",
                "a[href*='http']"
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                for elem in elements:
                    href = elem.get("href")
                    if href and href.startswith("http"):
                        # Очищаем DuckDuckGo редиректы
                        if "/l/?uddg=" in href:
                            try:
                                from urllib.parse import unquote, parse_qs
                                parsed = parse_qs(href.split("?")[1])
                                if "uddg" in parsed:
                                    real_url = unquote(parsed["uddg"][0])
                                    if real_url.startswith("http"):
                                        href = real_url
                                    else:
                                        continue
                                else:
                                    continue
                            except:
                                continue
                        elif href.startswith("//"):
                            href = "https:" + href
                        
                        if href.startswith("http") and href not in links:
                            links.append(href)
                
                if links:  # Если нашли ссылки, прекращаем поиск
                    break
            
            logger.info(f"Найдено ссылок: {len(links)}")
            
            # Если не нашли ссылки, используем fallback
            if not links:
                logger.warning("DuckDuckGo не вернул ссылки, используем fallback")
                return self._fallback_search(query, max_results)
            
            return links[:max_results]
            
        except Exception as e:
            logger.error(f"Ошибка поиска DuckDuckGo: {e}")
            return self._fallback_search(query, max_results)
    
    def _fallback_search(self, query: str, max_results: int = 5) -> List[str]:
        """Fallback поиск через простые источники"""
        try:
            # Простой поиск через известные источники
            fallback_urls = [
                f"https://en.wikipedia.org/wiki/{quote(query.replace(' ', '_'))}",
                f"https://coinmarketcap.com/search/?q={quote(query)}",
                f"https://www.google.com/search?q={quote(query)}"
            ]
            
            # Возвращаем только валидные URL
            valid_urls = [url for url in fallback_urls if url.startswith("http")]
            logger.info(f"Fallback поиск: {len(valid_urls)} URL")
            
            return valid_urls[:max_results]
            
        except Exception as e:
            logger.error(f"Ошибка fallback поиска: {e}")
            return []
    
    def fetch_text(self, url: str) -> str:
        """Извлечение и очистка текста с веб-страницы"""
        try:
            logger.info(f"Загрузка: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Удаляем ненужные элементы
            for element in soup(["script", "style", "noscript", "nav", "footer", "header", "aside"]):
                element.decompose()
            
            # Удаляем элементы с классами рекламы и навигации
            for element in soup.find_all(class_=re.compile(r"(ad|advertisement|banner|menu|navigation|sidebar|footer|header)")):
                element.decompose()
            
            # Извлекаем основной контент
            main_content = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"(content|main|article)"))
            
            if main_content:
                text = main_content.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)
            
            # Очистка текста
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)
            
            # Ограничиваем размер
            return text[:5000]  # Увеличили лимит для лучшего контекста
            
        except Exception as e:
            logger.error(f"Ошибка загрузки {url}: {e}")
            return ""
    
    def cache_path(self, key: str) -> str:
        """Получить путь к файлу кэша"""
        return os.path.join(CACHE_DIR, hashlib.md5(key.encode()).hexdigest() + ".txt")
    
    def get_cached_or_fetch(self, url: str) -> str:
        """Получить данные из кэша или загрузить"""
        cache_file = self.cache_path(url)
        
        # Проверяем кэш (действителен 24 часа)
        if os.path.exists(cache_file):
            file_age = time.time() - os.path.getmtime(cache_file)
            if file_age < 86400:  # 24 часа
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    logger.info(f"Загружено из кэша: {url}")
                    return content
                except Exception as e:
                    logger.warning(f"Ошибка чтения кэша {url}: {e}")
        
        # Загружаем и кэшируем
        content = self.fetch_text(url)
        if content:
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info(f"Сохранено в кэш: {url}")
            except Exception as e:
                logger.warning(f"Ошибка записи в кэш {url}: {e}")
        
        return content
    
    def rank_contexts(self, query: str, docs: List[str]) -> List[str]:
        """Ранжирование документов по релевантности (sklearn отключен)"""
        # Временно возвращаем документы без ранжирования
        logger.info("TF-IDF ранжирование отключено - возвращаем оригинальные документы")
        return docs
    
    def search_and_analyze(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Основная функция поиска и анализа"""
        logger.info(f"🔍 Начинаем продвинутый поиск: {query}")
        
        # Поиск ссылок
        links = self.duck_search(query, max_results)
        if not links:
            return {
                "error": "Не удалось найти результаты поиска",
                "query": query,
                "results": []
            }
        
        # Загрузка и кэширование контента
        raw_docs = []
        successful_links = []
        
        for link in links:
            content = self.get_cached_or_fetch(link)
            if content:
                raw_docs.append(content)
                successful_links.append(link)
        
        if not raw_docs:
            return {
                "error": "Не удалось загрузить контент с найденных страниц",
                "query": query,
                "results": []
            }
        
        # Ранжирование по релевантности
        ranked_docs = self.rank_contexts(query, raw_docs)
        
        # Формируем результат
        results = []
        for i, (doc, link) in enumerate(zip(ranked_docs, successful_links)):
            results.append({
                "rank": i + 1,
                "url": link,
                "content": doc,
                "relevance_score": 1.0 - (i * 0.1)  # Простой скор на основе ранга
            })
        
        logger.info(f"✅ Поиск завершен. Обработано {len(results)} результатов")
        
        return {
            "query": query,
            "total_results": len(results),
            "results": results,
            "cache_hits": len([f for f in os.listdir(CACHE_DIR) if f.endswith('.txt')]) if os.path.exists(CACHE_DIR) else 0
        }

# Глобальный экземпляр для использования
advanced_search = AdvancedWebSearch()

def get_advanced_web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Получить результаты продвинутого веб-поиска"""
    return advanced_search.search_and_analyze(query, max_results)

def format_advanced_search_results(search_data: Dict[str, Any]) -> str:
    """Форматировать результаты продвинутого поиска для AI"""
    if "error" in search_data:
        return f"❌ Ошибка поиска: {search_data['error']}"
    
    if not search_data.get("results"):
        return "❌ Результаты поиска не найдены"
    
    formatted_text = f"🌐 ПРОДВИНУТЫЙ ВЕБ-ПОИСК ПО ЗАПРОСУ '{search_data['query']}':\n"
    formatted_text += f"📊 Найдено результатов: {search_data['total_results']}\n"
    formatted_text += f"💾 Кэш-файлов: {search_data.get('cache_hits', 0)}\n\n"
    
    for result in search_data["results"][:3]:  # Топ-3 результата
        formatted_text += f"### Результат #{result['rank']}\n"
        formatted_text += f"🔗 URL: {result['url']}\n"
        formatted_text += f"📈 Релевантность: {result['relevance_score']:.2f}\n"
        formatted_text += f"📄 Контент:\n{result['content'][:1000]}...\n\n"
    
    return formatted_text
