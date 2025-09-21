#!/usr/bin/env python3
"""
Pipeline Flow Improvements - Database Schema Enhancements

Adds missing database indexes, constraints, and triggers to improve
pipeline performance and ensure data integrity.
"""

import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

def apply_pipeline_improvements():
    """Apply database improvements for better pipeline flow."""
    db_path = os.getenv("DB_PATH", "./news.db")
    conn = sqlite3.connect(db_path)
    
    print("Applying pipeline flow improvements...")
    
    # 1. Add performance indexes
    print("Adding performance indexes...")
    
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_items_pipeline_flow 
        ON items(pipeline_run_id, pipeline_stage, selected_for_processing, is_match)
    """)
    
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_items_selection_processing 
        ON items(selected_for_processing, selection_rank) 
        WHERE selected_for_processing = 1
    """)
    
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_items_triage_confidence 
        ON items(triage_confidence DESC, first_seen_at DESC) 
        WHERE is_match = 1
    """)
    
    # 2. Add constraint to prevent duplicate selection ranks within same run
    print("Adding selection rank constraint...")
    try:
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_selection_rank 
            ON items(pipeline_run_id, selection_rank) 
            WHERE selection_rank IS NOT NULL AND pipeline_run_id IS NOT NULL
        """)
        print("✓ Selection rank uniqueness constraint added")
    except Exception as e:
        print(f"Note: Selection rank constraint may already exist: {e}")
    
    # 3. Create article_clusters table if it doesn't exist (for deduplication)
    print("Ensuring article_clusters table exists...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS article_clusters (
            cluster_id TEXT,
            article_id INTEGER,
            is_primary INTEGER DEFAULT 0,
            similarity_score REAL DEFAULT 0.0,
            clustering_method TEXT DEFAULT 'title_similarity',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (cluster_id, article_id),
            FOREIGN KEY (article_id) REFERENCES items(id)
        )
    """)
    
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_article_clusters_primary 
        ON article_clusters(is_primary, similarity_score DESC) 
        WHERE is_primary = 1
    """)
    
    # 4. Add trigger for pipeline stage validation (optional, can be disabled if too strict)
    print("Adding pipeline stage validation trigger...")
    try:
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS validate_pipeline_stage_transition
            BEFORE UPDATE OF pipeline_stage ON items
            FOR EACH ROW
            WHEN NEW.pipeline_stage IS NOT NULL AND OLD.pipeline_stage IS NOT NULL
            BEGIN
                SELECT CASE
                    WHEN OLD.pipeline_stage = 'collected' AND NEW.pipeline_stage NOT IN ('matched', 'filtered_out') THEN
                        RAISE(ABORT, 'Invalid stage transition from collected to ' || NEW.pipeline_stage)
                    WHEN OLD.pipeline_stage = 'matched' AND NEW.pipeline_stage NOT IN ('selected', 'filtered_out') THEN
                        RAISE(ABORT, 'Invalid stage transition from matched to ' || NEW.pipeline_stage)
                    WHEN OLD.pipeline_stage = 'selected' AND NEW.pipeline_stage NOT IN ('scraped', 'failed') THEN
                        RAISE(ABORT, 'Invalid stage transition from selected to ' || NEW.pipeline_stage)
                    WHEN OLD.pipeline_stage = 'scraped' AND NEW.pipeline_stage NOT IN ('summarized', 'failed') THEN
                        RAISE(ABORT, 'Invalid stage transition from scraped to ' || NEW.pipeline_stage)
                END;
            END;
        """)
        print("✓ Pipeline stage validation trigger added")
    except Exception as e:
        print(f"Note: Pipeline stage trigger may already exist: {e}")
    
    # 5. Add trigger to automatically update pipeline_stage when articles are processed
    print("Adding automatic stage transition triggers...")
    
    # Update stage to 'scraped' when content is extracted
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS auto_update_stage_scraped
        AFTER INSERT ON articles
        FOR EACH ROW
        WHEN NEW.extracted_text IS NOT NULL
        BEGIN
            UPDATE items 
            SET pipeline_stage = 'scraped' 
            WHERE id = NEW.item_id 
            AND pipeline_stage = 'selected'
            AND pipeline_run_id IS NOT NULL;
        END;
    """)
    
    # Update stage to 'summarized' when summary is created
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS auto_update_stage_summarized
        AFTER INSERT ON summaries
        FOR EACH ROW
        BEGIN
            UPDATE items 
            SET pipeline_stage = 'summarized' 
            WHERE id = NEW.item_id 
            AND pipeline_stage = 'scraped'
            AND pipeline_run_id IS NOT NULL;
        END;
    """)
    
    # 6. Add view for easy pipeline monitoring
    print("Creating pipeline monitoring view...")
    conn.execute("""
        CREATE VIEW IF NOT EXISTS v_pipeline_status AS
        SELECT 
            pipeline_run_id,
            pipeline_stage,
            COUNT(*) as article_count,
            AVG(triage_confidence) as avg_confidence,
            MIN(first_seen_at) as earliest_article,
            MAX(first_seen_at) as latest_article
        FROM items
        WHERE pipeline_run_id IS NOT NULL
        GROUP BY pipeline_run_id, pipeline_stage
        ORDER BY pipeline_run_id DESC, pipeline_stage;
    """)
    
    conn.commit()
    conn.close()
    
    print("✅ Pipeline flow improvements applied successfully!")
    print("\nImprovements applied:")
    print("- Performance indexes for pipeline queries")
    print("- Selection rank uniqueness constraint")
    print("- Article clusters table for deduplication")
    print("- Pipeline stage validation triggers")
    print("- Automatic stage transition triggers")
    print("- Pipeline monitoring view")
    
    return True

def remove_strict_validation():
    """Remove strict pipeline stage validation if it causes issues."""
    db_path = os.getenv("DB_PATH", "./news.db")
    conn = sqlite3.connect(db_path)
    
    try:
        conn.execute("DROP TRIGGER IF EXISTS validate_pipeline_stage_transition")
        conn.commit()
        print("Removed strict pipeline stage validation trigger")
    except Exception as e:
        print(f"Could not remove trigger: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Apply pipeline flow improvements")
    parser.add_argument("--remove-validation", action="store_true", 
                       help="Remove strict stage validation triggers")
    
    args = parser.parse_args()
    
    if args.remove_validation:
        remove_strict_validation()
    else:
        apply_pipeline_improvements()
