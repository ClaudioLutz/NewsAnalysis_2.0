# Story Clustering Implementation - Brainstorming Session Results

**Session Date:** 2025-10-03  
**Topic:** Implementation approaches for story clustering logic in NewsAnalysis_2.0  
**Goal:** Transform output from topic-aggregated summaries to individual article-link-summary pairs with intelligent topic deduplication  
**Approach:** Hybrid brainstorming combining problem decomposition, technical architecture, workflow mapping, and comparative analysis

## Executive Summary

**Session Scope:**
- Focus on implementation approaches for semantic story clustering
- Preserve existing sophisticated filtering logic
- Enable multiple daily runs with topic-level deduplication
- Transform output format while maintaining incremental processing capabilities

**Current System Context:**
- Sophisticated 5-step pipeline with incremental digest generation
- Entity extraction already available from existing summaries
- digest_state table tracks processed articles per topic/date
- Template-based output generation using Jinja2

---

## Phase 1: Problem Decomposition

### Core Challenge Analysis
**Fundamental Question:** "What makes two articles about the same story?"

**Context:** Multiple Swiss news sources (NZZ, Blick, Handelszeitung, etc.) covering same events
**Goal:** Identify reliable clustering signals for Swiss business news ecosystem

### User Input - Story Similarity Patterns
**Key Insight:** Deduplication logic already exists and works effectively using GPT-5-mini model that identifies duplicates from titles/links.

**The Real Challenge:** Cross-run deduplication within the same day
- Want to run pipeline multiple times per day (morning, afternoon, etc.)
- If a topic was covered in the morning report, it should NOT appear in the afternoon report
- Need to track "what topics have already been reported today" across multiple daily runs
- This is different from cross-source deduplication (which already works)

**Business Logic Requirement:** 
- Day-level topic persistence across multiple pipeline executions
- Same-day topic exclusion logic
- Maintain topic uniqueness for entire day, reset at midnight

---

## Phase 2: Technical Architecture Exploration

### Challenge Refinement
**The Real Problem:** Not story clustering, but **topic persistence across same-day runs**

**Current State:**
- Cross-source deduplication: ✅ Works (GPT-5-mini on titles/links)  
- Incremental daily updates: ✅ Works (digest_state table)
- Output format: ❌ Needs change (topic-aggregated → individual articles)
- Cross-run topic exclusion: ❌ New requirement

### Architecture Options for Topic Persistence

#### Option 1: Topic Signature Tracking
**Concept:** Create unique signatures for each topic/story and track what's been reported
**Implementation Approaches:**

### ✅ User's Preferred Approach: Two-Step GPT Deduplication

**Step 1: Cross-Source Deduplication** ✅ Already implemented
- GPT-5-mini compares titles/links to identify duplicate articles from different sources
- Works effectively for same story across multiple news sources

**Step 2: Cross-Run Topic Deduplication** ❌ Needs implementation  
- GPT-5-mini compares new articles against "already covered topics from today"
- Question: "Is this article about a topic that was already covered in a previous run today?"
- Leverages same proven GPT approach but different comparison logic

### Implementation Architecture for Step 2

#### Approach A: Compare Against Previous Article Summaries
**Data Flow:**
1. New articles come in (afternoon run)
2. Retrieve all article summaries from morning run(s) 
3.0 GPT-5-mini deduplicate Articles from this run
3.1 GPT-5-mini comparison: "Is new article about same topic as any of these previous summaries?"
4. Filter out matches, proceed with remaining articles

#### Approach B: Compare Against Previous Topic Digest Headlines  
**Data Flow:**
1. New articles come in (afternoon run)
2. Retrieve topic digest headlines from morning run(s)
3. GPT-5-mini comparison: "Is new article about same topic as these previous headlines?"
4. More efficient (fewer tokens) but potentially less accurate

#### Approach C: Hybrid - Previous Summaries + Topic Signatures
**Data Flow:**
1. Store simplified "topic signatures" from morning run
2. GPT comparison against both individual summaries AND topic themes
3. Best accuracy with manageable token usage

### ✅ Selected Architecture: Approach A - Full Summary Comparison

**User Decision:** Approach A - Compare against all previous article summaries from today
**Rationale:** Maximum accuracy, leverage existing rich summary data
**Trade-off:** Accept higher token usage for better precision

**Pipeline Integration Point:** 
After existing deduplication step (Step 1) but requires summaries to exist
**Proposed Flow:**
1. NewsCollector (includes existing cross-source deduplication ✅)
2. AIFilter 
3. ContentScraper
4. ArticleSummarizer
5. **NEW: Cross-Run Topic Deduplication** (Step 4.5)
6. MetaAnalyzer (modified for individual article output)

### Detailed Implementation for Step 4.5 - CORRECTED FLOW

**Input:** Newly summarized articles from current run
**Process:** 
1. New articles come in (afternoon run)
2. Retrieve all article summaries from morning run(s)
3.0 GPT-5-mini deduplicate articles from THIS run - **✅ Already implemented**
    - Cross-source deduplication within current run
    - Keep the article with the most words when duplicates found
3.1 GPT-5-mini comparison: "Is new article about same topic as any of these previous summaries?" 
    - Compare against previous runs' summaries from today
    - **Remove articles** that match topics already covered
4. Filter out topic matches, proceed with remaining articles
5. Pass remaining "unique topic" articles to MetaAnalyzer

**Database Schema Extension:**
```sql
-- Track cross-run topic deduplication
ALTER TABLE summaries ADD COLUMN topic_already_covered BOOLEAN DEFAULT FALSE;
ALTER TABLE summaries ADD COLUMN matched_previous_summary_id INTEGER;
```

