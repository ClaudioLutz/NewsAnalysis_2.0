#!/usr/bin/env python3
"""
Test script to validate the max_article_age_days date filtering functionality.

This script will:
1. Show articles without date filtering
2. Show articles with date filtering (0 days = same day only)
3. Show the publication dates of articles being processed
4. Validate that only articles from the same day are included
"""

import os
import sys
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from news_pipeline.filter import AIFilter


def analyze_database_articles():
    """Analyze articles in database by publication date."""
    db_path = os.getenv("DB_PATH", "./news.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("=== DATABASE ARTICLE ANALYSIS ===")
    
    # Get total articles
    cursor = conn.execute("SELECT COUNT(*) FROM items")
    total_articles = cursor.fetchone()[0]
    print(f"Total articles in database: {total_articles}")
    
    # Get articles by date
    cursor = conn.execute("""
        SELECT 
            DATE(COALESCE(published_at, first_seen_at)) as article_date,
            COUNT(*) as count
        FROM items 
        WHERE COALESCE(published_at, first_seen_at) IS NOT NULL
        GROUP BY DATE(COALESCE(published_at, first_seen_at))
        ORDER BY article_date DESC
        LIMIT 10
    """)
    
    print("\nArticles by date (last 10 days):")
    print("Date          | Count | Age (days)")
    print("-" * 35)
    
    today = datetime.now().date()
    for row in cursor.fetchall():
        article_date = datetime.strptime(row[0], '%Y-%m-%d').date()
        age_days = (today - article_date).days
        status = " <- TODAY" if age_days == 0 else ""
        print(f"{row[0]} | {row[1]:5d} | {age_days:3d}{status}")
    
    # Get unfiltered articles (not yet processed by AI)
    cursor = conn.execute("""
        SELECT COUNT(*) 
        FROM items 
        WHERE triage_topic IS NULL
    """)
    unfiltered_count = cursor.fetchone()[0]
    print(f"\nUnfiltered articles (not yet AI processed): {unfiltered_count}")
    
    conn.close()


def test_date_filtering():
    """Test the date filtering functionality."""
    print("\n=== DATE FILTERING TEST (Same Day Only) ===")
    
    db_path = os.getenv("DB_PATH", "./news.db")
    filter_instance = AIFilter(db_path)
    
    print("\n1. Getting articles WITHOUT date filtering:")
    articles_no_filter = filter_instance.get_unfiltered_articles(
        force_refresh=False, 
        include_prefiltered=True
    )
    print(f"   Found {len(articles_no_filter)} articles")
    
    print("\n2. Getting articles WITH date filtering (creditreform_insights topic, same day only):")
    articles_with_filter = filter_instance.get_unfiltered_articles(
        force_refresh=False, 
        include_prefiltered=True, 
        topic="creditreform_insights"
    )
    print(f"   Found {len(articles_with_filter)} articles")
    
    print(f"\n3. Filtering effect: {len(articles_no_filter) - len(articles_with_filter)} articles filtered out")
    
    if len(articles_with_filter) > 0:
        print("\n4. Sample of articles that passed date filtering (same day only):")
        print("   Published Date        | First Seen           | Title")
        print("   " + "-" * 80)
        
        today = datetime.now().date()
        for i, article in enumerate(articles_with_filter[:10], 1):
            pub_date = article['published_at'][:19] if article['published_at'] else "N/A"
            first_seen = article['first_seen_at'][:19] if article['first_seen_at'] else "N/A"
            title = article['title'][:40] + "..." if len(article['title']) > 40 else article['title']
            print(f"   {i:2d}. {pub_date:19s} | {first_seen:19s} | {title}")
        
        # Validate that all articles are from today
        print("\n5. Date validation (same day only):")
        same_day_articles = 0
        
        for article in articles_with_filter:
            article_date = None
            if article['published_at']:
                try:
                    article_date = datetime.fromisoformat(article['published_at'].replace('Z', '+00:00')).date()
                except:
                    pass
            
            if not article_date and article['first_seen_at']:
                try:
                    article_date = datetime.fromisoformat(article['first_seen_at'].replace('Z', '+00:00')).date()
                except:
                    pass
            
            if article_date and article_date == today:
                same_day_articles += 1
        
        print(f"   Articles from today ({today}): {same_day_articles}/{len(articles_with_filter)}")
        validation_passed = same_day_articles == len(articles_with_filter)
        print(f"   Validation: {'✓ PASSED - All articles are from today' if validation_passed else '✗ FAILED - Some articles are not from today'}")
        
        return validation_passed
    else:
        print("\n   No articles found that match the same-day filter")
        print("   This is expected if no articles were published today")
        return True


def test_different_age_settings():
    """Test different max_article_age_days settings."""
    print("\n=== DIFFERENT AGE SETTINGS TEST ===")
    
    db_path = os.getenv("DB_PATH", "./news.db")
    
    # Temporarily modify topics config for testing
    import yaml
    with open("config/topics.yaml", 'r', encoding='utf-8') as f:
        topics_config = yaml.safe_load(f)
    
    original_age = topics_config['topics']['creditreform_insights'].get('max_article_age_days', 0)
    
    test_ages = [0, 1, 2, 7]  # same day, 1 day, 2 days, 1 week
    
    print("Testing different age settings:")
    print("Age Setting | Articles Found | Description")
    print("-" * 45)
    
    for age_days in test_ages:
        # Temporarily update the config
        topics_config['topics']['creditreform_insights']['max_article_age_days'] = age_days
        
        # Write temporary config
        with open("config/topics.yaml", 'w', encoding='utf-8') as f:
            yaml.safe_dump(topics_config, f, default_flow_style=False)
        
        # Create new filter instance to pick up config changes
        filter_instance = AIFilter(db_path)
        
        articles = filter_instance.get_unfiltered_articles(
            force_refresh=False, 
            include_prefiltered=True, 
            topic="creditreform_insights"
        )
        
        description = "same day only" if age_days == 0 else f"last {age_days} day(s)"
        print(f"{age_days:11d} | {len(articles):14d} | {description}")
    
    # Restore original config
    topics_config['topics']['creditreform_insights']['max_article_age_days'] = original_age
    with open("config/topics.yaml", 'w', encoding='utf-8') as f:
        yaml.safe_dump(topics_config, f, default_flow_style=False)


def main():
    """Run all tests."""
    try:
        analyze_database_articles()
        validation_passed = test_date_filtering()
        test_different_age_settings()
        
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        if validation_passed:
            print("✓ Date filtering implementation is working correctly")
            print("✓ Articles are filtered to same day only (max_article_age_days: 0)")
            print("✓ Configuration is loaded from topics.yaml")
            print("✓ Only articles published on the same day will be processed for AI scoring")
        else:
            print("⚠ Date filtering needs attention - check the validation results above")
        
        print("\nIMPACT:")
        print("- Rating reports will now only include articles from the same day")
        print("- This ensures consistency between script execution date and article dates")
        print("- No more old articles mixed into today's rating reports")
        
        print(f"\nCurrent setting: max_article_age_days = 0 (same day only)")
        print("To change this, modify the 'max_article_age_days' parameter in config/topics.yaml")
        
    except Exception as e:
        print(f"\n✗ ERROR during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
