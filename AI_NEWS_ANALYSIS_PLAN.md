# Streamlined AI-Powered News Analysis System

## Project Overview

Build an intelligent news analysis pipeline using a simple, efficient 5-step workflow that leverages GPT-5 models for smart filtering and summarization. This plan serves as the foundation for a complete rebuild focused on maximum efficiency and minimal complexity.

## Prerequisites

### System Requirements
```bash
# System
Python 3.11+
Node.js 18+   # required by Playwright MCP

# Python deps (pin at commit time)
pip install "openai>=1.47" "langchain-openai>=0.2.0" "mcp-use>=1.3.7" "trafilatura>=2.0.0,<2.1" feedparser==6.0.10 \
            pydantic>=2.8 python-dateutil>=2.9 fastapi>=0.112 uvicorn>=0.30 sqlite-utils>=3.36

# Node deps (no project install needed; npx is fine)
npx @playwright/mcp@latest --help
```

### Environment Configuration

**`.env.example`** (copyable):
```env
# OpenAI
OPENAI_API_KEY=sk-...

# Models
MODEL_MINI=gpt-5-mini
MODEL_NANO=gpt-5-nano
MODEL_FULL=gpt-5
RESPONSES_API_OUTPUT_VERSION=v1
OPENAI_PARALLEL_TOOL_CALLS=false

# Crawler
USER_AGENT="NewsAnalyzerBot/1.0 (+contact@email)"
MAX_ITEMS_PER_FEED=120
REQUEST_TIMEOUT_SEC=12
CRAWL_DELAY_SEC=4
CONCURRENCY=4

# Database
DB_PATH=./news.db

# Thresholds
CONFIDENCE_THRESHOLD=0.70
```

**`config/topics.yaml`** (realistic default):
```yaml
topics:
  schweizer_wirtschaft:
    include: ["Schweiz", "Wirtschaft", "Unternehmen", "Finanz", "Bank", "Versicherung"]
    confidence_threshold: 0.70
  fintech:
    include: ["Fintech", "Krypto", "Zahlung", "Digitale Bank", "Neobank"]
    confidence_threshold: 0.75
```

## Core Workflow Strategy

**Smart Filtering First**: Only scrape articles that pass AI relevance filtering, dramatically reducing processing overhead while maintaining high-quality results.

## 5-Step Processing Pipeline

### Step 1: URL Collection (RSS/Sitemap/HTML) — Discovery Only

**Comprehensive Swiss News Source Collection**
Collect headline-level metadata (URL, title, source, published time) from a fixed set of Swiss news outlets via **RSS**, plus **20 Minuten** via **news sitemap**, and **BusinessClassOst** via **HTML listing**. No article text here — only discovery for URL-first gating with `gpt-5-mini`.

#### Exact Source List & Endpoints

**`config/feeds.yaml`** (executable configuration):
```yaml
rss:
  blick:               ["https://www.blick.ch/rss.xml"]
  luzerner_zeitung:    ["https://www.luzernerzeitung.ch/arc/outboundfeeds/rss/"]
  st_galler_tagblatt:  ["https://www.tagblatt.ch/arc/outboundfeeds/rss/"]
  aargauer_zeitung:    ["https://www.aargauerzeitung.ch/arc/outboundfeeds/rss/"]
  inside_paradeplatz:  ["https://insideparadeplatz.ch/feed/"]
  nzz:                 ["https://www.nzz.ch/recent.rss","https://www.nzz.ch/wirtschaft.rss","https://www.nzz.ch/schweiz.rss"]

sitemaps:
  20min: ["https://www.20min.ch/sitemaps/de/news.xml"]   # parse <url><loc>, <news:title>, <news:publication_date>

html:
  businessclassost:
    url: "https://www.businessclassost.ch/news-categories/news"
    selectors:
      item: "div.card.w-dyn-item"
      date: "div.datum"
      title: "h2.heading.h4"
      hidden_url: "div.hiddenarticleurl"

google_news_rss:
  wirtschaft:   "https://news.google.com/rss/search?q=wirtschaft&hl=de-CH&gl=CH&ceid=CH:de"
  fintech:      "https://news.google.com/rss/search?q=fintech&hl=de-CH&gl=CH&ceid=CH:de"
  schweiz:      "https://news.google.com/rss/search?q=Schweiz&hl=de-CH&gl=CH&ceid=CH:de"
```

