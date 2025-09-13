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


class NewsCollector:
    """Collect headline-level metadata from various Swiss news sources."""
    
    def __init__(self, db_path: str, config_path: str = "config/feeds.yaml"):
        self.db_path = db_path
        self.config_path = config_path
        self.user_agent = os.getenv("USER_AGENT", "NewsAnalyzerBot/1.0 (+contact@email)")
        self.max_items_per_feed = int(os.getenv("MAX_ITEMS_PER_FEED", "120"))
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT_SEC", "12"))
        self.crawl_delay = int(os.getenv("CRAWL_DELAY_SEC", "4"))
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'application/rss+xml,application/xml;q=0.9,text/xml;q=0.8,*/*;q=0.5'
        })
        
        self.logger = logging.getLogger(__name__)
        
        # Load feeds configuration
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
    
    def collect_from_rss(self, feed_urls: List[str], source: str) -> List[Dict[str, Any]]:
        """Collect articles from RSS feeds using feedparser."""
        articles = []
        
        for url in feed_urls:
            try:
                if not is_allowed_by_robots(url, self.user_agent):
                    self.logger.warning(f"Robots.txt disallows {url}")
                    continue
                
                self.logger.info(f"Fetching RSS feed: {url}")
                
                # Use feedparser to parse RSS/Atom feeds
                feed = feedparser.parse(url)
                
                if feed.bozo and feed.bozo_exception:
                    self.logger.warning(f"Feed parsing issues for {url}: {feed.bozo_exception}")
                
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
                if not is_allowed_by_robots(url, self.user_agent):
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
                
                if not is_allowed_by_robots(url, self.user_agent):
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
    
    def collect_from_google_news(self, queries: Dict[str, str]) -> List[Dict[str, Any]]:
        """Collect articles from Google News RSS feeds."""
        articles = []
        
        for topic, url in queries.items():
            try:
                if not is_allowed_by_robots(url, self.user_agent):
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
        results = {'rss': 0, 'sitemaps': 0, 'html': 0, 'google_news': 0}
        all_articles = []
        
        # Collect from RSS feeds
        if 'rss' in self.config:
            for source, urls in self.config['rss'].items():
                articles = self.collect_from_rss(urls, source)
                all_articles.extend(articles)
                results['rss'] += len(articles)
        
        # Collect from sitemaps
        if 'sitemaps' in self.config:
            for source, urls in self.config['sitemaps'].items():
                articles = self.collect_from_sitemaps(urls, source)
                all_articles.extend(articles)
                results['sitemaps'] += len(articles)
        
        # Collect from HTML listings
        if 'html' in self.config:
            articles = self.collect_from_html_listings(self.config['html'])
            all_articles.extend(articles)
            results['html'] += len(articles)
        
        # Collect from Google News
        if 'google_news_rss' in self.config:
            articles = self.collect_from_google_news(self.config['google_news_rss'])
            all_articles.extend(articles)
            results['google_news'] += len(articles)
        
        # Deduplicate and save
        deduplicated = self.deduplicate_articles(all_articles)
        saved = self.save_articles(deduplicated)
        
        results['total_collected'] = len(all_articles)
        results['after_dedup'] = len(deduplicated)
        results['saved'] = saved
        
        self.logger.info(f"Collection complete: {results}")
        
        return results
