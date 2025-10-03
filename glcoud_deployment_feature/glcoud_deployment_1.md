# AI-Powered News Analysis System - Google Cloud Deployment Guide

## Project Overview

**System Name:** AI-Powered News Analysis System  
**Version:** 2.0  
**Primary Language:** Python 3.11+  
**Architecture:** 5-Step AI Pipeline for Swiss Business News Analysis  
**Repository:** https://github.com/ClaudioLutz/NewsAnalysis_2.0.git  
**Current Commit:** f632f406330f364363677de2c8b84d98b1557912  

### Core Functionality
The system implements a streamlined 5-step workflow leveraging GPT models for intelligent Swiss business news monitoring:

1. **URL Collection** - RSS feeds, sitemaps, HTML listings
2. **AI-Powered Filtering** - GPT-5-mini for relevance filtering by title/URL
3. **Selective Content Scraping** - MCP+Playwright and Trafilatura (90% scraping reduction)
4. **Individual Article Summarization** - Structured summaries with GPT-5-mini
5. **Meta-Summary Generation** - Executive briefings and topic digests

### Key Benefits
- **90% reduction in scraping overhead** through AI-first filtering
- **Cost optimization** using GPT-5-mini for filtering, GPT-5 for analysis
- **Comprehensive insights** with trend identification and executive summaries
- **Multi-format export** (JSON, Markdown)

---

## Technical Architecture

### Application Stack
```
┌─────────────────────────────────────┐
│           Frontend/API              │
│         FastAPI + Uvicorn           │
├─────────────────────────────────────┤
│        Application Layer            │
│     news_analyzer.py (Main)         │
│   5-Step Pipeline Components        │
├─────────────────────────────────────┤
│         AI Integration              │
│    OpenAI GPT Models + MCP          │
├─────────────────────────────────────┤
│       Content Processing            │
│  Playwright + Trafilatura + FTS5    │
├─────────────────────────────────────┤
│         Data Layer                  │
│      SQLite + WAL Mode              │
└─────────────────────────────────────┘
```

### Core Components

#### Pipeline Components (`news_pipeline/`)
- **collector.py** - URL collection from RSS/Sitemaps/HTML
- **filter.py** - AI-powered relevance filtering
- **scraper.py** - Content extraction with MCP+Playwright
- **summarizer.py** - Individual article summarization
- **analyzer.py** - Meta-analysis and digest generation
- **deduplication.py** - Semantic article deduplication
- **state_manager.py** - Pipeline state tracking

#### Support Components
- **utils.py** - Shared utilities and logging
- **language_config.py** - German language processing
- **german_rating_formatter.py** - Swiss business formatting

### Database Schema (SQLite + FTS5)

```sql
-- Core article storage
CREATE TABLE items (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    normalized_url TEXT NOT NULL,
    title TEXT,
    published_at TEXT,
    first_seen_at TEXT DEFAULT (datetime('now')),
    triage_topic TEXT,
    triage_confidence REAL,
    is_match INTEGER DEFAULT 0,
    pipeline_run_id TEXT,
    pipeline_stage TEXT,
    selected_for_processing INTEGER DEFAULT 0,
    selection_rank INTEGER
);

-- Full-text search capability
CREATE VIRTUAL TABLE items_fts USING fts5(
    title, url, content='items', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

-- Extracted content
CREATE TABLE articles (
    item_id INTEGER PRIMARY KEY REFERENCES items(id),
    extracted_text TEXT,
    extracted_at TEXT DEFAULT (datetime('now')),
    method TEXT CHECK(method IN ('trafilatura','playwright'))
);

-- AI-generated summaries
CREATE TABLE summaries (
    item_id INTEGER PRIMARY KEY REFERENCES items(id),
    topic TEXT,
    model TEXT,
    summary TEXT,
    key_points_json TEXT,
    entities_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Pipeline state tracking
CREATE TABLE pipeline_state (
    id INTEGER PRIMARY KEY,
    run_id TEXT UNIQUE NOT NULL,
    step_name TEXT CHECK(step_name IN ('collection', 'filtering', 'scraping', 'summarization', 'analysis')),
    status TEXT CHECK(status IN ('pending', 'running', 'completed', 'failed', 'paused')),
    started_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    metadata TEXT,
    article_count INTEGER DEFAULT 0,
    match_count INTEGER DEFAULT 0,
    error_message TEXT
);

-- Deduplication clusters
CREATE TABLE article_clusters (
    id INTEGER PRIMARY KEY,
    cluster_id TEXT NOT NULL,
    article_id INTEGER REFERENCES items(id),
    is_primary INTEGER DEFAULT 0,
    similarity_score REAL DEFAULT 0.0,
    created_at TEXT DEFAULT (datetime('now')),
    clustering_method TEXT DEFAULT 'title_similarity'
);
```