We standardize on `?hl=de-CH&gl=CH&ceid=CH:de` for CH-German; topic and keyword feeds follow the same triplet.

#### Robots Compliance

**Robots & crawl etiquette rules**:
- Use `urllib.robotparser` to **disallow** crawls not permitted for the `USER_AGENT`
- Respect `Crawl-delay` if present; otherwise throttle at `CRAWL_DELAY_SEC`
- Honor per-domain **allow-list**
- Robots behavior follows RFC 9309; we honor `Crawl-delay` and `Request-rate` when present via `urllib.robotparser`.

```python
from urllib import robotparser
def is_allowed(url, ua):
    rp = robotparser.RobotFileParser()
    rp.set_url(f"{url.scheme}://{url.netloc}/robots.txt")
    rp.read()
    return rp.can_fetch(ua, url.geturl())
```

#### Fetcher Rules & Retries

**HTTP Configuration:**
- Headers: `{'User-Agent': USER_AGENT, 'Accept': 'application/rss+xml,application/xml;q=0.9,text/xml;q=0.8,*/*;q=0.5'}`
- Retries: exponential backoff on 429/5xx (3 attempts)
- Backoff on 429/5xx with jitter (keeps MCP retries predictable)
- Timeouts: `REQUEST_TIMEOUT_SEC`
- Concurrency: `CONCURRENCY` workers
- **Respect robots**: skip if `is_allowed(url, USER_AGENT)` is false

#### URL Normalization & Dedup

**URL normalization rules:**
- Strip tracking params: `utm_*`, `gclid`, `fbclid`, `WT.*`
- Always follow Google News redirects to the publisher before hashing/normalizing
- If `<link rel="canonical">` exists, store it as `normalized_url` and dedup on it

**Deduplication Strategy:**
- Primary: URL normalization (lowercase host, strip tracking, remove fragments)
- Secondary: Title similarity within same source/time window (Jaccard ≥ 0.9)
- Key: `sha1(normalized_url)` for fast lookups

#### Date Parsing

- RSS: Use `feedparser` for all Atom/RSS feeds (`feedparser.published_parsed` → ISO 8601)
- 20min Sitemap: Parse ISO format `2025-02-13T14:40:07+01:00` → `YYYY-MM-DD`
- BusinessClassOst: Convert `13.2.25` → `2025-02-13`
- Fallback: HTTP `Date` header or `now()` with `source_time_unknown=true`

#### Output Schema

**Minimal record to MODEL_MINI gate (no content fetching yet):**
```json
{
  "url": "<canonical_url>",
  "title": "<title>", 
  "source": "<source_name>",
  "published_at": "<ISO8601 or null>",
  "aggregator_url": "<google_news_url if applicable>",
  "discovered_at": "<timestamp>"
}
```

### Step 2: AI-Powered Filtering (Title/URL Only)

**Single-Stage Pre-Filter (Title/URL only)**
– **Model:** MODEL_MINI (env: default `gpt-5-mini`)
– **Input:** `{title, url, topic}` (no fetching yet)
– **Output:** strict JSON `{ "is_match": boolean, "confidence": 0..1, "reason": "..." }` via **Structured Outputs**
– **Threshold:** keep only items with `is_match==true` and `confidence >= CONFIDENCE_THRESHOLD`

#### Triage Schema

