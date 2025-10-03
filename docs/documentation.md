# NewsAnalysis_2.0 – Technical Documentation

*Last updated: 20 Sep 2025*

## Table of Contents

1. [Purpose & Scope](#1-purpose--scope)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Directory Layout](#3-directory-layout)
4. [Configuration](#4-configuration)
5. [Database Schema](#5-database-schema)
6. [Components & Algorithms](#6-components--algorithms)
7. [CLI Usage](#7-cli-usage)
8. [API Reference](#8-api-reference)
9. [Logging & Observability](#9-logging--observability)
10. [Operations Runbook](#10-operations-runbook)
11. [Performance Optimization](#11-performance-optimization)
12. [Security & Compliance](#12-security--compliance)
13. [Deployment Guide](#13-deployment-guide)
14. [Troubleshooting](#14-troubleshooting)
15. [Extensibility & Customization](#15-extensibility--customization)
16. [Testing](#16-testing)
17. [Monitoring & Alerts](#17-monitoring--alerts)
18. [Data Flow Diagrams](#18-data-flow-diagrams)
19. [Code Examples](#19-code-examples)
20. [Glossary](#20-glossary)
21. [FAQ](#21-faq)
22. [Future Work](#22-future-work)

---

## 1) Purpose & Scope

### 1.1 Overview

NewsAnalysis_2.0 is a sophisticated, modular pipeline designed for collecting, triaging, scraping, deduplicating, and analyzing Swiss business news with a specific focus on Creditreform-relevant insights. The system emphasizes high-precision filtering, resumable execution, and fast "express" runs that can surface actionable items within minutes.

### 1.2 Key Features

- **Multi-source Collection**: RSS feeds, XML sitemaps, HTML parsing, and Google News integration
- **AI-Powered Triage**: Title/URL-only classification to minimize processing costs
- **Smart Deduplication**: Semantic clustering to eliminate duplicate content
- **Resumable Execution**: Checkpoint-based state management for reliable operation
- **Express Mode**: Fast-track processing for urgent insights (<3 minutes)
- **Multi-format Export**: JSON, Markdown, and specialized German rating reports
- **Robust Error Handling**: Graceful fallbacks and comprehensive logging
- **Scalable Architecture**: Modular design supporting horizontal scaling

### 1.3 Target Use Cases

- **Daily News Monitoring**: Automated collection and analysis of Swiss business news
- **Creditreform Intelligence**: Identification of bankruptcy, financial distress, and business changes
- **Competitive Analysis**: Tracking industry trends and competitor mentions
- **Risk Assessment**: Early warning system for financial sector developments
- **Regulatory Compliance**: Monitoring of FINMA, SNB, and other regulatory announcements

### 1.4 System Requirements

**Minimum Requirements:**
- Python 3.8+
- SQLite 3.35+
- 2GB RAM
- 10GB disk space

**Recommended:**
- Python 3.11+
- SQLite 3.40+
- 8GB RAM
- 50GB disk space
- SSD storage for database

**Optional Dependencies:**
- Playwright for advanced scraping
- SentenceTransformers for enhanced similarity detection
- MCP servers for extended functionality

---

## 2) High-Level Architecture

### 2.1 Pipeline Overview

The NewsAnalysis_2.0 system follows a multi-stage pipeline architecture:

```
[Collection] → [Filtering/Triage] → [Scraping] → [Deduplication] → [Analysis] → [Export]
     ↓              ↓                  ↓             ↓              ↓          ↓
  SQLite        AI Classification   Content      Clustering     Summary    Reports
  Storage       (title/URL only)   Extraction    Analysis      Generation   & Alerts
```

### 2.2 Core Modules

#### 2.2.1 Collection Module (`news_pipeline/collector.py`)
- **RSS Feed Processing**: Handles standard RSS 2.0 and Atom feeds
- **Sitemap Parsing**: XML sitemap navigation with selective URL extraction  
- **HTML Parsing**: CSS selector-based content discovery
- **URL Normalization**: Consistent URL handling and deduplication

#### 2.2.2 Filtering Module (`news_pipeline/filter.py`)
- **AI Classification**: GPT-based title/URL analysis for relevance scoring
- **Priority Ranking**: Multi-factor scoring including source authority and freshness
- **Early Termination**: Cost-optimized processing with configurable thresholds
- **Cache Management**: Persistent filtering results to avoid reprocessing

#### 2.2.3 Scraping Module (`news_pipeline/scraper.py`)
- **Primary Engine**: Trafilatura with high-recall configuration
- **Fallback Systems**: MCP+Playwright for JavaScript-heavy sites
- **Content Enhancement**: JSON-LD structured data extraction
- **Google News Decoder**: Specialized handling of Google News redirects

#### 2.2.4 Deduplication Module (`news_pipeline/deduplication.py`)
- **Similarity Detection**: Multiple algorithms (SentenceTransformers, TF-IDF, basic matching)
- **Clustering Engine**: Groups similar articles with configurable thresholds
- **Primary Selection**: Authority-based selection of representative articles
- **Performance Tracking**: Comprehensive deduplication metrics

#### 2.2.5 State Management (`news_pipeline/state_manager.py`)
- **Run Orchestration**: Manages pipeline execution flow and dependencies
- **Checkpoint System**: Resumable execution from any pipeline stage
- **Error Recovery**: Graceful handling of interruptions and failures
- **Progress Tracking**: Real-time status updates and completion estimates

#### 2.2.6 Express Mode (`news_pipeline/express_mode.py`)
- **Fast Processing**: Optimized pipeline for urgent news analysis
- **Reduced Scope**: Focus on recent, high-priority content
- **Time Constraints**: Hard limits to ensure sub-3-minute execution
- **Quality Maintenance**: Maintains accuracy while optimizing speed

### 2.3 Data Flow Architecture

#### 2.3.1 Input Sources
- **RSS Feeds**: Curated list of Swiss financial and business news sources
- **XML Sitemaps**: Selective parsing of major news websites
- **HTML Sources**: Direct parsing of sites without RSS feeds
- **Manual URLs**: Ad-hoc addition of specific articles for analysis

#### 2.3.2 Processing Stages
1. **Collection**: Raw URL and metadata extraction
2. **Normalization**: URL cleaning and deduplication preparation
3. **Triage**: AI-powered relevance classification
4. **Content Extraction**: Full article text retrieval
5. **Deduplication**: Similarity-based clustering
6. **Analysis**: Summary generation and entity extraction
7. **Export**: Multi-format output generation

#### 2.3.3 Output Formats
- **JSON**: Machine-readable structured data
- **Markdown**: Human-readable reports with formatting
- **German Rating Reports**: Specialized Creditreform format
- **Database Exports**: Raw data extraction for external tools

### 2.4 Storage Architecture

#### 2.4.1 Primary Database (SQLite)
- **Operational Data**: Real-time pipeline state and content storage
- **Full-Text Search**: Integrated FTS5 for content search
- **Indexing Strategy**: Optimized indexes for common query patterns
- **Backup Strategy**: Regular snapshots and WAL mode for reliability

#### 2.4.2 File System Storage
- **Exports Directory**: Generated reports and data exports
- **Logs Directory**: Structured logging with rotation
- **Cache Directory**: Temporary files and processing artifacts
- **Config Directory**: YAML configuration files

---

## 3) Directory Layout

### 3.1 Complete Directory Structure

```
NewsAnalysis_2.0/
├─ config/                          # Configuration files
│  ├─ feeds.yaml                     # News source definitions
│  ├─ topics.yaml                    # Topic classification rules
│  └─ mcp.json                      # MCP server configuration
├─ news_pipeline/                   # Core pipeline modules
│  ├─ __init__.py                   # Package initialization
│  ├─ analyzer.py                   # Summary and digest generation
│  ├─ collector.py                  # URL collection from sources
│  ├─ deduplication.py             # Article clustering and dedup
│  ├─ express_mode.py              # Fast-track pipeline
│  ├─ filter.py                    # AI-powered article triage
│  ├─ german_rating_formatter.py   # Creditreform report generation
│  ├─ google_news_decoder.py       # Google News redirect handling
│  ├─ scraper.py                   # Content extraction
│  ├─ state_manager.py             # Pipeline orchestration
│  ├─ summarizer.py                # Article summarization
│  └─ utils.py                     # Shared utilities
├─ schemas/                         # JSON validation schemas
│  ├─ triage.schema.json           # Triage result validation
│  └─ summary.schema.json          # Summary format validation
├─ scripts/                        # Utility and setup scripts
│  ├─ init_db.py                   # Database initialization
│  ├─ load_feeds.py                # Feed configuration loader
│  └─ maintenance/                 # Database maintenance scripts
├─ tests/                          # Test suite
│  ├─ unit/                        # Unit tests
│  ├─ integration/                 # Integration tests
│  └─ fixtures/                    # Test data
├─ logs/                           # Application logs
│  ├─ pipeline_YYYYMMDD.log        # Daily pipeline logs
│  ├─ error_YYYYMMDD.log          # Error-specific logs
│  └─ latest_pipeline.log          # Symlink to current log
├─ exports/                        # Generated reports and exports
│  ├─ daily_digest_YYYYMMDD.json   # Daily analysis exports
│  ├─ daily_digest_YYYYMMDD.md     # Human-readable reports
│  └─ rating_reports/              # German rating reports
├─ data/                           # Data storage
│  ├─ cache/                       # Temporary processing files
│  └─ backups/                     # Database backups
├─ deprecated_docs/                # Legacy documentation
├─ deprecated_code/                # Legacy code for reference
├─ discussion/                     # Design discussions and decisions
├─ news_analyzer.py               # Main CLI entry point
├─ requirements.txt               # Python dependencies
├─ setup.py                       # Package installation
├─ Dockerfile                     # Container deployment
├─ .env.example                   # Environment configuration template
├─ .gitignore                     # Git ignore patterns
└─ README.md                      # Basic usage guide
```

### 3.2 Configuration Directory Details

#### 3.2.1 feeds.yaml Structure
```yaml
feeds:
  rss:
    - name: "NZZ Finance"
      url: "https://www.nzz.ch/wirtschaft.rss"
      authority: "high"
      language: "de"
      region: "swiss"
    - name: "FINMA News"
      url: "https://www.finma.ch/en/news/rss/"
      authority: "government"
      language: "en"
  
  sitemaps:
    - name: "20 Minuten"
      url: "https://www.20min.ch/sitemap.xml"
      authority: "medium"
      filter_patterns:
        - "/wirtschaft/"
        - "/news/"
  
  html:
    - name: "SNB Press"
      url: "https://www.snb.ch/en/mmr/reference/pre_all/source"
      authority: "government"
      selectors:
        link: "a.press-release"
        title: ".title"
        date: ".date"
```

#### 3.2.2 topics.yaml Structure
```yaml
topics:
  creditreform_insights:
    enabled: true
    confidence_threshold: 0.7
    max_articles_per_run: 100
    max_articles_express: 25
    focus_areas:
      - "bankruptcy proceedings"
      - "financial difficulties"
      - "company closures"
      - "debt restructuring"
      - "insolvency proceedings"
    keywords:
      high_priority:
        - "konkurs"
        - "insolvenz"
        - "zahlungsunfähig"
        - "sanierung"
      medium_priority:
        - "finanziell"
        - "schulden"
        - "liquidation"
    source_tiers:
      government: 1.0
      financial: 0.8
      general: 0.6
```

---

## 4) Configuration

### 4.1 Feed Configuration (`config/feeds.yaml`)

The feed configuration system supports multiple source types with sophisticated filtering and prioritization.

#### 4.1.1 RSS Feed Configuration

RSS feeds form the backbone of the content collection system. Each RSS source supports:

```yaml
rss:
  - name: "Source Display Name"
    url: "https://example.com/feed.rss"
    authority: "high|medium|low|government|financial"
    language: "de|en|fr|it"
    region: "swiss|eu|global"
    enabled: true
    poll_interval: 3600  # seconds
    custom_headers:
      User-Agent: "NewsAnalysis/2.0"
    filters:
      include_patterns:
        - "/business/"
        - "/finance/"
      exclude_patterns:
        - "/sports/"
        - "/entertainment/"
```

**Authority Levels:**
- `government`: Official government sources (SNB, FINMA, BFS) - highest priority
- `financial`: Financial news outlets (NZZ, FuW) - high priority  
- `high`: Major news outlets with strong business coverage
- `medium`: Regional news sources
- `low`: General interest sources with occasional business content

#### 4.1.2 Sitemap Configuration

XML sitemaps provide comprehensive coverage of larger news sites:

```yaml
sitemaps:
  - name: "20 Minuten Business"
    url: "https://www.20min.ch/sitemap.xml"
    authority: "medium"
    max_urls: 1000
    filter_patterns:
      - "/wirtschaft/"
      - "/geld/"
    exclude_patterns:
      - "/people/"
      - "/leben/"
    date_range_days: 7  # Only URLs from last 7 days
    respect_robots: true
```

#### 4.1.3 HTML Source Configuration

For sites without RSS feeds, direct HTML parsing:

```yaml
html:
  - name: "Custom News Source"
    url: "https://example.com/news"
    authority: "medium"
    selectors:
      container: ".news-list"
      link: "a.news-item"
      title: ".headline"
      date: ".publish-date"
      summary: ".excerpt"
    pagination:
      enabled: true
      next_selector: ".pagination .next"
      max_pages: 5
    rate_limit: 1.0  # seconds between requests
```

#### 4.1.4 Google News Integration

Google News support (disabled by default due to complexity):

```yaml
google_news:
  enabled: false  # Disabled by default
  query_templates:
    - "Switzerland bankruptcy"
    - "Swiss company insolvency"
    - "Schweiz Konkurs"
  languages: ["de", "en"]
  regions: ["CH"]
  max_results: 50
  decode_redirects: true
```

### 4.2 Topic Configuration (`config/topics.yaml`)

Topics define what content is relevant for analysis and how it should be classified.

#### 4.2.1 Core Topic Structure

```yaml
topics:
  creditreform_insights:
    enabled: true
    description: "Swiss business financial distress and bankruptcy monitoring"
    
    # Classification thresholds
    confidence_threshold: 0.7
    confidence_threshold_express: 0.8  # Higher threshold for express mode
    
    # Processing limits
    max_articles_per_run: 100
    max_articles_express: 25
    max_processing_time: 1800  # 30 minutes
    max_processing_time_express: 180  # 3 minutes
    
    # Content focus areas
    focus_areas:
      primary:
        - "bankruptcy proceedings"
        - "insolvency proceedings" 
        - "financial restructuring"
        - "company liquidation"
      secondary:
        - "payment difficulties"
        - "debt restructuring"
        - "credit rating changes"
        - "financial audits"
    
    # Keyword matching
    keywords:
      german:
        critical:
          - "konkurs"
          - "insolvenz"
          - "zahlungsunfähigkeit"
        important:
          - "sanierung"
          - "liquidation"
          - "überschuldung"
      english:
        critical:
          - "bankruptcy"
          - "insolvency"
          - "liquidation"
        important:
          - "financial difficulties"
          - "debt restructuring"
    
    # Source weighting
    source_tiers:
      government: 1.0
      financial: 0.8
      high: 0.7
      medium: 0.6
      low: 0.4
    
    # Geographic focus
    regions:
      primary: ["CH"]  # Switzerland
      secondary: ["DE", "AT"]  # Germany, Austria for context
    
    languages: ["de", "en", "fr", "it"]
    
    # AI model configuration
    classification_model: "gpt-5-nano"
    classification_prompt_template: |
      Analyze this Swiss business news article for bankruptcy, insolvency, 
      or financial distress indicators. Consider both direct mentions and 
      contextual indicators.
      
      Title: {title}
      URL: {url}
      Source: {source}
      
      Provide classification with confidence score (0.0-1.0).
```

### 4.3 Environment Configuration

#### 4.3.1 Core Environment Variables

```bash
# Database Configuration
DB_PATH=./news.db
DB_BACKUP_ENABLED=true
DB_BACKUP_INTERVAL=3600

# AI Model Configuration  
MODEL_NANO=gpt-5-nano           # Fast classification model
MODEL_MINI=gpt-4o-mini          # Content analysis model
MODEL_TIMEOUT=30                # Model request timeout

# Network Configuration
REQUEST_TIMEOUT_SEC=12          # HTTP request timeout
MAX_CONCURRENT_REQUESTS=5       # Parallel request limit
USER_AGENT="NewsAnalysis/2.0"   # HTTP User-Agent header

# Feature Flags
SKIP_GNEWS_REDIRECTS=true       # Disable Google News processing
ENABLE_PLAYWRIGHT=false         # Enable Playwright scraping
ENABLE_DEDUPLICATION=true       # Enable similarity detection
ENABLE_CACHING=true            # Enable processed links cache

# Logging Configuration
LOG_LEVEL=INFO                  # DEBUG, INFO, WARNING, ERROR
LOG_TO_FILE=true               # Enable file logging
LOG_ROTATION_SIZE=10MB         # Log file rotation size
LOG_RETENTION_DAYS=30          # Log file retention

# Express Mode Configuration
EXPRESS_MAX_ARTICLES=25         # Article limit for express runs
EXPRESS_TIMEOUT=180            # Express mode timeout (seconds)
EXPRESS_CONFIDENCE_BOOST=0.1   # Confidence threshold adjustment

# Export Configuration
EXPORT_FORMATS=json,md         # Default export formats
GERMAN_REPORT_ENABLED=true     # Enable German rating reports
EXPORT_COMPRESSION=true        # Compress export files
```

#### 4.3.2 Production Environment Template

```bash
# Production Configuration Template
# Copy to .env and customize

# Database
DB_PATH=/var/lib/news_analysis/news.db
DB_BACKUP_PATH=/var/backups/news_analysis/
DB_BACKUP_ENABLED=true
DB_BACKUP_INTERVAL=1800  # 30 minutes

# Performance
MAX_CONCURRENT_REQUESTS=10
REQUEST_TIMEOUT_SEC=20
ENABLE_CACHING=true
CACHE_TTL=86400  # 24 hours

# Reliability  
RETRY_ATTEMPTS=3
RETRY_BACKOFF=2.0
GRACEFUL_SHUTDOWN_TIMEOUT=30

# Monitoring
METRICS_ENABLED=true
METRICS_PORT=8080
HEALTH_CHECK_ENABLED=true

# Security
RESPECT_ROBOTS_TXT=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
```

### 4.4 MCP Server Configuration

The system supports Model Context Protocol (MCP) servers for extended functionality:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-playwright"],
      "env": {
        "PLAYWRIGHT_BROWSERS_PATH": "/opt/playwright"
      }
    },
    "perplexity": {
      "command": "node",
      "args": ["/opt/mcp-servers/perplexity/index.js"],
      "env": {
        "PERPLEXITY_API_KEY": "${PERPLEXITY_API_KEY}"
      }
    }
  }
}
```

---

## 5) Database Schema

### 5.1 Schema Overview

The NewsAnalysis_2.0 system uses SQLite as its primary datastore, optimized for both operational efficiency and analytical queries. The schema is designed for:

- **High Performance**: Optimized indexes for common query patterns
- **Data Integrity**: Foreign key constraints and validation
- **Flexibility**: JSON columns for semi-structured data
- **Scalability**: Partitioning-ready design for future growth

### 5.2 Core Tables

#### 5.2.1 feeds Table

Stores configuration for all news sources loaded from `feeds.yaml`:

```sql
CREATE TABLE feeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK (kind IN ('rss', 'sitemap', 'html', 'google_news')),
    url TEXT NOT NULL,
    authority TEXT NOT NULL DEFAULT 'medium' 
        CHECK (authority IN ('government', 'financial', 'high', 'medium', 'low')),
    language TEXT DEFAULT 'de' CHECK (language IN ('de', 'en', 'fr', 'it')),
    region TEXT DEFAULT 'swiss',
    enabled BOOLEAN NOT NULL DEFAULT 1,
    poll_interval INTEGER DEFAULT 3600,  -- seconds
    last_polled_at TIMESTAMP,
    last_success_at TIMESTAMP,
    error_count INTEGER DEFAULT 0,
    config_json TEXT,  -- Additional configuration as JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for feeds table
CREATE INDEX idx_feeds_kind_enabled ON feeds(kind, enabled);
CREATE INDEX idx_feeds_authority ON feeds(authority);
CREATE INDEX idx_feeds_last_polled ON feeds(last_polled_at);
```

#### 5.2.2 items Table

Central table storing all discovered news articles:

```sql
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,  -- Source name from feeds
    url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,  -- Cleaned URL for deduplication
    url_hash TEXT NOT NULL,  -- SHA-256 hash of normalized_url
    title TEXT NOT NULL,
    description TEXT,  -- RSS description/summary
    published_at TIMESTAMP,  -- Original publication date
    first_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Triage results
    triage_topic TEXT,  -- Matched topic name
    triage_confidence REAL,  -- 0.0 to 1.0
    triage_at TIMESTAMP,
    is_match BOOLEAN DEFAULT 0,  -- 1 if confidence >= threshold
    
    -- Processing status
    scraped_at TIMESTAMP,
    summarized_at TIMESTAMP,
    export_count INTEGER DEFAULT 0,
    
    -- Metadata
    language TEXT,
    region TEXT,
    priority_score REAL,  -- Computed priority for processing order
    
    UNIQUE(url_hash)
);

-- Core indexes for items
CREATE INDEX idx_items_source ON items(source);
CREATE INDEX idx_items_url_hash ON items(url_hash);
CREATE INDEX idx_items_normalized_url ON items(normalized_url);
CREATE INDEX idx_items_published_at ON items(published_at);
CREATE INDEX idx_items_first_seen_at ON items(first_seen_at);
CREATE INDEX idx_items_triage ON items(triage_topic, is_match);
CREATE INDEX idx_items_match_confidence ON items(is_match, triage_confidence DESC);
CREATE INDEX idx_items_priority ON items(priority_score DESC);
CREATE INDEX idx_items_processing_status ON items(scraped_at, summarized_at);

-- Composite indexes for common queries
CREATE INDEX idx_items_source_match_date ON items(source, is_match, published_at DESC);
CREATE INDEX idx_items_topic_confidence_date ON items(triage_topic, triage_confidence DESC, published_at DESC);
```

#### 5.2.3 items_fts Table

Full-text search table for content discovery:

```sql
CREATE VIRTUAL TABLE items_fts USING fts5(
    title, 
    description,
    url,
    content='items',  -- Link to items table
    content_rowid='id'
);

-- Triggers to maintain FTS index
CREATE TRIGGER items_fts_insert AFTER INSERT ON items BEGIN
    INSERT INTO items_fts(rowid, title, description, url) 
    VALUES (new.id, new.title, new.description, new.url);
END;

CREATE TRIGGER items_fts_delete AFTER DELETE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, description, url) 
    VALUES('delete', old.id, old.title, old.description, old.url);
END;

CREATE TRIGGER items_fts_update AFTER UPDATE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, description, url) 
    VALUES('delete', old.id, old.title, old.description, old.url);
    INSERT INTO items_fts(rowid, title, description, url) 
    VALUES (new.id, new.title, new.description, new.url);
END;
```

#### 5.2.4 articles Table

Stores scraped content for matched articles:

```sql
CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    extracted_text TEXT NOT NULL,
    extracted_html TEXT,  -- Original HTML if needed
    word_count INTEGER,
    extraction_method TEXT NOT NULL 
        CHECK (extraction_method IN ('trafilatura', 'playwright', 'jsonld', 'fallback')),
    extraction_quality REAL,  -- 0.0 to 1.0 quality score
    extracted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Content metadata
    author TEXT,
    publish_date TIMESTAMP,
    language_detected TEXT,
    encoding TEXT DEFAULT 'utf-8',
    
    -- Technical metadata  
    final_url TEXT,  -- URL after redirects
    http_status INTEGER,
    content_type TEXT,
    extraction_time_ms INTEGER,
    
    FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE
);

-- Indexes for articles
CREATE UNIQUE INDEX idx_articles_item_id ON articles(item_id);
CREATE INDEX idx_articles_extracted_at ON articles(extracted_at);
CREATE INDEX idx_articles_method_quality ON articles(extraction_method, extraction_quality DESC);
CREATE INDEX idx_articles_word_count ON articles(word_count);
CREATE INDEX idx_articles_language ON articles(language_detected);
```

#### 5.2.5 summaries Table

AI-generated summaries and analysis results:

```sql
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    model TEXT NOT NULL,  -- AI model used
    
    -- Summary content
    title TEXT,  -- Cleaned/standardized title
    summary TEXT NOT NULL,  -- Main summary text
    key_points_json TEXT,  -- JSON array of key points
    entities_json TEXT,  -- JSON object with named entities
    sentiment_score REAL,  -- -1.0 to 1.0
    relevance_score REAL,  -- 0.0 to 1.0
    
    -- Analysis metadata
    word_count_original INTEGER,
    word_count_summary INTEGER,
    compression_ratio REAL,  -- summary_words / original_words
    processing_time_ms INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE
);

-- Indexes for summaries
CREATE INDEX idx_summaries_item_id ON summaries(item_id);
CREATE INDEX idx_summaries_topic_model ON summaries(topic, model);
CREATE INDEX idx_summaries_relevance ON summaries(relevance_score DESC);
CREATE INDEX idx_summaries_sentiment ON summaries(sentiment_score);
CREATE INDEX idx_summaries_created_at ON summaries(created_at);
```

### 5.3 Pipeline Management Tables

#### 5.3.1 pipeline_state Table

Tracks pipeline execution state for resumable processing:

```sql
CREATE TABLE pipeline_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,  -- UUID for this pipeline run
    step_name TEXT NOT NULL CHECK (step_name IN 
        ('collect', 'filter', 'scrape', 'deduplicate', 'summarize', 'digest')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN 
        ('pending', 'running', 'completed', 'failed', 'paused')),
    
    -- Execution tracking
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    
    -- Progress tracking  
    total_items INTEGER,
    processed_items INTEGER DEFAULT 0,
    successful_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    skipped_items INTEGER DEFAULT 0,
    
    -- Results
    article_count INTEGER DEFAULT 0,
    match_count INTEGER DEFAULT 0,
    
    -- State data
    metadata_json TEXT,  -- Step-specific metadata
    checkpoint_data TEXT,  -- Resumption data
    error_message TEXT,
    
    -- Flags
    can_resume BOOLEAN DEFAULT 1,
    is_express_mode BOOLEAN DEFAULT 0,
    
    UNIQUE(run_id, step_name)
);

-- Indexes for pipeline_state
CREATE INDEX idx_pipeline_state_run_id ON pipeline_state(run_id);
CREATE INDEX idx_pipeline_state_status ON pipeline_state(status);
CREATE INDEX idx_pipeline_state_step ON pipeline_state(step_name, status);
CREATE INDEX idx_pipeline_state_started ON pipeline_state(started_at);
CREATE INDEX idx_pipeline_state_resumable ON pipeline_state(can_resume, status);
```

#### 5.3.2 processed_links Table

Cache table to prevent reprocessing of articles:

```sql
CREATE TABLE processed_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT NOT NULL,
    url TEXT NOT NULL,
    topic TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('match', 'no_match', 'error')),
    confidence REAL,  -- Triage confidence if applicable
    model TEXT,  -- AI model used for classification
    processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Expiration management
    expires_at TIMESTAMP,  -- Cache entry expiration
    last_accessed_at TIMESTAMP,
    access_count INTEGER DEFAULT 1,
    
    UNIQUE(url_hash, topic)
);

-- Indexes for processed_links
CREATE INDEX idx_processed_links_url_hash ON processed_links(url_hash);
CREATE INDEX idx_processed_links_topic_result ON processed_links(topic, result);
CREATE INDEX idx_processed_links_expires ON processed_links(expires_at);
CREATE INDEX idx_processed_links_processed_at ON processed_links(processed_at);
```

#### 5.3.3 article_clusters Table

Manages article deduplication through clustering:

```sql
CREATE TABLE article_clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster_id TEXT NOT NULL,  -- UUID for cluster group
    item_id INTEGER NOT NULL,  -- Reference to items table
    is_primary BOOLEAN NOT NULL DEFAULT 0,  -- 1 for cluster representative
    similarity_score REAL,  -- 0.0 to 1.0 similarity to cluster centroid
    clustering_method TEXT NOT NULL CHECK (clustering_method IN 
        ('sentence_transformer', 'tfidf', 'basic_similarity')),
    cluster_size INTEGER,  -- Total articles in this cluster
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE
);

-- Indexes for article_clusters
CREATE INDEX idx_article_clusters_cluster_id ON article_clusters(cluster_id);
CREATE INDEX idx_article_clusters_item_id ON article_clusters(item_id);
CREATE INDEX idx_article_clusters_primary ON article_clusters(is_primary, similarity_score DESC);
CREATE INDEX idx_article_clusters_method ON article_clusters(clustering_method);
CREATE INDEX idx_article_clusters_created_at ON article_clusters(created_at);
```

### 5.4 Analytical Views

#### 5.4.1 Daily Processing Statistics

```sql
CREATE VIEW daily_stats AS
SELECT 
    DATE(first_seen_at) as date,
    COUNT(*) as total_items,
    COUNT(CASE WHEN is_match = 1 THEN 1 END) as matched_items,
    COUNT(CASE WHEN scraped_at IS NOT NULL THEN 1 END) as scraped_items,
    COUNT(CASE WHEN summarized_at IS NOT NULL THEN 1 END) as summarized_items,
    ROUND(AVG(CASE WHEN is_match = 1 THEN triage_confidence END), 3) as avg_confidence,
    COUNT(DISTINCT source) as active_sources
FROM items
GROUP BY DATE(first_seen_at)
ORDER BY date DESC;
```

#### 5.4.2 Source Performance View

```sql
CREATE VIEW source_performance AS
SELECT 
    i.source,
    f.authority,
    COUNT(*) as total_articles,
    COUNT(CASE WHEN i.is_match = 1 THEN 1 END) as matches,
    ROUND(100.0 * COUNT(CASE WHEN i.is_match = 1 THEN 1 END) / COUNT(*), 2) as match_rate_pct,
    ROUND(AVG(CASE WHEN i.is_match = 1 THEN i.triage_confidence END), 3) as avg_confidence,
    MAX(i.first_seen_at) as last_article_date
FROM items i
LEFT JOIN feeds f ON i.source = f.name
GROUP BY i.source, f.authority
ORDER BY matches DESC, match_rate_pct DESC;
```

---

## 6) Components & Algorithms

### 6.1 Collection System (`news_pipeline/collector.py`)

The collection system is responsible for discovering and ingesting URLs from various news sources.

#### 6.1.1 RSS Feed Processing

**Algorithm:**
1. **Feed Discovery**: Parse RSS/Atom feeds using `feedparser` library
2. **Content Extraction**: Extract title, URL, description, and publication date
3. **Normalization**: Apply URL normalization and generate content hashes
4. **Deduplication**: Check against existing `items` using `url_hash`
5. **Persistence**: Insert new items into database with metadata

**Key Features:**
- Support for RSS 2.0, Atom 1.0, and various RSS extensions
- Robust error handling for malformed feeds
- Timezone-aware date parsing
- Custom header support for authentication/user-agent
- Rate limiting and respectful crawling

```python
class RSSCollector:
    def collect_from_feed(self, feed_config):
        """
        Collect articles from RSS feed with error handling and normalization.
        
        Args:
            feed_config: Dictionary with feed configuration
            
        Returns:
            List of normalized article dictionaries
        """
        try:
            feed = feedparser.parse(feed_config['url'], 
                                  request_headers=self._get_headers())
            
            articles = []
            for entry in feed.entries:
                article = self._normalize_entry(entry, feed_config)
                if article and self._is_valid_article(article):
                    articles.append(article)
                    
            return articles
            
        except Exception as e:
            logger.error(f"RSS collection failed for {feed_config['name']}: {e}")
            return []
```

#### 6.1.2 Sitemap Processing

**Algorithm:**
1. **XML Parsing**: Parse sitemap XML to extract URL listings
2. **Filtering**: Apply date range and URL pattern filters
3. **Prioritization**: Score URLs by recency and relevance patterns
4. **Batch Processing**: Process URLs in manageable batches

**Performance Optimizations:**
- Streaming XML parsing for large sitemaps
- Parallel processing of URL validation
- Intelligent caching of sitemap metadata
- Respectful crawling with configurable delays

#### 6.1.3 HTML Content Discovery

**Algorithm:**
1. **Page Fetching**: Retrieve HTML content with custom headers
2. **CSS Selection**: Apply configured selectors to extract links
3. **Data Extraction**: Parse title, date, and summary information
4. **Pagination**: Follow pagination links within configured limits
5. **Content Validation**: Verify extracted data quality

**Robustness Features:**
- Multiple fallback selectors for each data type
- JavaScript rendering detection and warnings
- Character encoding detection and handling
- Broken link detection and reporting

### 6.2 AI Filtering System (`news_pipeline/filter.py`)

The filtering system provides cost-effective AI-powered relevance classification.

#### 6.2.1 Classification Algorithm

**Multi-Stage Classification Process:**

1. **Pre-filtering**: Apply keyword and URL pattern filters for obvious matches/rejections
2. **Priority Scoring**: Calculate multi-factor priority scores:
   ```python
   priority_score = (
       source_authority_weight * 0.4 +
       freshness_decay_factor * 0.3 +
       url_quality_score * 0.2 +
       title_keyword_bonus * 0.1
   )
   ```
3. **AI Classification**: Use LLM for title/URL analysis with structured output
4. **Confidence Thresholding**: Apply topic-specific confidence thresholds
5. **Early Termination**: Stop processing when sufficient matches found

**Priority Scoring Components:**

- **Source Authority**: Government (1.0) > Financial (0.8) > High (0.7) > Medium (0.6) > Low (0.4)
- **Freshness Decay**: Exponential decay with configurable half-life (default 24 hours)
- **URL Quality**: Penalize generic URLs, reward specific business/finance paths
- **Keyword Bonus**: Boost for title containing critical keywords

#### 6.2.2 AI Model Integration

**Structured Classification Prompt:**
```python
classification_prompt = f"""
Analyze this Swiss business news article for relevance to {topic_description}.

Article Details:
- Title: {title}
- URL: {url}  
- Source: {source_name} ({source_authority})
- Published: {published_date}

Focus Areas: {focus_areas}
Keywords: {keywords}

Provide classification as JSON:
{{
    "is_relevant": boolean,
    "confidence": float (0.0-1.0),
    "reasoning": "explanation",
    "key_indicators": [list of relevant phrases/concepts],
    "business_entities": [list of companies/organizations mentioned]
}}
"""
```

**Response Validation:**
- JSON Schema validation using `schemas/triage.schema.json`
- Confidence score validation (0.0-1.0 range)
- Required field presence checking
- Fallback scoring for invalid responses

#### 6.2.3 Batch Processing Optimization

**Batch Management:**
- Dynamic batch sizing based on processing speed
- Priority-based ordering within batches
- Parallel classification with configurable concurrency
- Progress tracking and checkpoint creation

**Cost Optimization:**
- Token count estimation before API calls
- Model switching based on complexity (nano for simple, mini for complex)
- Aggressive caching of classification results
- Early termination when match quota reached

### 6.3 Content Scraping System (`news_pipeline/scraper.py`)

The scraping system extracts full article content using multiple strategies.

#### 6.3.1 Multi-Strategy Content Extraction

**Primary Strategy: Trafilatura**
- High-recall configuration optimized for news content
- Language detection and encoding handling
- Structured data extraction (JSON-LD, microdata)
- Content quality scoring

**Secondary Strategy: MCP + Playwright**
- JavaScript-heavy sites requiring browser rendering
- Dynamic content loading and interaction
- Anti-bot detection circumvention
- Screenshot capture for debugging

**Fallback Strategy: Basic HTML Parsing**
- CSS selector-based content extraction
- Multiple selector attempts for robustness
- Text cleaning and formatting
- Minimum content length validation

#### 6.3.2 Content Quality Assessment

**Quality Metrics:**
1. **Content Length**: Minimum word count requirements
2. **Text Density**: Ratio of text to HTML markup
3. **Language Consistency**: Match expected language
4. **Structural Indicators**: Presence of article elements
5. **Duplicate Detection**: Check against existing content

**Quality Scoring Algorithm:**
```python
def calculate_quality_score(content, metadata):
    score = 0.0
    
    # Length scoring (0-0.3)
    word_count = len(content.split())
    if word_count >= 100:
        score += min(0.3, word_count / 1000 * 0.3)
    
    # Structure scoring (0-0.2)  
    if metadata.get('title'):
        score += 0.1
    if metadata.get('author'):
        score += 0.05
    if metadata.get('publish_date'):
        score += 0.05
    
    # Language scoring (0-0.2)
    if metadata.get('language') == expected_language:
        score += 0.2
    
    # Content density (0-0.3)
    density = calculate_text_density(content, metadata.get('html'))
    score += density * 0.3
    
    return min(1.0, score)
```

#### 6.3.3 Google News Decoder

**Redirect Resolution Algorithm:**
1. **URL Pattern Detection**: Identify Google News redirect patterns
2. **Parameter Extraction**: Parse encoded target URL from parameters
3. **Validation**: Verify decoded URL is accessible and valid
4. **Caching**: Store successful decodings to avoid reprocessing
5. **Fallback**: Handle failed decodings gracefully

**Google News URL Patterns:**
- `https://news.google.com/rss/articles/[encoded]`
- `https://news.google.com/articles/[article_id]`
- Various regional and language-specific patterns

### 6.4 Deduplication System (`news_pipeline/deduplication.py`)

The deduplication system identifies and clusters similar articles.

#### 6.4.1 Similarity Detection Algorithms

**SentenceTransformers (Primary)**
- Uses multilingual BERT models for semantic similarity
- Generates 768-dimensional embeddings
- Cosine similarity for distance calculation
- Configurable similarity threshold (default 0.85)

**TF-IDF (Secondary)**
- Term frequency-inverse document frequency vectorization
- Language-specific stopword removal
- N-gram features (1-3 grams)
- Efficient sparse matrix operations

**Basic String Similarity (Fallback)**
- Levenshtein distance for title comparison
- Jaccard similarity for content overlap
- URL similarity scoring
- Fast computation for large datasets

#### 6.4.2 Clustering Algorithm

**Hierarchical Clustering Process:**
1. **Embedding Generation**: Create vector representations of articles
2. **Distance Calculation**: Compute pairwise similarities
3. **Cluster Formation**: Group articles exceeding similarity threshold
4. **Primary Selection**: Choose best representative per cluster
5. **Metadata Storage**: Persist cluster relationships

**Primary Article Selection Criteria:**
1. **Source Authority**: Government > Financial > High > Medium > Low
2. **Content Quality**: Higher extraction quality scores preferred
3. **Publication Date**: More recent articles preferred
4. **Content Length**: Longer, more comprehensive articles preferred
5. **Classification Confidence**: Higher AI confidence scores preferred

#### 6.4.3 Performance Optimization

**Scalability Enhancements:**
- Incremental clustering for new articles
- Batch processing for similarity calculations
- Sparse matrix operations for efficiency
- Configurable processing limits

**Memory Management:**
- Streaming processing for large article sets
- Periodic cleanup of intermediate results
- Configurable batch sizes based on available memory
- Efficient data structures for similarity storage

### 6.5 Summarization System (`news_pipeline/summarizer.py`)

The summarization system generates structured analysis of articles.

#### 6.5.1 Summary Generation Algorithm

**Multi-Component Summarization:**
1. **Title Normalization**: Clean and standardize article titles
2. **Content Summarization**: Generate concise article summaries (≤200 words)
3. **Key Points Extraction**: Identify 3-6 most important points
4. **Entity Recognition**: Extract companies, people, locations, topics
5. **Sentiment Analysis**: Assess overall article sentiment
6. **Relevance Scoring**: Calculate topic-specific relevance

**Summary Structure (JSON Schema):**
```json
{
  "title": "Normalized article title",
  "summary": "Concise article summary (≤200 words)",
  "key_points": ["Point 1", "Point 2", "..."],
  "entities": {
    "companies": ["Company A", "Company B"],
    "people": ["Person X", "Person Y"],
    "locations": ["Location 1", "Location 2"],
    "topics": ["Topic A", "Topic B"]
  },
  "sentiment_score": 0.2,
  "relevance_score": 0.85,
  "metadata": {
    "word_count_original": 800,
    "word_count_summary": 150,
    "compression_ratio": 0.19,
    "processing_time_ms": 2500
  }
}
```

#### 6.5.2 Entity Recognition

**Multi-Language Entity Detection:**
- **German**: Companies (AG, GmbH, SA), places, person names
- **English**: Corporations (Inc, Ltd, Corp), locations, individuals
- **French**: Société (SA, SARL), geographic entities
- **Italian**: Società (SpA, SRL), regional identifiers

**Entity Validation:**
- Minimum entity length requirements
- Blacklist filtering for common false positives
- Context validation for ambiguous entities
- Confidence scoring for extracted entities

### 6.6 State Management System (`news_pipeline/state_manager.py`)

The state management system orchestrates pipeline execution and provides resumability.

#### 6.6.1 Pipeline Orchestration

**Execution Flow Management:**
1. **Run Initialization**: Create unique run ID and initialize state
2. **Step Dependencies**: Validate prerequisite step completion
3. **Progress Tracking**: Monitor processing metrics and estimates
4. **Checkpoint Creation**: Save intermediate results at step boundaries  
5. **Error Handling**: Capture errors with context for debugging
6. **Graceful Shutdown**: Handle interruption signals cleanly

**State Persistence:**
```python
class PipelineState:
    def create_run(self, is_express_mode=False):
        """Create new pipeline run with initial state."""
        run_id = str(uuid.uuid4())
        steps = ['collect', 'filter', 'scrape', 'deduplicate', 'summarize', 'digest']
        
        for step in steps:
            self.db.execute("""
                INSERT INTO pipeline_state (run_id, step_name, status, is_express_mode)
                VALUES (?, ?, 'pending', ?)
            """, (run_id, step, is_express_mode))
        
        return run_id
```

#### 6.6.2 Resume Capability

**Resumption Logic:**
1. **State Detection**: Identify incomplete pipeline runs
2. **Integrity Validation**: Verify data consistency at resume point
3. **Context Restoration**: Reload step-specific configuration and data
4. **Progress Continuation**: Resume from last successful checkpoint
5. **Error Recovery**: Handle partial failures gracefully

**Resume Safety Checks:**
- Database consistency validation
- Configuration compatibility verification
- Resource availability confirmation
- Time-based expiration handling

---

## 7) CLI Usage

### 7.1 Command Overview

The `news_analyzer.py` script provides comprehensive command-line interface for all pipeline operations.

#### 7.1.1 Basic Usage Patterns

```bash
# Complete pipeline execution
python news_analyzer.py

# Express mode (fast processing, <3 minutes)
python news_analyzer.py --express

# Step-by-step execution
python news_analyzer.py --step collect
python news_analyzer.py --step filter --limit 50
python news_analyzer.py --step scrape --resume [run_id]

# Diagnostic and export operations
python news_analyzer.py --stats
python news_analyzer.py --export --format json
python news_analyzer.py --export --format md --date 2025-09-20
```

### 7.2 Command Reference

#### 7.2.1 Pipeline Execution Commands

**Full Pipeline:**
```bash
python news_analyzer.py [OPTIONS]
```

**Options:**
- `--express`: Enable express mode with time and article limits
- `--dry-run`: Simulate execution without making changes
- `--force`: Force execution even if recent run exists
- `--config CONFIG_FILE`: Use alternative configuration file

**Step-wise Execution:**
```bash
python news_analyzer.py --step STEP_NAME [OPTIONS]
```

**Step Names:**
- `collect`: Gather URLs from configured sources
- `filter`: AI-powered relevance classification
- `scrape`: Extract full article content
- `deduplicate`: Cluster and remove duplicate articles
- `summarize`: Generate article summaries and analysis
- `digest`: Create daily digest and reports

**Step Options:**
- `--limit N`: Process maximum N articles
- `--resume RUN_ID`: Resume specific pipeline run
- `--topic TOPIC`: Process specific topic only
- `--source SOURCE`: Process specific source only

#### 7.2.2 Management Commands

**Database Operations:**
```bash
# Initialize database schema
python scripts/init_db.py

# Load feed configuration
python scripts/load_feeds.py

# Database maintenance
python scripts/maintenance/vacuum.py
python scripts/maintenance/cleanup.py --days 30
```

**State Management:**
```bash
# List pipeline runs
python news_analyzer.py --list-runs

# Show run details
python news_analyzer.py --show-run RUN_ID

# Clean up failed runs
python news_analyzer.py --cleanup-runs --status failed

# Resume incomplete runs
python news_analyzer.py --resume RUN_ID
```

#### 7.2.3 Export and Analysis Commands

**Data Export:**
```bash
# Export daily digest
python news_analyzer.py --export --format json
python news_analyzer.py --export --format md --date 2025-09-20

# Export specific topic
python news_analyzer.py --export --topic creditreform_insights

# Export raw data
python news_analyzer.py --export-raw --table items --limit 1000
```

**Statistics and Analysis:**
```bash
# Pipeline statistics
python news_analyzer.py --stats

# Source performance
python news_analyzer.py --stats --by-source

# Processing metrics
python news_analyzer.py --stats --processing

# Match analysis
python news_analyzer.py --analyze-matches --topic creditreform_insights
```

### 7.3 Advanced Usage

#### 7.3.1 Configuration Overrides

**Environment Variables:**
```bash
# Override database path
DB_PATH=/custom/path/news.db python news_analyzer.py

# Use different AI model
MODEL_NANO=gpt-4o-mini python news_analyzer.py --step filter

# Enable debug logging
LOG_LEVEL=DEBUG python news_analyzer.py --debug
```

**Configuration Files:**
```bash
# Use custom configuration
python news_analyzer.py --config /custom/config/topics.yaml

# Override specific settings
python news_analyzer.py --set max_articles_per_run=50 --set confidence_threshold=0.8
```

#### 7.3.2 Batch Processing

**Multiple Topics:**
```bash
# Process all enabled topics
python news_analyzer.py --all-topics

# Process specific topics
python news_analyzer.py --topics creditreform_insights,general_business
```

**Date Range Processing:**
```bash
# Process specific date range
python news_analyzer.py --start-date 2025-09-01 --end-date 2025-09-20

# Process last N days
python news_analyzer.py --days 7
```

#### 7.3.3 Monitoring and Debugging

**Verbose Output:**
```bash
# Debug mode with detailed logging
python news_analyzer.py --debug --verbose

# Trace mode for troubleshooting
python news_analyzer.py --trace --step filter
```

**Progress Monitoring:**
```bash
# Watch mode for real-time updates
python news_analyzer.py --watch

# Progress notification
python news_analyzer.py --notify-email admin@company.com
```

### 7.4 Common Workflows

#### 7.4.1 Daily Operations

**Morning News Check:**
```bash
#!/bin/bash
# Daily express run for urgent insights
python news_analyzer.py --express --notify-email team@company.com

# If matches found, generate full report
if [ $? -eq 0 ]; then
    python news_analyzer.py --export --format md --email
fi
```

**Full Daily Processing:**
```bash
#!/bin/bash
# Complete daily news analysis
python news_analyzer.py --force

# Generate reports
python news_analyzer.py --export --format json
python news_analyzer.py --export --format md

# German rating report if applicable
python news_analyzer.py --german-report
```

#### 7.4.2 Maintenance Workflows

**Weekly Maintenance:**
```bash
#!/bin/bash
# Database cleanup
python scripts/maintenance/cleanup.py --days 30

# Vacuum database
python scripts/maintenance/vacuum.py

# Update feed configuration
python scripts/load_feeds.py --update
```

**Performance Monitoring:**
```bash
#!/bin/bash
# Generate performance report
python news_analyzer.py --stats --export > weekly_stats.json

# Check for issues
python news_analyzer.py --health-check --alert-threshold 0.5
```

---

## 8) API Reference

### 8.1 Core Classes

#### 8.1.1 NewsCollector

**Class: `news_pipeline.collector.NewsCollector`**

Primary class for collecting articles from various news sources.

**Constructor:**
```python
NewsCollector(db_path: str = None, config: dict = None)
```

**Methods:**

```python
def collect_from_sources(self, source_types: List[str] = None, limit: int = None) -> Dict[str, Any]:
    """
    Collect articles from configured news sources.
    
    Args:
        source_types: List of source types to collect from ('rss', 'sitemap', 'html')
        limit: Maximum number of articles to collect per source
        
    Returns:
        Dictionary with collection statistics and results
        
    Example:
        collector = NewsCollector()
        results = collector.collect_from_sources(['rss'], limit=100)
        print(f"Collected {results['total_articles']} articles")
    """
```

```python
def collect_from_rss(self, feed_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Collect articles from a single RSS feed.
    
    Args:
        feed_config: RSS feed configuration dictionary
        
    Returns:
        List of normalized article dictionaries
    """
```

```python
def collect_from_sitemap(self, sitemap_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Collect articles from XML sitemap.
    
    Args:
        sitemap_config: Sitemap configuration dictionary
        
    Returns:
        List of discovered article URLs with metadata
    """
```

#### 8.1.2 AIFilter

**Class: `news_pipeline.filter.AIFilter`**

AI-powered article classification and relevance filtering.

**Constructor:**
```python
AIFilter(db_path: str = None, model_name: str = None, config: dict = None)
```

**Methods:**

```python
def classify_articles(self, topic: str, limit: int = None, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Classify articles for relevance to specified topic.
    
    Args:
        topic: Topic name from configuration
        limit: Maximum articles to process
        force_refresh: Skip cache and reprocess articles
        
    Returns:
        Dictionary with classification statistics
        
    Example:
        filter_system = AIFilter()
        results = filter_system.classify_articles('creditreform_insights', limit=50)
        print(f"Found {results['matches']} relevant articles")
    """
```

```python
def classify_article(self, article: Dict[str, Any], topic_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify single article for topic relevance.
    
    Args:
        article: Article dictionary with title, url, source
        topic_config: Topic configuration dictionary
        
    Returns:
        Classification result with confidence score and reasoning
    """
```

```python
def calculate_priority_score(self, article: Dict[str, Any], topic_config: Dict[str, Any]) -> float:
    """
    Calculate priority score for article processing order.
    
    Args:
        article: Article dictionary
        topic_config: Topic configuration
        
    Returns:
        Priority score (0.0 to 1.0)
    """
```

#### 8.1.3 ContentScraper

**Class: `news_pipeline.scraper.ContentScraper`**

Content extraction from web articles using multiple strategies.

**Constructor:**
```python
ContentScraper(db_path: str = None, config: dict = None)
```

**Methods:**

```python
def scrape_articles(self, limit: int = None, method: str = 'auto') -> Dict[str, Any]:
    """
    Scrape content for matched articles.
    
    Args:
        limit: Maximum articles to scrape
        method: Extraction method ('trafilatura', 'playwright', 'auto')
        
    Returns:
        Dictionary with scraping statistics and results
    """
```

```python
def scrape_article(self, url: str, method: str = 'auto') -> Dict[str, Any]:
    """
    Extract content from single article URL.
    
    Args:
        url: Article URL to scrape
        method: Extraction method
        
    Returns:
        Extracted content with metadata and quality score
    """
```

```python
def extract_with_trafilatura(self, url: str) -> Dict[str, Any]:
    """
    Extract content using Trafilatura library.
    
    Args:
        url: Article URL
        
    Returns:
        Extracted content and metadata
    """
```

#### 8.1.4 ArticleDeduplicator

**Class: `news_pipeline.deduplication.ArticleDeduplicator`**

Similarity detection and duplicate article clustering.

**Constructor:**
```python
ArticleDeduplicator(db_path: str = None, config: dict = None)
```

**Methods:**

```python
def deduplicate_articles(self, similarity_threshold: float = 0.85) -> Dict[str, Any]:
    """
    Identify and cluster similar articles.
    
    Args:
        similarity_threshold: Minimum similarity for clustering (0.0-1.0)
        
    Returns:
        Deduplication statistics and cluster information
    """
```

```python
def calculate_similarity(self, article1: str, article2: str, method: str = 'auto') -> float:
    """
    Calculate similarity between two articles.
    
    Args:
        article1: First article content
        article2: Second article content  
        method: Similarity method ('sentence_transformer', 'tfidf', 'basic')
        
    Returns:
        Similarity score (0.0-1.0)
    """
```

#### 8.1.5 PipelineStateManager

**Class: `news_pipeline.state_manager.PipelineStateManager`**

Pipeline orchestration and state management.

**Constructor:**
```python
PipelineStateManager(db_path: str = None)
```

**Methods:**

```python
def create_run(self, is_express_mode: bool = False) -> str:
    """
    Initialize new pipeline run.
    
    Args:
        is_express_mode: Enable express mode constraints
        
    Returns:
        Unique run ID for tracking
    """
```

```python
def resume_run(self, run_id: str) -> bool:
    """
    Resume incomplete pipeline run.
    
    Args:
        run_id: Run ID to resume
        
    Returns:
        True if run can be resumed, False otherwise
    """
```

```python
def update_step_status(self, run_id: str, step_name: str, status: str, metadata: dict = None):
    """
    Update status of pipeline step.
    
    Args:
        run_id: Pipeline run identifier
        step_name: Name of pipeline step
        status: New status ('pending', 'running', 'completed', 'failed', 'paused')
        metadata: Optional metadata dictionary
    """
```

```python
def get_run_status(self, run_id: str) -> Dict[str, Any]:
    """
    Get current status of pipeline run.
    
    Args:
        run_id: Pipeline run identifier
        
    Returns:
        Dictionary with run status and progress information
    """
```

### 8.2 Utility Functions

#### 8.2.1 URL Utilities (`news_pipeline/utils.py`)

**Function Reference:**

```python
def normalize_url(url: str) -> str:
    """
    Normalize URL for consistent handling and deduplication.
    
    Args:
        url: Raw URL string
        
    Returns:
        Normalized URL string
        
    Example:
        normalized = normalize_url("https://example.com/article?utm_source=google")
        # Returns: "https://example.com/article"
    """
```

```python
def url_hash(url: str) -> str:
    """
    Generate SHA-256 hash of normalized URL.
    
    Args:
        url: URL string to hash
        
    Returns:
        Hexadecimal hash string
    """
```

```python
def is_robots_allowed(url: str, user_agent: str = '*') -> bool:
    """
    Check if URL is allowed by robots.txt.
    
    Args:
        url: URL to check
        user_agent: User agent string
        
    Returns:
        True if crawling is allowed, False otherwise
    """
```

#### 8.2.2 Database Utilities

```python
def get_db_connection(db_path: str = None) -> sqlite3.Connection:
    """
    Get database connection with proper configuration.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        Configured SQLite connection object
    """
```

```python
def execute_with_retry(connection: sqlite3.Connection, query: str, params: tuple = None, 
                      max_retries: int = 3) -> Any:
    """
    Execute database query with retry logic.
    
    Args:
        connection: Database connection
        query: SQL query string
        params: Query parameters tuple
        max_retries: Maximum retry attempts
        
    Returns:
        Query result
    """
```

### 8.3 Configuration Classes

#### 8.3.1 TopicConfig

**Class: `news_pipeline.config.TopicConfig`**

Configuration wrapper for topic settings.

```python
class TopicConfig:
    def __init__(self, topic_name: str, config_dict: Dict[str, Any]):
        """
        Initialize topic configuration.
        
        Args:
            topic_name: Name of the topic
            config_dict: Configuration dictionary from topics.yaml
        """
    
    def get_confidence_threshold(self, is_express: bool = False) -> float:
        """Get confidence threshold for topic."""
        
    def get_max_articles(self, is_express: bool = False) -> int:
        """Get maximum articles limit for topic."""
        
    def get_keywords(self, language: str = 'de') -> List[str]:
        """Get keywords list for specified language."""
```

### 8.4 Exception Classes

#### 8.4.1 Custom Exceptions

```python
class NewsAnalysisError(Exception):
    """Base exception for NewsAnalysis system."""
    pass

class CollectionError(NewsAnalysisError):
    """Exception raised during article collection."""
    pass

class ClassificationError(NewsAnalysisError):
    """Exception raised during AI classification."""
    pass

class ScrapingError(NewsAnalysisError):
    """Exception raised during content extraction."""
    pass

class DeduplicationError(NewsAnalysisError):
    """Exception raised during deduplication."""
    pass

class StateError(NewsAnalysisError):
    """Exception raised during state management."""
    pass
```

---

## 9) Logging & Observability

### 9.1 Logging System

The NewsAnalysis_2.0 system implements comprehensive logging for debugging, monitoring, and audit trails.

#### 9.1.1 Log Configuration

**Log Levels:**
- `DEBUG`: Detailed diagnostic information
- `INFO`: General operational messages  
- `WARNING`: Important events that may need attention
- `ERROR`: Error conditions that don't stop execution
- `CRITICAL`: Serious errors that may stop execution

**Log Destinations:**
- **Console Output**: Real-time feedback during execution
- **File Logging**: Persistent logs with rotation
- **Structured Logging**: JSON format for log analysis tools

#### 9.1.2 File Logging Structure

```
logs/
├── pipeline_20250920.log      # Daily pipeline execution logs
├── error_20250920.log         # Error-specific logs
├── classification_20250920.log # AI classification decisions
├── scraping_20250920.log      # Content extraction logs
├── latest_pipeline.log        # Symlink to current pipeline log
├── latest_error.log          # Symlink to current error log
└── archive/                   # Compressed historical logs
    ├── pipeline_20250919.log.gz
    └── error_20250919.log.gz
```

#### 9.1.3 Log Format Examples

**Standard Log Format:**
```
2025-09-20 19:15:33,245 [INFO] pipeline.collector: Collected 45 articles from NZZ Finance RSS feed
2025-09-20 19:15:34,123 [DEBUG] pipeline.filter: Processing article: "Swiss Bank Reports Q3 Results"
2025-09-20 19:15:34,456 [WARNING] pipeline.scraper: Trafilatura extraction failed for https://example.com/article, trying Playwright
2025-09-20 19:15:35,789 [ERROR] pipeline.filter: AI classification timeout for article ID 12345
```

**Structured JSON Logging:**
```json
{
  "timestamp": "2025-09-20T19:15:33.245Z",
  "level": "INFO",
  "component": "pipeline.collector",
  "message": "Collected articles from RSS feed",
  "metadata": {
    "source": "NZZ Finance",
    "article_count": 45,
    "feed_url": "https://www.nzz.ch/wirtschaft.rss",
    "execution_time_ms": 2340
  },
  "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

#### 9.1.4 Context-Aware Logging

**Log Context:**
- **Run ID**: Unique identifier for each pipeline execution
- **Step Name**: Current pipeline step being executed
- **Article ID**: Specific article being processed
- **Source**: News source being processed
- **Topic**: Classification topic context

**Example Implementation:**
```python
import structlog
from news_pipeline.utils import get_logger

logger = get_logger(__name__)

def process_article(article_id, run_id):
    """Process article with contextual logging."""
    log = logger.bind(
        run_id=run_id,
        article_id=article_id,
        step="classification"
    )
    
    log.info("Starting article classification")
    try:
        result = classify_article(article_id)
        log.info("Classification completed", 
                confidence=result.confidence,
                is_match=result.is_match)
    except Exception as e:
        log.error("Classification failed", 
                 error=str(e), 
                 error_type=type(e).__name__)
```

### 9.2 Performance Metrics

#### 9.2.1 Pipeline Metrics

**Core Metrics:**
- **Execution Time**: Total and per-step timing
- **Throughput**: Articles processed per minute
- **Success Rate**: Percentage of successful operations
- **Error Rate**: Frequency and types of errors
- **Resource Usage**: Memory, CPU, and storage utilization

**Metrics Collection:**
```python
class PipelineMetrics:
    def __init__(self):
        self.start_time = time.time()
        self.step_times = {}
        self.counters = defaultdict(int)
        
    def start_step(self, step_name):
        """Start timing a pipeline step."""
        self.step_times[step_name] = time.time()
        
    def complete_step(self, step_name, success_count=0, error_count=0):
        """Complete step timing and record results."""
        duration = time.time() - self.step_times[step_name]
        self.counters[f'{step_name}_duration'] = duration
        self.counters[f'{step_name}_success'] = success_count
        self.counters[f'{step_name}_errors'] = error_count
        
    def get_summary(self):
        """Get comprehensive metrics summary."""
        total_time = time.time() - self.start_time
        return {
            'total_execution_time': total_time,
            'step_breakdown': self.step_times,
            'counters': dict(self.counters)
        }
```

#### 9.2.2 Classification Metrics

**AI Model Performance:**
- **Response Time**: Average API call duration
- **Token Usage**: Input/output token consumption
- **Confidence Distribution**: Histogram of confidence scores
- **Accuracy Tracking**: When ground truth available

**Cost Tracking:**
```python
class ClassificationMetrics:
    def __init__(self):
        self.total_requests = 0
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.response_times = []
        self.confidence_scores = []
        
    def record_classification(self, tokens_in, tokens_out, response_time, confidence):
        """Record metrics for single classification."""
        self.total_requests += 1
        self.total_tokens_in += tokens_in
        self.total_tokens_out += tokens_out
        self.response_times.append(response_time)
        self.confidence_scores.append(confidence)
        
    def get_cost_estimate(self, cost_per_1k_tokens=0.0001):
        """Calculate estimated API costs."""
        total_tokens = self.total_tokens_in + self.total_tokens_out
        return (total_tokens / 1000) * cost_per_1k_tokens
```

### 9.3 Health Monitoring

#### 9.3.1 System Health Checks

**Health Check Categories:**
1. **Database Connectivity**: SQLite connection and query performance
2. **External Services**: RSS feed availability and response times
3. **AI Model Access**: Classification service availability
4. **File System**: Disk space and write permissions
5. **Memory Usage**: Available memory and potential leaks

**Health Check Implementation:**
```python
class HealthChecker:
    def check_database_health(self):
        """Check database connectivity and performance."""
        try:
            conn = get_db_connection()
            start_time = time.time()
            conn.execute("SELECT COUNT(*) FROM items").fetchone()
            response_time = time.time() - start_time
            
            return {
                'status': 'healthy',
                'response_time_ms': response_time * 1000,
                'details': 'Database accessible'
            }
        except Exception as e:
            return {
                'status': 'unhealthy', 
                'error': str(e),
                'details': 'Database connection failed'
            }
    
    def check_feed_sources(self):
        """Check availability of configured news sources."""
        results = []
        for feed in get_enabled_feeds():
            try:
                response = requests.head(feed['url'], timeout=10)
                results.append({
                    'source': feed['name'],
                    'status': 'healthy' if response.status_code == 200 else 'degraded',
                    'http_status': response.status_code,
                    'response_time_ms': response.elapsed.total_seconds() * 1000
                })
            except Exception as e:
                results.append({
                    'source': feed['name'],
                    'status': 'unhealthy',
                    'error': str(e)
                })
        return results
```

#### 9.3.2 Alerting System

**Alert Conditions:**
- Pipeline execution failures
- High error rates (>5% in 1 hour)
- Extended execution times (>2x normal)
- Low article collection rates
- Database connectivity issues
- Disk space warnings (<10% free)

**Alert Channels:**
- Email notifications
- Log file markers
- System exit codes
- External monitoring integration

---

## 10) Operations Runbook

### 10.1 Daily Operations

#### 10.1.1 Morning Startup Procedures

**Express Mode Check (First Priority):**
```bash
#!/bin/bash
# Morning express analysis for urgent insights
echo "🌅 Starting morning express analysis..."

# Run express mode
python news_analyzer.py --express --log-level INFO

# Check results
if [ $? -eq 0 ]; then
    echo "✅ Express analysis completed successfully"
    
    # Export urgent findings
    python news_analyzer.py --export --format md --date today
    
    # Check for high-confidence matches
    python news_analyzer.py --stats --topic creditreform_insights
else
    echo "❌ Express analysis failed - check logs"
    exit 1
fi
```

**Full Pipeline Execution:**
```bash
#!/bin/bash
# Complete daily news analysis pipeline
echo "🔄 Starting full pipeline execution..."

# Pre-execution checks
python scripts/health_check.py
if [ $? -ne 0 ]; then
    echo "❌ Health check failed - resolving issues..."
    # Add resolution steps here
fi

# Execute full pipeline
python news_analyzer.py --force --log-level INFO

# Post-execution tasks
python news_analyzer.py --export --format json
python news_analyzer.py --export --format md
python news_analyzer.py --german-report

echo "✅ Daily pipeline completed"
```

#### 10.1.2 Health Monitoring

**System Status Check:**
```bash
#!/bin/bash
# Comprehensive system health check
python news_analyzer.py --health-check --verbose

# Check disk space
df -h | grep -E "(news_analysis|logs|exports)"

# Check database size
ls -lh news.db

# Check recent errors
tail -50 logs/latest_error.log | grep -E "(ERROR|CRITICAL)"

# Check processing rates
python news_analyzer.py --stats --last-24h
```

#### 10.1.3 Performance Monitoring

**Daily Performance Report:**
```bash
#!/bin/bash
# Generate daily performance metrics
echo "📊 Daily Performance Report - $(date)"
echo "========================================"

# Pipeline execution statistics
python news_analyzer.py --stats --processing --format table

# Source performance analysis  
python news_analyzer.py --stats --by-source --format table

# Classification accuracy metrics
python news_analyzer.py --stats --classification --format table

# Resource usage summary
python news_analyzer.py --stats --resources --format table
```

### 10.2 Weekly Maintenance

#### 10.2.1 Database Maintenance

**Weekly Database Cleanup:**
```bash
#!/bin/bash
# Weekly database maintenance tasks
echo "🗂️ Starting weekly database maintenance..."

# Backup database
cp news.db "backups/news_$(date +%Y%m%d).db"

# Clean old processed links (>30 days)
python scripts/maintenance/cleanup_processed_links.py --days 30

# Clean old pipeline states (>14 days) 
python scripts/maintenance/cleanup_pipeline_states.py --days 14

# Vacuum database to reclaim space
python scripts/maintenance/vacuum_database.py

# Update statistics
python scripts/maintenance/update_statistics.py

echo "✅ Database maintenance completed"
```

**Index Optimization:**
```bash
#!/bin/bash
# Optimize database indexes for performance
echo "⚡ Optimizing database indexes..."

# Analyze query patterns
python scripts/maintenance/analyze_queries.py --days 7

# Rebuild indexes if needed
python scripts/maintenance/rebuild_indexes.py --analyze-first

# Update query planner statistics
python scripts/maintenance/analyze_database.py

echo "✅ Index optimization completed"
```

#### 10.2.2 Configuration Review

**Weekly Configuration Audit:**
```bash
#!/bin/bash
# Review and update configuration
echo "⚙️ Configuration audit..."

# Check feed availability
python scripts/maintenance/check_feeds.py --test-all

# Validate topic configuration
python scripts/maintenance/validate_topics.py

# Review source performance
python scripts/maintenance/source_performance.py --weeks 4

# Update feed list if needed
echo "📝 Review feed recommendations:"
python scripts/maintenance/recommend_feeds.py
```

### 10.3 Monthly Operations

#### 10.3.1 Comprehensive Analysis

**Monthly Review Process:**
```bash
#!/bin/bash
# Monthly comprehensive analysis
echo "📈 Monthly Analysis - $(date +%B\ %Y)"
echo "=================================="

# Generate monthly report
python news_analyzer.py --monthly-report --month $(date +%Y-%m)

# Analyze trends
python scripts/analysis/trend_analysis.py --month $(date +%Y-%m)

# Performance benchmarks
python scripts/analysis/benchmark_performance.py --baseline last-month

# Cost analysis
python scripts/analysis/cost_analysis.py --month $(date +%Y-%m)
```

#### 10.3.2 System Updates

**Monthly Update Procedure:**
```bash
#!/bin/bash
# Monthly system updates
echo "🔄 Monthly system updates..."

# Update Python dependencies
pip install -r requirements.txt --upgrade

# Update feed configurations
python scripts/load_feeds.py --update --backup

# Test configuration changes
python scripts/test_config.py --comprehensive

# Update documentation
python scripts/generate_docs.py --update-api-reference

echo "✅ System updates completed"
```

### 10.4 Troubleshooting Procedures

#### 10.4.1 Common Issues Resolution

**Pipeline Failures:**

1. **Classification Timeouts:**
   ```bash
   # Check AI service availability
   python scripts/test_ai_service.py
   
   # Increase timeout if needed
   export MODEL_TIMEOUT=60
   
   # Resume from last checkpoint
   python news_analyzer.py --resume [run_id]
   ```

2. **Database Lock Issues:**
   ```bash
   # Check for long-running transactions
   python scripts/debug/check_db_locks.py
   
   # Kill blocking processes if needed
   python scripts/debug/kill_db_locks.py
   
   # Restart pipeline with retry logic
   python news_analyzer.py --retry-on-lock
   ```

3. **Memory Issues:**
   ```bash
   # Check memory usage
   python scripts/debug/memory_usage.py
   
   # Run with reduced batch size
   python news_analyzer.py --batch-size 10
   
   # Enable memory optimization
   python news_analyzer.py --optimize-memory
   ```

**Feed Collection Issues:**

1. **RSS Feed Failures:**
   ```bash
   # Test individual feeds
   python scripts/debug/test_feed.py --feed-name "NZZ Finance"
   
   # Check robots.txt compliance
   python scripts/debug/check_robots.py --url [feed_url]
   
   # Disable problematic feeds temporarily
   python scripts/manage_feeds.py --disable [feed_name]
   ```

2. **Content Extraction Failures:**
   ```bash
   # Test scraping methods
   python scripts/debug/test_scraping.py --url [article_url]
   
   # Force specific extraction method
   python news_analyzer.py --step scrape --method playwright
   
   # Update extraction selectors
   python scripts/update_selectors.py --source [source_name]
   ```

#### 10.4.2 Emergency Procedures

**System Recovery:**
```bash
#!/bin/bash
# Emergency system recovery procedure
echo "🚨 Emergency Recovery Mode"

# Stop all running processes
pkill -f "news_analyzer.py"

# Backup current state
cp news.db "emergency_backup_$(date +%Y%m%d_%H%M%S).db"

# Restore from last known good backup
if [ -f "backups/news_$(date -d yesterday +%Y%m%d).db" ]; then
    cp "backups/news_$(date -d yesterday +%Y%m%d).db" news.db
    echo "✅ Database restored from yesterday's backup"
fi

# Run system verification
python scripts/verify_system.py --comprehensive

# Resume operations in safe mode
python news_analyzer.py --safe-mode --express
```

**Data Corruption Recovery:**
```bash
#!/bin/bash
# Data corruption recovery
echo "🔧 Data Corruption Recovery"

# Check database integrity
sqlite3 news.db "PRAGMA integrity_check;"

# Repair if possible
python scripts/repair/fix_database.py --auto-repair

# Rebuild indexes
python scripts/repair/rebuild_all_indexes.py

# Verify data consistency
python scripts/repair/verify_data_consistency.py
```

### 10.5 Monitoring Dashboards

#### 10.5.1 Real-time Status

**Pipeline Status Dashboard:**
- Current pipeline step and progress
- Articles processed in current run
- Success/error rates by component  
- Recent error messages and context
- Estimated time to completion

**System Health Dashboard:**
- Database response times
- Memory and disk usage
- Feed availability status
- AI service response times
- Recent performance trends

#### 10.5.2 Historical Analytics

**Performance Trends:**
- Daily article processing volumes
- Source reliability over time
- Classification accuracy trends
- Processing time variations
- Cost analysis and projections

**Business Intelligence:**
- Topic relevance trends
- Source value analysis
- Content quality metrics
- User engagement with exports
- ROI calculations

---

## 11) Performance Optimization

### 11.1 Database Optimization

#### 11.1.1 Query Optimization

**Index Strategy:**
- **Composite Indexes**: Multi-column indexes for common query patterns
- **Covering Indexes**: Include all columns needed for queries
- **Partial Indexes**: Filtered indexes for specific conditions
- **Expression Indexes**: Indexes on computed values

**Query Optimization Examples:**
```sql
-- Optimized query for recent matches
SELECT i.id, i.title, i.url, i.triage_confidence, s.summary
FROM items i
JOIN summaries s ON i.id = s.item_id  
WHERE i.is_match = 1 
  AND i.published_at >= date('now', '-7 days')
ORDER BY i.triage_confidence DESC, i.published_at DESC
LIMIT 50;

-- Use query plan analysis
EXPLAIN QUERY PLAN SELECT ...;

-- Index for the above query
CREATE INDEX idx_items_match_recent ON items(is_match, published_at DESC, triage_confidence DESC);
```

**Database Configuration:**
```python
# SQLite optimization settings
def optimize_database_connection(conn):
    """Apply performance optimizations to SQLite connection."""
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    
    # Increase cache size (in KB)
    conn.execute("PRAGMA cache_size=10000")
    
    # Optimize for write performance
    conn.execute("PRAGMA synchronous=NORMAL")
    
    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys=ON")
    
    # Set memory-mapped I/O
    conn.execute("PRAGMA mmap_size=268435456")  # 256MB
    
    # Optimize automatic vacuum
    conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
```

#### 11.1.2 Connection Management

**Connection Pooling:**
```python
class DatabasePool:
    def __init__(self, db_path, max_connections=10):
        self.db_path = db_path
        self.max_connections = max_connections
        self.pool = queue.Queue(maxsize=max_connections)
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Create initial connection pool."""
        for _ in range(self.max_connections):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            optimize_database_connection(conn)
            self.pool.put(conn)
    
    @contextmanager
    def get_connection(self):
        """Get connection from pool with automatic return."""
        conn = self.pool.get()
        try:
            yield conn
        finally:
            self.pool.put(conn)
```

### 11.2 AI Processing Optimization

#### 11.2.1 Batch Processing

**Batch Classification:**
```python
class BatchClassifier:
    def __init__(self, batch_size=20, max_concurrent=3):
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def classify_batch(self, articles):
        """Process articles in optimized batches."""
        batches = [articles[i:i+self.batch_size] 
                  for i in range(0, len(articles), self.batch_size)]
        
        tasks = [self._process_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results and handle exceptions
        flattened_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch processing failed: {result}")
                continue
            flattened_results.extend(result)
        
        return flattened_results
    
    async def _process_batch(self, batch):
        """Process single batch with rate limiting."""
        async with self.semaphore:
            # Add delay to respect rate limits
            await asyncio.sleep(0.1)  
            return await self._classify_articles(batch)
```

#### 11.2.2 Caching Strategy

**Multi-Level Caching:**
```python
class ClassificationCache:
    def __init__(self):
        # In-memory cache for current session
        self.memory_cache = {}
        # Database cache for persistence
        self.db_cache_enabled = True
        # Redis cache for distributed systems (optional)
        self.redis_cache = None
    
    def get_cached_result(self, url_hash, topic):
        """Get cached classification result with fallback hierarchy."""
        # Try memory cache first (fastest)
        memory_key = f"{url_hash}:{topic}"
        if memory_key in self.memory_cache:
            self._update_access_stats(memory_key, 'memory')
            return self.memory_cache[memory_key]
        
        # Try Redis cache (fast)
        if self.redis_cache:
            result = self.redis_cache.get(memory_key)
            if result:
                # Cache in memory for future requests
                self.memory_cache[memory_key] = result
                self._update_access_stats(memory_key, 'redis')
                return result
        
        # Try database cache (slower but persistent)
        if self.db_cache_enabled:
            result = self._get_db_cached_result(url_hash, topic)
            if result:
                # Cache in faster layers
                self.memory_cache[memory_key] = result
                if self.redis_cache:
                    self.redis_cache.setex(memory_key, 3600, result)
                self._update_access_stats(memory_key, 'database')
                return result
        
        return None
    
    def cache_result(self, url_hash, topic, result, ttl=86400):
        """Cache result across all available layers."""
        memory_key = f"{url_hash}:{topic}"
        
        # Cache in memory
        self.memory_cache[memory_key] = result
        
        # Cache in Redis with TTL
        if self.redis_cache:
            self.redis_cache.setex(memory_key, ttl, result)
        
        # Cache in database
        if self.db_cache_enabled:
            self._save_db_cache(url_hash, topic, result, ttl)
```

### 11.3 Content Processing Optimization

#### 11.3.1 Parallel Processing

**Concurrent Scraping:**
```python
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor

class ParallelScraper:
    def __init__(self, max_workers=5, max_concurrent_requests=10):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
    
    async def scrape_articles_parallel(self, article_urls):
        """Scrape multiple articles concurrently."""
        tasks = [self._scrape_article_async(url) for url in article_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful results
        successful_results = [r for r in results if not isinstance(r, Exception)]
        failed_count = len(results) - len(successful_results)
        
        logger.info(f"Scraped {len(successful_results)} articles successfully, "
                   f"{failed_count} failed")
        return successful_results
    
    async def _scrape_article_async(self, url):
        """Scrape single article with concurrency control."""
        async with self.semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor, 
                self._scrape_article_sync, 
                url
            )
```

#### 11.3.2 Memory Management

**Streaming Processing:**
```python
class StreamingProcessor:
    def __init__(self, chunk_size=100):
        self.chunk_size = chunk_size
    
    def process_articles_streaming(self, article_iterator):
        """Process articles in chunks to manage memory usage."""
        chunk = []
        processed_count = 0
        
        for article in article_iterator:
            chunk.append(article)
            
            if len(chunk) >= self.chunk_size:
                # Process chunk
                results = self._process_chunk(chunk)
                yield from results
                
                # Clear chunk an
