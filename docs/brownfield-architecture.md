# NewsAnalysis_2.0 Brownfield Architecture Document

## Introduction

This document captures the **CURRENT STATE** of the NewsAnalysis_2.0 codebase, including technical debt, workarounds, and real-world patterns. It serves as a reference for AI agents and developers working on enhancements to this Swiss business news analysis system.

### Document Purpose

This is a **brownfield architecture document** - it documents what EXISTS, not what should exist. This includes:
- Technical debt and workarounds
- Inconsistent patterns between different parts
- Legacy code and constraints
- Integration points and dependencies
- Performance characteristics and bottlenecks

### Document Scope

Comprehensive documentation of the entire NewsAnalysis_2.0 system as it exists today.

### Change Log

| Date       | Version | Description                          | Author  |
|------------|---------|--------------------------------------|---------|
| 2025-01-03 | 1.0     | Initial brownfield analysis          | Winston |

---

## Quick Reference - Key Files and Entry Points

### Critical Files for Understanding the System

**Main Entry Point:**
- `news_analyzer.py` - CLI orchestrator for the 5-step pipeline

**Core Pipeline Components:**
- `news_pipeline/collector.py` - Step 1: URL collection from RSS/sitemaps/HTML
- `news_pipeline/filter.py` - Step 2: AI-powered filtering with GPT-5-nano
- `news_pipeline/scraper.py` - Step 3: Content extraction (Trafilatura + MCP/Playwright)
- `news_pipeline/summarizer.py` - Step 4: Article summarization with GPT-5-mini
- `news_pipeline/enhanced_analyzer.py` - Step 5: Meta-analysis and digest generation

**Deduplication System:**
- `news_pipeline/deduplication.py` - Semantic similarity-based deduplication
- `news_pipeline/gpt_deduplication.py` - GPT-based title clustering (Step 3.0)
- `news_pipeline/cross_run_deduplication.py` - Cross-run topic deduplication (Step 3.1)
- `news_pipeline/cross_run_state_manager.py` - State management for cross-run tracking

**State Management:**
- `news_pipeline/state_manager.py` - Pipeline execution state tracking
- `news_pipeline/incremental_digest.py` - Incremental digest generation state

**Configuration:**
- `config/feeds.yaml` - News source definitions (RSS, sitemaps, HTML, Google News)
- `config/topics.yaml` - Topic definitions and filtering criteria
- `config/pipeline_config.yaml` - Pipeline behavior configuration
- `config/mcp.json` - MCP server configuration for Playwright
- `.env` - Environment variables (OpenAI API key, model selection)

**Database:**
- `scripts/init_db.py` - Database schema definition
- `news.db` - SQLite database (not in repo)

**Templates:**
- `templates/daily_digest.md.j2` - Jinja2 template for markdown output

**Utilities:**
- `news_pipeline/utils.py` - Shared utilities (logging, URL normalization, similarity)
- `news_pipeline/paths.py` - Path resolution utilities
- `news_pipeline/language_config.py` - German/English language support

---

## High Level Architecture

### System Overview

NewsAnalysis_2.0 is a **Python-based news analysis pipeline** that processes Swiss business news through a sophisticated 5-step workflow:

1. **URL Collection** - Gather article URLs from multiple source types
2. **AI Filtering** - Use GPT-5-nano to filter relevant articles by title/URL only
3. **Content Scraping** - Extract full content only from relevant articles
4. **Summarization** - Generate structured summaries with GPT-5-mini
5. **Meta-Analysis** - Create executive briefings and topic digests with GPT-5

**Key Architectural Characteristics:**
- **Modular pipeline design** - Each step is independent and can be run separately
- **State-managed execution** - Pipeline tracks progress and supports resume
- **Confidence-based selection** - Articles selected based on AI confidence scores
- **Multi-level deduplication** - Semantic, GPT-based, and cross-run deduplication
- **Incremental processing** - Supports multiple runs per day with state persistence
- **German language focus** - Specialized prompts and output formatting for German

### Actual Tech Stack

| Category           | Technology              | Version    | Notes                                           |
|--------------------|-------------------------|------------|-------------------------------------------------|
| Runtime            | Python                  | 3.12       | Required for latest OpenAI SDK features         |
| Database           | SQLite                  | 3.x        | Single-file database with WAL mode              |
| AI/ML API          | OpenAI API              | Latest     | GPT-5 models (gpt-5-nano, gpt-5-mini, gpt-5)    |
| Web Scraping       | Trafilatura             | 2.0.x      | Primary content extraction                      |
| Browser Automation | MCP + Playwright        | Latest     | For JavaScript-heavy sites                      |
| RSS Parsing        | feedparser              | 6.0.11+    | RSS feed processing                             |
| HTML Parsing       | BeautifulSoup4 + lxml   | Latest     | HTML parsing and extraction                     |
| Templates          | Jinja2                  | 3.0+       | Markdown digest generation                      |
| HTTP Client        | requests                | 2.28+      | HTTP requests with retry logic                  |
| Data Validation    | Pydantic                | 2.8+       | Schema validation for AI responses              |
| Configuration      | PyYAML + python-dotenv  | Latest     | YAML configs + environment variables            |
| Orchestration      | LangChain               | 0.3.x      | AI workflow orchestration (limited use)         |
| API Framework      | FastAPI                 | 0.112+     | Installed but not actively used                 |

**IMPORTANT NOTES:**
- **No virtual environment in repo** - Dependencies installed globally or in user's venv
- **MCP requires Node.js** - `npx @playwright/mcp@latest` must be available
- **OpenAI API key required** - System fails without valid key in `.env`
- **FastAPI installed but unused** - Legacy dependency, not removed yet

### Repository Structure Reality Check

