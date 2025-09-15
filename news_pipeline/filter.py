"""
AIFilter - Step 2: AI-Powered Filtering (Title/URL Only)

Single-stage pre-filter using GPT-5-mini for relevance detection.
"""

import os
import json
import sqlite3
import yaml
from typing import List, Dict, Any, Tuple
import logging

from openai import OpenAI
from .utils import (
    setup_logging, log_progress, log_step_start, log_step_complete, 
    log_error_with_context, format_number, format_rate
)
import time
from .utils import url_hash


class AIFilter:
    """AI-powered relevance filtering using MODEL_NANO."""
    
    def __init__(self, db_path: str, topics_config_path: str = "config/topics.yaml"):
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
    
    def get_unfiltered_articles(self) -> List[Dict[str, Any]]:
        """Get articles from database that haven't been filtered yet."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT id, source, url, title, published_at, first_seen_at
            FROM items 
            WHERE triage_topic IS NULL 
            ORDER BY first_seen_at DESC
        """)
        
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
        return articles
    
    def save_classification(self, article_id: int, topic: str, classification: Dict[str, Any]) -> None:
        """Save classification result to database."""
        conn = sqlite3.connect(self.db_path)
        
        try:
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
    
    def filter_all_topics(self) -> Dict[str, Dict[str, int]]:
        """
        Filter all unfiltered articles against all configured topics with enhanced logging.
        
        Returns:
            Results summary by topic
        """
        start_time = time.time()
        results = {}
        
        # Get unfiltered articles
        log_step_start(self.logger, "AI-Powered Article Filtering", 
                      "Using AI to classify articles by relevance to topics")
        
        unfiltered = self.get_unfiltered_articles()
        if not unfiltered:
            self.logger.warning("WARNING: No unfiltered articles found - nothing to process")
            return results
        
        topics = list(self.topics_config['topics'].keys())
        total_articles = len(unfiltered)
        total_topics = len(topics)
        total_classifications = total_articles * total_topics
        
        self.logger.info(f"Processing {format_number(total_articles)} articles against {total_topics} topics")
        self.logger.info(f"Total AI classifications to perform: {format_number(total_classifications)}")
        self.logger.info(f"Using model: {self.model}")
        self.logger.info(f"Confidence threshold: {self.confidence_threshold}")
        
        # Process each topic
        overall_matched = 0
        overall_processed = 0
        
        for topic_idx, topic_name in enumerate(topics, 1):
            topic_start_time = time.time()
            
            self.logger.info(f"\nTopic {topic_idx}/{total_topics}: '{topic_name}'")
            
            topic_config = self.topics_config['topics'].get(topic_name, {})
            keywords = topic_config.get('include', [])
            threshold = topic_config.get('confidence_threshold', self.confidence_threshold)
            
            self.logger.info(f"   Keywords: {', '.join(keywords[:5])}{'...' if len(keywords) > 5 else ''}")
            self.logger.info(f"   Threshold: {threshold}")
            
            # Classify all articles for this topic
            classifications = self.batch_classify(unfiltered, topic_name)
            
            # Process results
            topic_results = {
                'processed': 0,
                'matched': 0,
                'avg_confidence': 0.0
            }
            
            total_confidence = 0.0
            high_confidence_matches = 0
            
            for article, classification in classifications:
                # Save classification
                self.save_classification(article['id'], topic_name, classification)
                
                topic_results['processed'] += 1
                total_confidence += classification['confidence']
                overall_processed += 1
                
                if classification['is_match']:
                    topic_results['matched'] += 1
                    overall_matched += 1
                    
                    if classification['confidence'] > 0.85:
                        high_confidence_matches += 1
            
            # Calculate metrics
            if topic_results['processed'] > 0:
                topic_results['avg_confidence'] = total_confidence / topic_results['processed']
            
            results[topic_name] = topic_results
            
            # Topic completion summary
            topic_duration = time.time() - topic_start_time
            match_rate = format_rate(topic_results['matched'], topic_results['processed'])
            
            self.logger.info(f"   [DONE] Completed in {topic_duration:.1f}s")
            self.logger.info(f"   [STATS] Matches: {topic_results['matched']}/{format_number(topic_results['processed'])} ({match_rate})")
            self.logger.info(f"   [AVG] Avg confidence: {topic_results['avg_confidence']:.3f}")
            if high_confidence_matches > 0:
                self.logger.info(f"   [HIGH] High confidence matches: {high_confidence_matches}")
        
        # Overall completion summary
        total_duration = time.time() - start_time
        overall_rate = format_rate(overall_matched, overall_processed)
        
        summary_results = {
            'total_processed': format_number(overall_processed),
            'total_matched': format_number(overall_matched), 
            'match_rate': overall_rate,
            'duration': f"{total_duration:.1f}s",
            'topics_processed': len(topics),
            'avg_time_per_topic': f"{total_duration/len(topics):.1f}s"
        }
        
        log_step_complete(self.logger, "AI-Powered Article Filtering", total_duration, summary_results)
        
        return results
    
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
