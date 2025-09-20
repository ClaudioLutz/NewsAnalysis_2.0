#!/usr/bin/env python3
"""
Migrate the articles table to support failure tracking.
"""

import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

def migrate_articles_table():
    """Add failure tracking columns to articles table."""
    db_path = os.getenv("DB_PATH", "./news.db")
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} does not exist. Please run init_db.py first.")
        return
    
    conn = sqlite3.connect(db_path)
    
    try:
        # Check if migration is needed by checking for failure_count column
        cursor = conn.execute("PRAGMA table_info(articles)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'failure_count' in columns:
            print("Migration already applied - failure tracking columns exist")
            conn.close()
            return
        
        print("Applying migration to add failure tracking columns...")
        
        # Add new columns to articles table
        migration_sql = """
        -- Add failure tracking columns
        ALTER TABLE articles ADD COLUMN failure_count INTEGER DEFAULT 0;
        ALTER TABLE articles ADD COLUMN last_failure_reason TEXT;
        
        -- Rename method to extraction_method for consistency
        -- SQLite doesn't support column renaming directly, so we'll create new column
        ALTER TABLE articles ADD COLUMN extraction_method TEXT CHECK(extraction_method IN ('trafilatura','playwright','failed'));
        
        -- Copy data from old method column to new extraction_method column
        UPDATE articles SET extraction_method = method WHERE method IS NOT NULL;
        
        -- Create index for failure tracking queries
        CREATE INDEX IF NOT EXISTS idx_articles_failure_count ON articles(failure_count);
        CREATE INDEX IF NOT EXISTS idx_articles_extraction_method ON articles(extraction_method);
        """
        
        conn.executescript(migration_sql)
        conn.commit()
        
        print("Migration completed successfully!")
        print("- Added failure_count column")
        print("- Added last_failure_reason column") 
        print("- Added extraction_method column")
        print("- Created performance indexes")
        
        # Show updated schema
        cursor = conn.execute("PRAGMA table_info(articles)")
        columns = cursor.fetchall()
        print("\nUpdated articles table schema:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
    
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_articles_table()