**Type:** Monorepo (single repository, flat structure)
**Package Manager:** pip (requirements.txt)
**Notable Decisions:**
- Flat module structure in `news_pipeline/` - no deep nesting
- Scripts in `scripts/` directory - database migrations and testing
- Configuration in `config/` directory - YAML-based
- Documentation in `docs/` directory - markdown files
- Templates in `templates/` directory - Jinja2 templates
- Output in `outputs/` and `rating_reports/` - generated files (not in repo)

---

## Source Tree and Module Organization

### Project Structure (Actual)

```
NewsAnalysis_2.0/
├── news_analyzer.py              # Main CLI entry point
├── news.db                        # SQLite database (generated, not in repo)
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variable template
├── .env                           # Actual environment (not in repo)
├── Dockerfile                     # Docker containerization
├── README.md                      # User documentation
│
├── config/                        # Configuration files
│   ├── feeds.yaml                 # News source definitions
│   ├── topics.yaml                # Topic filtering criteria
│   ├── pipeline_config.yaml       # Pipeline behavior settings
│   ├── mcp.json                   # MCP server configuration
│   ├── test_config.yaml           # Test configuration
│   └── test_feeds.yaml            # Test feed definitions
│
├── news_pipeline/                 # Core pipeline modules
│   ├── __init__.py                # Package initialization
│   ├── collector.py               # Step 1: URL collection
│   ├── filter.py                  # Step 2: AI filtering
│   ├── scraper.py                 # Step 3: Content scraping
│   ├── summarizer.py              # Step 4: Summarization
│   ├── analyzer.py                # Legacy meta-analyzer
│   ├── enhanced_analyzer.py       # Step 5: Enhanced meta-analysis
│   ├── deduplication.py           # Semantic deduplication
│   ├── gpt_deduplication.py       # GPT title clustering
│   ├── cross_run_deduplication.py # Cross-run topic dedup
│   ├── cross_run_state_manager.py # Cross-run state management
│   ├── state_manager.py           # Pipeline state tracking
│   ├── incremental_digest.py      # Incremental digest generation
│   ├── express_mode.py            # Fast analysis mode (experimental)
│   ├── german_rating_formatter.py # German markdown formatting
│   ├── google_news_decoder.py     # Google News URL decoding
│   ├── language_config.py         # Language-specific prompts
│   ├── paths.py                   # Path resolution utilities
│   └── utils.py                   # Shared utilities
│
├── scripts/                       # Database and testing scripts
│   ├── init_db.py                 # Database schema initialization
│   ├── load_feeds.py              # Load feeds from config
│   ├── add_cross_run_schema.py    # Cross-run schema migration
│   ├── test_cross_run_dedup.py    # Cross-run dedup testing
│   ├── test_enhanced_analyzer.py  # Enhanced analyzer testing
│   ├── test_pipeline_flow.py      # Pipeline flow testing
│   └── (other migration/test scripts)
│
├── templates/                     # Jinja2 templates
│   └── daily_digest.md.j2         # Markdown digest template
│
├── docs/                          # Documentation
│   ├── architecture.md            # Enhancement-focused architecture
│   ├── documentation.md           # System documentation
│   ├── pipeline_flow_documentation.md
│   ├── confidence_selection_implementation.md
│   ├── enhanced_output_generation.md
│   └── stories/                   # User stories and epics
│
├── outputs/                       # Generated outputs (not in repo)
│   ├── debug_scores.csv
│   ├── prefilter_model.json
│   └── (other generated files)
│
├── rating_reports/                # German markdown reports (not in repo)
│   └── bonitaets_tagesanalyse_*.md
│
├── logs/                          # Log files (not in repo)
│   └── news_pipeline.log
│
├── prefilter/                     # Embedding-based prefiltering (experimental)
│   ├── embedding_utils.py
│   ├── faiss_index.py
│   ├── prefilter_runtime.py
│   └── tune_prefilter.py
│
├── schemas/                       # JSON schemas for validation
│   ├── summary.schema.json
│   └── triage.schema.json
│
├── deprecated_code/               # Old code kept for reference
├── deprecated_docs/               # Old documentation
└── discussion/                    # Design discussions and planning
```

### Key Modules and Their Purpose

**Pipeline Orchestration:**
- `news_analyzer.py` - Main CLI, orchestrates all pipeline steps, handles state management
- `news_pipeline/state_manager.py` - Tracks pipeline execution state, supports resume/pause

**Data Collection:**
- `news_pipeline/collector.py` - Collects URLs from RSS, sitemaps, HTML listings, Google News
- `news_pipeline/google_news_decoder.py` - Decodes Google News redirect URLs

**Filtering and Selection:**
- `news_pipeline/filter.py` - AI-powered filtering with confidence scoring and selection
- `prefilter/` - Experimental embedding-based prefiltering (not in main pipeline)

**Content Extraction:**
- `news_pipeline/scraper.py` - Content extraction using Trafilatura and MCP/Playwright

**Deduplication (Multi-Level):**
- `news_pipeline/deduplication.py` - Semantic similarity-based deduplication
- `news_pipeline/gpt_deduplication.py` - GPT-based title clustering
- `news_pipeline/cross_run_deduplication.py` - Cross-run topic deduplication
- `news_pipeline/cross_run_state_manager.py` - Manages cross-run state

**Analysis and Output:**
- `news_pipeline/summarizer.py` - Individual article summarization
- `news_pipeline/enhanced_analyzer.py` - Meta-analysis and digest generation
- `news_pipeline/incremental_digest.py` - Incremental digest state management
- `news_pipeline/german_rating_formatter.py` - German markdown formatting

**Utilities:**
- `news_pipeline/utils.py` - Logging, URL normalization, similarity calculations
- `news_pipeline/paths.py` - Cross-platform path resolution
- `news_pipeline/language_config.py` - German/English language support

---

## Data Models and Database Schema

### Database Schema (SQLite)

The system uses SQLite with the following schema:

#### Core Tables

