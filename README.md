# AI-Powered News Analysis System

A streamlined 5-step workflow that leverages GPT-5 models for smart filtering and summarization of Swiss business news, implementing the complete system as described in the analysis plan.

## Overview

This system implements an intelligent news analysis pipeline using GPT-5 models for maximum efficiency with minimal complexity:

### 5-Step Processing Pipeline

1. **URL Collection** - Discover headlines from RSS feeds, news sitemaps, and HTML listings
2. **AI-Powered Filtering** - Use GPT-5-mini to filter relevant articles by title/URL only 
3. **Selective Content Scraping** - Extract full content only from relevant articles using MCP+Playwright and Trafilatura
4. **Individual Article Summarization** - Generate structured summaries with GPT-5-mini
5. **Meta-Summary Generation** - Create executive briefings and topic digests

### Key Benefits

- **90% reduction in scraping** - Only scrape relevant articles
- **Cost optimization** - Use GPT-5-mini for filtering, GPT-5 for final analysis
- **Smart filtering first** - Dramatically reduces processing overhead
- **Comprehensive insights** - Individual + meta-analysis with trend identification

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for MCP Playwright)
- OpenAI API key

### Installation

1. **Clone and setup**:
```bash
git clone <repository-url>
cd news_analysis_2.0
```

2. **Install Python dependencies**:
```bash
pip install -r requirements.txt
```

3. **Install MCP Playwright** (for complex site scraping):
```bash
npx @playwright/mcp@latest --help  # Verify installation
```

4. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your OpenAI API key and settings
```

5. **Initialize database**:
```bash
python scripts/init_db.py
python scripts/load_feeds.py
```

## Configuration

### Environment Variables (.env)

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-...
MODEL_MINI=gpt-5-mini
MODEL_FULL=gpt-5

# Pipeline Settings
CONFIDENCE_THRESHOLD=0.70
MAX_ITEMS_PER_FEED=120
REQUEST_TIMEOUT_SEC=12

# Database
DB_PATH=./news.db
```

### Topics Configuration (config/topics.yaml)

```yaml
topics:
  schweizer_wirtschaft:
    include: ["Schweiz", "Wirtschaft", "Unternehmen", "Finanz"]
    confidence_threshold: 0.70
  fintech:
    include: ["Fintech", "Krypto", "Zahlung", "Digitale Bank"]
    confidence_threshold: 0.75
```

### News Sources (config/feeds.yaml)

Pre-configured with Swiss news sources:
- RSS feeds: NZZ, Blick, regional papers
- Sitemaps: 20min news sitemap
- HTML listings: BusinessClassOst
- Google News RSS: Swiss business topics

## Usage

### Full Pipeline

Run the complete 5-step analysis:

```bash
python news_analyzer.py
```

### Step-by-Step Execution

```bash
# Step 1: Collect URLs
python news_analyzer.py --step collect

# Step 2: AI filtering
python news_analyzer.py --step filter

# Step 3: Content scraping
python news_analyzer.py --step scrape

# Step 4: Summarization
python news_analyzer.py --step summarize

# Step 5: Generate digest
python news_analyzer.py --step digest
```

### Export Options

```bash
# Export daily digest as JSON
python news_analyzer.py --export

# Export as Markdown
python news_analyzer.py --export --format markdown

# Show statistics
python news_analyzer.py --stats
```

### Advanced Usage

```bash
# Run with custom limits
python news_analyzer.py --limit 100

# Debug mode
python news_analyzer.py --debug

# Custom database path
python news_analyzer.py --db-path /path/to/news.db
```

## Architecture

### Core Components

```
news_pipeline/
├── collector.py      # Step 1: URL Collection
├── filter.py         # Step 2: AI Filtering  
├── scraper.py        # Step 3: Content Scraping
├── summarizer.py     # Step 4: Article Summarization
├── analyzer.py       # Step 5: Meta-Analysis
└── utils.py          # Shared utilities
```

### Data Flow

```
RSS/Sitemaps/HTML → URL Collection → AI Filtering (GPT-5-mini)
                                          ↓
Relevant URLs Only → Content Scraping → Article Summarization
                                          ↓  
Individual Summaries → Meta-Analysis → Executive Digest
```

### Database Schema

SQLite with FTS5 full-text search:

- `items` - Article metadata and filtering results
- `articles` - Extracted content  
- `summaries` - Individual article summaries
- `items_fts` - Full-text search index

### MCP Integration

Uses Model Context Protocol (MCP) with Playwright for complex JavaScript-heavy sites:

```python
# MCP configuration in config/mcp.json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

## Deployment

### Development

```bash
# Run full pipeline daily
python news_analyzer.py

# Check results
python news_analyzer.py --stats
```

### Production

#### Docker Deployment

```bash
# Build image
docker build -t news-analyzer .

