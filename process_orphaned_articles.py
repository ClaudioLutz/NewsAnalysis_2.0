#!/usr/bin/env python3
"""
Process orphaned selected articles through scraping, summarizing, and digest generation.
"""

import sqlite3
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from news_pipeline.scraper import ContentScraper
from news_pipeline.summarizer import ArticleSummarizer  
from news_pipeline.analyzer import MetaAnalyzer
from news_pipeline.utils import setup_logging

def process_orphaned_articles():
    setup_logging()
    logger = logging.getLogger(__name__)
    
    run_id = '5734a9a7-f53b-4ccc-b851-e085506ddb2f'  # The run ID from select_orphaned_articles
    
    logger.info(f"Processing orphaned articles for run: {run_id}")
    
    # Step 1: Scrape selected articles
    logger.info("Step 1: Scraping selected articles...")
    scraper = ContentScraper('news.db')
    scrape_result = scraper.scrape_selected_articles(limit=50)
    logger.info(f"Scraping completed: {scrape_result}")
    
    # Step 2: Summarize scraped articles
    logger.info("Step 2: Summarizing scraped articles...")
    summarizer = ArticleSummarizer('news.db')
    summary_result = summarizer.summarize_for_run(run_id=run_id, limit=50)
    logger.info(f"Summarization completed: {summary_result}")
    
    # Step 3: Generate daily digest
    logger.info("Step 3: Generating daily digest...")
    try:
        digest_generator = MetaAnalyzer('news.db')
        digest_result = digest_generator.export_daily_digest()
        logger.info(f"Digest generation completed: {digest_result}")
    except Exception as e:
        logger.error(f"Error generating digest: {e}")
        # Try alternative approach
        logger.info("Trying alternative digest generation...")
        digest_generator = MetaAnalyzer('news.db')
        digest_result = digest_generator.export_daily_digest()
        logger.info(f"Alternative digest generation completed")
    
    # Step 4: Check results
    conn = sqlite3.connect('news.db')
    
    # Count scraped articles
    cursor = conn.execute("""
        SELECT COUNT(*) FROM articles a
        INNER JOIN items i ON a.item_id = i.id
        WHERE i.pipeline_run_id = ?
    """, (run_id,))
    scraped_count = cursor.fetchone()[0]
    
    # Count summarized articles  
    cursor = conn.execute("""
        SELECT COUNT(*) FROM summaries s
        INNER JOIN items i ON s.item_id = i.id
        WHERE i.pipeline_run_id = ?
    """, (run_id,))
    summarized_count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n✅ PROCESSING COMPLETE")
    print(f"Run ID: {run_id}")
    print(f"Scraped articles: {scraped_count}")
    print(f"Summarized articles: {summarized_count}")
    print(f"Daily digest should now be available with these articles")

if __name__ == "__main__":
    process_orphaned_articles()
