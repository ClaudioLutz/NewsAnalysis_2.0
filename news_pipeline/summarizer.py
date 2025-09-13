"""
ArticleSummarizer - Step 4: Individual Article Summarization

MODEL_MINI powered summarization with structured outputs for key insights.
"""

import os
import json
import sqlite3
import logging
from typing import List, Dict, Any, Optional

from openai import OpenAI


class ArticleSummarizer:
    """Individual article processing using MODEL_MINI."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.client = OpenAI()
        self.model = os.getenv("MODEL_MINI", "gpt-5-mini")
        
        self.logger = logging.getLogger(__name__)
        
        # Load summary schema
        with open("schemas/summary.schema.json", 'r', encoding='utf-8') as f:
            self.summary_schema = json.load(f)
    
    def summarize_article(self, content: str, title: str = "", url: str = "") -> Dict[str, Any]:
        """
        Summarize a single article using MODEL_MINI.
        
        Args:
            content: Full article text
            title: Article title (optional)
            url: Article URL (optional)
            
        Returns:
            Structured summary with title, summary, key_points, and entities
        """
        try:
            # Build system prompt
            system_prompt = """You are an expert Swiss business and financial news analyst.

Your task is to create a comprehensive summary of the article with key insights and extracted entities.

Return strict JSON with:
- title: cleaned/enhanced article title
- summary: concise 150-200 word summary capturing main points
- key_points: array of 3-6 most important bullet points
- entities: object with categories (companies, people, locations, topics) as keys and arrays of relevant entities as values

Focus on:
1. Swiss business context and implications
2. Financial impacts and market relevance
3. Key stakeholders and companies mentioned
4. Important dates, numbers, and metrics
5. Strategic implications and future outlook

