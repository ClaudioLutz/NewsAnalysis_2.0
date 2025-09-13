"""
AI-Powered News Analysis Pipeline

A streamlined 5-step workflow that leverages GPT-5 models for smart filtering and summarization.
"""

__version__ = "1.0.0"

from .collector import NewsCollector
from .filter import AIFilter
from .scraper import ContentScraper
from .summarizer import ArticleSummarizer
from .analyzer import MetaAnalyzer

__all__ = [
    "NewsCollector",
    "AIFilter", 
    "ContentScraper",
    "ArticleSummarizer",
    "MetaAnalyzer"
]
