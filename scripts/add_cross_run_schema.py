#!/usr/bin/env python3
"""
Add cross-run deduplication schema to the database.

This migration adds tables and columns needed for tracking topic signatures
across multiple daily pipeline runs to enable cross-run deduplication.
"""

import sqlite3
import os
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def create_backup(db_path: str) -> str:
    """
    Create a backup of the database before migration.
    
    Args:
        db_path: Path to the database file
        
    Returns:
        Path to the backup file
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"Created backup: {backup_path}")
    return backup_path


def validate_existing_schema(conn: sqlite3.Connection) -> bool:
    """
    Validate that the database has required existing tables.
    
    Args:
        conn: Database connection
        
    Returns:
        True if schema is valid, False otherwise
    """
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    
    required_tables = {'items', 'summaries'}
    if not required_tables.issubset(tables):
        print(f"ERROR: Missing required tables. Found: {tables}")
        return False
    
    return True


def check_migration_needed(conn: sqlite3.Connection) -> bool:
    """
    Check if migration has already been applied.
    
    Args:
        conn: Database connection
        
    Returns:
        True if migration is needed, False if already applied
    """
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    
    if 'cross_run_topic_signatures' in tables:
        print("Migration already applied - cross_run_topic_signatures table exists")
        return False
    
    return True


def migrate_schema(db_path: str = None, create_if_missing: bool = False) -> bool:
    """
    Add cross-run deduplication schema to existing database.
    
    Args:
        db_path: Path to SQLite database file (default from env)
        create_if_missing: If True, create database if it doesn't exist (for tests)
        
    Returns:
        True if migration succeeded, False otherwise
    """
    if db_path is None:
        db_path = os.getenv("DB_PATH", "./news.db")
    
    db_exists = os.path.exists(db_path)
    
    if not db_exists and not create_if_missing:
        print(f"ERROR: Database {db_path} does not exist")
        return False
    
    if db_exists:
        print(f"Starting migration on database: {db_path}")
        print(f"Migration started at: {datetime.now().isoformat()}")
        
        # Create backup for existing database
        try:
            backup_path = create_backup(db_path)
        except Exception as e:
            print(f"ERROR: Failed to create backup: {e}")
            return False
    else:
        print(f"Creating new database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    try:
        # Validate or create base schema
        if db_exists:
            if not validate_existing_schema(conn):
                print("ERROR: Database schema validation failed")
                return False
        
        # Check if migration needed
        if not check_migration_needed(conn):
            return True
        
        print("\nApplying cross-run deduplication schema migration...")
        
        # Execute migration SQL - base tables
        base_migration_sql = """
        -- Create cross_run_topic_signatures table
        CREATE TABLE IF NOT EXISTS cross_run_topic_signatures (
            signature_id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            article_summary TEXT NOT NULL,
            topic_theme TEXT,
            source_article_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            run_sequence INTEGER NOT NULL
        );

        -- Create indexes for fast date-based queries
        CREATE INDEX IF NOT EXISTS idx_signatures_date 
            ON cross_run_topic_signatures(date);
        CREATE INDEX IF NOT EXISTS idx_signatures_source 
            ON cross_run_topic_signatures(source_article_id);

        -- Create cross_run_deduplication_log table
        CREATE TABLE IF NOT EXISTS cross_run_deduplication_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            new_article_id INTEGER NOT NULL,
            matched_signature_id TEXT,
            decision TEXT NOT NULL CHECK(decision IN ('DUPLICATE', 'UNIQUE')),
            confidence_score REAL,
            processing_time REAL NOT NULL,
            created_at TEXT NOT NULL
        );

        -- Create index for log queries
        CREATE INDEX IF NOT EXISTS idx_dedup_log_date 
            ON cross_run_deduplication_log(date);
        """
        
        conn.executescript(base_migration_sql)
        
        # Add columns to summaries table only if it exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='summaries'")
        if cursor.fetchone():
            try:
                conn.execute("ALTER TABLE summaries ADD COLUMN topic_already_covered INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # Column may already exist
            try:
                conn.execute("ALTER TABLE summaries ADD COLUMN cross_run_cluster_id TEXT DEFAULT NULL")
            except sqlite3.OperationalError:
                pass  # Column may already exist
        conn.commit()
        
        print("\nMigration completed successfully!")
        print("- Created cross_run_topic_signatures table")
        print("- Created cross_run_deduplication_log table")
        print("- Added topic_already_covered column to summaries table")
        print("- Added cross_run_cluster_id column to summaries table")
        print("- Created performance indexes")
        
        # Validate migration
        print("\nValidating migration...")
        if not validate_migration(conn):
            print("ERROR: Migration validation failed")
            return False
        
        print("Migration validation passed!")
        print(f"Migration completed at: {datetime.now().isoformat()}")
        
        return True
        
    except Exception as e:
        print(f"\nERROR: Migration failed: {e}")
        conn.rollback()
        print(f"\nDatabase backup available at: {backup_path}")
        print("You can restore the backup if needed:")
        print(f"  cp {backup_path} {db_path}")
        return False
        
    finally:
        conn.close()


def validate_migration(conn: sqlite3.Connection) -> bool:
    """
    Validate that migration was applied correctly.
    
    Args:
        conn: Database connection
        
    Returns:
        True if validation passed, False otherwise
    """
    # Check tables exist
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    
    required_tables = {'cross_run_topic_signatures', 'cross_run_deduplication_log'}
    if not required_tables.issubset(tables):
        print(f"ERROR: Missing required tables after migration")
        return False
    
    # Check columns added to summaries
    cursor = conn.execute("PRAGMA table_info(summaries)")
    columns = {row[1] for row in cursor.fetchall()}
    
    required_columns = {'topic_already_covered', 'cross_run_cluster_id'}
    if not required_columns.issubset(columns):
        print(f"ERROR: Missing required columns in summaries table")
        return False
    
    # Check indexes created
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = {row[0] for row in cursor.fetchall()}
    
    required_indexes = {
        'idx_signatures_date',
        'idx_signatures_source',
        'idx_dedup_log_date'
    }
    if not required_indexes.issubset(indexes):
        print(f"ERROR: Missing required indexes")
        return False
    
    print("  ✓ All tables created")
    print("  ✓ All columns added")
    print("  ✓ All indexes created")
    
    return True


def show_rollback_instructions(db_path: str):
    """Display rollback instructions."""
    print("\n" + "=" * 60)
    print("ROLLBACK PROCEDURE (if needed)")
    print("=" * 60)
    print("\nTo rollback this migration:")
    print("1. Restore from backup:")
    print(f"   cp {db_path}.backup_* {db_path}")
    print("\n2. Or manually drop tables and columns:")
    print("   DROP TABLE IF EXISTS cross_run_topic_signatures;")
    print("   DROP TABLE IF EXISTS cross_run_deduplication_log;")
    print("   -- Note: SQLite doesn't support DROP COLUMN")
    print("   -- New columns will be ignored by existing code")
    print("=" * 60)


if __name__ == "__main__":
    db_path = os.getenv("DB_PATH", "./news.db")
    
    print("=" * 60)
    print("CROSS-RUN DEDUPLICATION SCHEMA MIGRATION")
    print("=" * 60)
    
    success = migrate_schema(db_path)
    
    if success:
        print("\n✓ Migration completed successfully")
        show_rollback_instructions(db_path)
    else:
        print("\n✗ Migration failed - database unchanged")
        show_rollback_instructions(db_path)