**`feeds`** - News source definitions
```sql
CREATE TABLE feeds(
  id INTEGER PRIMARY KEY, 
  source TEXT NOT NULL,        -- Source name (e.g., "NZZ", "Blick")
  kind TEXT NOT NULL,           -- Type: "rss", "sitemap", "html", "google_news"
  url TEXT NOT NULL UNIQUE      -- Feed URL
);
```

**`items`** - Article metadata and filtering results
```sql
CREATE TABLE items(
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  normalized_url TEXT NOT NULL,
  title TEXT,
  published_at TEXT,
  first_seen_at TEXT DEFAULT (datetime('now')),
  triage_topic TEXT,            -- Matched topic
  triage_confidence REAL,       -- AI confidence score (0.0-1.0)
  is_match INTEGER DEFAULT 0,   -- 1 if matched, 0 if rejected
  
  -- Pipeline tracking (added later)
  pipeline_run_id TEXT,         -- UUID of pipeline run
  pipeline_stage TEXT,          -- Current stage: collected, filtered, scraped, summarized
  selected_for_processing INTEGER DEFAULT 0,  -- 1 if selected for processing
  selection_rank INTEGER,       -- Rank in selection (1 = highest confidence)
  
  -- Deduplication tracking
  is_duplicate INTEGER DEFAULT 0,
  duplicate_of INTEGER REFERENCES items(id),
  cluster_id TEXT               -- Cluster identifier for deduplication
);
```

**IMPORTANT NOTES:**
- `pipeline_run_id`, `pipeline_stage`, `selected_for_processing`, `selection_rank` were added later
- Schema migrations done manually via ALTER TABLE statements
- No formal migration framework - changes tracked in `scripts/` directory

**`items_fts`** - Full-text search index
```sql
CREATE VIRTUAL TABLE items_fts USING fts5(
  title, url, 
  content='items', 
  content_rowid='id', 
  tokenize='unicode61 remove_diacritics 2'
);
```

**`articles`** - Extracted content
```sql
CREATE TABLE articles(
  item_id INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
  extracted_text TEXT,          -- Full article text
  extracted_at TEXT DEFAULT (datetime('now')),
  method TEXT CHECK(method IN ('trafilatura','playwright'))
);
```

**`summaries`** - Article summaries
```sql
CREATE TABLE summaries(
  item_id INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
  topic TEXT,                   -- Topic classification
  model TEXT,                   -- AI model used (e.g., "gpt-4o-mini")
  summary TEXT,                 -- Generated summary
  key_points_json TEXT,         -- JSON array of key points
  entities_json TEXT,           -- JSON object of extracted entities
  created_at TEXT DEFAULT (datetime('now')),
  
  -- Cross-run deduplication (added later)
  topic_already_covered INTEGER DEFAULT 0,
  cross_run_cluster_id TEXT
);
```

#### State Management Tables

**`processed_links`** - Deduplication cache
```sql
CREATE TABLE processed_links (
  url_hash TEXT PRIMARY KEY,    -- SHA256 hash of normalized URL
  url TEXT NOT NULL,
  processed_at TEXT DEFAULT (datetime('now')),
  topic TEXT NOT NULL,
  result TEXT NOT NULL CHECK(result IN ('matched', 'rejected', 'error')),
  confidence REAL DEFAULT 0.0
);
```

**CRITICAL:** This table prevents re-processing the same URL for the same topic. However, it can cause issues if:
- URL normalization changes
- Topic definitions change
- You want to reprocess articles

**`pipeline_state`** - Pipeline execution tracking
```sql
CREATE TABLE pipeline_state (
  id INTEGER PRIMARY KEY,
  run_id TEXT UNIQUE NOT NULL,  -- UUID for each pipeline run
  step_name TEXT NOT NULL CHECK(step_name IN ('collection', 'filtering', 'scraping', 'summarization', 'analysis')),
  status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'paused')) DEFAULT 'pending',
  started_at TEXT DEFAULT (datetime('now')),
  completed_at TEXT,
  metadata TEXT,                -- JSON for step-specific data
  article_count INTEGER DEFAULT 0,
  match_count INTEGER DEFAULT 0,
  error_message TEXT,
  can_resume INTEGER DEFAULT 1
);
```

**`article_clusters`** - Deduplication clusters
```sql
CREATE TABLE article_clusters (
  id INTEGER PRIMARY KEY,
  cluster_id TEXT NOT NULL,     -- Generated hash for similar articles
  article_id INTEGER REFERENCES items(id) ON DELETE CASCADE,
  is_primary INTEGER DEFAULT 0, -- 1 for best article in cluster
  similarity_score REAL DEFAULT 0.0,
  created_at TEXT DEFAULT (datetime('now')),
  clustering_method TEXT DEFAULT 'title_similarity'  -- 'title_similarity', 'gpt_clustering', 'cross_run'
);
```

#### Cross-Run Deduplication Tables (New)

**`cross_run_topic_signatures`** - Topic signatures for cross-run comparison
```sql
CREATE TABLE cross_run_topic_signatures (
  signature_id TEXT PRIMARY KEY,
  date TEXT NOT NULL,           -- YYYY-MM-DD
  article_summary TEXT NOT NULL,
  topic_theme TEXT,
  source_article_id INTEGER REFERENCES items(id),
  created_at TEXT DEFAULT (datetime('now')),
  run_sequence INTEGER          -- Run number within the day
);
```

**`cross_run_deduplication_log`** - Audit trail for cross-run deduplication
```sql
CREATE TABLE cross_run_deduplication_log (
  log_id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  new_article_id INTEGER REFERENCES items(id),
  matched_signature_id TEXT REFERENCES cross_run_topic_signatures(signature_id),
  decision TEXT CHECK(decision IN ('DUPLICATE', 'UNIQUE')),
  confidence_score REAL,
  processing_time REAL,
  created_at TEXT DEFAULT (datetime('now'))
);
```

#### Digest State Tables

