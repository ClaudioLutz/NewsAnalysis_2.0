# Confidence-Based Article Selection Implementation

## Overview
Successfully implemented a confidence-based selection system that limits the number of articles processed through expensive scraping and summarization stages based on their relevance confidence scores.

## Key Components Implemented

### 1. Database Schema Enhancement
- **New Columns Added to `items` table**:
  - `pipeline_stage`: Tracks current processing stage (`collected`, `matched`, `selected`, `scraped`, `summarized`)
  - `pipeline_run_id`: Unique identifier for each pipeline run
  - `selected_for_processing`: Boolean flag for selected articles
  - `selection_rank`: Ranking by confidence (1 = highest confidence)
  - `last_error`: Error tracking for debugging

- **New Indexes**:
  - `idx_items_pipeline`: For efficient pipeline stage queries
  - `idx_items_selection`: For confidence-based selection queries

### 2. Pipeline Configuration (`config/pipeline_config.yaml`)
```yaml
pipeline:
  filtering:
    confidence_threshold: 0.70  # Minimum confidence to consider
    max_articles_to_process: 35  # Maximum articles to scrape/summarize
```

### 3. Enhanced AIFilter (`news_pipeline/filter.py`)
- **New Methods**:
  - `filter_for_run()`: Main entry point for pipeline runs
  - `_select_top_articles()`: Selects top N articles above threshold
  - Enhanced `save_classification()` to track pipeline stages

- **Selection Logic**:
  1. Run AI classification on all collected articles
  2. Filter by confidence threshold (default: 0.70)
  3. Select top N articles (default: 35)
  4. Mark selected articles with rank

### 4. Updated Scraper (`news_pipeline/scraper.py`)
- **New Methods**:
  - `scrape_for_run()`: Scrapes only selected articles
  - Modified `get_articles_to_scrape()` to filter by selection

- **Key Changes**:
  - Only processes articles with `selected_for_processing = 1`
  - Maintains selection rank order
  - Updates pipeline stage to 'scraped'

### 5. Updated Summarizer (`news_pipeline/summarizer.py`)
- **New Methods**:
  - `summarize_for_run()`: Summarizes only scraped selected articles
  - Modified `get_articles_to_summarize()` to maintain selection order

- **Key Changes**:
  - Only processes scraped selected articles
  - Maintains selection rank order
  - Updates pipeline stage to 'summarized'

### 6. Enhanced Pipeline Orchestrator (`news_analyzer.py`)
- **New CLI Arguments**:
  - `--confidence-threshold`: Override minimum confidence (default: 0.70)
  - `--max-articles`: Override maximum articles to process (default: 35)

- **New Features**:
  - `get_enhanced_pipeline_stats()`: Detailed funnel statistics
  - `print_selection_report()`: Visual selection report
  - Runtime config override capability

### 7. Selection Report
The pipeline now generates a detailed selection report showing:
- Top 10 selected articles with confidence scores
- Articles just below threshold
- Pipeline funnel statistics
- Actual threshold used

## Usage Examples

### Basic Usage (Default Settings)
```bash
python news_analyzer.py
```
- Uses confidence threshold: 0.70
- Processes maximum 35 articles

### Custom Threshold
```bash
python news_analyzer.py --confidence-threshold 0.75 --max-articles 20
```
- Only processes articles with confidence ≥ 0.75
- Limits to top 20 articles

### View Selection Report
```bash
python news_analyzer.py --stats
```
Shows current pipeline statistics and article counts

## Expected Pipeline Behavior

### Before Implementation
```
Collected: 1000 articles
  ↓
Filtered: 200 matched (all matched articles processed)
  ↓
Scraped: 200 articles (expensive)
  ↓
Summarized: 180 articles (expensive)
```

### After Implementation
```
Collected: 1000 articles
  ↓
Filtered: 200 matched (20% match rate)
  ↓
Selected: 35 articles (confidence ≥ 0.70, top N by confidence)
  ↓
Scraped: 33 articles (2 failed)
  ↓
Summarized: 30 articles (3 had insufficient content)
```

## Benefits
1. **Cost Reduction**: Processes only the most relevant articles
2. **Quality Focus**: Prioritizes high-confidence matches
3. **Configurable**: Runtime control over thresholds and limits
4. **Transparent**: Clear reporting of selection criteria
5. **Consistent**: Maintains article order by confidence throughout pipeline

## Sample Selection Report Output
```
======================================================================
ARTICLE SELECTION REPORT
======================================================================

📈 Top 10 Selected Articles:
----------------------------------------------------------------------
  # 1 [85.3%] Creditreform warnt vor Zahlungsausfällen...
      Source: handelszeitung.ch
  # 2 [82.1%] Neue Insolvenzstatistik zeigt Anstieg...
      Source: nzz.ch
  [...]

⚠️ Not Selected (below threshold or outside top N):
----------------------------------------------------------------------
  [68.5%] Wirtschaftslage in der Schweiz... (finews.ch)
  [67.2%] Börsenupdate: SMI schliesst höher... (cash.ch)

📊 Pipeline Funnel:
----------------------------------------------------------------------
  Collected:  1000 articles
  ↓ Filtered
  Matched:     200 articles (20.0%)
  ↓ Selected (confidence-based)
  Selected:     35 articles (17.5%)
  ↓ Scraped
  Scraped:      33 articles
  ↓ Summarized
  Summarized:   30 articles

  Actual confidence threshold used: 71.2%
======================================================================
```

## Testing
The implementation has been successfully tested with:
- `python news_analyzer.py --help`: Shows new CLI arguments
- `python news_analyzer.py --stats`: Displays pipeline statistics

## Migration Script
Run the migration to add selection tracking columns:
```bash
python scripts/migrate_selection_tracking.py
```

## Future Enhancements
1. Topic-specific thresholds (already supported in config)
2. Dynamic threshold adjustment based on article quality
3. Historical selection performance tracking
4. A/B testing different threshold values
5. Machine learning-based threshold optimization
