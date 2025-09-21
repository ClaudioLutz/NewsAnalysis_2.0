#!/usr/bin/env python3
"""
Fix the UNIQUE constraint issue in pipeline_state table.

The current schema has UNIQUE constraint on run_id alone, but the design
requires multiple rows per run_id (one per step). This script fixes the
constraint to be on (run_id, step_name) combination.
"""

import sqlite3
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def fix_pipeline_state_constraint():
    """Fix the pipeline_state table constraint."""
    db_path = os.getenv("DB_PATH", "./news.db")
    
    print(f"Fixing pipeline_state constraint in {db_path}...")
    
    if not Path(db_path).exists():
        print(f"Database {db_path} does not exist. Nothing to fix.")
        return
    
    conn = sqlite3.connect(db_path)
    
    try:
        # Check if pipeline_state table exists
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='pipeline_state'
        """)
        
        if not cursor.fetchone():
            print("pipeline_state table does not exist. Nothing to fix.")
            return
        
        # Check current schema
        cursor = conn.execute("PRAGMA table_info(pipeline_state)")
        columns = cursor.fetchall()
        print(f"Current pipeline_state columns: {len(columns)} columns")
        
        # Create new table with correct constraint
        print("Creating new pipeline_state table with correct constraint...")
        conn.execute("""
            CREATE TABLE pipeline_state_new (
                id INTEGER PRIMARY KEY,
                run_id TEXT NOT NULL,
                step_name TEXT NOT NULL CHECK(step_name IN ('collection', 'filtering', 'scraping', 'summarization', 'analysis')),
                status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'paused')) DEFAULT 'pending',
                started_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT,
                metadata TEXT,
                article_count INTEGER DEFAULT 0,
                match_count INTEGER DEFAULT 0,
                error_message TEXT,
                can_resume INTEGER DEFAULT 1,
                UNIQUE(run_id, step_name)
            )
        """)
        
        # Copy existing data
        print("Copying existing data...")
        conn.execute("""
            INSERT INTO pipeline_state_new 
            SELECT * FROM pipeline_state
        """)
        
        # Drop old table and rename new one
        print("Replacing old table...")
        conn.execute("DROP TABLE pipeline_state")
        conn.execute("ALTER TABLE pipeline_state_new RENAME TO pipeline_state")
        
        # Recreate indexes
        print("Recreating indexes...")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_state_run_id ON pipeline_state(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_state_status ON pipeline_state(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_state_step ON pipeline_state(step_name)")
        
        conn.commit()
        print("✅ Successfully fixed pipeline_state constraint!")
        
        # Verify the fix
        cursor = conn.execute("PRAGMA table_info(pipeline_state)")
        columns = cursor.fetchall()
        print(f"New pipeline_state table has {len(columns)} columns")
        
        # Test the constraint
        print("Testing new constraint...")
        test_run_id = "test-constraint-fix"
        
        # This should work (different steps)
        conn.execute("""
            INSERT INTO pipeline_state (run_id, step_name, status)
            VALUES (?, 'collection', 'pending'), (?, 'filtering', 'pending')
        """, (test_run_id, test_run_id))
        
        # Clean up test data
        conn.execute("DELETE FROM pipeline_state WHERE run_id = ?", (test_run_id,))
        conn.commit()
        
        print("✅ Constraint test passed!")
        
    except sqlite3.IntegrityError as e:
        print(f"❌ Integrity error during migration: {e}")
        conn.rollback()
        raise
    except Exception as e:
        print(f"❌ Error fixing constraint: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    fix_pipeline_state_constraint()
