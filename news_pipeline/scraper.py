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
        RESEARCH FIX: Better headers, encoding support, and ZSTD compression handling.
        
        Args:
            url: Article URL to scrape
            
        Returns:
            Extracted text or None if failed
        """
        try:
            self.logger.debug(f"Extracting with trafilatura: {url}")
            
            # CRITICAL FIX: Handle ZSTD compression and other encoding issues
            # Use custom headers to avoid ZSTD compression which causes parsing errors
            import requests
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',  # Avoid ZSTD compression
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            try:
                # Custom download with proper headers
                response = requests.get(url, headers=headers, timeout=self.request_timeout)
                response.raise_for_status()
                downloaded = response.text
            except Exception as req_error:
                self.logger.debug(f"Custom download failed: {req_error}, falling back to trafilatura")
                # Fallback to trafilatura's built-in download
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
                extracted = asyncio.run(
                    asyncio.wait_for(
                        self.scrape_with_mcp(resolved_url), 
                        timeout=60.0
                    )
                )
                if extracted:
                    return extracted, "playwright"
            except asyncio.TimeoutError:
                self.logger.error(f"MCP extraction timeout for {resolved_url}")
            except Exception as e:
                self.logger.error(f"MCP extraction failed for {resolved_url}: {e}")
        
        # Both methods failed
        self.logger.warning(f"Content extraction failed for {resolved_url}")
        return None, "failed"
    
    def get_articles_to_scrape(self, limit: int = 50, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get articles that need content extraction.
        
        Args:
            limit: Maximum number of articles to return
            run_id: If provided, only get selected articles from this run
            
        Returns:
            List of articles to scrape
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Build query, optionally excluding Google News redirects when skip flag is enabled
        skip_gnews = os.getenv("SKIP_GNEWS_REDIRECTS", "true").lower() in ("1", "true", "yes", "on")
        
        if run_id:
            # NEW: Only get selected articles from a specific pipeline run
            base_query = """
                SELECT i.id, i.url, i.title, i.source, i.triage_topic, 
                       i.triage_confidence, i.selection_rank
                FROM items i
                LEFT JOIN articles a ON i.id = a.item_id
                WHERE i.pipeline_run_id = ?
                  AND i.selected_for_processing = 1
                  AND i.pipeline_stage = 'selected'
                  AND (a.item_id IS NULL OR (a.extracted_text IS NULL AND COALESCE(a.failure_count, 0) < 3))
            """
            params: List[Any] = [run_id]
        else:
            # Legacy: Get all matched articles (for backward compatibility)
            base_query = """
                SELECT i.id, i.url, i.title, i.source, i.triage_topic
                FROM items i
                LEFT JOIN articles a ON i.id = a.item_id
                WHERE i.is_match = 1
                  AND (a.item_id IS NULL OR (a.extracted_text IS NULL AND COALESCE(a.failure_count, 0) < 3))
            """
            params = []
        
        if skip_gnews:
            # Exclude Google News redirect URLs to allow non-GNews items to fill the batch
            base_query += " AND i.url NOT LIKE ?"
            params.append("%news.google.com/rss/articles/%")
        
        # Order by selection rank if available, otherwise by confidence
        if run_id:
            base_query += " ORDER BY i.selection_rank, i.triage_confidence DESC"
        else:
            base_query += " ORDER BY i.triage_confidence DESC, i.first_seen_at DESC"
        
        base_query += " LIMIT ?"
        params.append(limit)
        
        cursor = conn.execute(base_query, tuple(params))
        
        articles = []
        for row in cursor.fetchall():
            article = {
                'id': row['id'],
                'url': row['url'],
                'title': row['title'],
                'source': row['source'],
                'topic': row['triage_topic']
            }
            
            # Add rank and confidence if available
            if run_id:
                article['confidence'] = row['triage_confidence']
                article['rank'] = row['selection_rank']
            
            articles.append(article)
        
        conn.close()
        
        # Log what we found for debugging
        if run_id:
            self.logger.info(f"Found {len(articles)} selected articles to scrape for run {run_id}")
            if articles and 'rank' in articles[0]:
                self.logger.debug(f"Articles ordered by selection rank: {[a['rank'] for a in articles[:5]]}")
        else:
            self.logger.debug(f"Found {len(articles)} articles that need scraping")
        
        return articles
    
    def save_extracted_content(self, item_id: int, extracted_text: str, method: str, 
                              run_id: Optional[str] = None) -> bool:
        """Save extracted content to database and update pipeline stage."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Save extracted content
            conn.execute("""
                INSERT OR REPLACE INTO articles (item_id, extracted_text, extraction_method)
                VALUES (?, ?, ?)
            """, (item_id, extracted_text, method))
            
            # Update pipeline stage if run_id provided
            if run_id:
                conn.execute("""
                    UPDATE items 
                    SET pipeline_stage = 'scraped'
                    WHERE id = ? AND pipeline_run_id = ?
                """, (item_id, run_id))
            
            conn.commit()
            self.logger.debug(f"Saved extracted content for article {item_id} using {method}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving extracted content for article {item_id}: {e}")
            return False
        finally:
            conn.close()

    def mark_article_failed(self, item_id: int, error_reason: str) -> bool:
        """Mark article as failed to prevent infinite retries."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            # First check if there's already a failure record
            cursor = conn.execute("""
                SELECT failure_count FROM articles WHERE item_id = ? AND extracted_text IS NULL
            """, (item_id,))
            existing = cursor.fetchone()
            
            if existing:
                # Update failure count
                new_count = existing[0] + 1
                conn.execute("""
                    UPDATE articles 
                    SET failure_count = ?, last_failure_reason = ?, extracted_at = CURRENT_TIMESTAMP
                    WHERE item_id = ?
                """, (new_count, error_reason, item_id))
            else:
                # Insert new failure record
                conn.execute("""
                    INSERT OR REPLACE INTO articles (item_id, extracted_text, extraction_method, failure_count, last_failure_reason)
                    VALUES (?, NULL, 'failed', 1, ?)
                """, (item_id, error_reason))
            
            conn.commit()
            self.logger.debug(f"Marked article {item_id} as failed: {error_reason}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error marking article {item_id} as failed: {e}")
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
        return self._scrape_articles_impl(limit, run_id=None)
    
    def scrape_for_run(self, run_id: str, limit: Optional[int] = None) -> Dict[str, int]:
        """
        Scrape content for selected articles in a specific pipeline run.
        
        Args:
            run_id: Pipeline run identifier
            limit: Maximum number of articles to process (default: from config)
            
        Returns:
            Results summary including selected article statistics
        """
        if limit is None:
            # Use max_articles from config
            import yaml
            try:
                with open("config/pipeline_config.yaml", 'r') as f:
                    config = yaml.safe_load(f)
                    limit = config['pipeline']['filtering'].get('max_articles_to_process', 35)
            except:
                limit = 35
        
        # Ensure limit is not None for type safety
        limit_value: int = limit if limit is not None else 35
        
        self.logger.info(f"Starting scraping for pipeline run {run_id} (limit: {limit_value})")
        return self._scrape_articles_impl(limit_value, run_id)
    
    def _scrape_articles_impl(self, limit: int, run_id: Optional[str]) -> Dict[str, int]:
        """
        Internal implementation of article scraping.
        
        Args:
            limit: Maximum number of articles to process
            run_id: Pipeline run identifier (if processing selected articles)
            
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
        articles = self.get_articles_to_scrape(limit, run_id)
        if not articles:
            self.logger.info("No articles found that need scraping")
            return results
        
        self.logger.info(f"Scraping content from {len(articles)} {'selected' if run_id else ''} articles")
        
        for i, article in enumerate(articles, 1):
            if 'rank' in article:
                self.logger.info(f"Scraping {i}/{len(articles)} [Rank {article['rank']}]: {article['title'][:100]}...")
            else:
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
                    # Mark as failed due to insufficient content
                    self.mark_article_failed(article['id'], f"content_too_short_{len(extracted_text)}_chars")
                    continue
                
                # Save to database with run_id to update pipeline stage
                if self.save_extracted_content(article['id'], extracted_text, method, run_id):
                    results['extracted'] += 1
                    results[method] += 1
                    self.logger.debug(f"Extracted {len(extracted_text)} chars using {method}")
            else:
                if method == "skipped_redirect":
                    results['skipped_redirect'] += 1
                    # Mark as failed due to redirect issues
                    self.mark_article_failed(article['id'], "skipped_google_news_redirect")
                    continue

                results['failed'] += 1
                
                # Mark the article as failed to prevent retries
                error_reason = f"extraction_failed_{method}"
                self.mark_article_failed(article['id'], error_reason)
                
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
                if hasattr(self.mcp_client, 'close'):
                    self.mcp_client.close()
                self.mcp_client = None
                self.mcp_agent = None
            except Exception as e:
                self.logger.warning(f"Error cleaning up MCP client: {e}")
