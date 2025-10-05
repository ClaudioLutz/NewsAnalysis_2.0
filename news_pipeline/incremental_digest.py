"""
Incremental Digest Generation System

Enables efficient daily digest updates by tracking processed articles
and only generating content for new articles, then merging with existing digests.
"""

import os
import json
import sqlite3
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(override=True)

from openai import OpenAI
from news_pipeline.language_config import get_language_config


class DigestStateManager:
    """Manages digest state persistence in the database."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
    
    def get_digest_state(self, date: str, topic: str) -> Optional[Dict[str, Any]]:
        """Get existing digest state for a specific date and topic."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT processed_article_ids, digest_content, article_count, 
                   created_at, updated_at
            FROM digest_state 
            WHERE digest_date = ? AND topic = ?
        """, (date, topic))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'processed_article_ids': json.loads(row['processed_article_ids']),
                'digest_content': json.loads(row['digest_content']),
                'article_count': row['article_count'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        return None
    
    def save_digest_state(self, date: str, topic: str, article_ids: List[int], 
                         digest_content: Dict[str, Any]) -> None:
        """Save or update digest state."""
        conn = sqlite3.connect(self.db_path)
        current_time = datetime.now().isoformat()
        
        # Check if state exists
        existing = self.get_digest_state(date, topic)
        
        if existing:
            # Update existing state
            conn.execute("""
                UPDATE digest_state 
                SET processed_article_ids = ?, digest_content = ?, 
                    article_count = ?, updated_at = ?
                WHERE digest_date = ? AND topic = ?
            """, (json.dumps(article_ids), json.dumps(digest_content),
                  len(article_ids), current_time, date, topic))
        else:
            # Insert new state
            conn.execute("""
                INSERT INTO digest_state 
                (digest_date, topic, processed_article_ids, digest_content, 
                 article_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (date, topic, json.dumps(article_ids), json.dumps(digest_content),
                  len(article_ids), current_time, current_time))
        
        conn.commit()
        conn.close()
    
    def get_all_digest_states(self, date: str) -> Dict[str, Dict[str, Any]]:
        """Get all digest states for a specific date."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT topic, processed_article_ids, digest_content, article_count,
                   created_at, updated_at
            FROM digest_state 
            WHERE digest_date = ?
        """, (date,))
        
        states = {}
        for row in cursor.fetchall():
            states[row['topic']] = {
                'processed_article_ids': json.loads(row['processed_article_ids']),
                'digest_content': json.loads(row['digest_content']),
                'article_count': row['article_count'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        
        conn.close()
        return states
    
    def clear_old_states(self, days_to_keep: int = 7) -> None:
        """Clear digest states older than specified days."""
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM digest_state WHERE digest_date < ?", (cutoff_date,))
        conn.execute("DELETE FROM digest_generation_log WHERE digest_date < ?", (cutoff_date,))
        conn.commit()
        conn.close()
        
        self.logger.info(f"Cleared digest states older than {cutoff_date}")

    def log_generation(self, date: str, generation_type: str, topics_processed: int,
                      total_articles: int, new_articles: int = 0, 
                      api_calls: int = 0, execution_time: float = 0.0) -> None:
        """Log digest generation statistics."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO digest_generation_log 
            (digest_date, generation_type, topics_processed, total_articles,
             new_articles, api_calls_made, execution_time_seconds, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (date, generation_type, topics_processed, total_articles,
              new_articles, api_calls, execution_time, datetime.now().isoformat()))
        conn.commit()
        conn.close()


class IncrementalDigestGenerator:
    """Generates incremental digests by processing only new articles."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.client = OpenAI()
        self.model = os.getenv("MODEL_MINI", "gpt-4o-mini")
        self.state_manager = DigestStateManager(db_path)
        self.logger = logging.getLogger(__name__)
    
    def get_new_articles_for_topic(self, topic: str, date: str, 
                                  processed_ids: Set[int]) -> List[Dict[str, Any]]:
        """Get articles for topic that haven't been processed yet."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Get articles from the specified date that aren't in processed_ids
        cursor = conn.execute("""
            SELECT i.id, i.url, i.title, i.source, i.published_at,
                   s.summary, s.key_points_json, s.entities_json
            FROM items i
            JOIN summaries s ON i.id = s.item_id
            LEFT JOIN article_clusters ac ON i.id = ac.article_id
            WHERE s.topic = ? 
            AND DATE(i.published_at) = ?
            AND COALESCE(s.topic_already_covered, 0) = 0
            AND (ac.is_primary = 1 OR ac.article_id IS NULL)
            ORDER BY i.triage_confidence DESC, s.created_at DESC
        """, (topic, date))
        
        new_articles = []
        for row in cursor.fetchall():
            if row['id'] not in processed_ids:
                # Parse JSON fields
                key_points = json.loads(row['key_points_json']) if row['key_points_json'] else []
                entities = json.loads(row['entities_json']) if row['entities_json'] else {}
                
                new_articles.append({
                    'id': row['id'],
                    'url': row['url'],
                    'title': row['title'],
                    'source': row['source'],
                    'published_at': row['published_at'],
                    'summary': row['summary'],
                    'key_points': key_points,
                    'entities': entities
                })
        
        conn.close()
        return new_articles
    
    def generate_partial_digest(self, topic: str, new_articles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Generate digest content for new articles only."""
        if not new_articles:
            return None
            
        try:
            # Use language configuration for prompt
            language_config = get_language_config()
            system_prompt = language_config.get_partial_digest_prompt(topic)

            # Prepare input data
            input_data = {
                'topic': topic,
                'new_article_count': len(new_articles),
                'articles': []
            }
            
            for article in new_articles:
                input_data['articles'].append({
                    'title': article['title'],
                    'url': article['url'],
                    'source': article['source'],
                    'summary': article['summary'],
                    'key_points': article['key_points'][:3]
                })
            
            response_schema = {
                "type": "object",
                "properties": {
                    "key_insights": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                    "important_developments": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                    "new_sources": {"type": "array", "items": {"type": "string"}},
                    "entities_mentioned": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["key_insights", "important_developments", "new_sources", "entities_mentioned"],
                "additionalProperties": False
            }
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(input_data)}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "partial_digest",
                        "schema": response_schema,
                        "strict": True
                    }
                }
            )
            
            response_content = response.choices[0].message.content
            if response_content is None:
                raise ValueError("OpenAI response content is None")
            
            result = json.loads(response_content)
            result['article_count'] = len(new_articles)
            result['generated_at'] = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating partial digest for {topic}: {e}")
            return None
    
    def merge_digests(self, existing_digest: Dict[str, Any], 
                     partial_digest: Dict[str, Any], topic: str) -> Dict[str, Any]:
        """Merge new partial digest with existing digest."""
        try:
            # Use language configuration for prompt
            language_config = get_language_config()
            system_prompt = language_config.get_merge_digests_prompt(topic)

            input_data = {
                'topic': topic,
                'existing_digest': existing_digest,
                'new_insights': partial_digest,
                'total_articles': existing_digest.get('article_count', 0) + partial_digest.get('article_count', 0)
            }
            
            response_schema = {
                "type": "object",
                "properties": {
                    "headline": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "sources": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["headline", "why_it_matters", "sources"],
                "additionalProperties": False
            }
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(input_data)}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "merged_digest",
                        "schema": response_schema,
                        "strict": True
                    }
                }
            )
            
            response_content = response.choices[0].message.content
            if response_content is None:
                raise ValueError("OpenAI response content is None")
            
            result = json.loads(response_content)
            
            # Add metadata
            result.update({
                'topic': topic,
                'date_range': 'today',
                'article_count': input_data['total_articles'],
                'generated_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error merging digests for {topic}: {e}")
            # Fallback: return existing digest with updated counts
            existing_digest['article_count'] = existing_digest.get('article_count', 0) + partial_digest.get('article_count', 0)
            existing_digest['last_updated'] = datetime.now().isoformat()
            return existing_digest
    
    def generate_incremental_topic_digest(self, topic: str, date: str) -> Tuple[Dict[str, Any], bool]:
        """
        Generate or update topic digest incrementally.
        
        Returns:
            Tuple of (digest_dict, was_updated)
        """
        # Get existing state
        existing_state = self.state_manager.get_digest_state(date, topic)
        
        if existing_state:
            processed_ids = set(existing_state['processed_article_ids'])
            existing_digest = existing_state['digest_content']
        else:
            processed_ids = set()
            existing_digest = None
        
        # Get new articles
        new_articles = self.get_new_articles_for_topic(topic, date, processed_ids)
        
        if not new_articles:
            # No new articles, return existing digest
            if existing_digest:
                # ensure key exists for downstream math
                existing_digest.setdefault('new_articles_count', 0)
                return existing_digest, False
            else:
                # No existing digest and no new articles - return empty digest
                return {
                    'topic': topic,
                    'date_range': 'today',
                    'headline': f'No {topic} news found',
                    'why_it_matters': 'No significant developments to report.',
                    'bullets': [],
                    'sources': [],
                    'article_count': 0,
                    'new_articles_count': 0,
                    'generated_at': datetime.now().isoformat()
                }, False
        
        # Generate partial digest for new articles
        partial_digest = self.generate_partial_digest(topic, new_articles)
        if not partial_digest:
            # Failed to generate partial digest, return existing if available
            return existing_digest or {}, False
        
        # Merge with existing or create new digest
        was_updated = True
        if existing_digest:
            final_digest = self.merge_digests(existing_digest, partial_digest, topic)
            # surface how many were new in THIS run for KPI accuracy
            final_digest['new_articles_count'] = len(partial_digest.get('new_articles', [])) if 'new_articles' in partial_digest else len(new_articles)
        else:
            # No existing digest, convert partial to full digest
            from news_pipeline.analyzer import MetaAnalyzer
            analyzer = MetaAnalyzer(self.db_path)
            final_digest = analyzer.generate_topic_digest(topic, new_articles, "today")
            final_digest['new_articles_count'] = len(new_articles)
        
        # Update processed article IDs
        all_processed_ids = list(processed_ids) + [a['id'] for a in new_articles]
        
        # Save state
        self.state_manager.save_digest_state(date, topic, all_processed_ids, final_digest)
        
        return final_digest, was_updated