---

## Dependencies & Requirements

### System Requirements
- **OS:** Linux-based (Ubuntu 22.04+ recommended)
- **Python:** 3.11+ 
- **Node.js:** 18+ (for MCP Playwright)
- **Memory:** Minimum 2GB RAM, 4GB+ recommended
- **Storage:** 10GB+ for data and models
- **Network:** Outbound HTTPS for OpenAI API and news sources

### Python Dependencies (`requirements.txt`)
```
openai>=1.47                 # OpenAI API integration
langchain-openai>=0.2.0      # LangChain OpenAI integration
mcp-use>=1.3.7              # Model Context Protocol
trafilatura>=2.0.0,<2.1     # Content extraction
feedparser>=6.0.11          # RSS feed parsing
pydantic>=2.8               # Data validation
python-dateutil>=2.9        # Date/time handling
fastapi>=0.112              # Web framework
uvicorn>=0.30               # ASGI server
sqlite-utils>=3.36          # SQLite utilities
PyYAML>=6.0                 # YAML configuration
requests>=2.28.0            # HTTP requests
urllib3[zstd]>=2.0.0        # URL handling with compression
beautifulsoup4>=4.11.0      # HTML parsing
lxml>=4.9.0                 # XML processing
python-dotenv>=1.0.0        # Environment variables
```

### Node.js Dependencies
```bash
@playwright/mcp             # MCP Playwright server
playwright                  # Browser automation
```

### External APIs
- **OpenAI API** - GPT models for filtering and summarization
- **Various News Sources** - RSS feeds, sitemaps (configured in `config/feeds.yaml`)

---

## Environment Configuration

### Required Environment Variables

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-...                    # OpenAI API key (REQUIRED)
MODEL_MINI=gpt-3.5-turbo                 # Cost-efficient model for filtering
MODEL_NANO=gpt-5-nano                    # Ultra-light model if available
MODEL_FULL=gpt-5                         # Premium model for complex analysis
RESPONSES_API_OUTPUT_VERSION=v1          # OpenAI API version
OPENAI_PARALLEL_TOOL_CALLS=false         # Disable parallel calls

# Feature Flags
SKIP_GNEWS_REDIRECTS=true                # Skip Google News redirects

# Crawler Configuration
USER_AGENT="NewsAnalyzerBot/1.0 (+contact@email)"  # Bot identification
MAX_ITEMS_PER_FEED=120                   # Articles per feed
REQUEST_TIMEOUT_SEC=12                   # HTTP timeout
CRAWL_DELAY_SEC=4                       # Politeness delay
CONCURRENCY=4                           # Concurrent requests

# Database
DB_PATH=./news.db                       # SQLite database path

# Processing Thresholds
CONFIDENCE_THRESHOLD=0.70               # Minimum confidence for processing