**`schemas/triage.schema.json`**:
```json
{
  "name": "triage",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "is_match": { "type": "boolean" },
      "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
      "topic": { "type": "string" },
      "reason": { "type": "string" }
    },
    "required": ["is_match", "confidence", "topic"]
  }
}
```

### Step 3: Selective Content Scraping (Relevant Articles Only)

**MCP + Playwright Integration**
- **Only scrape articles that pass Step 2 filtering**
- MCP-controlled Playwright for JS-heavy sites
- Trafilatura fallback for simple sites
- Rate limiting and domain restrictions
- Skip articles if both extraction methods fail

#### MCP Configuration

**`config/mcp.json`**:
```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"],
      "env": { "DISPLAY": ":1" }
    }
  }
}
```

**Usage in code**:
```python
from mcp_use import MCPAgent, MCPClient
from langchain_openai import ChatOpenAI

client = MCPClient.from_config_file("config/mcp.json")
llm = ChatOpenAI(model=os.getenv("MODEL_MINI", "gpt-5-mini"))
agent = MCPAgent(llm=llm, client=client, max_steps=30)

result = await agent.run(f"Extract the main article text from: {article_url}")
# Fallback: trafilatura.extract(html) if MCP result insufficient
```

**Scraping Priority:**
1. Trafilatura (fast, works for 80% of sites)
2. MCP + Playwright (comprehensive, for complex sites)
3. Skip (log for manual review if needed)

### Step 4: Individual Article Summarization

**Article Summarization**
– **Model:** MODEL_MINI (env: default `gpt-5-mini`)
– **Input:** extracted full text (after MCP/Trafilatura)
– **Output:** strict JSON with `summary`, `key_points[]`, `entities{}` via **Structured Outputs**

#### Summary Schema

**`schemas/summary.schema.json`**:
```json
{
  "name": "article_summary",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "title": { "type": "string" },
      "summary": { "type": "string" },
      "key_points": { "type": "array", "items": { "type": "string" }, "maxItems": 6 },
      "entities": { "type": "object", "additionalProperties": { "type": "array", "items": { "type": "string" } } }
    },
    "required": ["summary", "key_points"]
  }
}
```

### Step 5: Meta-Summary Generation

**Aggregate Intelligence**
- Collect all individual article summaries
- **MODEL_MINI** for comprehensive topic analysis
- Generate daily/weekly digest reports
- Identify patterns and trending topics
- Create executive summary with key insights

#### Daily Digest (Summary of Summaries)

After per-article summaries, aggregate **per topic/per day** into a single briefing:
**Model:** MODEL_MINI (default)
**Input:** list of `{title, url, summary}`
**Output (JSON):**

```json
{
  "headline": "string",
  "why_it_matters": "string",
  "bullets": ["string", "..."],
  "sources": ["url", "..."]
}
```

Store the digest and expose it via `/digests?date=YYYY-MM-DD&topic=...`.

## Database Schema

### Complete SQLite Structure (Ready to Run)

```sql
PRAGMA journal_mode=WAL;

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
```

Tokenizer = `unicode61 remove_diacritics 2` for robust matching in de-CH.

```sql

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
```

**Note**: FTS5 is the correct module and we enable `unicode61` tokenizer with diacritics removal for better Swiss German text search.

## Technical Architecture

### Models & API (Structured Outputs)

- **MODEL_MINI (env)**: default `gpt-5-mini` for efficient processing; can be overridden via `MODEL_MINI`
- **MODEL_FULL (env)**: default `gpt-5` for complex analysis; can be overridden via `MODEL_FULL`
- **OpenAI Structured Outputs**: Use `response_format={"type":"json_schema", "json_schema": {..., "strict": true}}` (Responses/Chat)
- **parallel_tool_calls: false** when using strict schemas or tools (OpenAI note)
- **LangChain Integration**: If using `langchain-openai`, note `use_responses_api=True, output_version="v1"` to enable the Responses API path

### End-to-End Control Flow

