#!/usr/bin/env python3
"""
Load feed configurations from YAML into the database.
"""

import sqlite3
import yaml
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def load_feeds_from_config(config_path="config/feeds.yaml"):
    """Load feed configurations from YAML file into database."""
    db_path = os.getenv("DB_PATH", "./news.db")
    
    if not Path(config_path).exists():
        print(f"Error: Config file {config_path} not found")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    conn = sqlite3.connect(db_path)
    
    # Clear existing feeds
    conn.execute("DELETE FROM feeds")
    
    # Load RSS feeds
    if 'rss' in config:
        for source, urls in config['rss'].items():
            for url in urls:
                conn.execute(
                    "INSERT OR REPLACE INTO feeds (source, kind, url) VALUES (?, ?, ?)",
                    (source, 'rss', url)
                )
    
    # Load sitemap feeds  
    if 'sitemaps' in config:
        for source, urls in config['sitemaps'].items():
            for url in urls:
                conn.execute(
                    "INSERT OR REPLACE INTO feeds (source, kind, url) VALUES (?, ?, ?)",
                    (source, 'sitemap', url)
                )
    
    # Load HTML feeds
    if 'html' in config:
        for source, config_data in config['html'].items():
            conn.execute(
                "INSERT OR REPLACE INTO feeds (source, kind, url) VALUES (?, ?, ?)",
                (source, 'html', config_data['url'])
            )
    
    # Load Google News RSS feeds
    if 'google_news_rss' in config:
        for source, url in config['google_news_rss'].items():
            conn.execute(
                "INSERT OR REPLACE INTO feeds (source, kind, url) VALUES (?, ?, ?)",
                (f"google_news_{source}", 'rss', url)
            )
    
    conn.commit()
    
    # Print summary
    cursor = conn.execute("SELECT kind, COUNT(*) FROM feeds GROUP BY kind")
    print("Feeds loaded successfully:")
    for kind, count in cursor.fetchall():
        print(f"  {kind}: {count} feeds")
    
    cursor = conn.execute("SELECT COUNT(*) FROM feeds")
    total = cursor.fetchone()[0]
    print(f"Total: {total} feeds")
    
    conn.close()

if __name__ == "__main__":
    import sys
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/feeds.yaml"
    load_feeds_from_config(config_path)
