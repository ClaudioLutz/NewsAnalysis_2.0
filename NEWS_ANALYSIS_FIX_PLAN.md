# News Analysis System - Critical Fix Plan

## Issues Identified

### 1. **Performance Crisis - 3+ Hours Runtime**
- Processing 536 articles × 3 topics = 1,608 individual AI calls
- Each API call takes ~5-6 seconds = 2-3 hours total
- **NO database deduplication** - same links processed repeatedly
- Extremely inefficient sequential processing

### 2. **Unicode Encoding Errors**
- Emoji characters (🚀, ✅, 📊, 🎯, ⭐) causing Windows cp1252 crashes
- Box-drawing characters (─) failing in Windows terminal
- All logging breaks due to charset issues

### 3. **Duplicate Execution**
- System appears to run twice based on log output
- No proper run state management
- Pipeline restarts/loops without clear cause

### 4. **Wrong Topic Focus**
- Current topics too generic for Creditreform Schweiz
- Missing **bonität/rating** specific keywords
- Not optimized for B2B credit analysis use case

## Critical Fixes Required

### Phase 1: Emergency Stabilization (Day 1)

#### Fix 1.1: Remove All Unicode Characters
**Files to modify:**
- `news_pipeline/utils.py` - Replace all emojis and Unicode chars
- `news_pipeline/filter.py` - Remove emoji logging
- All logging functions - ASCII only

**Changes:**
```python
# Before: 
logger.info(f"🚀 Starting pipeline...")
logger.info(f"{'─'*60}")

# After:
logger.info("Starting pipeline...")  
logger.info("-" * 60)
```

#### Fix 1.2: Add Database Link Deduplication
**New table:** `processed_links`
```sql
CREATE TABLE processed_links (
    url_hash TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    processed_at TEXT DEFAULT (datetime('now')),
    topic TEXT NOT NULL,
    result TEXT NOT NULL -- 'matched', 'rejected', 'error'
);
```

#### Fix 1.3: Skip Already Processed URLs
**Logic:**
- Before AI classification, check `processed_links` table
- Skip if URL already classified for this topic
- Only process genuinely new links

### Phase 2: Performance Optimization (Day 1)

#### Fix 2.1: Batch API Calls
**Current:** 1 API call per article per topic
**New:** Batch multiple articles in single API call
- Process 5-10 articles per API call
- Reduce total API calls by 80-90%

#### Fix 2.2: Smart Topic Filtering
**Priority queue approach:**
1. **bonitaet_b2b_ch** (highest priority for Creditreform)
2. **schweizer_wirtschaft** (medium priority)  
3. **fintech** (lowest priority)

#### Fix 2.3: Early Exit Strategy
- Stop processing if sufficient matches found per topic
- Configurable limits: max 50 matches per topic per run

### Phase 3: Creditreform-Specific Configuration (Day 1)

#### Fix 3.1: New Topic Configuration
**`config/topics.yaml`:**
```yaml
topics:
  bonitaet_b2b_ch:
    include: 
      - "Bonität"
      - "Bonitätsprüfung" 
      - "Bonitätsauskunft"
      - "Firmenrating"
      - "Ratingagentur"
      - "Creditreform"
      - "Kreditwürdigkeit"
      - "Zahlungsausfall"
      - "Insolvenz"
      - "Firmenpleite"
      - "Konkurs"
      - "Rating"
      - "Schuldnerverzeichnis"
    confidence_threshold: 0.7
    max_matches_per_run: 25
    
  schweizer_wirtschaft:
    include: ["Schweiz", "Wirtschaft", "Unternehmen", "KMU", "Finanz"]
    confidence_threshold: 0.75
    max_matches_per_run: 15
    
  fintech:
    include: ["Fintech", "Krypto", "Zahlung", "Digitale Bank"]
    confidence_threshold: 0.8
    max_matches_per_run: 10
```

#### Fix 3.2: Creditreform-Focused News Sources
**Add to `config/feeds.yaml`:**
```yaml
rss:
  # Existing sources...
  handelszeitung: ["https://www.handelszeitung.ch/rss.xml"]
  bilanz: ["https://www.bilanz.ch/rss.xml"] 
  kmu_portal: ["https://www.kmu.admin.ch/kmu/de/home/_jcr_content.rss.xml"]
  
google_news_rss:
  # Existing queries...
  bonität: "https://news.google.com/rss/search?q=bonität+schweiz&hl=de-CH&gl=CH&ceid=CH:de"
  rating: "https://news.google.com/rss/search?q=rating+unternehmen+schweiz&hl=de-CH&gl=CH&ceid=CH:de"  
  insolvenz: "https://news.google.com/rss/search?q=insolvenz+schweiz&hl=de-CH&gl=CH&ceid=CH:de"
```

### Phase 4: Execution Fixes (Day 1)

#### Fix 4.1: Add Run State Management
**New table:** `pipeline_runs`
```sql
CREATE TABLE pipeline_runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    status TEXT CHECK(status IN ('running', 'completed', 'failed')),
    step TEXT,
    articles_processed INTEGER DEFAULT 0
);
```

#### Fix 4.2: Prevent Duplicate Runs
- Check for active runs before starting
- Lock mechanism using database
- Clear status on completion

#### Fix 4.3: Add Progress Persistence  
- Save progress after every 10 articles
- Resume from last checkpoint on restart
- No starting from scratch

## Implementation Priority

### **IMMEDIATE (Day 1 Morning)**
1. ✅ Remove all Unicode/emoji characters → Fix encoding errors
2. ✅ Add processed_links table → Prevent duplicate processing  
3. ✅ Update topics.yaml → Focus on Creditreform needs

### **URGENT (Day 1 Afternoon)**  
4. ✅ Implement batch API calls → Reduce runtime from 3h to 20-30min
5. ✅ Add run state management → Prevent duplicate execution
6. ✅ Add smart limits → Stop at reasonable match count

### **HIGH PRIORITY (Day 2)**
7. ✅ Add Creditreform-specific news sources
8. ✅ Implement progress checkpoints
9. ✅ Add performance monitoring

## Expected Results

### Performance Improvements
- **Runtime:** 3 hours → 20-30 minutes (90% reduction)
- **API Calls:** 1,608 calls → 150-200 calls (88% reduction)  
- **Duplicate Processing:** Eliminated completely
- **Unicode Errors:** Eliminated completely

### Quality Improvements  
- **Creditreform Relevance:** Dramatically improved with bonität focus
- **No Missed Articles:** Database tracks all processed URLs
- **Reliable Execution:** No more crashes or duplicate runs

## Files to Modify

### Critical Files
1. `news_pipeline/utils.py` - Remove Unicode, improve logging
2. `news_pipeline/filter.py` - Add dedup logic, batch processing
3. `config/topics.yaml` - Creditreform-specific topics
4. `scripts/init_db.py` - Add new tables
5. `news_analyzer.py` - Add run state management

### Database Schema Updates
- `processed_links` table for deduplication
- `pipeline_runs` table for state management
- Indexes for performance

## Rollback Plan

1. Keep current code as backup branch
2. Test new version with `--dry-run` flag first
3. Gradual rollout with monitoring
4. Database migration with rollback scripts

## Success Metrics

- [ ] Runtime under 30 minutes 
- [ ] Zero Unicode encoding errors
- [ ] Zero duplicate URL processing
- [ ] At least 20 bonität-related articles found per run
- [ ] Consistent execution without restarts

This plan addresses all critical issues while maintaining system functionality and dramatically improving performance for Creditreform Schweiz use case.
