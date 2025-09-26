#!/usr/bin/env python3
"""
Select orphaned matched articles that were never processed due to pipeline crashes.
"""

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
import uuid

def select_orphaned_articles():
    conn = sqlite3.connect('news.db')
    
    # Swiss timezone
    TZ = ZoneInfo("Europe/Zurich")
    today = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    today_iso = today.isoformat()
    
    print("=== SELECTING ORPHANED MATCHED ARTICLES ===")
    
    # Find matched articles from today that were never selected
    cursor = conn.execute("""
        SELECT id, title, triage_confidence, pipeline_run_id
        FROM items 
        WHERE is_match = 1 
        AND triage_topic = 'creditreform_insights'
        AND selected_for_processing = 0
        AND triage_confidence >= 0.71
        AND (published_at >= ? OR (published_at IS NULL AND first_seen_at >= ?))
        ORDER BY triage_confidence DESC
        LIMIT 35
    """, (today_iso, today_iso))
    
    orphaned_articles = cursor.fetchall()
    
    if not orphaned_articles:
        print("No orphaned articles found")
        return
    
    print(f"Found {len(orphaned_articles)} orphaned articles to select:\n")
    
    # Create a new pipeline run ID for these articles
    new_run_id = str(uuid.uuid4())
    print(f"Assigning to new pipeline run: {new_run_id}\n")
    
    # Select these articles for processing
    for rank, (article_id, title, confidence, old_run_id) in enumerate(orphaned_articles, 1):
        conn.execute("""
            UPDATE items 
            SET selected_for_processing = 1,
                selection_rank = ?,
                pipeline_stage = 'selected',
                pipeline_run_id = ?
            WHERE id = ?
        """, (rank, new_run_id, article_id))
        
        print(f"Rank {rank}: {title[:80]}... (confidence: {confidence:.2f})")
        if old_run_id != new_run_id:
            print(f"         Re-assigned from run {old_run_id} to {new_run_id}")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Successfully selected {len(orphaned_articles)} articles for processing")
    print(f"Pipeline run ID: {new_run_id}")
    print("\nNow run 'python news_analyzer.py' to scrape and summarize these articles")

if __name__ == "__main__":
    select_orphaned_articles()
