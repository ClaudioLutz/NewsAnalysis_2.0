-- CLEANED PIPELINE DATABASE SCHEMA
-- Ensures consistent data flow across all 5 steps

-- Main articles table with complete pipeline status tracking
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Step 1: Collection
    source TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    normalized_url TEXT NOT NULL,
    url_hash TEXT NOT NULL UNIQUE, -- SHA-256 hash for deduplication
    title TEXT,
    description TEXT,
    published_at TIMESTAMP,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Step 2: Filtering
    filtering_attempted_at TIMESTAMP,
    filtering_completed_at TIMESTAMP,
    triage_topic TEXT,
    triage_confidence REAL,
    is_match BOOLEAN DEFAULT 0,
    filtering_error TEXT,
    
    -- Step 3: Scraping  
    scraping_attempted_at TIMESTAMP,
    scraping_completed_at TIMESTAMP,
    extraction_method TEXT,
    content_length INTEGER,
    scraping_error TEXT,
    
    -- Step 4: Summarization
    summarization_attempted_at TIMESTAMP, 
    summarization_completed_at TIMESTAMP,
    summarization_model TEXT,
    summarization_error TEXT,
    
    -- Step 5: Analysis (included in digest)
    included_in_digest_at TIMESTAMP,
    
    -- Deduplication
    cluster_id TEXT,
    is_cluster_primary BOOLEAN DEFAULT 1,
    similarity_score REAL,
    
    -- Pipeline status
    pipeline_status TEXT DEFAULT 'collected' CHECK (
        pipeline_status IN ('collected', 'filtered', 'scraped', 'summarized', 'analyzed', 'failed')
    ),
    failed_at_step TEXT,
    
    -- Indexes
    UNIQUE(url_hash)
);

-- Extracted content (Step 3 output)
CREATE TABLE articles (
    item_id INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
    extracted_text TEXT NOT NULL,
    extracted_html TEXT,
    word_count INTEGER,
    extraction_quality REAL,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Generated summaries (Step 4 output)  
CREATE TABLE summaries (
    item_id INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    model TEXT NOT NULL,
    summary TEXT NOT NULL,
    key_points_json TEXT,
    entities_json TEXT,
    word_count_original INTEGER,
    word_count_summary INTEGER,
    compression_ratio REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Pipeline run tracking
CREATE TABLE pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    mode TEXT DEFAULT 'standard' CHECK (mode IN ('express', 'standard', 'deep')),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'paused')),
    
    -- Progress tracking per step
    step1_collected INTEGER DEFAULT 0,
    step2_filtered INTEGER DEFAULT 0,
    step2_matched INTEGER DEFAULT 0,
    step3_scraped INTEGER DEFAULT 0,
    step4_summarized INTEGER DEFAULT 0,
    step5_analyzed INTEGER DEFAULT 0,
    
    -- Error summary
    total_errors INTEGER DEFAULT 0,
    error_summary TEXT,
    
    metadata_json TEXT
);

-- Simplified indexes for performance
CREATE INDEX idx_items_pipeline_status ON items(pipeline_status);
CREATE INDEX idx_items_cluster ON items(cluster_id, is_cluster_primary);
CREATE INDEX idx_items_filtering ON items(filtering_completed_at, is_match);
CREATE INDEX idx_items_scraping ON items(scraping_completed_at, content_length);
CREATE INDEX idx_items_summarization ON items(summarization_completed_at);

-- FTS for content search
CREATE VIRTUAL TABLE items_fts USING fts5(
    title, description, url,
    content='items', content_rowid='id'
);