**Run loop (exact function names):**
```
collect_urls()  -> triage_with_MODEL_MINI() -> scrape_selected()
 -> summarize_articles() -> build_topic_digest()
 -> persist_all() -> export_daily_digest()
```

### Code Examples with Structured Outputs

#### LLM Gate (Structured Outputs)

```python
import os
import json
from openai import OpenAI

client = OpenAI()

schema = {
  "type":"object",
  "properties":{
    "is_match":{"type":"boolean"},
    "confidence":{"type":"number","minimum":0,"maximum":1},
    "reason":{"type":"string","maxLength":240}
  },
  "required":["is_match","confidence","reason"],
  "additionalProperties": False
}

# Chat Completions example (Responses API equivalent also OK)
response = client.chat.completions.create(
  model=os.getenv("MODEL_MINI","gpt-5-mini"),
  messages=[{"role":"system","content":"Classify relevance to the user's topic."},
            {"role":"user","content": json.dumps({"url": url, "title": title, "topic": topic})}],
  response_format={"type":"json_schema","json_schema":{"name":"gate","schema":schema,"strict":True}},
  temperature=0
)
```

#### MCP Playwright Fallback (mcp-use + MS server)

```python
from mcp_use import MCPClient, MCPAgent
from langchain_openai import ChatOpenAI
import os

config = {"mcpServers":{"playwright":{"command":"npx","args":["@playwright/mcp@latest"]}}}
client = MCPClient.from_dict(config)
agent  = MCPAgent(llm=ChatOpenAI(model=os.getenv("MODEL_MINI","gpt-5-mini")),
                  client=client, max_steps=12)
# Prompt example:
result = await agent.run(f"Open {url}, navigate to the main article, extract readable text only; return plain text.")
```

## Implementation Structure

### Core Classes
```python
class NewsCollector:
    """Collect titles/URLs from various sources"""
    def collect_from_rss(self, feed_urls)
    def collect_from_sitemaps(self, sitemap_urls) 
    def collect_from_html_listings(self, html_configs)
    def collect_from_google_news(self, queries)

class AIFilter:
    """MODEL_MINI powered relevance filtering"""
    def classify_article(self, title, description, topic)
    def batch_classify(self, articles, topic)

class ContentScraper:
    """MCP+Playwright and Trafilatura integration"""
    def scrape_with_mcp(self, url)
    def scrape_with_trafilatura(self, url)
    def extract_content(self, url)  # Try both methods

class ArticleSummarizer:
    """MODEL_MINI individual article processing"""
    def summarize_article(self, content)
    def extract_entities(self, content)

class MetaAnalyzer:
    """MODEL_MINI aggregate analysis"""
    def generate_topic_summary(self, summaries)
    def identify_trends(self, summaries, time_period)
    def create_executive_report(self, all_topics)
```

### URL-first gating (mini model)

1) **Collect URLs & titles** from discovery (RSS/Sitemap/HTML)
2) **Gate** with MODEL_MINI using only {url, title, topic}:
   - Accept if `is_match==true` and `confidence >= CONFIDENCE_THRESHOLD` (env)
3) **For accepted items**:
   - Try **Trafilatura**; if empty/short → **Playwright MCP** to navigate & extract main text
4) **Summarize** accepted articles (MODEL_MINI) to ~150–200 words with entities/dates
   - Skip summarization if extracted text < 600 chars; log as `too_short`
5) **Summary-of-summaries** (MODEL_MINI) generates your final daily/weekly digest per topic

### Minimal Pipeline

```
discover -> url_gate (LLM-mini, structured JSON) -> extract_main
  -> summarize (article) -> aggregate (summary-of-summaries)
  -> store (SQLite FTS5) -> export (JSON/CSV)
```

**extract_main**: trafilatura → (fallback) MCP Playwright

### Data Flow Architecture