**`digest_state`** - Incremental digest generation state
```sql
CREATE TABLE digest_state (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL,
  topic TEXT NOT NULL,
  article_ids TEXT,             -- JSON array of article IDs
  digest_content TEXT,          -- JSON of digest content
  last_updated TEXT DEFAULT (datetime('now')),
  UNIQUE(date, topic)
);
```

**`digest_generation_log`** - Digest generation history
```sql
CREATE TABLE digest_generation_log (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL,
  generation_type TEXT,         -- 'full', 'incremental', 'update'
  topics_processed INTEGER,
  articles_included INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);
```

### Data Flow and Relationships

```
feeds → items → articles → summaries
              ↓
         processed_links (dedup cache)
              ↓
         article_clusters (dedup results)
              ↓
         cross_run_topic_signatures (cross-run state)
              ↓
         digest_state (incremental digests)
```

**Key Relationships:**
- `items.id` → `articles.item_id` (1:1)
- `items.id` → `summaries.item_id` (1:1)
- `items.id` → `article_clusters.article_id` (1:many)
- `items.url` → `processed_links.url` (via hash)

**IMPORTANT CONSTRAINTS:**
- URLs must be unique in `items` table
- Each article can have only one extracted content and one summary
- Articles can belong to multiple clusters (different clustering methods)
- Cross-run signatures are date-partitioned

---

## Component Architecture

### Pipeline Components

#### NewsCollector (`news_pipeline/collector.py`)

**Responsibility:** Collect article URLs from multiple source types

**Key Methods:**
- `collect_from_rss()` - Parse RSS feeds
- `collect_from_sitemaps()` - Parse XML sitemaps
- `collect_from_html_listings()` - Scrape HTML article listings
- `collect_from_google_news()` - Query Google News RSS
- `collect_all()` - Orchestrate all collection methods

**Integration Points:**
- Reads from `config/feeds.yaml`
- Writes to `items` table
- Uses `GoogleNewsDecoder` for Google News URLs

**Known Issues:**
- Google News URLs require decoding (redirect URLs)
- Some HTML listings have inconsistent structure
- Rate limiting not implemented for Google News

#### AIFilter (`news_pipeline/filter.py`)

**Responsibility:** AI-powered filtering with confidence-based selection

**Key Methods:**
- `classify_article()` - Single article classification
- `batch_classify()` - Batch classification for efficiency
- `filter_for_creditreform()` - Main filtering workflow
- `apply_embedding_prefilter()` - Optional embedding-based prefiltering
- `_select_top_articles()` - Confidence-based selection

**Integration Points:**
- Reads from `items` table (unfiltered articles)
- Writes to `items` table (triage results)
- Writes to `processed_links` table (dedup cache)
- Uses OpenAI API (GPT-4o-mini)
- Reads from `config/topics.yaml` and `config/pipeline_config.yaml`

**CRITICAL PATTERNS:**
- Uses structured outputs with JSON schema validation
- Implements retry logic with exponential backoff
- Caches results in `processed_links` to avoid reprocessing
- Confidence-based selection: selects top N articles above threshold

**Known Issues:**
- `processed_links` cache can prevent reprocessing when needed
- Prefilter is experimental and not well-integrated
- Confidence threshold and max_articles can be overridden at runtime

#### ContentScraper (`news_pipeline/scraper.py`)

**Responsibility:** Extract full article content

**Key Methods:**
- `scrape_with_trafilatura()` - Primary extraction method
- `scrape_with_mcp()` - Fallback for JavaScript-heavy sites
- `extract_content()` - Orchestrates extraction with fallback
- `scrape_selected_articles()` - Batch scraping workflow

**Integration Points:**
- Reads from `items` table (selected articles)
- Writes to `articles` table
- Uses Trafilatura library
- Uses MCP + Playwright for complex sites
- Reads from `config/mcp.json`

**CRITICAL PATTERNS:**
- Tries Trafilatura first, falls back to MCP/Playwright
- MCP requires Node.js and `npx @playwright/mcp@latest`
- Async/await for MCP operations
- Marks failed extractions in database

**Known Issues:**
- MCP initialization can fail silently
- Some sites block scraping (403/404 errors)
- No retry logic for failed extractions
- MCP cleanup not always called (resource leak potential)

#### ArticleSummarizer (`news_pipeline/summarizer.py`)

**Responsibility:** Generate structured article summaries

**Key Methods:**
- `summarize_article()` - Single article summarization
- `summarize_articles()` - Batch summarization workflow
- `get_articles_to_summarize()` - Query articles needing summarization

**Integration Points:**
- Reads from `articles` table
- Writes to `summaries` table
- Uses OpenAI API (GPT-4o-mini)
- Uses `language_config` for German prompts

**CRITICAL PATTERNS:**
- Structured output with JSON schema
- Extracts key points and entities
- German-language prompts by default
- Skips articles already summarized

**Known Issues:**
- No retry logic for API failures
- Long articles may exceed token limits
- Entity extraction quality varies

#### EnhancedMetaAnalyzer (`news_pipeline/enhanced_analyzer.py`)

**Responsibility:** Generate meta-analysis and daily digests

**Key Methods:**
- `generate_incremental_daily_digests()` - Main digest generation
- `create_executive_summary()` - Executive summary generation
- `export_enhanced_daily_digest()` - Export to JSON/Markdown
- `identify_trending_topics()` - Trend analysis

**Integration Points:**
- Reads from `summaries` table
- Reads from `digest_state` table
- Writes to `digest_state` table
- Uses Jinja2 templates (`templates/daily_digest.md.j2`)
- Uses `IncrementalDigestGenerator` for state management

**CRITICAL PATTERNS:**
- Incremental digest generation (multiple runs per day)
- State persistence in `digest_state` table
- Jinja2 templates for markdown output
- German-language output by default

**Known Issues:**
- Template customization requires code changes
- Incremental state can become stale
- No automatic cleanup of old digest states

### Deduplication System (Multi-Level)

#### ArticleDeduplicator (`news_pipeline/deduplication.py`)

**Responsibility:** Semantic similarity-based deduplication

