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

def is_allowed_by_robots(url: str, user_agent: str, respect_robots: bool = True) -> bool:
    """
    Check if URL is allowed by robots.txt.
    
    Args:
        url: URL to check
        user_agent: User agent string
        respect_robots: Whether to respect robots.txt (default: True)
        
    Returns:
        True if allowed, False otherwise
    """
    if not respect_robots:
        return True
        
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
    """Set up enhanced logging configuration with better formatting."""
    import sys
    
    # Create formatter with better format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Console handler with custom formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # File handler
    file_handler = logging.FileHandler('news_pipeline.log', mode='a')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Reduce noise from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)


def log_progress(logger: logging.Logger, current: int, total: int, operation: str = "Processing", prefix: str = "") -> None:
    """
    Log progress with percentage and progress bar.
    
    Args:
        logger: Logger instance
        current: Current item number
        total: Total items to process
        operation: Operation being performed
        prefix: Optional prefix for the log message
    """
    if total == 0:
        return
        
    percentage = (current / total) * 100
    bar_length = 20
    filled_length = int(bar_length * current / total)
    bar = '#' * filled_length + '-' * (bar_length - filled_length)
    
    message = f"{prefix}{operation}: [{bar}] {current}/{total} ({percentage:.1f}%)"
    logger.info(message)


def log_step_start(logger: logging.Logger, step_name: str, description: str = "") -> None:
    """Log the start of a pipeline step with clear formatting."""
    logger.info(f"\n{'='*60}")
    logger.info(f">> {step_name}")
    if description:
        logger.info(f"   {description}")
    logger.info(f"{'='*60}")


def log_step_complete(logger: logging.Logger, step_name: str, duration: float, results: dict | None = None) -> None:
    """Log the completion of a pipeline step with results."""
    logger.info(f"\n[COMPLETED] {step_name} in {duration:.1f}s")
    if results:
        for key, value in results.items():
            logger.info(f"   * {key}: {value}")
    logger.info(f"{'-'*60}")


def log_error_with_context(logger: logging.Logger, error: Exception, context: str) -> None:
    """Log error with additional context."""
    logger.error(f"[ERROR] {context}: {type(error).__name__}: {str(error)}")


def format_number(num: int) -> str:
    """Format numbers with thousand separators."""
    return f"{num:,}"


def format_rate(success: int, total: int) -> str:
    """Format success rate as percentage."""
    if total == 0:
        return "0%"
    return f"{(success/total)*100:.1f}%"
