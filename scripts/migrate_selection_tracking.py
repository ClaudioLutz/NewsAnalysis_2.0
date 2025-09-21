#!/usr/bin/env python3
"""
Add selection tracking columns to items table for confidence-based filtering.
"""

import sqlite3
import sys
from pathlib import Path

def apply_migration(db_path: str = "news.db"):
    """Add selection tracking columns to items table."""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(items)")
        columns = {col[1] for col in cursor.fetchall()}
        
        migrations_needed = []
        
        # Add pipeline_stage if not exists
        if 'pipeline_stage' not in columns:
            migrations_needed.append(
                "ALTER TABLE items ADD COLUMN pipeline_stage TEXT DEFAULT 'collected'"
            )
        
        # Add pipeline_run_id if not exists
        if 'pipeline_run_id' not in columns:
            migrations_needed.append(
                "ALTER TABLE items ADD COLUMN pipeline_run_id TEXT"
            )
        
        # Add last_error if not exists
        if 'last_error' not in columns:
            migrations_needed.append(
                "ALTER TABLE items ADD COLUMN last_error TEXT"
            )
        
        # Add selected_for_processing if not exists
        if 'selected_for_processing' not in columns:
            migrations_needed.append(
                "ALTER TABLE items ADD COLUMN selected_for_processing INTEGER DEFAULT 0"
            )
        
        # Add selection_rank if not exists
        if 'selection_rank' not in columns:
            migrations_needed.append(
                "ALTER TABLE items ADD COLUMN selection_rank INTEGER"
            )
        
        if not migrations_needed:
            print("Selection tracking columns already exist - no migration needed")
            return False
        
        # Apply migrations
        for migration in migrations_needed:
            print(f"Applying: {migration}")
            cursor.execute(migration)
        
        # Create indices for performance
        indices = [
            ("idx_items_pipeline", "items(pipeline_stage, pipeline_run_id)"),
            ("idx_items_selection", "items(selected_for_processing, triage_confidence DESC)")
        ]
        
        for idx_name, idx_def in indices:
            cursor.execute(f"DROP INDEX IF EXISTS {idx_name}")
            cursor.execute(f"CREATE INDEX {idx_name} ON {idx_def}")
            print(f"Created index: {idx_name}")
        
        conn.commit()
        print(f"\nSuccessfully added {len(migrations_needed)} selection tracking columns")
        
        # Verify the changes
        cursor.execute("PRAGMA table_info(items)")
        columns_after = {col[1] for col in cursor.fetchall()}
        new_columns = {'pipeline_stage', 'pipeline_run_id', 'last_error', 
                      'selected_for_processing', 'selection_rank'}
        
        if new_columns.issubset(columns_after):
            print("✓ All selection tracking columns verified")
            return True
        else:
            missing = new_columns - columns_after
            print(f"⚠ Warning: Some columns may be missing: {missing}")
            return False
            
    except Exception as e:
        print(f"Error applying migration: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "news.db"
    
    if not Path(db_path).exists():
        print(f"Database {db_path} does not exist")
        sys.exit(1)
    
    success = apply_migration(db_path)
    sys.exit(0 if success else 1)