**Key Methods:**
- `calculate_similarity()` - Multi-method similarity calculation
- `find_similar_articles()` - Cluster similar articles
- `deduplicate_articles()` - Main deduplication workflow

**Integration Points:**
- Reads from `items` table
- Writes to `article_clusters` table
- Uses sentence transformers (if available) or TF-IDF

**CRITICAL PATTERNS:**
- Multiple similarity methods (sentence embeddings, TF-IDF, basic)
- Fallback to simpler methods if dependencies missing
- Clustering threshold: 0.75 (configurable)

**Known Issues:**
- Sentence transformers not in requirements.txt (optional dependency)
- Falls back to TF-IDF which is less accurate
- No GPU acceleration

#### GPTTitleDeduplicator (`news_pipeline/gpt_deduplication.py`)

**Responsibility:** GPT-based title clustering (Step 3.0)

**Key Methods:**
- `create_clustering_prompt()` - Generate clustering prompt
- `call_gpt_for_clustering()` - Call GPT for clustering
- `parse_clustering_output()` - Parse GPT response
- `deduplicate_articles()` - Main workflow

**Integration Points:**
- Reads from `items` and `articles` tables
- Writes to `article_clusters` table
- Uses OpenAI API (GPT-4o-mini)

**CRITICAL PATTERNS:**
- Clusters articles by title similarity
- Selects primary article (longest content)
- Stores clusters with method='gpt_clustering'

**Known Issues:**
- GPT output parsing can fail if format unexpected
- No retry logic for API failures
- Expensive for large batches (token costs)

#### CrossRunTopicDeduplicator (`news_pipeline/cross_run_deduplication.py`)

**Responsibility:** Cross-run topic deduplication (Step 3.1)

**Key Methods:**
- `deduplicate_against_previous_runs()` - Main workflow
- `compare_topics_with_gpt()` - GPT-based topic comparison
- `get_todays_new_summaries()` - Query new summaries
- `mark_duplicate_topics()` - Mark duplicates in database

**Integration Points:**
- Reads from `summaries` table
- Reads from `cross_run_topic_signatures` table
- Writes to `summaries` table (topic_already_covered flag)
- Writes to `cross_run_topic_signatures` table
- Writes to `cross_run_deduplication_log` table
- Uses OpenAI API (GPT-4o-mini)

**CRITICAL PATTERNS:**
- Compares summaries across same-day runs
- Stores topic signatures for comparison
- Uses GPT for semantic topic comparison
- Marks duplicates but doesn't delete them

**Known Issues:**
- Not integrated into main pipeline yet (manual invocation)
- No automatic cleanup of old signatures
- GPT comparison can be expensive

#### CrossRunStateManager (`news_pipeline/cross_run_state_manager.py`)

**Responsibility:** Manage cross-run state and signatures

**Key Methods:**
- `store_topic_signature()` - Store topic signature
- `get_previous_signatures()` - Retrieve signatures for comparison
- `cleanup_old_signatures()` - Remove old signatures
- `log_deduplication_decision()` - Audit logging

**Integration Points:**
- Reads/writes `cross_run_topic_signatures` table
- Writes to `cross_run_deduplication_log` table

**CRITICAL PATTERNS:**
- Date-based partitioning
- Signature storage with run sequence
- Audit trail for all decisions

**Known Issues:**
- No automatic cleanup (manual invocation required)
- Signature storage can grow large over time

### State Management

#### PipelineStateManager (`news_pipeline/state_manager.py`)

**Responsibility:** Track pipeline execution state

**Key Methods:**
- `start_pipeline_run()` - Initialize new run
- `start_step()` - Mark step as started
- `complete_step()` - Mark step as completed
- `fail_step()` - Mark step as failed
- `pause_pipeline()` - Pause execution
- `resume_pipeline_run()` - Resume paused run

**Integration Points:**
- Reads/writes `pipeline_state` table
- Updates `items.pipeline_run_id` and `items.pipeline_stage`
- Signal handling for graceful shutdown

**CRITICAL PATTERNS:**
- UUID-based run identification
- Step-by-step state tracking
- Resume capability for interrupted runs
- Signal handling (SIGINT, SIGTERM)

**Known Issues:**
- Resume logic not fully tested
- No automatic cleanup of old runs
- State can become inconsistent if process killed

#### DigestStateManager (`news_pipeline/incremental_digest.py`)

**Responsibility:** Manage incremental digest state

**Key Methods:**
- `get_digest_state()` - Retrieve digest state
- `save_digest_state()` - Save digest state
- `clear_old_states()` - Cleanup old states

**Integration Points:**
- Reads/writes `digest_state` table
- Writes to `digest_generation_log` table

**CRITICAL PATTERNS:**
- Date + topic based state
- JSON storage of article IDs and digest content
- Incremental updates

**Known Issues:**
- No automatic cleanup (manual invocation required)
- State can become stale if articles deleted

---

## Configuration and Environment

### Environment Variables (`.env`)

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-...          # REQUIRED: OpenAI API key
MODEL_NANO=gpt-5-nano          # Model for filtering (fastest, cheapest)
MODEL_MINI=gpt-5-mini          # Model for summarization
MODEL_FULL=gpt-5               # Model for complex analysis
MODEL_ANALYSIS=gpt-5           # Model for rating analysis

# Pipeline Settings
CONFIDENCE_THRESHOLD=0.70      # Minimum confidence for article selection
MAX_ITEMS_PER_FEED=120         # Max articles to collect per feed
REQUEST_TIMEOUT_SEC=12         # HTTP request timeout

# Database
DB_PATH=./news.db              # SQLite database path

