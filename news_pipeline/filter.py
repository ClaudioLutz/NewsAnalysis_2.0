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
from .utils import setup_logging


class AIFilter:
    """AI-powered relevance filtering using MODEL_MINI."""
    
    def __init__(self, db_path: str, topics_config_path: str = "config/topics.yaml"):
        self.db_path = db_path
        self.client = OpenAI()
        self.model = os.getenv("MODEL_MINI", "gpt-5-mini")
        self.confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))
        
        self.logger = logging.getLogger(__name__)
        
        # Load topics configuration
        with open(topics_config_path, 'r', encoding='utf-8') as f:
            self.topics_config = yaml.safe_load(f)
        
        # Load triage schema
        with open("schemas/triage.schema.json", 'r', encoding='utf-8') as f:
            self.triage_schema = json.load(f)
    
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
                },
                temperature=0
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
        Classify multiple articles for a topic.
        
        Args:
            articles: List of article dictionaries with title, url, etc.
            topic: Topic to classify against
            
        Returns:
            List of (article, classification_result) tuples
        """
        results = []
        
        for article in articles:
            classification = self.classify_article(
                article.get('title', ''),
                article.get('url', ''),
                topic
            )
            results.append((article, classification))
        
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
        Filter all unfiltered articles against all configured topics.
        
        Returns:
            Results summary by topic
        """
        results = {}
        
        # Get unfiltered articles
        unfiltered = self.get_unfiltered_articles()
        if not unfiltered:
            self.logger.info("No unfiltered articles found")
            return results
        
        self.logger.info(f"Filtering {len(unfiltered)} articles against {len(self.topics_config['topics'])} topics")
        
        # Process each topic
        for topic_name in self.topics_config['topics'].keys():
            self.logger.info(f"Filtering for topic: {topic_name}")
            
            topic_results = {
                'processed': 0,
                'matched': 0,
                'avg_confidence': 0.0
            }
            
            total_confidence = 0.0
            
            # Classify all articles for this topic
            classifications = self.batch_classify(unfiltered, topic_name)
            
            for article, classification in classifications:
                # Save classification
                self.save_classification(article['id'], topic_name, classification)
                
                topic_results['processed'] += 1
                total_confidence += classification['confidence']
                
                if classification['is_match']:
                    topic_results['matched'] += 1
                    self.logger.debug(f"Matched: {article['title']} (confidence: {classification['confidence']:.2f})")
            
            # Calculate average confidence
            if topic_results['processed'] > 0:
                topic_results['avg_confidence'] = total_confidence / topic_results['processed']
            
            results[topic_name] = topic_results
            
            self.logger.info(f"Topic {topic_name}: {topic_results['matched']}/{topic_results['processed']} matched "
                           f"(avg confidence: {topic_results['avg_confidence']:.2f})")
        
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
