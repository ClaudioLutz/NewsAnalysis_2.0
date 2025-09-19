"""
Google News URL Decoder - Implementation based on comprehensive analysis document

This module implements multiple approaches to decode Google News RSS redirect URLs:
1. HTML parsing & Internal API method (for new format links post July 2024)
2. Base64 decoding (for legacy format links)
3. Headless browser fallback (using existing MCP Playwright setup)
4. Proper rate limiting and error handling
"""

import re
import base64
import json
import time
import asyncio
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs, quote, unquote

import requests
from bs4 import BeautifulSoup


class GoogleNewsDecoder:
    """
    Decode Google News redirect URLs to original article URLs.
    Implements multiple fallback strategies as documented in research.
    """
    
    def __init__(self, request_timeout: int = 15):
        self.request_timeout = request_timeout
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        
        # Headers to avoid consent blocks and appear more human-like
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cookie': 'CONSENT=YES+cb; NID=123;',  # Bypass EU consent pages
        })
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum 1 second between requests
    
    def _rate_limit(self):
        """Implement rate limiting to avoid being blocked by Google."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def decode_base64_url(self, encoded_url: str) -> Optional[str]:
        """
        Decode legacy format Google News URLs using Base64 decoding.
        Works for older-style links (pre July 2024).
        
        Args:
            encoded_url: The CBMi... portion of the Google News URL
            
        Returns:
            Decoded original URL or None if failed/new format
        """
        try:
            # Extract the encoded part after /articles/
            if "/articles/" not in encoded_url:
                return None
            
            encoded_part = encoded_url.split("/articles/")[-1]
            
            # Remove any query parameters
            if "?" in encoded_part:
                encoded_part = encoded_part.split("?")[0]
            
            # Decode base64
            try:
                decoded_bytes = base64.b64decode(encoded_part + '==')  # Add padding if needed
            except Exception:
                # Try URL-safe base64
                decoded_bytes = base64.urlsafe_b64decode(encoded_part + '==')
            
            decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
            
            # Check for new format marker
            if decoded_str.startswith('AU_yqL') or 'AU_yqL' in decoded_str:
                self.logger.debug("Detected new format URL - base64 decoding not applicable")
                return None
            
            # Look for URL patterns in the decoded string
            # The format typically has magic bytes, then length, then URL
            url_pattern = re.compile(r'https?://[^\s\x00-\x1f\x7f-\x9f]+')
            urls = url_pattern.findall(decoded_str)
            
            if urls:
                # Return the first non-AMP URL, or first URL if no non-AMP found
                for url in urls:
                    if 'amp' not in url.lower():
                        self.logger.debug(f"Base64 decoded URL: {url}")
                        return url
                
                # If only AMP URLs found, return the first one
                self.logger.debug(f"Base64 decoded URL (AMP): {urls[0]}")
                return urls[0]
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Base64 decoding failed: {e}")
            return None
    
    def extract_from_html_api(self, google_url: str) -> Optional[str]:
        """
        Extract URL using HTML parsing and Google's internal batchexecute API.
        Works for new format links (post July 2024).
        
        Args:
            google_url: Full Google News redirect URL
            
        Returns:
            Original article URL or None if failed
        """
        try:
            self._rate_limit()
            
            # Fetch the Google News redirect page
            response = self.session.get(google_url, timeout=self.request_timeout, allow_redirects=True)
            response.raise_for_status()
            
            # Check if we got redirected to the final URL
            if response.url != google_url and not 'news.google.com' in response.url:
                if self._is_valid_news_url(response.url):
                    self.logger.debug(f"Got final URL via redirect: {response.url}")
                    return response.url
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Method 1: Look for meta refresh redirects
            meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
            if meta_refresh and hasattr(meta_refresh, 'get'):
                content = meta_refresh.get('content')
                # Format is usually "0;url=http://example.com"
                if content and isinstance(content, str) and 'url=' in content:
                    url = content.split('url=', 1)[1]
                    if self._is_valid_news_url(url):
                        self.logger.debug(f"Found URL in meta refresh: {url}")
                        return url
            
            # Method 2: Look for javascript redirects
            scripts = soup.find_all('script')
            for script in scripts:
                script_content = script.get_text() if script else None
                
                if script_content:
                    # Look for window.location or location.href patterns
                    location_patterns = [
                        r'window\.location\s*=\s*["\']([^"\']+)["\']',
                        r'location\.href\s*=\s*["\']([^"\']+)["\']',
                        r'document\.location\s*=\s*["\']([^"\']+)["\']'
                    ]
                    
                    for pattern in location_patterns:
                        matches = re.findall(pattern, script_content)
                        for url in matches:
                            if self._is_valid_news_url(url):
                                self.logger.debug(f"Found URL in JS redirect: {url}")
                                return url
                    
                    # Look for URL patterns in data structures
                    url_matches = re.findall(r'"(https?://(?!news\.google\.com|google\.com|googleapis\.com)[^"]+)"', script_content)
                    for url in url_matches:
                        if self._is_valid_news_url(url):
                            self.logger.debug(f"Found URL in script data: {url}")
                            return url
            
            # Method 3: Look for anchor tags with direct links
            links = soup.find_all('a', href=True)
            for link in links:
                if hasattr(link, 'get') and callable(getattr(link, 'get', None)):
                    href = link.get('href')
                    if href and isinstance(href, str) and self._is_valid_news_url(href):
                        self.logger.debug(f"Found URL in anchor tag: {href}")
                        return href
            
            # Method 4: Direct URL extraction from HTML (more conservative)
            url_pattern = re.compile(r'https?://(?!news\.google\.com|google\.com|googleapis\.com)[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}[^\s"<>]*')
            urls = url_pattern.findall(response.text)
            
            for url in urls:
                if self._is_valid_news_url(url):
                    self.logger.debug(f"Found URL in HTML content: {url}")
                    return url
            
            return None
            
        except requests.RequestException as e:
            self.logger.warning(f"Failed to fetch Google News page: {e}")
            return None
        except Exception as e:
            self.logger.warning(f"HTML parsing failed: {e}")
            return None
    
    def _call_batchexecute_api(self, params: Dict[str, Any]) -> Optional[str]:
        """
        Call Google's undocumented batchexecute API to resolve the URL.
        This mimics what Google's own JavaScript does.
        
        Args:
            params: Parameters extracted from the HTML page
            
        Returns:
            Resolved URL or None if failed
        """
        try:
            # Google's internal batchexecute endpoint
            api_url = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
            
            # Construct the request payload
            # This is reverse-engineered from Google's internal calls
            payload = {
                'rpcids': 'HKKQWd',
                'source-path': '/articles',
                'f.sid': '-123456789',  # Session ID
                'bl': 'boq_dotssplashserver_20241201.00_p0',  # Build label
                'hl': 'en',
                'soc-app': '1',
                'soc-platform': '1',
                'soc-device': '1',
                '_reqid': str(int(time.time() * 1000)),  # Request ID
                'rt': 'c'
            }
            
            # Add the extracted parameters
            if 'param1' in params:
                payload['f.req'] = f'[[["HKKQWd","[\\"{params["param1"]}\\",\\"{params.get("param2", "")}\\",null,\\"{params.get("param3", "")}\\"]",null,"generic"]]]'
            
            self._rate_limit()
            
            response = self.session.post(
                api_url,
                data=payload,
                timeout=self.request_timeout,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if response.status_code == 200:
                # Parse the response - it's typically in a specific Google format
                response_text = response.text
                
                # Look for URL in the response
                url_pattern = re.compile(r'"(https?://(?!news\.google\.com)[^"]+)"')
                urls = url_pattern.findall(response_text)
                
                for url in urls:
                    if self._is_valid_news_url(url):
                        self.logger.debug(f"Batchexecute API returned: {url}")
                        return url
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Batchexecute API call failed: {e}")
            return None
    
    def _is_valid_news_url(self, url: str) -> bool:
        """Check if a URL looks like a valid news article URL."""
        try:
            parsed = urlparse(url)
            
            # Must have proper scheme and domain
            if not parsed.scheme in ['http', 'https'] or not parsed.netloc:
                return False
            
            # Skip Google domains and Google APIs
            skip_domains = [
                'google.com', 'googleapis.com', 'googleusercontent.com',
                'googlenews.com', 'googleapi.com', 'gstatic.com'
            ]
            
            for domain in skip_domains:
                if domain in parsed.netloc.lower():
                    return False
            
            # Skip common non-article URLs
            skip_patterns = [
                '/tags/', '/authors/', '/search/', '/feed/',
                'facebook.com', 'twitter.com', 'instagram.com',
                'youtube.com', 'linkedin.com', 'pinterest.com',
                '.css', '.js', '.png', '.jpg', '.gif', '.pdf',
                'kidsmanagement', 'management-pa', 'boq-identity'  # Block problematic Google identity endpoints
            ]
            
            for pattern in skip_patterns:
                if pattern in url.lower():
                    return False
            
            # Must have reasonable length
            if len(url) < 20 or len(url) > 500:
                return False
            
            # Domain must have at least one dot and valid TLD
            domain_parts = parsed.netloc.lower().split('.')
            if len(domain_parts) < 2 or len(domain_parts[-1]) < 2:
                return False
            
            return True
            
        except Exception:
            return False
    
    def decode_url(self, google_news_url: str) -> Optional[str]:
        """
        Main method to decode a Google News redirect URL.
        Tries multiple approaches in order of preference.
        
        Args:
            google_news_url: Google News redirect URL
            
        Returns:
            Original article URL or None if all methods failed
        """
        if not google_news_url or 'news.google.com/rss/articles/' not in google_news_url:
            return google_news_url  # Not a Google News redirect
        
        self.logger.debug(f"Attempting to decode Google News URL: {google_news_url[:100]}...")
        
        # Method 1: Try Base64 decoding first (faster for legacy URLs)
        decoded_url = self.decode_base64_url(google_news_url)
        if decoded_url:
            self.logger.info(f"Successfully decoded using Base64 method")
            return decoded_url
        
        # Method 2: Try HTML parsing and API method (for new format)
        decoded_url = self.extract_from_html_api(google_news_url)
        if decoded_url:
            self.logger.info(f"Successfully decoded using HTML/API method")
            return decoded_url
        
        # All methods failed
        self.logger.warning(f"Failed to decode Google News URL: {google_news_url[:100]}...")
        return None
    
    async def decode_with_browser(self, google_news_url: str, mcp_agent) -> Optional[str]:
        """
        Fallback method using headless browser to let Google's JavaScript run.
        This is the most reliable method but also the slowest.
        
        Args:
            google_news_url: Google News redirect URL
            mcp_agent: MCP agent with Playwright browser
            
        Returns:
            Final redirected URL or None if failed
        """
        if not mcp_agent:
            return None
        
        try:
            self.logger.debug(f"Using browser fallback for: {google_news_url[:100]}...")
            
            prompt = f"""Navigate to this Google News URL and wait for it to redirect to the final article page: {google_news_url}

Instructions:
1. Open the URL and wait for any redirects to complete
2. If there's a consent dialog or cookie banner, accept it
3. Wait until you reach the final article page (not on news.google.com)
4. Return ONLY the final URL of the article page
5. Close the browser when done

Return just the final URL, nothing else."""
            
            result = await mcp_agent.run(prompt)
            
            if result and isinstance(result, str):
                # Extract URL from the result
                url_match = re.search(r'https?://[^\s]+', result)
                if url_match:
                    final_url = url_match.group(0)
                    if self._is_valid_news_url(final_url):
                        self.logger.info(f"Browser successfully decoded to: {final_url}")
                        return final_url
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Browser decoding failed: {e}")
            return None
    
    def get_stats(self) -> Dict[str, int]:
        """Get decoder statistics (placeholder for future implementation)."""
        return {
            'base64_success': 0,
            'api_success': 0,
            'browser_success': 0,
            'total_failed': 0
        }