# Language
PIPELINE_LANGUAGE=de           # Output language (de=German, en=English)
```

**CRITICAL NOTES:**
- System fails without `OPENAI_API_KEY`
- **MODEL INCONSISTENCY WARNING:** The codebase has inconsistent model defaults:
  - `.env.example` specifies GPT-5 models (gpt-5-nano, gpt-5-mini, gpt-5)
  - Some code files still have hardcoded defaults to gpt-4o-mini
  - `filter.py` uses MODEL_NANO (gpt-5-nano) - correct
  - `summarizer.py` defaults to gpt-5-mini but code shows gpt-5-mini - correct
  - `enhanced_analyzer.py`, `incremental_digest.py`, `gpt_deduplication.py`, `cross_run_deduplication.py` still default to gpt-4o-mini in code
  - **RECOMMENDATION:** Update all hardcoded defaults in Python files to match .env.example
- `MODEL_NANO` is used for filtering (90% of API calls, cost optimization)
- `MODEL_MINI` is used for summarization
- `MODEL_FULL` is used for complex analysis (rarely)
- `CONFIDENCE_THRESHOLD` can be overridden at runtime
- `DB_PATH` defaults to `./news.db` if not set

### Configuration Files

#### `config/feeds.yaml`

Defines news sources:

```yaml
feeds:
  rss:
    - source: "NZZ"
      url: "https://www.nzz.ch/recent.rss"
    - source: "Blick"
      url: "https://www.blick.ch/rss.xml"
  
  sitemaps:
    - source: "20min"
      url: "https://www.20min.ch/sitemap_news.xml"
  
  html:
    - source: "BusinessClassOst"
      url: "https://businessclassost.ch/news"
      selectors:
        article_links: "a.article-link"
        title: "h2.title"
  
  google_news:
    - query: "Schweiz Wirtschaft"
      language: "de"
      country: "CH"
```

**IMPORTANT NOTES:**
- RSS feeds are most reliable
- Sitemaps provide structured data
- HTML scraping requires CSS selectors (brittle)
- Google News requires URL decoding

#### `config/topics.yaml`

Defines filtering topics and criteria:

```yaml
topics:
  creditreform_insights:
    include:
      - "Bonität"
      - "Insolvenz"
      - "Kreditwürdigkeit"
      - "Zahlungsfähigkeit"
      - "Creditreform"
    exclude:
      - "Sport"
      - "Unterhaltung"
    confidence_threshold: 0.70
    description: "Swiss business creditworthiness and insolvency news"
```

**IMPORTANT NOTES:**
- Topics are defined with include/exclude keywords
- Each topic has its own confidence threshold
- System currently focuses on single topic (creditreform_insights)
- Multi-topic support exists but not actively used

#### `config/pipeline_config.yaml`

Pipeline behavior configuration:

```yaml
pipeline:
  filtering:
    confidence_threshold: 0.70
    max_articles_to_process: 35
    enable_prefilter: false
    prefilter_top_n: 100
  
  scraping:
    timeout_seconds: 12
    max_retries: 3
    use_mcp_fallback: true
  
  summarization:
    max_summary_length: 500
    extract_entities: true
    extract_key_points: true
  
  deduplication:
    similarity_threshold: 0.75
    enable_gpt_clustering: true
    enable_cross_run: true
```

**IMPORTANT NOTES:**
- `confidence_threshold` and `max_articles_to_process` can be overridden at runtime
- `enable_prefilter` is false by default (experimental feature)
- `enable_cross_run` is true but not integrated into main pipeline yet

#### `config/mcp.json`

MCP server configuration for Playwright:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

**CRITICAL:** Requires Node.js and `npx` to be available in PATH.

---

## Technical Debt and Known Issues

### Critical Technical Debt

1. **processed_links Cache Issues**
   - **Location:** `news_pipeline/filter.py`, `processed_links` table
   - **Issue:** Cache prevents reprocessing articles even when needed
   - **Impact:** Can't reprocess articles if filtering logic changes
   - **Workaround:** Manual deletion from `processed_links` table
   - **Fix Needed:** Add cache invalidation logic or TTL

2. **MCP Resource Leaks**
   - **Location:** `news_pipeline/scraper.py`
   - **Issue:** MCP cleanup not always called, browser processes may leak
   - **Impact:** Memory leaks on long-running processes
   - **Workaround:** Manual process cleanup or restart
   - **Fix Needed:** Proper context manager for MCP lifecycle

3. **Schema Migration Chaos**
   - **Location:** `scripts/` directory, various migration scripts
   - **Issue:** No formal migration framework, manual ALTER TABLE statements
   - **Impact:** Schema changes are error-prone and hard to track
   - **Workaround:** Careful manual execution of migration scripts
   - **Fix Needed:** Implement proper migration framework (Alembic)

4. **Cross-Run Deduplication Not Integrated**
   - **Location:** `news_pipeline/cross_run_deduplication.py`
   - **Issue:** Implemented but not integrated into main pipeline
   - **Impact:** Manual invocation required, not part of automated workflow
   - **Workaround:** Run manually after pipeline completion
   - **Fix Needed:** Integrate into `news_analyzer.py` pipeline

5. **No Retry Logic for API Failures**
   - **Location:** `news_pipeline/summarizer.py`, `news_pipeline/scraper.py`
   - **Issue:** API failures cause article to be skipped permanently
   - **Impact:** Transient failures result in lost articles
   - **Workaround:** Rerun pipeline step manually
   - **Fix Needed:** Implement exponential backoff retry logic

6. **FastAPI Unused Dependency**
   - **Location:** `requirements.txt`
   - **Issue:** FastAPI installed but not used anywhere
   - **Impact:** Unnecessary dependency, larger install size
   - **Workaround:** None needed
   - **Fix Needed:** Remove from requirements.txt

7. **Sentence Transformers Optional**
   - **Location:** `news_pipeline/deduplication.py`
   - **Issue:** Sentence transformers not in requirements, falls back to TF-IDF
   - **Impact:** Lower quality deduplication
   - **Workaround:** Manual installation of sentence-transformers
   - **Fix Needed:** Add to requirements.txt or remove dependency

### Workarounds and Gotchas

**Environment Setup:**
- **MUST set OPENAI_API_KEY** - System fails immediately without it
- **Node.js required for MCP** - Not documented in requirements.txt
- **Database path resolution** - Uses `DB_PATH` env var or defaults to `./news.db`

**Pipeline Execution:**
- **First run requires database initialization** - Run `python scripts/init_db.py` first
- **Feeds must be loaded** - Run `python scripts/load_feeds.py` after init
- **processed_links cache** - May need manual clearing for reprocessing

**Configuration:**
- **Runtime overrides** - `--confidence-threshold` and `--max-articles` override config
- **Prefilter disabled by default** - Use `--enable-prefilter` to activate
- **German language default** - Set `LANGUAGE=en` for English output

**Deduplication:**
- **Multiple deduplication methods** - Semantic, GPT, and cross-run all active
- **Cross-run not automatic** - Must be invoked manually
- **Clusters stored separately** - Check `article_clusters` table for results

**State Management:**
- **Pipeline resume not fully tested** - May have issues with interrupted runs
- **Old states not cleaned automatically** - Manual cleanup required
- **Digest state can become stale** - No automatic invalidation

---

## Development and Deployment

### Local Development Setup

**Prerequisites:**
```bash
# Python 3.12+
python --version