# Language Configuration
PIPELINE_LANGUAGE=de                    # German language processing
```

### Configuration Files

#### `config/pipeline_config.yaml`
```yaml
pipeline:
  filtering:
    confidence_threshold: 0.8            # AI confidence threshold
    max_articles_to_process: 35          # Max articles per run
  reporting:
    show_funnel_stats: true              # Display pipeline funnel
    show_selection_details: true         # Show selection details
  scraping:
    max_retries: 3                       # Scraping retry attempts
    timeout: 30                          # Scraping timeout
  summarization:
    max_summary_length: 500              # Summary character limit
    min_content_length: 600              # Minimum content for processing
  topics:
    creditreform_insights:
      confidence_threshold: 0.71         # Topic-specific threshold
      max_articles: 35                   # Topic article limit
```

#### `config/feeds.yaml` (Swiss News Sources)
```yaml
feeds:
  rss:
    - source: "nzz"
      url: "https://www.nzz.ch/recent.rss"
    - source: "blick"
      url: "https://www.blick.ch/news/rss.xml"
    # Additional Swiss sources...
  
  sitemaps:
    - source: "20min"
      url: "https://www.20min.ch/news-sitemap.xml"
  
  html:
    - source: "businessclassost"
      url: "https://www.businessclassost.ch/"
```

#### `config/topics.yaml`
```yaml
topics:
  schweizer_wirtschaft:
    include: ["Schweiz", "Wirtschaft", "Unternehmen", "Finanz"]
    confidence_threshold: 0.70
  fintech:
    include: ["Fintech", "Krypto", "Zahlung", "Digitale Bank"]
    confidence_threshold: 0.75
  creditreform_insights:
    include: ["Kreditreform", "Bonitätsprüfung", "Wirtschaftsauskunft"]
    confidence_threshold: 0.75
```

---

## Google Cloud Deployment Strategy

### Option 1: Cloud Run (Recommended for Scheduled Jobs)

#### Service Configuration
```yaml
# cloud-run-service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: news-analyzer
  annotations:
    run.googleapis.com/ingress: private
    run.googleapis.com/execution-environment: gen2
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/cpu-boost: true
        run.googleapis.com/memory: "4Gi"
        run.googleapis.com/cpu: "2"
        run.googleapis.com/timeout: "3600s"  # 1 hour timeout
    spec:
      containerConcurrency: 1
      containers:
      - image: gcr.io/PROJECT_ID/news-analyzer:latest
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-secret
              key: api-key
        - name: DB_PATH
          value: "/app/data/news.db"
        - name: CONFIDENCE_THRESHOLD
          value: "0.70"
        volumeMounts:
        - name: data-volume
          mountPath: /app/data
        resources:
          limits:
            memory: "4Gi"
            cpu: "2"
      volumes:
      - name: data-volume
        persistentVolumeClaim:
          claimName: news-analyzer-pvc
```

#### Cloud Scheduler Configuration
```bash
# Daily execution at 6:00 AM CET
gcloud scheduler jobs create http news-analyzer-daily \
  --location=europe-west1 \
  --schedule="0 6 * * *" \
  --time-zone="Europe/Zurich" \
  --uri="https://news-analyzer-SERVICE_URL.a.run.app" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"action": "run_pipeline", "export_format": "json"}' \
  --oidc-service-account-email=scheduler@PROJECT_ID.iam.gserviceaccount.com
```

### Option 2: Google Kubernetes Engine (GKE)

#### Deployment Configuration
```yaml
# gke-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: news-analyzer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: news-analyzer
  template:
    metadata:
      labels:
        app: news-analyzer
    spec:
      containers:
      - name: news-analyzer
        image: gcr.io/PROJECT_ID/news-analyzer:latest
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-secret
              key: api-key
        - name: DB_PATH
          value: "/app/data/news.db"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
        volumeMounts:
        - name: data-volume
          mountPath: /app/data
      volumes:
      - name: data-volume
        persistentVolumeClaim:
          claimName: news-analyzer-pvc
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: news-analyzer-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
  storageClassName: standard-ssd