# Run container
docker run -d \
  -v $(pwd)/data:/app/data \
  -e OPENAI_API_KEY=your_key_here \
  news-analyzer
```

#### Cron Schedule

```bash
# Daily at 6 AM (Europe/Zurich)
0 6 * * * cd /path/to/news_analysis_2.0 && python news_analyzer.py --export --format markdown
```

### Environment Setup

For production deployment:

1. **Set environment variables**
2. **Configure topics** for your specific needs
3. **Adjust feed sources** in `config/feeds.yaml`
4. **Set up log rotation** for `news_pipeline.log`
5. **Schedule regular runs** via cron or task scheduler

## API Integration

### Structured Outputs

All AI interactions use OpenAI's Structured Outputs for reliability:

```python
# Example: Article filtering
response_format={
  "type": "json_schema",
  "json_schema": {
    "name": "triage",
    "schema": schema,
    "strict": True
  }
}
```

### Cost Optimization

- **MODEL_MINI** (gpt-5-mini) for filtering and summarization
- **MODEL_FULL** (gpt-5) for complex analysis when needed
- **Structured outputs** prevent retry costs
- **Smart filtering** reduces processing by 90%

## Output Examples

### Daily Digest (JSON)

```json
{
  "date": "2025-01-15",
  "executive_summary": {
    "headline": "Swiss Fintech Sector Shows Resilience Amid Regulatory Changes",
    "executive_summary": "Key developments in Swiss financial technology...",
    "key_themes": ["Regulatory adaptation", "Digital transformation", "Market consolidation"]
  },
  "topic_digests": {
    "fintech": {
      "headline": "Major Swiss banks accelerate digital transformation",
      "why_it_matters": "Strategic shift towards digital-first services...",
      "bullets": ["UBS launches new digital platform", "Credit Suisse invests in blockchain"],
      "article_count": 12
    }
  }
}
```

### Markdown Export

```markdown
# Swiss Business News Digest - 2025-01-15

## Executive Summary

**Swiss Fintech Sector Shows Resilience Amid Regulatory Changes**

Key developments show Swiss financial technology companies adapting well to new regulatory frameworks while maintaining growth momentum...

### Key Themes
- Regulatory adaptation and compliance
- Accelerated digital transformation
- Market consolidation trends

## Topic Analysis

### Fintech

**Major Swiss banks accelerate digital transformation initiatives**

Strategic shift towards digital-first services drives significant investment in technology infrastructure...

**Key Points:**
- UBS launches comprehensive digital banking platform
- Credit Suisse announces blockchain investment strategy

*Based on 12 articles*
```

## Testing

### Run Tests

```bash
# URL normalization tests
python -m pytest tests/test_normalize_url.py

# Schema validation tests  
python -m pytest tests/test_triage_schema.py

# Content extraction tests
python -m pytest tests/test_extract_trafilatura.py
```

### Test Data

Sample test files in `fixtures/sample_feeds/`:
- RSS feed samples
- Sitemap XML examples
- HTML page samples

## Monitoring

### Logs

- Application logs: `news_pipeline.log`
- Debug level available with `--debug` flag
- Structured logging with timestamps

### Statistics

```bash
python news_analyzer.py --stats
```

Shows:
- Collection success rates
- Filtering efficiency 
- Extraction success rates
- Processing times
- Trending topics

## Troubleshooting

### Common Issues

**MCP Connection Issues**:
```bash
# Verify MCP Playwright installation
npx @playwright/mcp@latest --help
```

**Database Issues**:
```bash
# Reinitialize database
python scripts/init_db.py
```

**API Rate Limits**:
- Check OpenAI usage dashboard
- Adjust `CONFIDENCE_THRESHOLD` to reduce API calls
- Use `--limit` parameter to process fewer articles

### Debug Mode

```bash
python news_analyzer.py --debug
```

Provides detailed logging for troubleshooting.

## Development

### Adding New Sources

1. **Edit `config/feeds.yaml`**
2. **Add RSS, sitemap, or HTML configuration**
3. **Test with specific step**: `python news_analyzer.py --step collect`

### Custom Topics

1. **Edit `config/topics.yaml`** 
2. **Add keywords and confidence threshold**
3. **Test filtering**: `python news_analyzer.py --step filter`

### Extending Pipeline

Each step is modular and can be extended:

- `NewsCollector` - Add new source types
- `AIFilter` - Customize filtering logic
- `ContentScraper` - Add extraction methods
- `ArticleSummarizer` - Modify summary format
- `MetaAnalyzer` - Add analysis features

## License

This project implements the AI News Analysis Plan with focus on Swiss business news monitoring and executive briefing generation.

---

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review logs in debug mode
3. Verify configuration files
4. Check OpenAI API status and quotas