# Node.js 18+ (for MCP)
node --version
npx --version

# Git
git --version
```

**Installation Steps:**
```bash
# 1. Clone repository
git clone <repository-url>
cd NewsAnalysis_2.0

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Verify MCP Playwright
npx @playwright/mcp@latest --help

# 5. Configure environment
cp .env.example .env
# Edit .env with your OpenAI API key

# 6. Initialize database
python scripts/init_db.py

# 7. Load feeds
python scripts/load_feeds.py

# 8. Test pipeline
python news_analyzer.py --step collect --limit 10
```

**IMPORTANT NOTES:**
- Virtual environment not required but recommended
- MCP Playwright downloads browser binaries on first use (~200MB)
- Database initialization creates `news.db` in project root
- First run may take longer due to browser downloads

### Running the Pipeline

**Full Pipeline:**
```bash
# Standard run (35 articles, confidence-based selection)
python news_analyzer.py

# Custom limits
python news_analyzer.py --max-articles 50 --confidence-threshold 0.75

# With prefilter (experimental)
python news_analyzer.py --enable-prefilter

# Export as markdown
python news_analyzer.py --format markdown
```

**Step-by-Step Execution:**
```bash
# Step 1: Collect URLs
python news_analyzer.py --step collect

# Step 2: Filter articles
python news_analyzer.py --step filter

# Step 3: Scrape content
python news_analyzer.py --step scrape --limit 50

# Step 4: Summarize articles
python news_analyzer.py --step summarize --limit 50

# Step 5: Generate digest
python news_analyzer.py --step digest --format markdown
```

**Statistics and Monitoring:**
```bash
# Show pipeline statistics
python news_analyzer.py --stats

# Debug mode (verbose logging)
python news_analyzer.py --debug

# Console output only (no log file)
python news_analyzer.py --no-file-logging
```

### Build and Deployment

**Docker Deployment:**
```bash
# Build image
docker build -t news-analyzer .

# Run container
docker run -d \
  -v $(pwd)/data:/app/data \
  -e OPENAI_API_KEY=your_key_here \
  news-analyzer
```

**IMPORTANT NOTES:**
- Dockerfile exists but may need updates
- Volume mount for database persistence
- Environment variables passed at runtime

**Cron Schedule (Linux/Mac):**
```bash
# Daily at 6 AM and 2 PM (Europe/Zurich)
0 6,14 * * * cd /path/to/NewsAnalysis_2.0 && python news_analyzer.py --format markdown
```

**Windows Task Scheduler:**
```powershell
# Create scheduled task
schtasks /create /tn "NewsAnalysis" /tr "python C:\path\to\news_analyzer.py" /sc daily /st 06:00
```

### Testing

**Unit Tests:**
```bash
# Run specific test
python scripts/test_cross_run_dedup.py

# Run pipeline flow test
python scripts/test_pipeline_flow.py

# Run enhanced analyzer test
python scripts/test_enhanced_analyzer.py
```

**IMPORTANT NOTES:**
- No comprehensive test suite
- Tests are in `scripts/` directory
- Most tests require database and API key
- No CI/CD pipeline configured

**Manual Testing:**
```bash
# Test with small dataset
python news_analyzer.py --limit 5 --debug

# Test specific feed
# (Edit config/test_feeds.yaml first)
python news_analyzer.py --step collect

