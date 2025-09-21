#!/usr/bin/env python3
"""
Database migration script to create digest state tracking table.
Enables incremental digest generation for efficient daily updates.
"""

import sqlite3
import os
import sys
from pathlib import Path

# Add parent directory to path to import from news_pipeline
sys.path.insert(0, str(Path(__file__).parent.parent))

def create_digest_state_table(db_path: str):
    """Create the digest_state table for tracking incremental digest generation."""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create digest_state table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS digest_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            digest_date TEXT NOT NULL,
            topic TEXT NOT NULL,
            processed_article_ids TEXT NOT NULL, -- JSON array of article IDs
            digest_content TEXT NOT NULL,        -- JSON digest content
            article_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(digest_date, topic)
        )
    """)
    
    # Create index for efficient queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_digest_state_date_topic 
        ON digest_state(digest_date, topic)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_digest_state_date 
        ON digest_state(digest_date)
    """)
    
    # Create digest_generation_log table for tracking generation history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS digest_generation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            digest_date TEXT NOT NULL,
            generation_type TEXT NOT NULL, -- 'full' or 'incremental'
            topics_processed INTEGER NOT NULL,
            total_articles INTEGER NOT NULL,
            new_articles INTEGER DEFAULT 0,
            api_calls_made INTEGER DEFAULT 0,
            execution_time_seconds REAL,
            created_at TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()
    
    print(f"Successfully created digest state tracking tables in {db_path}")

def main():
    """Main function to run the migration."""
    
    # Default database path
    db_path = "news.db"
    
    # Check if custom db path provided
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"Error: Database {db_path} does not exist!")
        print("Run scripts/init_db.py first to create the database.")
        sys.exit(1)
    
    try:
        create_digest_state_table(db_path)
        print("Migration completed successfully!")
    except Exception as e:
        print(f"Error during migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
