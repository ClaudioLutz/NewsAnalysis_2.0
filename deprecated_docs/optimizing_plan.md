# News Pipeline Optimization Plan
## From 100+ Irrelevant Articles to 5-10 Actionable Insights

**Target**: Optimize news pipeline for Creditreform Schweiz Product Manager/Data Analyst role
**Current Problem**: 35+ minute runtime, 103 irrelevant matches, no resume capability
**Goal**: 2-3 minute pipeline delivering 5-10 highly relevant, deduplicated insights

---

## Phase 1: Database Schema Enhancements
**Duration**: 30 minutes
**Purpose**: Add resume capability and better article management

### Step 1.1: Add Pipeline State Tracking Table
- Create `pipeline_state` table with columns:
  - `id` (primary key)
  - `run_id` (UUID for each pipeline run)
  - `step_name` (collection, filtering, scraping, etc.)
  - `status` (pending, running, completed, failed)
  - `started_at`, `completed_at`
  - `metadata` (JSON for step-specific data)
  - `article_count`, `match_count`

### Step 1.2: Add Article Clustering Table
- Create `article_clusters` table with columns:
  - `id` (primary key)
  - `cluster_id` (generated hash)
  - `article_id` (foreign key to items)
  - `is_primary` (boolean - best article in cluster)
  - `similarity_score` (float)
  - `created_at`

### Step 1.3: Enhance Items Table
- Add columns to existing `items` table:
  - `priority_score` (float - overall relevance score)
  - `processing_stage` (enum: collected, filtered, scraped, summarized)
  - `cluster_id` (link to article_clusters)
  - `duplicate_of` (self-reference for exact duplicates)

---

## Phase 2: Create Creditreform-Focused Topic Configuration
**Duration**: 45 minutes
**Purpose**: Replace broad topics with laser-focused Creditreform relevance

### Step 2.1: Design New Topic Structure
- Create new topic: `creditreform_insights`
- Remove or disable broad topics: `schweizer_wirtschaft`, `fintech`
- Set aggressive confidence threshold: 0.80 (vs current 0.70)

### Step 2.2: Define Creditreform-Specific Context
- **Core Focus Areas**:
  - Credit risk assessment and rating changes
  - Swiss corporate insolvencies and bankruptcies
  - Regulatory changes affecting credit (Basel III, FINMA)
  - B2B payment behavior and default trends
  - Data protection compliance (nDSG) impact on credit data
  - Trade credit insurance developments
  - SME financing and credit availability

### Step 2.3: Create Enhanced Topic Schema
```yaml
creditreform_insights:
  description: "Articles directly relevant to Creditreform's B2B credit risk, rating, and data business in Switzerland"
  
  focus_areas:
    credit_risk:
      - Corporate rating changes (upgrades/downgrades)
      - Default probability models and updates
      - Industry-specific risk trends
    
    insolvency_bankruptcy:
      - Swiss company insolvencies and procedures
      - Bankruptcy statistics and trends
      - Recovery rates and creditor impacts
    
    regulatory_compliance:
      - Basel III implementation and Swiss finish
      - FINMA guidelines affecting credit business
      - nDSG impact on data sharing and processing
    
    payment_behavior:
      - B2B payment delay statistics
      - Industry payment trends
      - Credit terms and collection effectiveness
    
    market_intelligence:
      - Credit insurance market changes
      - Competitor activities (Intrum, D&B, etc.)
      - Technology affecting credit assessment
  
  confidence_threshold: 0.80
  max_articles_per_run: 15
  priority_sources: ["admin.ch", "finma.ch", "snb.ch", "seco.admin.ch"]
```

---

## Phase 3: Implement Single-Pass AI Classification
**Duration**: 60 minutes
**Purpose**: Replace multi-topic processing with focused single classification

### Step 3.1: Refactor AIFilter Class
- Replace `filter_all_topics()` with `filter_for_creditreform()`
- Implement priority-based article processing:
  1. Process newest articles first
  2. Process articles from priority sources first
  3. Skip articles older than 7 days unless high-priority sources

### Step 3.2: Create Advanced Classification Prompt
- Design context-rich system prompt including:
  - Creditreform business model explanation
  - Swiss market context
  - Specific use cases for credit risk professionals
  - Examples of relevant vs irrelevant articles

### Step 3.3: Implement Smart Batching
- Process articles in batches of 10-20
- Early termination once 15 high-confidence matches found
- Skip remaining articles if enough quality matches obtained

### Step 3.4: Add Priority Scoring Algorithm
```python
# Priority calculation factors:
# - Source credibility (government, financial authorities = high)
# - Content keywords match strength
# - Article freshness (today = 1.0, yesterday = 0.9, etc.)
# - URL quality indicators
```

---

## Phase 4: Implement Semantic Deduplication System
**Duration**: 90 minutes
**Purpose**: Eliminate duplicate stories from multiple sources

### Step 4.1: Create Content Similarity Engine
- Implement title-based similarity using sentence transformers
- Calculate content fingerprints for articles
- Group similar articles (threshold: 0.75+ similarity)

### Step 4.2: Design Cluster Selection Logic
- Within each cluster, select primary article based on:
  1. Source authority (government > financial news > general news)
  2. Content completeness (longer, more detailed articles)
  3. Publication timing (first to report gets priority)
  4. URL quality (direct article vs aggregated feed)

### Step 4.3: Implement Cluster Management
- Store clustering decisions in database
- Allow manual override of cluster assignments
- Provide "related articles" metadata for context

---

## Phase 5: Build Resume/Checkpoint System
**Duration**: 75 minutes
**Purpose**: Allow pipeline interruption and restart at any point