# Test deduplication
python scripts/test_cross_run_dedup.py
```

---

## Performance Characteristics

### Pipeline Performance

**Typical Run Times (35 articles):**
- Collection: 30-60 seconds
- Filtering: 2-3 minutes (API calls)
- Scraping: 3-5 minutes (network I/O)
- Summarization: 3-4 minutes (API calls)
- Digest Generation: 30-60 seconds
- **Total: 10-15 minutes**

**Bottlenecks:**
1. **OpenAI API calls** - Rate limited, sequential processing
2. **Content scraping** - Network I/O, some sites slow
3. **MCP/Playwright** - Browser automation overhead
4. **Database writes** - SQLite single-writer limitation

**Optimization Opportunities:**
- Batch API calls (partially implemented)
- Parallel scraping (not implemented)
- Connection pooling (not implemented)
- Caching strategies (partially implemented)

### Resource Usage

**Memory:**
- Base: ~100MB
- With MCP: ~300-500MB (browser processes)
- Peak: ~800MB (large batch processing)

**Disk:**
- Database: 50-200MB (depends on article count)
- Logs: 10-50MB per day
- Browser cache: ~200MB (MCP Playwright)

**Network:**
- Collection: ~1-2MB (RSS/sitemap downloads)
- Scraping: ~10-50MB (article content)
- API: ~5-10MB (request/response data)

**API Costs (OpenAI):**
- Filtering: ~$0.10-0.20 per 100 articles
- Summarization: ~$0.15-0.25 per 100 articles
- Deduplication: ~$0.05-0.10 per 100 articles
- **Total: ~$0.30-0.55 per 100 articles**

---

## Security and Privacy

### Security Posture

**Authentication:**
- OpenAI API key via environment variable
- No user authentication (single-user system)
- No API endpoints exposed (local execution only)

**Data Protection:**
- SQLite database with file-system permissions
- No encryption at rest
- No sensitive data stored (public news articles)
- API key in `.env` file (not in repo)

**Network Security:**
- HTTPS for all external requests
- No incoming network connections
- Outbound only: OpenAI API, news sources

**Known Vulnerabilities:**
- `.env` file must be protected (contains API key)
- No input validation on configuration files
- SQL injection protected by parameterized queries
- No rate limiting on API calls (relies on OpenAI limits)

### Privacy Considerations

**Data Collection:**
- Collects publicly available news articles
- No personal data or PII
- No user tracking or analytics
- No cookies or session management

**Data Retention:**
- Articles stored indefinitely in database
- No automatic cleanup or archival
- Logs rotated manually
- No data sharing or external transmission (except OpenAI API)

**Compliance:**
- No GDPR requirements (no personal data)
- No data processing agreements needed
- News sources may have terms of service
- OpenAI API terms apply

---

## Troubleshooting Guide

### Common Issues

**1. "OpenAI API key not found"**
```bash
# Solution: Set API key in .env file
echo "OPENAI_API_KEY=sk-your-key-here" >> .env
```

**2. "MCP connection failed"**
```bash
# Solution: Verify Node.js and npx available
node --version
npx @playwright/mcp@latest --help

# If not installed:
npm install -g @playwright/mcp
```

**3. "Database locked"**
```bash
# Solution: Close other connections or enable WAL mode
sqlite3 news.db "PRAGMA journal_mode=WAL;"
```

**4. "No articles collected"**
```bash
# Solution: Check feeds configuration and network
python news_analyzer.py --step collect --debug

# Verify feeds loaded:
sqlite3 news.db "SELECT COUNT(*) FROM feeds;"
```

**5. "Articles not being processed"**
```bash
# Solution: Check processed_links cache
sqlite3 news.db "SELECT COUNT(*) FROM processed_links;"

# Clear cache if needed:
sqlite3 news.db "DELETE FROM processed_links WHERE processed_at < date('now', '-7 days');"
```

**6. "Scraping failures"**
```bash
# Solution: Check network and site availability
python news_analyzer.py --step scrape --debug

# Try with MCP disabled:
# (Edit scraper.py to skip MCP initialization)
```

**7. "API rate limit exceeded"**
```bash
# Solution: Reduce batch size or add delays
python news_analyzer.py --limit 20

# Check OpenAI usage:
# Visit https://platform.openai.com/usage
```

### Debug Mode

**Enable verbose logging:**
```bash
python news_analyzer.py --debug
```

**Check logs:**
```bash
# View recent logs
tail -f logs/news_pipeline.log

# Search for errors
grep ERROR logs/news_pipeline.log
```

**Database inspection:**
```bash
# Open database
sqlite3 news.db

# Check pipeline state
SELECT * FROM pipeline_state ORDER BY started_at DESC LIMIT 5;

# Check article counts
SELECT pipeline_stage, COUNT(*) FROM items GROUP BY pipeline_stage;

# Check recent articles
SELECT id, title, triage_confidence, is_match FROM items ORDER BY first_seen_at DESC LIMIT 10;
```

---

## Appendix

### Useful Commands

**Database Management:**
```bash
# Backup database
cp news.db news.db.backup

# Vacuum database (reclaim space)
sqlite3 news.db "VACUUM;"

# Check database size
du -h news.db

# Export to SQL
sqlite3 news.db .dump > backup.sql
```

**Log Management:**
```bash
# View recent logs
tail -100 logs/news_pipeline.log

# Search for errors
grep -i error logs/news_pipeline.log

# Clear old logs
find logs/ -name "*.log" -mtime +30 -delete
```

**Maintenance:**
```bash
# Clean old processed links
sqlite3 news.db "DELETE FROM processed_links WHERE processed_at < date('now', '-30 days');"

# Clean old pipeline states
sqlite3 news.db "DELETE FROM pipeline_state WHERE started_at < datetime('now', '-30 days');"

# Clean old digest states
sqlite3 news.db "DELETE FROM digest_state WHERE last_updated < datetime('now', '-30 days');"
```

### File Locations

**Configuration:**
- Environment: `.env`
- Feeds: `config/feeds.yaml`
- Topics: `config/topics.yaml`
- Pipeline: `config/pipeline_config.yaml`
- MCP: `config/mcp.json`

**Data:**
- Database: `news.db` (or `DB_PATH` env var)
- Logs: `logs/news_pipeline.log`
- Outputs: `outputs/` directory
- Reports: `rating_reports/` directory

**Code:**
- Main entry: `news_analyzer.py`
- Pipeline: `news_pipeline/` directory
- Scripts: `scripts/` directory
- Templates: `templates/` directory

### External Dependencies

**Python Packages:**
- See `requirements.txt` for complete list
- Key dependencies: openai, trafilatura, feedparser, pydantic, jinja2

**System Requirements:**
- Python 3.12+
- Node.js 18+ (for MCP)
- SQLite 3.x
- ~1GB disk space
- ~500MB RAM

**External Services:**
- OpenAI API (required)
- News sources (RSS/sitemaps/HTML)
- No other external services

---

## Document Maintenance

This brownfield architecture document should be updated when:
- New components are added to the pipeline
- Database schema changes
- Configuration options change
- Technical debt is addressed
- New workarounds are discovered
- Performance characteristics change

**Last Updated:** 2025-01-03
**Next Review:** When significant changes are made to the codebase

---

**End of Brownfield Architecture Document**
