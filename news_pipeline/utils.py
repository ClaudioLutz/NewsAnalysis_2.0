"""
Utility functions for the news pipeline.
"""

import hashlib
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from urllib.robotparser import RobotFileParser
from dateutil import parser as date_parser
import logging

def normalize_url(url: str) -> str:
    """
    Normalize URL by removing tracking parameters and fragments.
    
    Args:
        url: URL to normalize
        
    Returns:
        Normalized URL string
    """
    parsed = urlparse(url.lower())
    
    # Remove tracking parameters
    tracking_params = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
        'gclid', 'fbclid', 'dclid', 'gbraid', 'wbraid'
    }
    
    # Filter out tracking parameters and WT.* params
    query_params = parse_qs(parsed.query)
    clean_params = {
        k: v for k, v in query_params.items() 
        if k not in tracking_params and not k.startswith('WT.')
    }
    
    # Rebuild query string
    clean_query = urlencode(clean_params, doseq=True) if clean_params else ''
    
    # Rebuild URL without fragment
    clean_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        clean_query,
        ''  # Remove fragment
    ))
    
    return clean_url

def url_hash(url: str) -> str:
    """Generate SHA-1 hash for URL deduplication."""
    normalized = normalize_url(url)
    return hashlib.sha1(normalized.encode('utf-8')).hexdigest()

def is_allowed_by_robots(url: str, user_agent: str) -> bool:
    """
    Check if URL is allowed by robots.txt.
    
    Args:
        url: URL to check
        user_agent: User agent string
        
    Returns:
        True if allowed, False otherwise
    """
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        
        return rp.can_fetch(user_agent, url)
    except Exception as e:
        logging.warning(f"Could not check robots.txt for {url}: {e}")
        return True  # Allow if we can't check

def parse_date(date_str: str, fallback_format: str | None = None) -> str | None:
    """
    Parse date string to ISO 8601 format.
    
    Args:
        date_str: Date string to parse
        fallback_format: Specific format to try if general parsing fails
        
    Returns:
        ISO 8601 formatted date string or None
    """
    if not date_str:
        return None
        
    try:
        # Handle BusinessClassOst format (13.2.25 -> 2025-02-13)
        if re.match(r'\d{1,2}\.\d{1,2}\.\d{2}$', date_str):
            day, month, year = date_str.split('.')
            # Convert 2-digit year to 4-digit
            year = f"20{year}" if int(year) < 50 else f"19{year}"
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # Use dateutil parser for general cases
        parsed_date = date_parser.parse(date_str)
        return parsed_date.isoformat()
        
    except Exception as e:
        logging.warning(f"Could not parse date '{date_str}': {e}")
        return None

def jaccard_similarity(set1: set, set2: set) -> float:
    """Calculate Jaccard similarity between two sets."""
    if not set1 and not set2:
        return 1.0
    if not set1 or not set2:
        return 0.0
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    return intersection / union if union > 0 else 0.0

def title_similarity(title1: str, title2: str) -> float:
    """Calculate similarity between two titles using word tokens."""
    if not title1 or not title2:
        return 0.0
    
    # Convert to word sets (lowercase, remove punctuation)
    words1 = set(re.findall(r'\b\w+\b', title1.lower()))
    words2 = set(re.findall(r'\b\w+\b', title2.lower()))
    
    return jaccard_similarity(words1, words2)

def extract_canonical_url(html: str) -> str | None:
    """Extract canonical URL from HTML if present."""
    canonical_match = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', 
        html, 
        re.IGNORECASE
    )
    if canonical_match:
        return canonical_match.group(1)
    return None

def setup_logging(level: str = "INFO") -> logging.Logger:
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('news_pipeline.log', mode='a')
        ]
    )
    return logging.getLogger(__name__)
