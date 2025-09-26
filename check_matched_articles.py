#!/usr/bin/env python3
"""
Check matched articles in database that need processing.
"""

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

def check_matched_articles():
    conn = sqlite3.connect('news.db')
    conn.row_factory = sqlite3.Row
    
    # Swiss timezone
    TZ = ZoneInfo("Europe/Zurich")
    today = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    today_iso = today.isoformat()
    
    print("=== MATCHED ARTICLES STATUS ===")
    
    # Get all matched articles from today
    cursor = conn.execute("""
        SELECT id, title, url, triage_confidence, pipeline_stage, 
               selected_for_processing, first_seen_at, published_at
        FROM items 
        WHERE is_match = 1 
        AND triage_topic = 'creditreform_insights'
        AND (published_at >= ? OR (published_at IS NULL AND first_seen_at >= ?))
        ORDER BY triage_confidence DESC
    """, (today_iso, today_iso))
    
    articles = cursor.fetchall()
    
    if not articles:
        print("No matched articles found for today")
        return
    
    print(f"Found {len(articles)} matched articles from today:\n")
    
    for i, article in enumerate(articles, 1):
        print(f"{i}. ID: {article['id']}")
        print(f"   Title: {article['title'][:100]}...")
        print(f"   Confidence: {article['triage_confidence']:.2f}")
        print(f"   Stage: {article['pipeline_stage']}")
        print(f"   Selected: {'Yes' if article['selected_for_processing'] else 'No'}")
        print(f"   URL: {article['url']}")
        print()
    
    # Check if any have summaries
    cursor = conn.execute("""
        SELECT COUNT(*) FROM items i
        INNER JOIN summaries s ON i.id = s.item_id
        WHERE i.is_match = 1 
        AND i.triage_topic = 'creditreform_insights'
        AND (i.published_at >= ? OR (i.published_at IS NULL AND i.first_seen_at >= ?))
    """, (today_iso, today_iso))
    
    summarized_count = cursor.fetchone()[0]
    print(f"Articles with summaries: {summarized_count}")
    
    # Check pipeline stages
    cursor = conn.execute("""
        SELECT pipeline_stage, COUNT(*) as count
        FROM items 
        WHERE is_match = 1 
        AND triage_topic = 'creditreform_insights'
        AND (published_at >= ? OR (published_at IS NULL AND first_seen_at >= ?))
        GROUP BY pipeline_stage
        ORDER BY count DESC
    """, (today_iso, today_iso))
    
    print("\nPipeline stages:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} articles")
    
    conn.close()

if __name__ == "__main__":
    check_matched_articles()