### Step 5.1: Create Pipeline State Manager
- Track current run with unique UUID
- Save progress after each major operation:
  - URL collection completed
  - X articles processed for filtering
  - Y articles scraped
  - Z articles summarized

### Step 5.2: Implement Resume Logic
- Check for incomplete runs on startup
- Present user with resume options:
  - Continue from last checkpoint
  - Restart current step
  - Start completely fresh

### Step 5.3: Add Graceful Interruption Handling
- Catch CTRL+C and save current state
- Allow "pause and resume later" functionality
- Clean up resources properly on interruption

---

## Phase 6: Create Fast-Track Mode
**Duration**: 45 minutes
**Purpose**: Deliver quick daily insights in under 3 minutes

### Step 6.1: Design "Express Mode" Pipeline
- Skip scraping step - work with titles and snippets only
- Limit to 10 articles maximum
- Focus on today's articles only
- Use cached results when available

### Step 6.2: Implement Quick Classification
- Batch process articles in parallel
- Use lightweight summarization
- Generate executive summary only

### Step 6.3: Create Simple Output Format
```json
{
  "date": "2025-09-17",
  "mode": "express",
  "runtime": "2.3 minutes",
  "top_insights": [
    {
      "headline": "Brief insight headline",
      "relevance": "Why this matters for Creditreform",
      "source": "authority.ch",
      "confidence": 0.87
    }
  ]
}
```

---

## Phase 7: Optimize Article Collection Strategy
**Duration**: 60 minutes
**Purpose**: Reduce initial article volume while improving quality

### Step 7.1: Implement Source Prioritization
- Rank sources by relevance to Creditreform:
  1. Tier 1: Government/regulatory (admin.ch, finma.ch, snb.ch)
  2. Tier 2: Financial news (handelszeitung.ch, finews.ch)
  3. Tier 3: General news with business focus
  4. Tier 4: Aggregators and low-quality sources

### Step 7.2: Add Time-Based Collection Limits
- Collect from Tier 1 sources: all articles from last 7 days
- Collect from Tier 2 sources: all articles from last 3 days
- Collect from Tier 3 sources: all articles from last 24 hours
- Skip Tier 4 sources unless specifically requested

### Step 7.3: Implement Smart RSS Processing
- Parse RSS feeds with quality filters:
  - Skip entertainment, sports, lifestyle categories
  - Focus on business, finance, economy categories
  - Parse category tags and metadata when available

---

## Phase 8: Enhanced Configuration Management
**Duration**: 30 minutes
**Purpose**: Make pipeline behavior easily configurable

### Step 8.1: Create Enhanced Configuration Schema
```yaml
pipeline:
  mode: "standard" # or "express"
  max_runtime_minutes: 5
  max_articles_per_topic: 15
  confidence_threshold: 0.80
  enable_deduplication: true
  enable_checkpoints: true
  
creditreform:
  role_context: "product_manager" # or "data_analyst", "risk_manager"
  focus_timeframe_days: 7
  priority_sources: ["admin.ch", "finma.ch", "snb.ch"]
  excluded_categories: ["sport", "lifestyle", "entertainment"]
```

### Step 8.2: Add Runtime Configuration Options
- Command-line flags for common scenarios:
  - `--express` for quick daily insights
  - `--deep` for comprehensive weekly analysis
  - `--resume [run-id]` to continue interrupted run
  - `--sources [tier-level]` to limit source tiers

---

## Phase 9: Quality Assurance and Testing
**Duration**: 120 minutes
**Purpose**: Ensure reliability and accuracy

### Step 9.1: Create Test Data Sets
- Curate 50 sample articles with known relevance scores
- Include edge cases and tricky examples
- Test with articles from different time periods

### Step 9.2: Implement Validation Pipeline
- Compare old vs new classification results
- Measure precision/recall for Creditreform relevance
- Test resume functionality with simulated interruptions

### Step 9.3: Performance Benchmarking
- Measure end-to-end runtime for different scenarios
- Monitor resource usage (API calls, memory, disk)
- Validate that results are consistent across runs

---

## Phase 10: Documentation and Deployment
**Duration**: 60 minutes
**Purpose**: Document changes and create usage guides

### Step 10.1: Update Documentation
- Document new command-line options
- Create troubleshooting guide for common issues
- Update configuration file documentation

### Step 10.2: Create Usage Examples
- "Daily morning briefing in 2 minutes"
- "Weekly deep dive analysis"
- "Recovering from interrupted runs"
- "Custom topic configuration for different roles"

### Step 10.3: Deployment Preparation
- Update requirements.txt if new dependencies added
- Test in clean environment
- Create migration script for existing databases

---

## Implementation Priority Order

**Week 1 (Essential functionality)**:
1. Phase 2: New topic configuration 
2. Phase 3: Single-pass classification
3. Phase 5: Resume/checkpoint system

**Week 2 (Quality improvements)**:
4. Phase 4: Semantic deduplication
5. Phase 6: Fast-track mode
6. Phase 1: Database enhancements

**Week 3 (Optimization)**:
7. Phase 7: Collection strategy
8. Phase 8: Configuration management
9. Phase 9: Testing and QA

**Week 4 (Polish)**:
10. Phase 10: Documentation and deployment

---

## Success Metrics

**Performance Targets**:
- Express mode: < 3 minutes end-to-end
- Standard mode: < 8 minutes end-to-end  
- Resume capability: < 30 seconds to restart

**Quality Targets**:
- 5-15 articles maximum per run
- 90%+ relevance rate for Creditreform role
- < 20% duplicate content in final results
- 95%+ successful resume operations

**User Experience**:
- Clear progress indicators throughout
- Meaningful error messages
- Simple configuration options
- Actionable output format