Be precise, factual, and focus on business/financial significance."""
            
            # Prepare user input
            user_input = {
                "title": title,
                "url": url,
                "content": content
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
                        "name": "article_summary",
                        "schema": self.summary_schema["schema"],
                        "strict": True
                    }
                },
                temperature=0.1
            )
            
            response_content = response.choices[0].message.content
            if response_content is None:
                raise ValueError("OpenAI response content is None")
            
            result = json.loads(response_content)
            
            # Ensure we have required fields
            if not result.get("summary"):
                raise ValueError("Summary generation failed: no summary content")
            
            if not result.get("key_points"):
                result["key_points"] = []
            
            if not result.get("entities"):
                result["entities"] = {}
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error summarizing article: {e}")
            return {
                "title": title,
                "summary": "Summary generation failed due to processing error.",
                "key_points": [],
                "entities": {},
                "error": str(e)[:200]
            }
    
    def get_articles_to_summarize(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get extracted articles that need summarization."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT i.id, i.url, i.title, i.source, i.triage_topic, 
                   a.extracted_text, a.method
            FROM items i
            JOIN articles a ON i.id = a.item_id
            LEFT JOIN summaries s ON i.id = s.item_id
            WHERE i.is_match = 1 
            AND s.item_id IS NULL
            AND LENGTH(a.extracted_text) >= 600
            ORDER BY i.triage_confidence DESC, a.extracted_at DESC
            LIMIT ?
        """, (limit,))
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                'id': row['id'],
                'url': row['url'],
                'title': row['title'],
                'source': row['source'],
                'topic': row['triage_topic'],
                'extracted_text': row['extracted_text'],
                'extraction_method': row['method']
            })
        
        conn.close()
        return articles
    
    def save_summary(self, item_id: int, summary_data: Dict[str, Any], topic: str) -> bool:
        """Save article summary to database."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Convert lists and dicts to JSON strings for storage
            key_points_json = json.dumps(summary_data.get('key_points', []))
            entities_json = json.dumps(summary_data.get('entities', {}))
            
            conn.execute("""
                INSERT OR REPLACE INTO summaries 
                (item_id, topic, model, summary, key_points_json, entities_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                item_id,
                topic,
                self.model,
                summary_data.get('summary', ''),
                key_points_json,
                entities_json
            ))
            
            conn.commit()
            self.logger.debug(f"Saved summary for article {item_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving summary for article {item_id}: {e}")
            return False
        finally:
            conn.close()
    
    def summarize_articles(self, limit: int = 50) -> Dict[str, int]:
        """
        Summarize multiple articles.
        
        Args:
            limit: Maximum number of articles to process
            
        Returns:
            Results summary
        """
        results = {
            'processed': 0,
            'summarized': 0,
            'failed': 0,
            'avg_summary_length': 0
        }
        
        # Get articles to summarize
        articles = self.get_articles_to_summarize(limit)
        if not articles:
            self.logger.info("No articles found that need summarization")
            return results
        
        self.logger.info(f"Summarizing {len(articles)} articles")
        
        total_summary_length = 0
        
        for article in articles:
            self.logger.info(f"Summarizing: {article['title'][:100]}...")
            
            # Generate summary
            summary_data = self.summarize_article(
                content=article['extracted_text'],
                title=article['title'],
                url=article['url']
            )
            
            results['processed'] += 1
            
            if 'error' not in summary_data and summary_data.get('summary'):
                # Save summary
                if self.save_summary(article['id'], summary_data, article['topic']):
                    results['summarized'] += 1
                    total_summary_length += len(summary_data['summary'])
                    
                    self.logger.debug(f"Summary: {len(summary_data['summary'])} chars, "
                                    f"{len(summary_data.get('key_points', []))} key points")
            else:
                results['failed'] += 1
        
        # Calculate average summary length
        if results['summarized'] > 0:
            results['avg_summary_length'] = total_summary_length // results['summarized']
        
        self.logger.info(f"Summarization complete: {results}")
        return results
    
    def get_summarized_articles(self, topic: str | None = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get articles with summaries.
        
        Args:
            topic: Filter by topic
            limit: Maximum number to return
            
        Returns:
            List of articles with summaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        if topic:
            cursor = conn.execute("""
                SELECT i.id, i.url, i.title, i.source, i.published_at,
                       s.summary, s.key_points_json, s.entities_json, 
                       s.created_at as summarized_at
                FROM items i
                JOIN summaries s ON i.id = s.item_id
                WHERE i.is_match = 1 AND s.topic = ?
                ORDER BY i.triage_confidence DESC, s.created_at DESC
                LIMIT ?
            """, (topic, limit))
        else:
            cursor = conn.execute("""
                SELECT i.id, i.url, i.title, i.source, i.published_at,
                       s.topic, s.summary, s.key_points_json, s.entities_json,
                       s.created_at as summarized_at
                FROM items i
                JOIN summaries s ON i.id = s.item_id
                WHERE i.is_match = 1
                ORDER BY i.triage_confidence DESC, s.created_at DESC
                LIMIT ?
            """, (limit,))
        
        articles = []
        for row in cursor.fetchall():
            # Parse JSON fields
            key_points = json.loads(row['key_points_json']) if row['key_points_json'] else []
            entities = json.loads(row['entities_json']) if row['entities_json'] else {}
            
            articles.append({
                'id': row['id'],
                'url': row['url'],
                'title': row['title'],
                'source': row['source'],
                'published_at': row['published_at'],
                'topic': row.get('topic'),
                'summary': row['summary'],
                'key_points': key_points,
                'entities': entities,
                'summarized_at': row['summarized_at']
            })
        
        conn.close()
        return articles
    
    def extract_entities_by_category(self, topic: str | None = None) -> Dict[str, Dict[str, int]]:
        """
        Extract and count entities by category across all summaries.
        
        Args:
            topic: Filter by specific topic
            
        Returns:
            Dictionary with entity categories and counts
        """
        conn = sqlite3.connect(self.db_path)
        
        if topic:
            cursor = conn.execute("""
                SELECT entities_json FROM summaries WHERE topic = ?
            """, (topic,))
        else:
            cursor = conn.execute("SELECT entities_json FROM summaries")
        
        entity_counts = {}
        
        for row in cursor.fetchall():
            if row[0]:
                try:
                    entities = json.loads(row[0])
                    for category, entity_list in entities.items():
                        if category not in entity_counts:
                            entity_counts[category] = {}
                        
                        for entity in entity_list:
                            if entity in entity_counts[category]:
                                entity_counts[category][entity] += 1
                            else:
                                entity_counts[category][entity] = 1
                                
                except json.JSONDecodeError:
                    continue
        
        conn.close()
        
        # Sort entities by count within each category
        for category in entity_counts:
            entity_counts[category] = dict(
                sorted(entity_counts[category].items(), 
                      key=lambda x: x[1], reverse=True)
            )
        
        return entity_counts
    
    def get_summarization_stats(self) -> Dict[str, Any]:
        """Get summarization statistics."""
        conn = sqlite3.connect(self.db_path)
        
        # Total articles with extracted content
        cursor = conn.execute("SELECT COUNT(*) FROM articles")
        extracted_total = cursor.fetchone()[0]
        
        # Articles with summaries
        cursor = conn.execute("SELECT COUNT(*) FROM summaries")
        summarized_total = cursor.fetchone()[0]
        
        # Average summary length
        cursor = conn.execute("SELECT AVG(LENGTH(summary)) FROM summaries")
        avg_length = cursor.fetchone()[0] or 0
        
        # By topic
        cursor = conn.execute("""
            SELECT topic, COUNT(*) as count, AVG(LENGTH(summary)) as avg_length
            FROM summaries 
            GROUP BY topic
        """)
        
        by_topic = {}
        for row in cursor.fetchall():
            by_topic[row[0]] = {
                'count': row[1],
                'avg_summary_length': int(row[2]) if row[2] else 0
            }
        
        conn.close()
        
        return {
            'extracted_articles': extracted_total,
            'summarized_articles': summarized_total,
            'summarization_rate': summarized_total / extracted_total if extracted_total > 0 else 0,
            'avg_summary_length': int(avg_length),
            'by_topic': by_topic
        }
