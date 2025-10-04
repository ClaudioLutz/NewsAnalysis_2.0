#!/usr/bin/env python3
"""
Rerun Today's Pipeline - Testing Script

Completely resets today's matched articles and reruns the entire pipeline
to test fixes for cross-run deduplication and other features.

Usage:
    python scripts/rerun_todays_pipeline.py
"""

import os
import sys
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def reset_todays_articles(db_path: str = "news.db"):
    """Completely reset today's matched articles for reprocessing."""
    
    TZ = ZoneInfo("Europe/Zurich")
    today = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    today_iso = today.isoformat()
    
    print(f"\n{'='*70}")
    print("RERUN TODAY'S PIPELINE - RESET SCRIPT")
    print(f"{'='*70}\n")
    print(f"Date: {today.strftime('%Y-%m-%d')}")
    print(f"Cutoff: {today_iso}\n")
    
    conn = sqlite3.connect(db_path)
    
    # Get article IDs to reset
    cursor = conn.execute("""
        SELECT id, title, source FROM items
        WHERE triage_topic = 'creditreform_insights'
        AND is_match = 1
        AND (published_at >= ? OR (published_at IS NULL AND first_seen_at >= ?))
    """, (today_iso, today_iso))
    
    articles_to_reset = cursor.fetchall()
    
    if not articles_to_reset:
        print("❌ No articles found to reset")
        conn.close()
        return
    
    print(f"Found {len(articles_to_reset)} matched articles from today:\n")
    for i, (article_id, title, source) in enumerate(articles_to_reset[:10], 1):
        print(f"  {i}. [{source}] {title[:60]}...")
    if len(articles_to_reset) > 10:
        print(f"  ... and {len(articles_to_reset) - 10} more\n")
    
    article_ids = [row[0] for row in articles_to_reset]
    placeholders = ','.join('?' * len(article_ids))
    
    # Delete summaries
    cursor = conn.execute(f"""
        DELETE FROM summaries WHERE item_id IN ({placeholders})
    """, article_ids)
    summaries_deleted = cursor.rowcount
    
    # Delete scraped content
    cursor = conn.execute(f"""
        DELETE FROM articles WHERE item_id IN ({placeholders})
    """, article_ids)
    articles_deleted = cursor.rowcount
    
    # Delete cross-run topic signatures
    cursor = conn.execute(f"""
        DELETE FROM cross_run_topic_signatures WHERE source_article_id IN ({placeholders})
    """, article_ids)
    signatures_deleted = cursor.rowcount
    
    # Delete from article_clusters
    cursor = conn.execute(f"""
        DELETE FROM article_clusters WHERE article_id IN ({placeholders})
    """, article_ids)
    clusters_deleted = cursor.rowcount
    
    # Reset article state (items table) - clear classification to force re-filtering
    cursor = conn.execute(f"""
        UPDATE items 
        SET selected_for_processing = 0,
            selection_rank = NULL,
            pipeline_run_id = NULL,
            pipeline_stage = NULL,
            triage_topic = NULL,
            triage_confidence = NULL,
            is_match = 0
        WHERE id IN ({placeholders})
    """, article_ids)
    
    reset_count = cursor.rowcount
    
    # Also clear processed_links to allow re-classification
    cursor = conn.execute("""
        DELETE FROM processed_links 
        WHERE url IN (
            SELECT url FROM items WHERE id IN ({})
        )
    """.format(placeholders), article_ids)
    
    processed_links_deleted = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Reset Complete:")
    print(f"  - Reset {reset_count} articles (cleared classification)")
    print(f"  - Deleted {summaries_deleted} summaries")
    print(f"  - Deleted {articles_deleted} scraped content entries")
    print(f"  - Deleted {signatures_deleted} cross-run topic signatures")
    print(f"  - Deleted {clusters_deleted} cluster assignments")
    print(f"  - Deleted {processed_links_deleted} processed link records")
    print(f"\n{'='*70}")
    print("Ready to rerun pipeline!")
    print(f"{'='*70}\n")
    print("Run: python news_analyzer.py")
    print()

if __name__ == "__main__":
    reset_todays_articles()
