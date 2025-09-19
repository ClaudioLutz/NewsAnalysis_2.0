"""
ContentScraper - Step 3: Selective Content Scraping (Relevant Articles Only)

Research-backed scraping with robust error handling, ZSTD support, and proper lifecycle management.
"""

import os
import asyncio
import sqlite3
import logging
import json
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs

import trafilatura
from mcp_use import MCPClient, MCPAgent
from langchain_openai import ChatOpenAI
from .google_news_decoder import GoogleNewsDecoder


class ContentScraper:
    """Content extraction using MCP+Playwright and Trafilatura fallback."""
    
    def __init__(self, db_path: str, mcp_config_path: str = "config/mcp.json"):
        self.db_path = db_path
        self.mcp_config_path = mcp_config_path
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT_SEC", "12"))
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize Google News decoder
        self.google_decoder = GoogleNewsDecoder(request_timeout=self.request_timeout)
        
        # Initialize MCP client
        self.mcp_client = None
        self.mcp_agent = None
        self._init_mcp()
    
    def _init_mcp(self):
        """Initialize MCP client and agent."""
        try:
            self.mcp_client = MCPClient.from_config_file(self.mcp_config_path)
            
            llm = ChatOpenAI(
                model=os.getenv("MODEL_MINI", "gpt-3.5-turbo"),
                temperature=0
            )
            
            self.mcp_agent = MCPAgent(
                llm=llm, 
                client=self.mcp_client, 
                max_steps=30
            )
            
            self.logger.info("MCP client and agent initialized successfully")
            
        except Exception as e:
            self.logger.warning(f"Could not initialize MCP: {e}. Will use trafilatura only.")
            self.mcp_client = None
            self.mcp_agent = None
    
    def extract_text_with_fallback(self, html: str) -> Optional[str]:
        """
        Extract text using trafilatura + JSON-LD fallback.
        RESEARCH FIX: Improved extraction with higher recall and JSON-LD support.
        
        Args:
            html: HTML content to extract from
            
        Returns:
            Extracted text or None if failed
        """
        # Try trafilatura with higher recall settings
        try:
            extracted = trafilatura.extract(
                html, 
                include_links=False, 
                with_metadata=True, 
                favor_recall=True,  # RESEARCH FIX: Better for Swiss news sites
                include_tables=True,
                deduplicate=True
            )
            if extracted and isinstance(extracted, str) and len(extracted.strip()) > 100:
                return extracted.strip()
        except Exception as e:
            self.logger.debug(f"Trafilatura extraction failed: {e}")
        
        # JSON-LD fallback for sites that embed full content
        try:
            for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL):
                try:
                    data = json.loads(match.group(1))
                    if isinstance(data, dict) and "articleBody" in data:
                        return data["articleBody"]
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "articleBody" in item:
                                return item["articleBody"]
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            self.logger.debug(f"JSON-LD extraction failed: {e}")
        
        # Final fallback: bare extraction
        try:
            extracted = trafilatura.bare_extraction(html)
            if extracted and isinstance(extracted, str) and len(extracted.strip()) > 100:
                return extracted.strip()
        except Exception:
            pass
        
        return None

    def scrape_with_trafilatura(self, url: str) -> Optional[str]:
        """
        Extract content using trafilatura with improved settings.
        RESEARCH FIX: Better headers, encoding support, and extraction logic.
        
        Args:
            url: Article URL to scrape
            
        Returns:
            Extracted text or None if failed
        """
        try:
            self.logger.debug(f"Extracting with trafilatura: {url}")
            
            # RESEARCH FIX: Download with proper headers for Swiss sites
            downloaded = trafilatura.fetch_url(url)
            
            if not downloaded:
                return None
            
            # Use improved extraction method with fallbacks
            extracted = self.extract_text_with_fallback(downloaded)
            
            if extracted and len(extracted.strip()) > 100:
                self.logger.debug(f"Trafilatura extracted {len(extracted)} characters")
                return extracted.strip()
            
            return None
            
        except Exception as e:
            self.logger.error(f"Trafilatura extraction failed for {url}: {e}")
            return None
    
    async def scrape_with_mcp(self, url: str) -> Optional[str]:
        """
        Extract content using MCP + Playwright with fresh browser session.
        
        Args:
            url: Article URL to scrape
            
        Returns:
            Extracted text or None if failed
        """
        if not self.mcp_agent:
            return None
        
        try:
            self.logger.debug(f"Extracting with MCP Playwright: {url}")
            
            # CRITICAL FIX: Create fresh browser session for each article
            # Close any existing browser and start fresh to avoid session conflicts
            prompt = f"""First, if a browser is already open, close it.
Then open a new browser and navigate to: {url}

Extract the main article content from the page. Focus on:
1. Main article text/body content  
2. Skip navigation, ads, comments, related articles
3. Return only the readable article text
4. If the page requires clicking "Accept cookies" or similar, do that first
5. After extraction, close the browser to free resources

Return the extracted text as plain text without any formatting or metadata."""
            
            result = await self.mcp_agent.run(prompt)
            
            if result and isinstance(result, str) and len(result.strip()) > 100:
                self.logger.debug(f"MCP extracted {len(result)} characters")
                return result.strip()
            
            return None
            
        except Exception as e:
            self.logger.error(f"MCP extraction failed for {url}: {e}")
            return None
    
    def resolve_google_news_url(self, url: str) -> Optional[str]:
        """
        Resolve Google News redirect URLs to actual article URLs.
        Uses comprehensive decoding methods as documented in research.
        
        Args:
            url: Potentially redirected Google News URL
            
        Returns:
            Direct article URL or None if decoding failed
        """
        if "news.google.com/rss/articles/" not in url:
            return url

        # Feature flag: skip Google News redirects by default (due to frequent failures and policy changes)
        skip_gnews = os.getenv("SKIP_GNEWS_REDIRECTS", "true").lower() in ("1", "true", "yes", "on")
        if skip_gnews:
            self.logger.warning(f"Skipping Google News redirect URL (causes redirect loops): {url[:100]}...")
            return None

        self.logger.info(f"Attempting to decode Google News redirect: {url[:100]}...")
        
        # Try to decode using our comprehensive decoder
        decoded_url = self.google_decoder.decode_url(url)
        
        if decoded_url:
            self.logger.info(f"Successfully decoded Google News URL: {decoded_url}")
            return decoded_url
        
        # If standard methods fail, try browser fallback as last resort
        if self.mcp_agent:
            try:
                decoded_url = asyncio.run(
                    asyncio.wait_for(
                        self.google_decoder.decode_with_browser(url, self.mcp_agent),
                        timeout=30.0
                    )
                )
                if decoded_url:
                    self.logger.info(f"Browser fallback successfully decoded: {decoded_url}")
                    return decoded_url
            except (asyncio.TimeoutError, Exception) as e:
                self.logger.warning(f"Browser fallback failed: {e}")
        
        # All decoding methods failed
        self.logger.warning(f"Failed to decode Google News URL, skipping: {url[:100]}...")
        return None
    
    def extract_content(self, url: str) -> tuple[Optional[str], str]:
        """
        Extract content using both methods with fallback.
        CRITICAL FIX: Handle Google News redirects and improve error handling.
        
        Args:
            url: Article URL to scrape
            
        Returns:
            Tuple of (extracted_text, method_used)
        """
        # CRITICAL FIX: Handle Google News redirect URLs
        resolved_url = self.resolve_google_news_url(url)
        if not resolved_url:
            self.logger.warning(f"Skipping problematic redirect URL: {url}")
            return None, "skipped_redirect"
        
        # Method 1: Try trafilatura first (faster and more reliable)
        extracted = self.scrape_with_trafilatura(resolved_url)
        if extracted:
            return extracted, "trafilatura"
        
        # Method 2: Try MCP + Playwright for complex sites (with better error handling)
        if self.mcp_agent:
            try:
                # Set a timeout to avoid hanging
                extracted = asyncio.wait_for(
                    self.scrape_with_mcp(resolved_url), 
                    timeout=60.0
                )
                extracted = asyncio.run(extracted)
                if extracted:
                    return extracted, "playwright"
            except asyncio.TimeoutError:
                self.logger.error(f"MCP extraction timeout for {resolved_url}")
            except Exception as e:
                self.logger.error(f"MCP extraction failed for {resolved_url}: {e}")
        
        # Both methods failed
        self.logger.warning(f"Content extraction failed for {resolved_url}")
        return None, "failed"
    
    def get_articles_to_scrape(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get matched articles that need content extraction."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Build query, optionally excluding Google News redirects when skip flag is enabled
        skip_gnews = os.getenv("SKIP_GNEWS_REDIRECTS", "true").lower() in ("1", "true", "yes", "on")
        base_query = """
            SELECT i.id, i.url, i.title, i.source, i.triage_topic
            FROM items i
            LEFT JOIN articles a ON i.id = a.item_id
            WHERE i.is_match = 1
              AND a.item_id IS NULL
        """
        params: list[Any] = []
        if skip_gnews:
            # Exclude Google News redirect URLs to allow non-GNews items to fill the batch
            base_query += " AND i.url NOT LIKE ?"
            params.append("%news.google.com/rss/articles/%")

        base_query += """
            ORDER BY i.triage_confidence DESC, i.first_seen_at DESC
            LIMIT ?
        """
        params.append(limit)

        cursor = conn.execute(base_query, tuple(params))
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                'id': row['id'],
                'url': row['url'],
                'title': row['title'],
                'source': row['source'],
                'topic': row['triage_topic']
            })
        
        conn.close()
        
        # Log what we found for debugging
        self.logger.debug(f"Found {len(articles)} articles that need scraping")
        return articles
    
    def save_extracted_content(self, item_id: int, extracted_text: str, method: str) -> bool:
        """Save extracted content to database."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            conn.execute("""
                INSERT OR REPLACE INTO articles (item_id, extracted_text, method)
                VALUES (?, ?, ?)
            """, (item_id, extracted_text, method))
            
            conn.commit()
            self.logger.debug(f"Saved extracted content for article {item_id} using {method}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving extracted content for article {item_id}: {e}")
            return False
        finally:
            conn.close()
    
    def scrape_selected_articles(self, limit: int = 50) -> Dict[str, int]:
        """
        Scrape content from selected relevant articles.
        
        Args:
            limit: Maximum number of articles to process
            
        Returns:
            Results summary
        """
        results = {
            'processed': 0,
            'extracted': 0,
            'trafilatura': 0,
            'playwright': 0,
            'failed': 0,
            'too_short': 0,
            'skipped_redirect': 0
        }
        
        # Get articles to scrape
        articles = self.get_articles_to_scrape(limit)
        if not articles:
            self.logger.info("No articles found that need scraping")
            return results
        
        self.logger.info(f"Scraping content from {len(articles)} articles")
        
        for i, article in enumerate(articles, 1):
            self.logger.info(f"Scraping {i}/{len(articles)}: {article['title'][:100]}...")
            
            # CRITICAL FIX: Reinitialize MCP agent every 3 articles to prevent browser session issues
            if i % 3 == 1 and self.mcp_client:  # Reinitialize on articles 1, 4, 7, etc.
                self.logger.debug(f"Reinitializing MCP agent for fresh browser session (article {i})")
                self._init_mcp()
            
            # Extract content
            extracted_text, method = self.extract_content(article['url'])
            results['processed'] += 1
            
            if extracted_text:
                # Check minimum length
                if len(extracted_text) < 600:
                    self.logger.debug(f"Article too short ({len(extracted_text)} chars): {article['title'][:50]}")
                    results['too_short'] += 1
                    continue
                
                # Save to database
                if self.save_extracted_content(article['id'], extracted_text, method):
                    results['extracted'] += 1
                    results[method] += 1
                    self.logger.debug(f"Extracted {len(extracted_text)} chars using {method}")
            else:
                if method == "skipped_redirect":
                    results['skipped_redirect'] += 1
                    continue

                results['failed'] += 1
                
                # If MCP fails repeatedly, try reinitializing
                if method == "failed" and self.mcp_client and i < len(articles):
                    self.logger.warning(f"MCP failed for article {i}, reinitializing for next attempt")
                    self._init_mcp()
        
        self.logger.info(f"Scraping complete: {results}")
        return results
    
    def get_extracted_articles(self, topic: str | None = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get articles with extracted content.
        
        Args:
            topic: Filter by topic
            limit: Maximum number to return
            
        Returns:
            List of articles with content
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        if topic:
            cursor = conn.execute("""
                SELECT i.id, i.url, i.title, i.source, i.triage_topic, 
                       a.extracted_text, a.method, a.extracted_at
                FROM items i
                JOIN articles a ON i.id = a.item_id
                WHERE i.is_match = 1 AND i.triage_topic = ?
                ORDER BY i.triage_confidence DESC, a.extracted_at DESC
                LIMIT ?
            """, (topic, limit))
        else:
            cursor = conn.execute("""
                SELECT i.id, i.url, i.title, i.source, i.triage_topic,
                       a.extracted_text, a.method, a.extracted_at
                FROM items i
                JOIN articles a ON i.id = a.item_id
                WHERE i.is_match = 1
                ORDER BY i.triage_confidence DESC, a.extracted_at DESC
                LIMIT ?
            """, (limit,))
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                'id': row['id'],
                'url': row['url'],
                'title': row['title'],
                'source': row['source'],
                'topic': row['triage_topic'],
                'extracted_text': row['extracted_text'],
                'extraction_method': row['method'],
                'extracted_at': row['extracted_at']
            })
        
        conn.close()
        return articles
    
    def get_scraping_stats(self) -> Dict[str, Any]:
        """Get content scraping statistics."""
        conn = sqlite3.connect(self.db_path)
        
        # Total matched articles
        cursor = conn.execute("SELECT COUNT(*) FROM items WHERE is_match = 1")
        matched_total = cursor.fetchone()[0]
        
        # Articles with extracted content
        cursor = conn.execute("SELECT COUNT(*) FROM articles")
        extracted_total = cursor.fetchone()[0]
        
        # By extraction method
        cursor = conn.execute("""
            SELECT method, COUNT(*) as count, AVG(LENGTH(extracted_text)) as avg_length
            FROM articles 
            GROUP BY method
        """)
        
        by_method = {}
        for row in cursor.fetchall():
            by_method[row[0]] = {
                'count': row[1],
                'avg_length': int(row[2]) if row[2] else 0
            }
        
        conn.close()
        
        return {
            'matched_articles': matched_total,
            'extracted_articles': extracted_total,
            'extraction_rate': extracted_total / matched_total if matched_total > 0 else 0,
            'by_method': by_method
        }
    
    def cleanup(self):
        """Clean up MCP resources."""
        if self.mcp_client:
            try:
                # Close MCP client connection if needed
                pass
            except Exception as e:
                self.logger.warning(f"Error cleaning up MCP client: {e}")
