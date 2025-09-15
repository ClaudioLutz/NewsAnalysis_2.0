"""
ContentScraper - Step 3: Selective Content Scraping (Relevant Articles Only)

MCP + Playwright integration with trafilatura fallback for content extraction.
"""

import os
import asyncio
import sqlite3
import logging
from typing import List, Dict, Any, Optional

import trafilatura
from mcp_use import MCPClient, MCPAgent
from langchain_openai import ChatOpenAI


class ContentScraper:
    """Content extraction using MCP+Playwright and Trafilatura fallback."""
    
    def __init__(self, db_path: str, mcp_config_path: str = "config/mcp.json"):
        self.db_path = db_path
        self.mcp_config_path = mcp_config_path
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT_SEC", "12"))
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize MCP client
        self.mcp_client = None
        self.mcp_agent = None
        self._init_mcp()
    
    def _init_mcp(self):
        """Initialize MCP client and agent."""
        try:
            self.mcp_client = MCPClient.from_config_file(self.mcp_config_path)
            
            llm = ChatOpenAI(
                model=os.getenv("MODEL_MINI", "gpt-5-mini"),
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
    
    def scrape_with_trafilatura(self, url: str) -> Optional[str]:
        """
        Extract content using trafilatura.
        
        Args:
            url: Article URL to scrape
            
        Returns:
            Extracted text or None if failed
        """
        try:
            self.logger.debug(f"Extracting with trafilatura: {url}")
            
            # Download and extract
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                return None
            
            extracted = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=True,
                include_formatting=False,
                favor_precision=True,
                deduplicate=True
            )
            
            if extracted and len(extracted.strip()) > 100:
                self.logger.debug(f"Trafilatura extracted {len(extracted)} characters")
                return extracted.strip()
            
            return None
            
        except Exception as e:
            self.logger.error(f"Trafilatura extraction failed for {url}: {e}")
            return None
    
    async def scrape_with_mcp(self, url: str) -> Optional[str]:
        """
        Extract content using MCP + Playwright.
        
        Args:
            url: Article URL to scrape
            
        Returns:
            Extracted text or None if failed
        """
        if not self.mcp_agent:
            return None
        
        try:
            self.logger.debug(f"Extracting with MCP Playwright: {url}")
            
            # Create prompt for MCP agent
            prompt = f"""Navigate to the URL: {url}

Extract the main article content from the page. Focus on:
1. Main article text/body content
2. Skip navigation, ads, comments, related articles
3. Return only the readable article text
4. If the page requires clicking "Accept cookies" or similar, do that first

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
        
        Args:
            url: Potentially redirected Google News URL
            
        Returns:
            Direct article URL or resolved URL
        """
        if "news.google.com/rss/articles/" not in url:
            return url
            
        # Try to follow Google News redirects
        try:
            import requests
            
            # Try to follow redirects to get the actual URL
            self.logger.debug(f"Attempting to resolve Google News redirect: {url}")
            
            response = requests.head(url, allow_redirects=True, timeout=10)
            resolved_url = response.url
            
            # Check if we got a different URL
            if resolved_url != url and "google.com" not in resolved_url:
                self.logger.info(f"Resolved Google News URL: {url} -> {resolved_url}")
                return resolved_url
            else:
                # Fallback: try with requests.get to handle JavaScript redirects
                response = requests.get(url, timeout=10, allow_redirects=True)
                if response.url != url and "google.com" not in response.url:
                    self.logger.info(f"Resolved Google News URL via GET: {url} -> {response.url}")
                    return response.url
                
                # If still a Google URL, try to use the original URL anyway
                # Trafilatura and MCP might be able to handle it
                self.logger.warning(f"Could not resolve Google News redirect, using original: {url}")
                return url
                
        except Exception as e:
            self.logger.warning(f"Error resolving Google News URL {url}: {e}")
            # Don't skip entirely, try to use the original URL
            return url
    
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
        
        cursor = conn.execute("""
            SELECT i.id, i.url, i.title, i.source, i.triage_topic
            FROM items i
            LEFT JOIN articles a ON i.id = a.item_id
            WHERE i.is_match = 1 
            AND a.item_id IS NULL
            ORDER BY i.triage_confidence DESC, i.first_seen_at DESC
            LIMIT ?
        """, (limit,))
        
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
            'too_short': 0
        }
        
        # Get articles to scrape
        articles = self.get_articles_to_scrape(limit)
        if not articles:
            self.logger.info("No articles found that need scraping")
            return results
        
        self.logger.info(f"Scraping content from {len(articles)} articles")
        
        for article in articles:
            self.logger.info(f"Scraping: {article['title'][:100]}...")
            
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
                results['failed'] += 1
        
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
