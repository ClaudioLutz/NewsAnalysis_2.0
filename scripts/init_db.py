#!/usr/bin/env python3
"""
Initialize the SQLite database with the complete schema as specified in the plan.
"""

import sqlite3
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def init_database():
    """Initialize the SQLite database with the complete schema."""
    db_path = os.getenv("DB_PATH", "./news.db")
    
    # Ensure the directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    
    # Enable WAL mode for better concurrent access
    conn.execute("PRAGMA journal_mode=WAL")
    
    # Create tables as per the plan
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS feeds(
      id INTEGER PRIMARY KEY, 
      source TEXT NOT NULL, 
      kind TEXT NOT NULL, 
      url TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS items(
      id INTEGER PRIMARY KEY,
      source TEXT NOT NULL,
      url TEXT NOT NULL UNIQUE,
      normalized_url TEXT NOT NULL,
      title TEXT,
      published_at TEXT,
      first_seen_at TEXT DEFAULT (datetime('now')),
      triage_topic TEXT,
      triage_confidence REAL,
      is_match INTEGER DEFAULT 0
    );

    CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
      title, url, content='items', content_rowid='id', 
      tokenize='unicode61 remove_diacritics 2'
    );

    CREATE TABLE IF NOT EXISTS articles(
      item_id INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
      extracted_text TEXT,
      extracted_at TEXT DEFAULT (datetime('now')),
      method TEXT CHECK(method IN ('trafilatura','playwright'))
    );

    CREATE TABLE IF NOT EXISTS summaries(
      item_id INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
      topic TEXT, 
      model TEXT, 
      summary TEXT,
      key_points_json TEXT, 
      entities_json TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_items_source ON items(source);
    CREATE INDEX IF NOT EXISTS idx_items_match ON items(is_match, triage_topic);

    -- Critical deduplication table to prevent re-processing same URLs
    CREATE TABLE IF NOT EXISTS processed_links (
        url_hash TEXT PRIMARY KEY,
        url TEXT NOT NULL,
        processed_at TEXT DEFAULT (datetime('now')),
        topic TEXT NOT NULL,
        result TEXT NOT NULL CHECK(result IN ('matched', 'rejected', 'error')),
        confidence REAL DEFAULT 0.0
    );

    -- ENHANCED: Pipeline State Tracking (Phase 1 & 5)
    CREATE TABLE IF NOT EXISTS pipeline_state (
        id INTEGER PRIMARY KEY,
        run_id TEXT UNIQUE NOT NULL,  -- UUID for each pipeline run
        step_name TEXT NOT NULL CHECK(step_name IN ('collection', 'filtering', 'scraping', 'summarization', 'analysis')),
        status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'paused')) DEFAULT 'pending',
        started_at TEXT DEFAULT (datetime('now')),
        completed_at TEXT,
        metadata TEXT,  -- JSON for step-specific data
        article_count INTEGER DEFAULT 0,
        match_count INTEGER DEFAULT 0,
        error_message TEXT,
        can_resume INTEGER DEFAULT 1
    );

    -- ENHANCED: Article Clustering for Deduplication (Phase 4)
    CREATE TABLE IF NOT EXISTS article_clusters (
        id INTEGER PRIMARY KEY,
        cluster_id TEXT NOT NULL,  -- Generated hash for similar articles
        article_id INTEGER REFERENCES items(id) ON DELETE CASCADE,
        is_primary INTEGER DEFAULT 0,  -- Best article in cluster
        similarity_score REAL DEFAULT 0.0,
        created_at TEXT DEFAULT (datetime('now')),
        clustering_method TEXT DEFAULT 'title_similarity'
    );

    -- Legacy pipeline_runs table (keeping for compatibility)
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        id INTEGER PRIMARY KEY,
        started_at TEXT DEFAULT (datetime('now')),
        completed_at TEXT,
        status TEXT CHECK(status IN ('running', 'completed', 'failed')) DEFAULT 'running',
        step TEXT,
        articles_processed INTEGER DEFAULT 0
    );

    CREATE INDEX IF NOT EXISTS idx_processed_links_topic ON processed_links(topic);
    CREATE INDEX IF NOT EXISTS idx_processed_links_result ON processed_links(result);
    CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
    
    -- NEW: Enhanced indexing for optimization
    CREATE INDEX IF NOT EXISTS idx_pipeline_state_run_id ON pipeline_state(run_id);
    CREATE INDEX IF NOT EXISTS idx_pipeline_state_status ON pipeline_state(status);
    CREATE INDEX IF NOT EXISTS idx_pipeline_state_step ON pipeline_state(step_name);
    CREATE INDEX IF NOT EXISTS idx_article_clusters_cluster_id ON article_clusters(cluster_id);
    CREATE INDEX IF NOT EXISTS idx_article_clusters_primary ON article_clusters(is_primary);
    """)
    
    conn.commit()
    conn.close()
    
    print(f"Database initialized successfully at {db_path}")

if __name__ == "__main__":
    init_database()
