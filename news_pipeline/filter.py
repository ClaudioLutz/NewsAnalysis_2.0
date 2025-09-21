"""
AIFilter - Step 2: AI-Powered Filtering (Title/URL Only)

Single-stage pre-filter using GPT-5-mini for relevance detection.
"""

import os
import json
import sqlite3
import yaml
from typing import List, Dict, Any, Tuple, Optional
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

from openai import OpenAI
from .utils import (
    setup_logging, log_progress, log_step_start, log_step_complete, 
    log_error_with_context, format_number, format_rate
)
import time
from .utils import url_hash


class AIFilter:
    """AI-powered relevance filtering using MODEL_NANO."""
    
    def __init__(self, db_path: str, topics_config_path: str = "config/topics.yaml", 
                 pipeline_config_path: str = "config/pipeline_config.yaml"):
        self.db_path = db_path
        self.client = OpenAI()
        self.model = os.getenv("MODEL_NANO", "gpt-5-nano")
        self.confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))
        
        self.logger = logging.getLogger(__name__)
        
        # Load topics configuration
        with open(topics_config_path, 'r', encoding='utf-8') as f:
            self.topics_config = yaml.safe_load(f)
        
        # Load triage schema
        with open("schemas/triage.schema.json", 'r', encoding='utf-8') as f:
            self.triage_schema = json.load(f)
            
        # Load pipeline configuration
        try:
            with open(pipeline_config_path, 'r', encoding='utf-8') as f:
                self.pipeline_config = yaml.safe_load(f)
        except FileNotFoundError:
            self.logger.warning(f"Pipeline config not found at {pipeline_config_path}, using defaults")
            self.pipeline_config = {
                'pipeline': {
                    'filtering': {
                        'confidence_threshold': 0.70,
                        'max_articles_to_process': 35
                    }
                }
            }
    
    def is_url_already_processed(self, url: str, topic: str) -> bool:
        """Check if a URL has already been processed for a given topic."""
        conn = sqlite3.connect(self.db_path)
        url_hash_value = url_hash(url)
        
        cursor = conn.execute("""
            SELECT 1 FROM processed_links 
            WHERE url_hash = ? AND topic = ?
        """, (url_hash_value, topic))
        
        result = cursor.fetchone() is not None
        conn.close()
        return result
    
    def save_processed_link(self, url: str, topic: str, result: str, confidence: float = 0.0) -> None:
        """Save processed URL to prevent re-processing."""
        conn = sqlite3.connect(self.db_path)
        url_hash_value = url_hash(url)
        
        try:
            conn.execute("""
                INSERT OR REPLACE INTO processed_links 
                (url_hash, url, topic, result, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (url_hash_value, url, topic, result, confidence))
            conn.commit()
        except Exception as e:
            self.logger.error(f"Error saving processed link: {e}")
        finally:
            conn.close()

    def classify_article(self, title: str, url: str, topic: str) -> Dict[str, Any]:
        """
        Classify a single article for relevance using MODEL_MINI.
        
        Args:
            title: Article title
            url: Article URL
            topic: Topic to classify against
            
        Returns:
            Classification result with is_match, confidence, and reason
        """
        try:
            # Get topic configuration
            topic_config = self.topics_config['topics'].get(topic, {})
            include_keywords = topic_config.get('include', [])
            topic_threshold = topic_config.get('confidence_threshold', self.confidence_threshold)
            
            # Build system prompt
            system_prompt = f"""You are an expert news classifier for Swiss business and financial news.
            
Your task is to determine if an article is relevant to the topic: {topic}

Topic keywords: {', '.join(include_keywords)}

Classify based on:
1. Title content and keywords
2. URL structure and domain
3. Relevance to Swiss business/financial context

Return strict JSON with:
- is_match: boolean (true if relevant)
- confidence: number 0-1 (how confident you are)
- topic: the topic being classified
- reason: brief explanation (max 240 chars)

Be precise and conservative - only mark as relevant if clearly related to the topic."""
            
            # User input
            user_input = {
                "title": title,
                "url": url,
                "topic": topic
            }
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_input)}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "triage",
                        "schema": self.triage_schema["schema"],
                        "strict": True
                    }
                }
            )
            
            response_content = response.choices[0].message.content
            if response_content is None:
                raise ValueError("OpenAI response content is None")
            
            result = json.loads(response_content)
            
            # Apply topic-specific threshold
            if result.get('confidence', 0) < topic_threshold:
                result['is_match'] = False
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error classifying article '{title}': {e}")
            return {
                "is_match": False,
                "confidence": 0.0,
                "topic": topic,
                "reason": f"Classification error: {str(e)[:100]}"
            }
    
    def batch_classify(self, articles: List[Dict[str, Any]], topic: str) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Classify multiple articles for a topic with progress tracking.
        CRITICAL FIX: Skip already processed URLs to prevent 3+ hour runtime.
        
        Args:
            articles: List of article dictionaries with title, url, etc.
            topic: Topic to classify against
            
        Returns:
            List of (article, classification_result) tuples
        """
        results = []
        total = len(articles)
        matched_count = 0
        skipped_count = 0
        
        self.logger.info(f"Starting AI classification for {format_number(total)} articles on topic: {topic}")
        
        for i, article in enumerate(articles, 1):
            # Show progress every 10 items or at key milestones
            if i % 10 == 0 or i == total or i == 1:
                log_progress(self.logger, i, total, f"Classifying {topic}", "   ")
            
            url = article.get('url', '')
            
            # CRITICAL PERFORMANCE FIX: Skip already processed URLs
            if self.is_url_already_processed(url, topic):
                skipped_count += 1
                # Return cached result - we don't need to classify again
                results.append((article, {
                    "is_match": False,  # Conservative default for skipped items
                    "confidence": 0.0,
                    "topic": topic,
                    "reason": "Previously processed (skipped)"
                }))
                continue
            
            try:
                classification = self.classify_article(
                    article.get('title', ''),
                    url,
                    topic
                )
                
                # Log each article's classification result
                self.logger.info(
                    f"Title: {article.get('title', '')} | URL: {url} | "
                    f"Decision: {'MATCH' if classification['is_match'] else 'NO MATCH'} "
                    f"(confidence {classification['confidence']:.2f})"
                )
                
                # Save processed URL to prevent re-processing
                result_type = 'matched' if classification['is_match'] else 'rejected'
                self.save_processed_link(url, topic, result_type, classification['confidence'])
                
                if classification['is_match']:
                    matched_count += 1
                    # Log high-confidence matches
                    if classification['confidence'] > 0.85:
                        title = article.get('title', '')[:60] + "..." if len(article.get('title', '')) > 60 else article.get('title', '')
                        self.logger.debug(f"   [MATCH] High confidence match: {title} ({classification['confidence']:.2f})")
                
                results.append((article, classification))
                
            except Exception as e:
                log_error_with_context(self.logger, e, f"Classification failed for article {i}")
                
                # Save failed processing to prevent retry
                self.save_processed_link(url, topic, 'error', 0.0)
                
                # Add failed classification
                results.append((article, {
                    "is_match": False,
                    "confidence": 0.0,
                    "topic": topic,
                    "reason": f"Error: {str(e)[:50]}"
                }))
        
        actual_processed = total - skipped_count
        match_rate = format_rate(matched_count, actual_processed) if actual_processed > 0 else "0%"
        
        self.logger.info(f"   [COMPLETE] Topic '{topic}': {matched_count}/{format_number(actual_processed)} articles matched ({match_rate})")
        if skipped_count > 0:
            self.logger.info(f"   [SKIPPED] {skipped_count} articles already processed (90% time saved!)")
        
        return results
    
    def get_unfiltered_articles(self, force_refresh: bool = False, include_prefiltered: bool = False, 
                              topic: str = None) -> List[Dict[str, Any]]:
        """
        Get articles from database that haven't been filtered yet.
        
        Args:
            force_refresh: Re-process recent articles for testing
            include_prefiltered: Include articles that were never AI-classified
            topic: Topic name to read max_article_age_days configuration from
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Get max_article_age_days from topic configuration
        max_article_age_days = None
        if topic is not None and topic in self.topics_config['topics']:
            max_article_age_days = self.topics_config['topics'][topic].get('max_article_age_days')
        
        # Calculate date filter if max_article_age_days is configured
        date_filter = ""
        date_params = []
        if max_article_age_days is not None:
            from datetime import datetime, timedelta
            from zoneinfo import ZoneInfo
            
            # Swiss timezone
            TZ = ZoneInfo("Europe/Zurich")
            now = datetime.now(TZ)
            
            if max_article_age_days <= 0:
                # "today only" - start from local midnight
                cutoff_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                description = "today only (from midnight)"
            else:
                # last N days: start at local midnight N days ago
                cutoff_date = (now - timedelta(days=max_article_age_days)).replace(hour=0, minute=0, second=0, microsecond=0)
                description = f"last {max_article_age_days} day(s) (from midnight)"
            
            # Convert to ISO string for database comparison
            cutoff_iso = cutoff_date.isoformat()
            date_filter = "AND (published_at >= ? OR (published_at IS NULL AND first_seen_at >= ?))"
            date_params = [cutoff_iso, cutoff_iso]
            self.logger.info(f"Date filtering enabled: articles {description} (since {cutoff_date.strftime('%Y-%m-%d %H:%M:%S %Z')})")
        
        if force_refresh:
            # Re-process recent articles (last 3 days) for testing/refreshing
            query = f"""
                SELECT id, source, url, title, published_at, first_seen_at
                FROM items 
                WHERE first_seen_at > datetime('now', '-3 days')
                {date_filter}
                ORDER BY first_seen_at DESC
                LIMIT 100
            """
            cursor = conn.execute(query, date_params)
            self.logger.info("Force refresh mode: re-processing recent articles")
        elif include_prefiltered:
            # Include articles that were never AI-classified (only pre-filtered)
            query = f"""
                SELECT id, source, url, title, published_at, first_seen_at
                FROM items 
                WHERE triage_topic IS NULL 
                {date_filter}
                ORDER BY first_seen_at DESC
            """
            cursor = conn.execute(query, date_params)
            self.logger.info("Including pre-filtered articles that were never AI-classified")
        else:
            # Normal mode: only unfiltered articles
            query = f"""
                SELECT id, source, url, title, published_at, first_seen_at
                FROM items 
                WHERE triage_topic IS NULL 
                {date_filter}
                ORDER BY first_seen_at DESC
            """
            cursor = conn.execute(query, date_params)
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                'id': row['id'],
                'source': row['source'],
                'url': row['url'],
                'title': row['title'],
                'published_at': row['published_at'],
                'first_seen_at': row['first_seen_at']
            })
        
        conn.close()
        
        if max_article_age_days is not None:
            self.logger.info(f"Date filtering result: {len(articles)} articles found within {max_article_age_days} day(s)")
        
        return articles
    
    
    def calculate_priority_score(self, article: Dict[str, Any]) -> float:
        """
        Calculate priority score for article processing order.
        Higher score = process first.
        
        Factors:
        - Source credibility (government/financial = high)
        - Article freshness (today = 1.0, yesterday = 0.9, etc.)
        - URL quality indicators
        """
        score = 0.0
        url = article.get('url', '').lower()
        published_at = article.get('published_at', article.get('first_seen_at', ''))
        
        # Source credibility scoring
        tier_1_sources = ['admin.ch', 'finma.ch', 'snb.ch', 'seco.admin.ch', 'bfs.admin.ch']
        tier_2_sources = ['handelszeitung.ch', 'finews.ch', 'fuw.ch', 'cash.ch']
        tier_3_sources = ['nzz.ch', 'srf.ch']
        
        if any(source in url for source in tier_1_sources):
            score += 3.0  # Government sources get highest priority
        elif any(source in url for source in tier_2_sources):
            score += 2.0  # Financial news sources
        elif any(source in url for source in tier_3_sources):
            score += 1.0  # General news sources
        else:
            score += 0.5  # Unknown sources get lowest priority
        
        # Freshness scoring (rough approximation)
        if published_at:
            try:
                from datetime import datetime, timezone
                import dateutil.parser
                
                pub_date = dateutil.parser.parse(published_at)
                now = datetime.now(timezone.utc)
                days_old = (now - pub_date).days
                
                # Decay score by age: today=1.0, yesterday=0.9, etc.
                freshness_score = max(0.1, 1.0 - (days_old * 0.1))
                score += freshness_score
            except:
                score += 0.5  # Default if date parsing fails
        
        # URL quality indicators
        if '/artikel/' in url or '/news/' in url or '/artikel-' in url:
            score += 0.3  # Looks like a proper article URL
        if '?' not in url or url.count('?') == 1:
            score += 0.2  # Clean URL structure
        
        return score

    def filter_for_creditreform(self, mode: str = "standard", skip_prefilter: bool = False) -> Dict[str, Any]:
        """
        OPTIMIZED: Single-pass filtering focused on Creditreform insights only.
        Replaces filter_all_topics() with smart priority-based processing.
        
        Args:
            mode: "express" for < 3min, "standard" for < 8min
            skip_prefilter: If True, bypass priority scoring and process all deduplicated articles
            
        Returns:
            Enhanced results with priority scoring and early termination
        """
        start_time = time.time()
        
        log_step_start(self.logger, "Creditreform-Focused AI Filtering", 
                      f"Single-pass classification for actionable insights ({mode} mode)")
        
        # Get active topics (only enabled ones)
        active_topics = {name: config for name, config in self.topics_config['topics'].items() 
                        if config.get('enabled', True)}
        
        if not active_topics:
            self.logger.warning("WARNING: No enabled topics found")
            return {}
        
        # Use only creditreform_insights if available, otherwise use first active topic
        target_topic = "creditreform_insights" if "creditreform_insights" in active_topics else list(active_topics.keys())[0]
        
        # Get unfiltered articles - include pre-filtered articles when skip_prefilter=True
        # Pass the target_topic to enable date filtering
        if skip_prefilter:
            # When skipping prefilter, we want articles that were never AI-classified (only pre-filtered)
            unfiltered = self.get_unfiltered_articles(force_refresh=False, include_prefiltered=True, topic=target_topic)
        elif mode == "express":
            # Express mode uses force refresh for testing
            unfiltered = self.get_unfiltered_articles(force_refresh=True, include_prefiltered=False, topic=target_topic)
        else:
            # Standard mode gets only truly unprocessed articles
            unfiltered = self.get_unfiltered_articles(force_refresh=False, include_prefiltered=False, topic=target_topic)
        
        if not unfiltered:
            self.logger.warning("WARNING: No unfiltered articles found - nothing to process")
            if not skip_prefilter and mode != "express":
                self.logger.info("INFO: Try force refresh mode by clearing recent classification data")
            return {"creditreform_insights": {"processed": 0, "matched": 0}}
        
        topic_config = active_topics[target_topic]
        
        # Configuration - read skip_prefilter from topic config if not explicitly set
        if not skip_prefilter:
            skip_prefilter = topic_config.get('skip_prefilter', False)
            self.logger.info(f"Reading skip_prefilter from config: {skip_prefilter}")
        
        max_articles = 15 if mode == "express" else topic_config.get('max_articles_per_run', 25)
        confidence_threshold = topic_config.get('confidence_threshold', 0.80)
        early_terminate_at = topic_config.get('thresholds', {}).get('early_termination_at', max_articles)
        
        self.logger.info(f"Target topic: {target_topic}")
        self.logger.info(f"Processing mode: {mode}")
        self.logger.info(f"Max articles to process: {max_articles}")
        self.logger.info(f"Confidence threshold: {confidence_threshold}")
        self.logger.info(f"Pre-filtering: {'DISABLED - processing all articles' if skip_prefilter else 'ENABLED - priority-based filtering'}")
        self.logger.info(f"Available articles: {format_number(len(unfiltered))}")
        
        if skip_prefilter:
            # Skip pre-filtering: process all deduplicated articles
            self.logger.info("Skipping priority-based pre-filtering - processing all deduplicated articles")
            articles_to_process = unfiltered
            # Still add priority scores for logging/debugging purposes
            for article in articles_to_process:
                article['priority_score'] = self.calculate_priority_score(article)
        else:
            # Priority-based article sorting (original behavior)
            self.logger.info("Calculating article priorities...")
            for article in unfiltered:
                article['priority_score'] = self.calculate_priority_score(article)
            
            # Sort by priority (highest first)
            sorted_articles = sorted(unfiltered, key=lambda x: x['priority_score'], reverse=True)
            
            # Limit articles for processing (optimization)
            if mode == "express":
                # Express mode: process only top 50 articles maximum
                articles_to_process = sorted_articles[:min(50, len(sorted_articles))]
            else:
                # Standard mode: process top 100 articles maximum
                articles_to_process = sorted_articles[:min(100, len(sorted_articles))]
        
        self.logger.info(f"Processing {len(articles_to_process)} articles {'(all available)' if skip_prefilter else '(top priority)'}")
        
        # Enhanced system prompt for Creditreform context
        enhanced_system_prompt = self.build_creditreform_system_prompt(topic_config)
        
        # Smart batch processing with early termination
        results = []
        matched_count = 0
        processed_count = 0
        high_confidence_matches = 0
        
        for i, article in enumerate(articles_to_process, 1):
            # Progress logging
            if i % 5 == 0 or i == len(articles_to_process) or i == 1:
                log_progress(self.logger, i, len(articles_to_process), f"Processing {target_topic}", "   ")
            
            url = article.get('url', '')
            
            # Skip already processed URLs
            if self.is_url_already_processed(url, target_topic):
                continue
            
            try:
                # Enhanced classification with Creditreform context
                classification = self.classify_article_enhanced(
                    article.get('title', ''),
                    url,
                    target_topic,
                    enhanced_system_prompt,
                    article.get('priority_score', 0.0)
                )
                
                # Log each article's classification result
                self.logger.info(
                    f"Title: {article.get('title', '')} | URL: {url} | "
                    f"Decision: {'MATCH' if classification['is_match'] else 'NO MATCH'} "
                    f"(confidence {classification['confidence']:.2f})"
                )
                
                # Save processed URL
                result_type = 'matched' if classification['is_match'] else 'rejected'
                self.save_processed_link(url, target_topic, result_type, classification['confidence'])
                
                # Save classification to database
                self.save_classification(article['id'], target_topic, classification)
                
                processed_count += 1
                
                if classification['is_match']:
                    matched_count += 1
                    results.append((article, classification))
                    
                    if classification['confidence'] > 0.85:
                        high_confidence_matches += 1
                        title = article.get('title', '')[:60] + "..." if len(article.get('title', '')) > 60 else article.get('title', '')
                        self.logger.debug(f"   [HIGH] {title} ({classification['confidence']:.2f})")
            
            except Exception as e:
                log_error_with_context(self.logger, e, f"Classification failed for article {i}")
                self.save_processed_link(url, target_topic, 'error', 0.0)
                processed_count += 1
        
        # Results summary
        total_duration = time.time() - start_time
        match_rate = format_rate(matched_count, processed_count) if processed_count > 0 else "0%"
        
        summary_results = {
            'topic': target_topic,
            'mode': mode,
            'processed': processed_count,
            'matched': matched_count,
            'high_confidence': high_confidence_matches,
            'match_rate': match_rate,
            'duration': f"{total_duration:.1f}s",
            'avg_confidence': sum(r[1]['confidence'] for r in results) / len(results) if results else 0.0,
            'early_terminated': matched_count >= early_terminate_at
        }
        
        log_step_complete(self.logger, "Creditreform-Focused AI Filtering", total_duration, summary_results)
        
        return {target_topic: summary_results}

    def build_creditreform_system_prompt(self, topic_config: Dict[str, Any]) -> str:
        """
        Build enhanced system prompt with Creditreform business context.
        """
        description = topic_config.get('description', '')
        focus_areas = topic_config.get('focus_areas', {})
        
        focus_text = ""
        for area, info in focus_areas.items():
            keywords = info.get('keywords', [])
            priority = info.get('priority', 'medium')
            focus_text += f"\n- {area} ({priority} priority): {', '.join(keywords)}"
        
        return f"""You are an expert Swiss financial news analyst specializing in B2B credit risk assessment.

CREDITREFORM CONTEXT:
{description}

You're filtering news for a Product Manager/Data Analyst at Creditreform Switzerland who needs:
- Actionable insights for credit risk products and services
- Regulatory changes affecting B2B credit assessment
- Market intelligence on competitors and industry trends
- Swiss-specific financial and business developments

KEY FOCUS AREAS:{focus_text}

CLASSIFICATION CRITERIA:
- HIGH RELEVANCE (0.85+): Direct impact on credit risk business, regulatory changes, competitor news
- MEDIUM RELEVANCE (0.70-0.84): Industry trends, general business climate affecting B2B credit
- LOW RELEVANCE (< 0.70): Tangential business news, consumer finance, unrelated topics

Return strict JSON with:
- is_match: boolean (true if relevant for Creditreform business)
- confidence: number 0-1 (how relevant/actionable this is)
- topic: "creditreform_insights"
- reason: brief business justification (max 200 chars)

Be selective - only mark articles that provide actionable business intelligence."""

    def classify_article_enhanced(self, title: str, url: str, topic: str, 
                                 system_prompt: str, priority_score: float = 0.0) -> Dict[str, Any]:
        """
        Enhanced classification with Creditreform business context.
        """
        try:
            topic_config = self.topics_config['topics'].get(topic, {})
            topic_threshold = topic_config.get('confidence_threshold', self.confidence_threshold)
            
            # Enhanced user input with priority context
            user_input = {
                "title": title,
                "url": url,
                "topic": topic,
                "priority_score": priority_score,
                "source_tier": "tier_1" if priority_score >= 3.0 else "tier_2" if priority_score >= 2.0 else "tier_3"
            }
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_input)}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "triage",
                        "schema": self.triage_schema["schema"],
                        "strict": True
                    }
                }
            )
            
            response_content = response.choices[0].message.content
            if response_content is None:
                raise ValueError("OpenAI response content is None")
            
            result = json.loads(response_content)
            
            # Apply topic-specific threshold
            if result.get('confidence', 0) < topic_threshold:
                result['is_match'] = False
                result['reason'] = f"Below confidence threshold {topic_threshold}"
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in enhanced classification '{title}': {e}")
            return {
                "is_match": False,
                "confidence": 0.0,
                "topic": topic,
                "reason": f"Classification error: {str(e)[:100]}"
            }

    def filter_all_topics(self) -> Dict[str, Dict[str, int]]:
        """
        LEGACY: Filter all topics (replaced by filter_for_creditreform).
        Kept for compatibility but redirects to optimized approach.
        """
        self.logger.warning("filter_all_topics() is deprecated. Using optimized filter_for_creditreform() instead.")
        return self.filter_for_creditreform("standard")
    
    def get_matched_articles(self, topic: str | None = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get articles that passed filtering.
        
        Args:
            topic: Specific topic to filter by, or None for all
            limit: Maximum number of articles to return
            
        Returns:
            List of matched articles
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        if topic:
            cursor = conn.execute("""
                SELECT id, source, url, title, published_at, 
                       triage_topic, triage_confidence
                FROM items 
                WHERE is_match = 1 AND triage_topic = ?
                ORDER BY triage_confidence DESC, first_seen_at DESC
                LIMIT ?
            """, (topic, limit))
        else:
            cursor = conn.execute("""
                SELECT id, source, url, title, published_at, 
                       triage_topic, triage_confidence
                FROM items 
                WHERE is_match = 1
                ORDER BY triage_confidence DESC, first_seen_at DESC
                LIMIT ?
            """, (limit,))
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                'id': row['id'],
                'source': row['source'],
                'url': row['url'],
                'title': row['title'],
                'published_at': row['published_at'],
                'topic': row['triage_topic'],
                'confidence': row['triage_confidence']
            })
        
        conn.close()
        return articles
    
    def get_top_articles_by_confidence(self, topic: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get top X articles by confidence score for pipeline continuation.
        This method is called AFTER all articles have been rated to select the best ones.
        
        Args:
            topic: Specific topic to filter by
            limit: Number of top articles to return
            
        Returns:
            List of top articles ordered by confidence (highest first)
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Get all matched articles for the topic, ordered by confidence
        cursor = conn.execute("""
            SELECT id, source, url, title, published_at, first_seen_at,
                   triage_topic, triage_confidence
            FROM items 
            WHERE is_match = 1 AND triage_topic = ?
            ORDER BY triage_confidence DESC, first_seen_at DESC
            LIMIT ?
        """, (topic, limit))
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                'id': row['id'],
                'source': row['source'],
                'url': row['url'],
                'title': row['title'],
                'published_at': row['published_at'],
                'first_seen_at': row['first_seen_at'],
                'topic': row['triage_topic'],
                'confidence': row['triage_confidence']
            })
        
        conn.close()
        
        self.logger.info(f"Selected top {len(articles)} articles by confidence for pipeline continuation")
        if articles:
            self.logger.info(f"   [RANGE] Confidence range: {articles[0]['confidence']:.2f} to {articles[-1]['confidence']:.2f}")
            # Log top 5 articles
            for i, article in enumerate(articles[:5], 1):
                title_short = article['title'][:50] + "..." if len(article['title']) > 50 else article['title']
                self.logger.info(f"   [TOP {i}] {title_short} (confidence: {article['confidence']:.2f})")
        
        return articles
    
    def filter_for_run(self, run_id: str, mode: str = "standard") -> Dict[str, Any]:
        """
        Filter articles and select top N by confidence for a specific pipeline run.
        
        Args:
            run_id: Pipeline run identifier
            mode: Processing mode (standard/express)
            
        Returns:
            Results dictionary including selected article count
        """
        # Step 1: Run classification (existing logic)
        results = self.filter_for_creditreform(mode)
        
        # Step 2: Mark articles with pipeline run ID
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            UPDATE items 
            SET pipeline_run_id = ?
            WHERE triage_topic IS NOT NULL 
            AND pipeline_run_id IS NULL
        """, (run_id,))
        conn.commit()
        conn.close()
        
        # Step 3: Select top articles by confidence
        selected_count = self._select_top_articles(run_id)
        
        # Add selection info to results
        for topic, topic_results in results.items():
            topic_results['selected_for_processing'] = selected_count
            
        return results
    
    def _select_top_articles(self, run_id: str) -> int:
        """
        Select top N articles above threshold for processing.
        This is the KEY function that controls what flows to scraping/summarization.
        
        Args:
            run_id: Pipeline run identifier
            
        Returns:
            Number of articles selected
        """
        conn = sqlite3.connect(self.db_path)
        
        # Get configuration
        config = self.pipeline_config['pipeline']['filtering']
        threshold = config.get('confidence_threshold', 0.70)
        max_articles = config.get('max_articles_to_process', 35)
        
        # First, mark all articles as not selected
        conn.execute("""
            UPDATE items 
            SET selected_for_processing = 0,
                selection_rank = NULL,
                pipeline_stage = CASE 
                    WHEN is_match = 1 THEN 'matched'
                    ELSE 'filtered_out'
                END
            WHERE pipeline_run_id = ?
        """, (run_id,))
        
        # Get articles above threshold, ordered by confidence
        cursor = conn.execute("""
            SELECT id, triage_confidence, title
            FROM items 
            WHERE pipeline_run_id = ? 
            AND is_match = 1
            AND triage_confidence >= ?
            ORDER BY triage_confidence DESC, first_seen_at DESC
            LIMIT ?
        """, (run_id, threshold, max_articles))
        
        selected_articles = cursor.fetchall()
        
        # Mark selected articles with their rank
        for rank, (article_id, confidence, title) in enumerate(selected_articles, 1):
            conn.execute("""
                UPDATE items 
                SET selected_for_processing = 1,
                    selection_rank = ?,
                    pipeline_stage = 'selected'
                WHERE id = ? AND pipeline_run_id = ?
            """, (rank, article_id, run_id))
            
            self.logger.info(f"Selected rank {rank}: {title[:60]}... (confidence: {confidence:.2f})")
        
        # Mark non-selected matched articles
        conn.execute("""
            UPDATE items 
            SET pipeline_stage = 'matched_not_selected'
            WHERE pipeline_run_id = ?
            AND is_match = 1
            AND selected_for_processing = 0
        """, (run_id,))
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"Selected {len(selected_articles)} articles for processing "
                        f"(threshold: {threshold}, max: {max_articles})")
        
        return len(selected_articles)
    
    def save_classification(self, article_id: int, topic: str, classification: Dict[str, Any], 
                           run_id: Optional[str] = None) -> None:
        """Save classification result to database."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            if run_id:
                # Include pipeline run ID and stage
                conn.execute("""
                    UPDATE items 
                    SET triage_topic = ?, 
                        triage_confidence = ?, 
                        is_match = ?,
                        pipeline_run_id = ?,
                        pipeline_stage = CASE 
                            WHEN ? = 1 THEN 'matched'
                            ELSE 'filtered_out'
                        END
                    WHERE id = ?
                """, (
                    topic,
                    classification['confidence'],
                    1 if classification['is_match'] else 0,
                    run_id,
                    1 if classification['is_match'] else 0,
                    article_id
                ))
            else:
                # Original logic without run_id
                conn.execute("""
                    UPDATE items 
                    SET triage_topic = ?, 
                        triage_confidence = ?, 
                        is_match = ?
                    WHERE id = ?
                """, (
                    topic,
                    classification['confidence'],
                    1 if classification['is_match'] else 0,
                    article_id
                ))
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Error saving classification for article {article_id}: {e}")
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get filtering statistics."""
        conn = sqlite3.connect(self.db_path)
        
        # Total articles
        cursor = conn.execute("SELECT COUNT(*) FROM items")
        total = cursor.fetchone()[0]
        
        # Filtered articles
        cursor = conn.execute("SELECT COUNT(*) FROM items WHERE triage_topic IS NOT NULL")
        filtered = cursor.fetchone()[0]
        
        # Matched articles
        cursor = conn.execute("SELECT COUNT(*) FROM items WHERE is_match = 1")
        matched = cursor.fetchone()[0]
        
        # By topic
        cursor = conn.execute("""
            SELECT triage_topic, 
                   COUNT(*) as total,
                   SUM(is_match) as matched,
                   AVG(triage_confidence) as avg_confidence
            FROM items 
            WHERE triage_topic IS NOT NULL 
            GROUP BY triage_topic
        """)
        
        by_topic = {}
        for row in cursor.fetchall():
            by_topic[row[0]] = {
                'total': row[1],
                'matched': row[2],
                'avg_confidence': row[3]
            }
        
        conn.close()
        
        return {
            'total_articles': total,
            'filtered_articles': filtered,
            'matched_articles': matched,
            'match_rate': matched / filtered if filtered > 0 else 0,
            'by_topic': by_topic
        }