```

### Option 3: Compute Engine (VM-based)

#### VM Specifications
- **Machine Type:** e2-standard-2 (2 vCPUs, 8GB RAM)
- **OS:** Ubuntu 22.04 LTS
- **Boot Disk:** 50GB SSD persistent disk
- **Region:** europe-west1 (Belgium) or europe-west6 (Zurich)

#### Startup Script
```bash
#!/bin/bash
# startup-script.sh

# Update system
apt-get update && apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
systemctl enable docker
systemctl start docker

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Clone repository
git clone https://github.com/ClaudioLutz/NewsAnalysis_2.0.git /opt/news-analyzer
cd /opt/news-analyzer

# Set up environment
cp .env.example .env
# Configure environment variables from metadata or secrets

# Build and run
docker-compose up -d

# Set up cron job for daily execution
cat > /etc/cron.d/news-analyzer << EOF
0 6 * * * root cd /opt/news-analyzer && docker-compose exec -T app python news_analyzer.py --export --format json
EOF
```

---

## Container Deployment

### Dockerfile Analysis
```dockerfile
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    curl git && rm -rf /var/lib/apt/lists/*

# Node.js 18+ for MCP Playwright
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# MCP Playwright setup
RUN npm install -g @playwright/mcp
RUN npx playwright install --with-deps chromium

# Application setup
COPY . .
RUN mkdir -p /app/data /app/out/digests /app/logs

# Security: non-root user
RUN useradd -m -u 1000 newsanalyzer && \
    chown -R newsanalyzer:newsanalyzer /app
USER newsanalyzer

# Database initialization
RUN python scripts/init_db.py
RUN python scripts/load_feeds.py

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('${DB_PATH}').execute('SELECT 1')" || exit 1

CMD ["python", "news_analyzer.py", "--export", "--format", "json"]
```

### Docker Compose Configuration
```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: .
    container_name: news-analyzer
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DB_PATH=/app/data/news.db
      - CONFIDENCE_THRESHOLD=0.70
    volumes:
      - ./data:/app/data
      - ./outputs:/app/out/digests
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import sqlite3; sqlite3.connect('/app/data/news.db').execute('SELECT 1')"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Container Registry Setup
```bash
# Build and push to Google Container Registry
gcloud auth configure-docker
docker build -t gcr.io/PROJECT_ID/news-analyzer:latest .
docker push gcr.io/PROJECT_ID/news-analyzer:latest

# Alternative: Artifact Registry
gcloud auth configure-docker europe-west1-docker.pkg.dev
docker build -t europe-west1-docker.pkg.dev/PROJECT_ID/news-analyzer/app:latest .
docker push europe-west1-docker.pkg.dev/PROJECT_ID/news-analyzer/app:latest
```

---

## Storage Solutions

### Option 1: Cloud SQL (PostgreSQL)
- **Instance:** db-f1-micro (shared vCPU, 0.6GB RAM)
- **Storage:** 10GB SSD
- **Automated Backups:** Daily with 7-day retention
- **High Availability:** Multi-zone for production

```sql
-- Migration script to PostgreSQL
CREATE TABLE items (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    normalized_url TEXT NOT NULL,
    title TEXT,
    published_at TIMESTAMP,
    first_seen_at TIMESTAMP DEFAULT NOW(),
    triage_topic TEXT,
    triage_confidence DECIMAL(5,4),
    is_match BOOLEAN DEFAULT FALSE,
    pipeline_run_id TEXT,
    pipeline_stage TEXT,
    selected_for_processing BOOLEAN DEFAULT FALSE,
    selection_rank INTEGER
);

-- Full-text search with PostgreSQL
CREATE INDEX CONCURRENTLY idx_items_fts ON items 
USING GIN (to_tsvector('german', title || ' ' || COALESCE(url, '')));
```

### Option 2: Persistent Disk (SQLite)
- **Disk Type:** SSD persistent disk
- **Size:** 20GB (expandable)
- **Backup:** Snapshot schedule (daily, 7-day retention)
- **Mount Point:** `/app/data`

### Option 3: Cloud Storage (Archive)
```python
# Archive old data to Cloud Storage
from google.cloud import storage

def archive_old_data():
    """Archive articles older than 90 days to Cloud Storage."""
    storage_client = storage.Client()
    bucket = storage_client.bucket('news-analyzer-archive')
    
    # Export old data
    conn = sqlite3.connect(DB_PATH)
    old_articles = conn.execute("""
        SELECT * FROM items 
        WHERE first_seen_at < date('now', '-90 days')
    """).fetchall()
    
    # Upload to Cloud Storage
    blob = bucket.blob(f"archive/{datetime.now().strftime('%Y-%m')}/articles.json")
    blob.upload_from_string(json.dumps(old_articles))
    
    # Clean up local database
    conn.execute("DELETE FROM items WHERE first_seen_at < date('now', '-90 days')")
    conn.commit()
```

---

## Security Configuration

### IAM Roles and Permissions

#### Service Account Setup
```bash
# Create service account
gcloud iam service-accounts create news-analyzer \
    --display-name="News Analyzer Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:news-analyzer@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:news-analyzer@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:news-analyzer@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/logging.logWriter"
```

#### Secret Management
```bash
# Store OpenAI API key in Secret Manager
gcloud secrets create openai-api-key \
    --data-file=- <<< "sk-your-openai-api-key"

# Grant access to service account
gcloud secrets add-iam-policy-binding openai-api-key \
    --member="serviceAccount:news-analyzer@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### Network Security

#### VPC Configuration
```bash
# Create VPC network
gcloud compute networks create news-analyzer-vpc \
    --subnet-mode=regional

# Create subnet
gcloud compute networks subnets create news-analyzer-subnet \
    --network=news-analyzer-vpc \
    --range=10.0.0.0/24 \
    --region=europe-west1
```

#### Firewall Rules
```bash
# Allow internal communication
gcloud compute firewall-rules create news-analyzer-internal \
    --network=news-analyzer-vpc \
    --allow=tcp,udp,icmp \
    --source-ranges=10.0.0.0/24

# Allow HTTPS outbound (for API calls)
gcloud compute firewall-rules create news-analyzer-outbound \
    --network=news-analyzer-vpc \
    --direction=EGRESS \
    --action=ALLOW \
    --rules=tcp:443 \
    --destination-ranges=0.0.0.0/0
```

### SSL/TLS Configuration
```bash
# Create managed SSL certificate for custom domain
gcloud compute ssl-certificates create news-analyzer-ssl \
    --domains=news-analyzer.yourdomain.com \
    --global
```

---

## Monitoring and Logging

### Cloud Monitoring Setup

#### Custom Metrics
```python
# monitoring.py
from google.cloud import monitoring_v3
import time

def record_pipeline_metrics(articles_processed, success_rate, duration):
    """Record custom metrics for pipeline execution."""
    client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{PROJECT_ID}"
    
    # Articles processed metric
    series = monitoring_v3.TimeSeries()
    series.metric.type = "custom.googleapis.com/news_analyzer/articles_processed"
    series.resource.type = "global"
    
    point = series.points.add()
    point.value.int64_value = articles_processed
    point.interval.end_time.seconds = int(time.time())
    
    client.create_time_series(name=project_name, time_series=[series])
```

#### Alerting Policies
```yaml
# alerting-policy.yaml
displayName: "News Analyzer Pipeline Failure"
conditions:
  - displayName: "Pipeline execution failed"
    conditionThreshold:
      filter: 'resource.type="cloud_run_revision" AND resource.label.service_name="news-analyzer"'
      comparison: COMPARISON_GT
      thresholdValue: 0
      duration: "300s"
      aggregations:
        - alignmentPeriod: "300s"
          perSeriesAligner: ALIGN_COUNT_TRUE
notificationChannels:
  - projects/PROJECT_ID/notificationChannels/NOTIFICATION_CHANNEL_ID
```

### Structured Logging
```python
# Enhanced logging configuration
import logging
import json
from google.cloud import logging as cloud_logging

class StructuredLogger:
    def __init__(self, name):
        # Set up Cloud Logging
        cloud_logging_client = cloud_logging.Client()
        cloud_logging_client.setup_logging()
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
    
    def log_pipeline_start(self, run_id, config):
        self.logger.info("Pipeline started", extra={
            "run_id": run_id,
            "config": config,
            "event_type": "pipeline_start"
        })
    
    def log_step_complete(self, step, duration, metrics):
        self.logger.info(f"Step {step} completed", extra={
            "step": step,
            "duration_seconds": duration,
            "metrics": metrics,
            "event_type": "step_complete"
        })
```

### Health Monitoring
```python
# health_check.py
from fastapi import FastAPI, HTTPException
import sqlite3
import os

app = FastAPI()

@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint."""
    checks = {
        "database": check_database(),
        "openai_api": check_openai_api(),
        "disk_space": check_disk_space(),
        "memory": check_memory_usage()
    }
    
    if all(checks.values()):
        return {"status": "healthy", "checks": checks}
    else:
        raise HTTPException(status_code=503, detail={"status": "unhealthy", "checks": checks})

def check_database():
    try:
        conn = sqlite3.connect(os.getenv("DB_PATH"))
        conn.execute("SELECT 1")
        conn.close()
        return True
    except:
        return False
```

---

## Performance Optimization

### Caching Strategy

#### Redis Configuration (Optional)
```yaml
# redis-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "200m"
```

#### Application Caching
```python
# caching.py
import redis
import pickle
from functools import wraps

redis_client = redis.Redis(host='redis-service', port=6379, decode_responses=False)

def cache_result(ttl=3600):
    """Cache function results in Redis."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached = redis_client.get(cache_key)
            if cached:
                return pickle.loads(cached)
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            redis_client.setex(cache_key, ttl, pickle.dumps(result))
            return result
        return wrapper
    return decorator

# Usage
@cache_result(ttl=1800)  # 30 minutes
def get_feed_articles(feed_url):
    return feedparser.parse(feed_url)
```

### Database Optimization

#### SQLite Performance Tuning
```python
# database_optimization.py
def optimize_sqlite_connection(db_path):
    """Apply SQLite performance optimizations."""
    conn = sqlite3.connect(db_path)
    
    # Performance PRAGMA settings
    conn.executescript("""
        PRAGMA journal_mode = WAL;           -- Write-Ahead Logging
        PRAGMA synchronous = NORMAL;         -- Good balance of safety/speed
        PRAGMA cache_size = -64000;          -- 64MB cache
        PRAGMA temp_store = MEMORY;          -- Temp tables in memory
        PRAGMA mmap_size = 268435456;        -- 256MB memory-mapped I/O
        PRAGMA optimize;                     -- Optimize query planner
    """)
    
    return conn
```

#### Connection Pooling
```python
# connection_pool.py
import sqlite3
from contextlib import contextmanager
from queue import Queue
import threading

class SQLitePool:
    def __init__(self, db_path, pool_size=5):
        self.db_path = db_path
        self.pool = Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        
        # Pre-populate pool
        for _ in range(pool_size):
            conn = optimize_sqlite_connection(db_path)
            self.pool.put(conn)
    
    @contextmanager
    def get_connection(self):
        conn = self.pool.get()
        try:
            yield conn
        finally:
            self.pool.put(conn)
```

---

## Cost Optimization

### OpenAI API Cost Management

#### Token Usage Monitoring
```python
# token_monitoring.py
class TokenMonitor:
    def __init__(self):
        self.total_tokens = 0
        self.costs = {
            "gpt-3.5-turbo": 0.002 / 1000,      # $0
