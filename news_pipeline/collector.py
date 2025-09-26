"""
NewsCollector - Step 1: URL Collection (RSS/Sitemap/HTML)

Comprehensive Swiss News Source Collection via RSS, sitemaps, and HTML parsing.
"""

import os
import asyncio
import sqlite3
import yaml
import requests
import feedparser
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

from .utils import normalize_url, url_hash, is_allowed_by_robots, parse_date, title_similarity
from .paths import config_path, safe_open


class NewsCollector:
    """Collect headline-level metadata from various Swiss news sources."""
    
    def __init__(self, db_path: str, feeds_config_path: str | None = None, respect_robots: bool = False):
        self.db_path = db_path
        # Use robust path resolution for config file
        if feeds_config_path is None:
            config_file_path = config_path("feeds.yaml")
        elif feeds_config_path.startswith("config/") or not os.path.isabs(feeds_config_path):
            # Handle legacy relative path format - always use the robust path resolution
            config_file_path = config_path("feeds.yaml")
        else:
            # Use absolute path as-is
            from pathlib import Path
            config_file_path = Path(feeds_config_path)
        
        self.config_path = str(config_file_path)
        self.respect_robots = respect_robots
        self.user_agent = os.getenv("USER_AGENT", "NewsAnalyzerBot/1.0 (+contact@email)")
        self.max_items_per_feed = int(os.getenv("MAX_ITEMS_PER_FEED", "120"))
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT_SEC", "12"))
        self.crawl_delay = int(os.getenv("CRAWL_DELAY_SEC", "4"))
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'application/rss+xml,application/xml;q=0.9,text/xml;q=0.8,*/*;q=0.5',
            'Accept-Language': 'de-CH,de;q=0.9,en;q=0.8',  # RESEARCH FIX: Swiss locale preference
            'Accept-Encoding': 'gzip, deflate, br, zstd',  # RESEARCH FIX: Include zstd support
            'Connection': 'keep-alive',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1'
        })
        
        self.logger = logging.getLogger(__name__)
        
        # Load feeds configuration using safe path resolution
        try:
            with safe_open(config_file_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        except FileNotFoundError as e:
            # Provide helpful error message with context
            raise FileNotFoundError(
                f"Could not find feeds configuration file.\n"
                f"Tried path: {config_file_path}\n"
                f"Make sure config/feeds.yaml exists in the project root.\n"
                f"Original error: {e}"
            ) from e
    
    def collect_from_rss(self, feed_urls: List[str], source: str) -> List[Dict[str, Any]]:
        """Collect articles from RSS feeds using feedparser."""
        articles = []
        
        for url in feed_urls:
            try:
                if not is_allowed_by_robots(url, self.user_agent, self.respect_robots):
                    self.logger.warning(f"Robots.txt disallows {url}")
                    continue
                
                self.logger.info(f"Fetching RSS feed: {url}")
                
                # RESEARCH FIX: Use bozo-tolerant parsing with proper error handling
                feed = feedparser.parse(url)
                
                if feed.bozo and feed.bozo_exception:
                    self.logger.warning(f"Feed parsing issues for {url}: {feed.bozo_exception}")
                    # Continue processing despite malformed XML - feedparser often recovers
                    if not feed.entries:
                        self.logger.warning(f"No entries found in malformed feed {url}, skipping (this is normal for some feeds)")
                        continue
                
                for entry in feed.entries[:self.max_items_per_feed]:
                    # Get the article URL
                    article_url = entry.get('link', '')
                    if not article_url:
                        continue
                    
                    # Get published date
                    published_at = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            time_tuple = entry.published_parsed
                            if isinstance(time_tuple, (tuple, list)) and len(time_tuple) >= 6:
                                # Extract individual time components safely
                                components = []
                                for component in time_tuple[:6]:
                                    if isinstance(component, int):
                                        components.append(component)
                                    else:
                                        components.append(int(str(component)))
                                
                                if len(components) == 6:
                                    published_at = datetime(*components).isoformat()
                        except (TypeError, ValueError, AttributeError, IndexError):
                            pass
                    if published_at is None and hasattr(entry, 'published') and entry.published:
                        published_at = parse_date(str(entry.published))
                    
                    # Get title safely
                    title = entry.get('title')
                    if isinstance(title, str):
                        title = title.strip()
                    elif title is None:
                        title = ''
                    else:
                        title = str(title).strip()
                    
                    article = {
                        'url': article_url,
                        'title': title,
                        'source': source,
                        'published_at': published_at,
                        'aggregator_url': None,
                        'discovered_at': datetime.now().isoformat()
                    }
                    
                    articles.append(article)
                    
            except Exception as e:
                self.logger.error(f"Error fetching RSS feed {url}: {e}")
        
        return articles
    
    def collect_from_sitemaps(self, sitemap_urls: List[str], source: str) -> List[Dict[str, Any]]:
        """Collect articles from news sitemaps (e.g., 20min)."""
        articles = []
        
        for url in sitemap_urls:
            try:
                if not is_allowed_by_robots(url, self.user_agent, self.respect_robots):
                    self.logger.warning(f"Robots.txt disallows {url}")
                    continue
                
                self.logger.info(f"Fetching sitemap: {url}")
                
                response = self.session.get(url, timeout=self.request_timeout)
                response.raise_for_status()
                
                # Parse XML sitemap
                root = ET.fromstring(response.content)
                
                # Handle namespaces
                namespaces = {
                    'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
                    'news': 'http://www.google.com/schemas/sitemap-news/0.9'
                }
                
                for url_elem in root.findall('.//sm:url', namespaces)[:self.max_items_per_feed]:
                    loc_elem = url_elem.find('sm:loc', namespaces)
                    news_elem = url_elem.find('news:news', namespaces)
                    
                    if loc_elem is None:
                        continue
                    
                    article_url = loc_elem.text.strip() if loc_elem.text else ''
                    title = ''
                    published_at = None
                    
                    if news_elem is not None:
                        title_elem = news_elem.find('.//news:title', namespaces)
                        date_elem = news_elem.find('.//news:publication_date', namespaces)
                        
                        if title_elem is not None and title_elem.text:
                            title = title_elem.text.strip()
                        if date_elem is not None and date_elem.text:
                            published_at = parse_date(date_elem.text)
                    
                    article = {
                        'url': article_url,
                        'title': title,
                        'source': source,
                        'published_at': published_at,
                        'aggregator_url': None,
                        'discovered_at': datetime.now().isoformat()
                    }
                    
                    articles.append(article)
                    
            except Exception as e:
                self.logger.error(f"Error fetching sitemap {url}: {e}")
        
        return articles
    
    def collect_from_html_listings(self, html_configs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect articles from HTML listings (e.g., BusinessClassOst)."""
        articles = []
        
        for source, config_data in html_configs.items():
            try:
                url = config_data['url']
                selectors = config_data['selectors']
                
                if not is_allowed_by_robots(url, self.user_agent, self.respect_robots):
                    self.logger.warning(f"Robots.txt disallows {url}")
                    continue
                
                self.logger.info(f"Fetching HTML listing: {url}")
                
                response = self.session.get(url, timeout=self.request_timeout)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find article items
                items = soup.select(selectors['item'])[:self.max_items_per_feed]
                
                for item in items:
                    try:
                        # Extract title
                        title_elem = item.select_one(selectors['title'])
                        title = title_elem.get_text(strip=True) if title_elem else ''
                        
                        # Extract date
                        date_elem = item.select_one(selectors['date'])
                        date_text = date_elem.get_text(strip=True) if date_elem else ''
                        published_at = parse_date(date_text) if date_text else None
                        
                        # Extract URL (from hidden field for BusinessClassOst)
                        url_elem = item.select_one(selectors['hidden_url'])
                        article_url = url_elem.get_text(strip=True) if url_elem else ''
                        
                        if not article_url:
                            # Fallback: try to find link in title
                            link_elem = item.select_one('a[href]')
                            if link_elem:
                                href = link_elem.get('href')
                                if href:
                                    article_url = urljoin(url, str(href))
                        
                        if not article_url or not title:
                            continue
                        
                        article = {
                            'url': article_url,
                            'title': title,
                            'source': source,
                            'published_at': published_at,
                            'aggregator_url': None,
                            'discovered_at': datetime.now().isoformat()
                        }
                        
                        articles.append(article)
                        
                    except Exception as e:
                        self.logger.warning(f"Error parsing item in {source}: {e}")
                        
            except Exception as e:
                self.logger.error(f"Error fetching HTML listing {source}: {e}")
        
        return articles

    def _get_nested_value(self, obj: Any, path: str) -> Optional[Any]:
        """
        Resolve dotted path with optional list indices, e.g., 'a.b[0].c'.
        Returns None if any segment is missing.
        """
        try:
            cur = obj
            # Support empty path -> whole object
            if not path:
                return cur
            parts = path.split('.')
            for part in parts:
                # Handle array indices like 'arr[0]'
                while '[' in part and ']' in part:
                    key, rest = part.split('[', 1)
                    idx_str, maybe_rest = rest.split(']', 1)
                    if key:
                        if isinstance(cur, dict):
                            cur = cur.get(key)
                        else:
                            return None
                    if not isinstance(cur, (list, tuple)):
                        return None
                    idx = int(idx_str)
                    if idx < 0 or idx >= len(cur):
                        return None
                    cur = cur[idx]
                    # If there is trailing nested access like '][1].field'
                    part = maybe_rest[1:] if maybe_rest.startswith('.') else maybe_rest
                    if not part:
                        break
                if part:
                    if isinstance(cur, dict):
                        cur = cur.get(part)
                    else:
                        return None
            return cur
        except Exception:
            return None

    def collect_from_json_apis(self, json_configs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Collect articles from JSON APIs as configured in config['json'].

        Expected config per source:
          json:
            shab:
              url: "https://example/api"
              item_path: "items"            # dotted path to list of items
              fields:
                url: "link"                # relative to each item
                title: "title"
                published_at: "date"       # ISO8601 or parseable string
        """
        articles = []
        for source, cfg in json_configs.items():
            try:
                url = cfg['url']
                if not is_allowed_by_robots(url, self.user_agent, self.respect_robots):
                    self.logger.warning(f"Robots.txt disallows {url}")
                    continue

                self.logger.info(f"Fetching JSON API: {url}")

                resp = self.session.get(url, timeout=self.request_timeout, headers={'Accept': 'application/json'})
                resp.raise_for_status()
                data = resp.json()

                items_path = cfg.get('item_path', 'items')
                items = self._get_nested_value(data, items_path)
                if not isinstance(items, list):
                    # If top-level is already a list, use it
                    items = data if isinstance(data, list) else []

                fields = cfg.get('fields', {})
                url_field = fields.get('url', 'url')
                title_field = fields.get('title', 'title')
                published_field = fields.get('published_at', 'published_at')

                for item in items[:self.max_items_per_feed]:
                    article_url = self._get_nested_value(item, url_field)
                    title = self._get_nested_value(item, title_field)
                    published_val = self._get_nested_value(item, published_field)

                    if not article_url or not title:
                        continue

                    published_at = parse_date(str(published_val)) if published_val else None

                    article = {
                        'url': str(article_url),
                        'title': str(title).strip(),
                        'source': source,
                        'published_at': published_at,
                        'aggregator_url': url,
                        'discovered_at': datetime.now().isoformat()
                    }
                    articles.append(article)

            except Exception as e:
                self.logger.error(f"Error fetching JSON API {source}: {e}")

        return articles
    
    def collect_from_google_news(self, queries: Dict[str, str]) -> List[Dict[str, Any]]:
        """Collect articles from Google News RSS feeds."""
        articles = []
        
        for topic, url in queries.items():
            try:
                if not is_allowed_by_robots(url, self.user_agent, self.respect_robots):
                    self.logger.warning(f"Robots.txt disallows {url}")
                    continue
                
                self.logger.info(f"Fetching Google News RSS: {topic}")
                
                feed = feedparser.parse(url)
                
                for entry in feed.entries[:self.max_items_per_feed]:
                    # Google News entries often have redirects - get the real URL
                    article_url = entry.get('link', '')
                    if not article_url:
                        continue
                    
                    # Get published date
                    published_at = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            time_tuple = entry.published_parsed
                            if isinstance(time_tuple, (tuple, list)) and len(time_tuple) >= 6:
                                # Extract individual time components safely
                                components = []
                                for component in time_tuple[:6]:
                                    if isinstance(component, int):
                                        components.append(component)
                                    else:
                                        components.append(int(str(component)))
                                
                                if len(components) == 6:
                                    published_at = datetime(*components).isoformat()
                        except (TypeError, ValueError, AttributeError, IndexError):
                            pass
                    if published_at is None and hasattr(entry, 'published') and entry.published:
                        published_at = parse_date(str(entry.published))
                    
                    # Get title safely
                    title = entry.get('title')
                    if isinstance(title, str):
                        title = title.strip()
                    elif title is None:
                        title = ''
                    else:
                        title = str(title).strip()
                    
                    article = {
                        'url': article_url,
                        'title': title,
                        'source': f"google_news_{topic}",
                        'published_at': published_at,
                        'aggregator_url': url,  # Store Google News URL
                        'discovered_at': datetime.now().isoformat()
                    }
                    
                    articles.append(article)
                    
            except Exception as e:
                self.logger.error(f"Error fetching Google News feed {topic}: {e}")
        
        return articles
    
    def deduplicate_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate articles based on URL and title similarity."""
        seen_hashes = set()
        deduplicated = []
        
        for article in articles:
            # Primary deduplication by normalized URL
            url_sha1 = url_hash(article['url'])
            
            if url_sha1 in seen_hashes:
                continue
            
            # Secondary deduplication by title similarity within same source
            duplicate_found = False
            for existing in deduplicated:
                if (existing['source'] == article['source'] and
                    title_similarity(existing['title'], article['title']) >= 0.9):
                    duplicate_found = True
                    break
            
            if not duplicate_found:
                seen_hashes.add(url_sha1)
                deduplicated.append(article)
        
        return deduplicated
    
    def save_articles(self, articles: List[Dict[str, Any]]) -> int:
        """Save articles to database."""
        if not articles:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        saved_count = 0
        
        for article in articles:
            normalized_url = normalize_url(article['url'])
            
            try:
                cursor = conn.execute("""
                    INSERT OR IGNORE INTO items 
                    (source, url, normalized_url, title, published_at, first_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    article['source'],
                    article['url'],
                    normalized_url,
                    article['title'],
                    article['published_at'],
                    article['discovered_at']
                ))
                
                if cursor.lastrowid:
                    saved_count += 1
                    
            except Exception as e:
                self.logger.error(f"Error saving article {article['url']}: {e}")
        
        conn.commit()
        conn.close()
        
        return saved_count
    
    def collect_all(self) -> Dict[str, int]:
        """Collect articles from all configured sources."""
        results = {'rss': 0, 'sitemaps': 0, 'html': 0, 'json': 0, 'google_news': 0}
        all_articles = []
        
        # Add defensive checks for None config sections
        if not self.config:
            self.logger.error("ERROR: Configuration is None or empty")
            results['total_collected'] = 0
            results['after_dedup'] = 0
            results['saved'] = 0
            return results
        
        # Collect from RSS feeds
        if 'rss' in self.config and self.config['rss'] is not None:
            rss_config = self.config['rss']
            if isinstance(rss_config, dict):
                for source, urls in rss_config.items():
                    if urls:  # Ensure urls is not None
                        articles = self.collect_from_rss(urls, source)
                        all_articles.extend(articles)
                        results['rss'] += len(articles)
        
        # Collect from sitemaps
        if 'sitemaps' in self.config and self.config['sitemaps'] is not None:
            sitemaps_config = self.config['sitemaps']
            if isinstance(sitemaps_config, dict):
                for source, urls in sitemaps_config.items():
                    if urls:  # Ensure urls is not None
                        articles = self.collect_from_sitemaps(urls, source)
                        all_articles.extend(articles)
                        results['sitemaps'] += len(articles)
        
        # Collect from HTML listings
        if 'html' in self.config and self.config['html'] is not None:
            html_config = self.config['html']
            if isinstance(html_config, dict):
                articles = self.collect_from_html_listings(html_config)
                all_articles.extend(articles)
                results['html'] += len(articles)

        # Collect from JSON APIs (e.g., SHAB)
        if 'json' in self.config and self.config['json'] is not None:
            json_config = self.config['json']
            if isinstance(json_config, dict):
                articles = self.collect_from_json_apis(json_config)
                all_articles.extend(articles)
                results['json'] += len(articles)
        
        # Collect from additional RSS feeds (high-quality direct sources)
        if 'additional_rss' in self.config and self.config['additional_rss'] is not None:
            additional_rss_config = self.config['additional_rss']
            if isinstance(additional_rss_config, dict):
                for source, urls in additional_rss_config.items():
                    if urls:  # Ensure urls is not None
                        articles = self.collect_from_rss(urls, source)
                        all_articles.extend(articles)
                        results['rss'] += len(articles)  # Count as RSS feeds
        
        # DISABLED: Google News collection (causes redirect loops)
        # if 'google_news_rss' in self.config:
        #     articles = self.collect_from_google_news(self.config['google_news_rss'])
        #     all_articles.extend(articles)
        #     results['google_news'] += len(articles)
        
        # Deduplicate and save
        deduplicated = self.deduplicate_articles(all_articles)
        saved = self.save_articles(deduplicated)
        
        results['total_collected'] = len(all_articles)
        results['after_dedup'] = len(deduplicated)
        results['saved'] = saved
        
        self.logger.info(f"Collection complete: {results}")
        
        return results