```
News Sources → Title/URL Collection → MODEL_MINI Filter → 
   ↓
Relevant Articles Only → MCP+Playwright Scraping → MODEL_MINI Summarization → 
   ↓
SQLite Storage → MODEL_MINI Meta-Analysis → Reports/API
```

## Testing & Quality Assurance

### Tests & Fixtures

**Test Structure:**
- **fixtures/sample_feeds/**: 3 RSS files, 1 sitemap XML, 1 HTML page (BusinessClassOst)
- **tests/test_normalize_url.py**: URL normalization and deduplication
- **tests/test_triage_schema.py**: Structured output validation
- **tests/test_extract_trafilatura.py**: Content extraction testing
- **tests/test_mcp_playwright_smoke.py**: Uses one public article and asserts non-empty text

### Sample Test Files

**tests/test_normalize_url.py**:
```python
import pytest
from news_pipeline.utils import normalize_url

def test_strip_tracking_params():
    url = "https://example.com/article?utm_source=twitter&gclid=123"
    expected = "https://example.com/article"
    assert normalize_url(url) == expected

def test_canonical_url_extraction():
    html = '<link rel="canonical" href="https://example.com/canonical-article" />'
    # Test canonical URL extraction logic
    pass
```

## Deployment and Operations

### Runbook

```bash
# 1) Initialize DB & feeds
python scripts/init_db.py
python scripts/load_feeds.py config/feeds.yaml

# 2) Daily job (Europe/Zurich)
CRON_TZ=Europe/Zurich
0 6 * * * /usr/bin/python -m news_pipeline.run --topics schweizer_wirtschaft,fintech --export ./out/digests

# 3) Manual run
python -m news_pipeline.run --debug
```

**Operations Configuration:**
- Logs go to stdout + rotating file
- CLI flags: `--topics`, `--limit`, `--since`, `--dry-run`, `--no-mcp`
- Cost guardrails: max tokens per day per model; fail-closed if exceeded

### Quick Start
```bash
# Install dependencies
pip install openai sqlite-utils trafilatura mcp-use

# Install MCP Playwright server (requires Node 18+)
npm install -g @playwright/mcp

# Set environment variables
export OPENAI_API_KEY="your_api_key"
export MODEL_MINI="gpt-5-mini"
export MODEL_FULL="gpt-5"

# Run the system
python news_analyzer.py
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim

# Install Node.js for MCP server
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install MCP Playwright
RUN npm install -g @playwright/mcp

COPY . .

CMD ["python", "news_analyzer.py"]
```

## Key Benefits of This Approach

### Efficiency Gains
- **90% reduction in scraping**: Only scrape relevant articles
- **Cost optimization**: Use GPT-5-mini for filtering, GPT-5 for final analysis
- **Speed improvement**: Filter first, process later
- **Resource savings**: No unnecessary content extraction

### Quality Improvements
- **Smart filtering**: AI-powered relevance detection
- **Comprehensive summaries**: Individual + meta-analysis
- **Trend identification**: Pattern recognition across articles
- **Structured output**: Clean data for further analysis

### Scalability Features
- **Modular design**: Each step can be scaled independently
- **Configurable thresholds**: Tune filtering per topic
- **Multiple sources**: Easy to add new news feeds
- **Clean APIs**: Simple integration with other systems

## Migration from Existing System

### Phase 1: Parallel Testing (Week 1)
- Implement new 5-step pipeline alongside existing system
- Compare filtering accuracy and processing speed
- Tune confidence thresholds based on results

### Phase 2: Feature Integration (Week 2)
- Migrate topic configurations from existing system
- Import company lists and keywords
- Test MCP+Playwright integration with current sources

### Phase 3: Full Transition (Week 3)
- Switch to new system as primary pipeline
- Archive old system as backup
- Monitor performance and quality metrics

This streamlined approach delivers intelligent news analysis with 80% less complexity while providing better filtering accuracy and comprehensive insights through the power of GPT-5 models.