---

## Phase 3: User Experience Validation

### Daily Workflow Scenarios

#### Scenario A: Morning Run (8:00 AM)
- **Input:** 15-20 new articles from overnight/early morning
- **Process:** Normal pipeline flow (no previous summaries to compare against)
- **Output:** Management Summary + 12-15 individual article-link-summary pairs
- **Result:** Full report with all unique topics

#### Scenario B: Afternoon Run (2:00 PM)
- **Input:** 10-15 new articles from midday sources
- **Cross-Run Check:** Compare against morning's 12-15 summaries
- **Filtering:** Maybe 5-7 articles filtered out as "topic already covered"
- **Output:** Management Summary + 5-8 NEW individual article-link-summary pairs
- **Result:** Supplemental report with only new topics

#### Scenario C: Evening Run (6:00 PM)
- **Input:** 8-12 new articles from late afternoon
- **Cross-Run Check:** Compare against ALL summaries from morning + afternoon runs  
- **Filtering:** Maybe 3-4 articles filtered out
- **Output:** Management Summary + 4-8 NEW individual article-link-summary pairs

### Output Format Evolution

**Current Format:**
```
Management Summary
├── Topic: Swiss Banking Regulations
│   └── [Aggregated summary from 3 articles]
└── Topic: Credit Risk Updates  
    └── [Aggregated summary from 5 articles]
```

**New Format:**
```
Management Summary (Overview of 8 unique topics found)
├── [Swiss Bank UBS CEO Change] → Link + Individual Summary
├── [FINMA New Capital Requirements] → Link + Individual Summary  
├── [Creditreform Rating Methodology Update] → Link + Individual Summary
└── [Swiss SME Credit Default Analysis] → Link + Individual Summary
```

---

## Phase 4: Best Practice Integration

### Reference Implementations Analysis

#### Google News Approach
- **Method:** Content similarity scoring + time-based clustering
- **Pros:** Handles high volume, good at breaking news
- **Cons:** Less semantic understanding, more false positives
- **Applicability:** Your GPT approach is superior for semantic accuracy

#### Apple News Approach  
- **Method:** Editorial curation + algorithmic filtering
- **Pros:** High quality, human oversight
- **Cons:** Not scalable, requires manual intervention
- **Applicability:** Your automated approach better for business intelligence

#### Reuters/Bloomberg Terminal Approach
- **Method:** Topic tagging + entity matching
- **Pros:** Business-focused, entity-centric
- **Cons:** Requires extensive entity databases
- **Applicability:** Similar philosophy but your GPT approach more flexible

### Performance Optimization Strategies

#### Token Management
- **Batch Comparison:** Compare new article against multiple previous summaries in single GPT call
- **Summary Truncation:** Use only key points from previous summaries (first 200 chars)
- **Smart Caching:** Cache topic comparison results to avoid re-processing

#### Database Optimization
- **Indexing:** Add indexes on date columns for fast "today's summaries" queries
- **Archiving:** Archive old summaries to separate table after 7 days
- **Query Optimization:** Use prepared statements for repeated queries

---

## Synthesis & Action Plan

### Core Implementation Requirements

#### 1. New Cross-Run Deduplication Module
**File:** `news_pipeline/cross_run_deduplicator.py`
**Key Methods:**
- `get_todays_previous_summaries(date)` 
- `compare_against_previous_topics(new_summary, previous_summaries)`
- `filter_already_covered_topics(new_articles)`

#### 2. Database Schema Updates
**Migration Script:** `scripts/add_cross_run_deduplication_schema.py`
**Changes:**
- Add topic tracking columns to summaries table
- Create indexes for fast date-based queries
- Add audit trail for filtered articles

#### 3. Modified Template for Individual Articles
**File:** `templates/individual_articles_digest.md.j2`
**Structure:**
- Management summary (topic overview)
- Individual article-link-summary pairs
- Metadata about filtering (X topics already covered today)

#### 4. Enhanced MetaAnalyzer Integration
**File:** `news_pipeline/enhanced_analyzer.py`
**Modifications:**
- Integrate cross-run deduplication before digest generation
- Modify output structure for individual articles
- Update incremental digest logic

### Priority Implementation Order

#### Phase 1: Core Deduplication Logic (Week 1)
1. ✅ Create cross_run_deduplicator.py module
2. ✅ Implement GPT-based topic comparison logic
3. ✅ Add database schema changes
4. ✅ Unit tests for deduplication logic

#### Phase 2: Pipeline Integration (Week 2)
1. ✅ Integrate into existing pipeline after Step 4
2. ✅ Modify EnhancedMetaAnalyzer for individual output
3. ✅ Update template system
4. ✅ End-to-end testing with multiple daily runs

#### Phase 3: Performance & Polish (Week 3)
1. ✅ Optimize token usage and batch processing
2. ✅ Add monitoring and metrics
3. ✅ Create migration script for existing data
4. ✅ Documentation and deployment guide

### Success Criteria

#### Functional Requirements
- ✅ Multiple daily runs produce non-overlapping topics
- ✅ Output format: Management Summary + Individual Articles
- ✅ Sophisticated filtering logic preserved
- ✅ Performance acceptable (< 15 minutes per run)

#### Quality Metrics
- **Topic Deduplication Accuracy:** >90% correct topic exclusions
- **False Positive Rate:** <5% unique topics incorrectly filtered
- **Performance Target:** Additional processing time <2 minutes
- **Token Efficiency:** <50% increase in OpenAI API costs

---

*Session completed with comprehensive technical architecture and implementation roadmap*
