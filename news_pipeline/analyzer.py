"""
MetaAnalyzer - Step 5: Meta-Summary Generation

Aggregate intelligence using MODEL_FULL for comprehensive topic analysis.
"""

import os
import json
import sqlite3
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

from openai import OpenAI

from news_pipeline.language_config import get_language_config
from .paths import config_path, safe_open, output_path


class MetaAnalyzer:
    """Aggregate analysis and meta-summary generation using MODEL_FULL."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.client = OpenAI()
        self.model = os.getenv("MODEL_FULL", "gpt-5")
        self.language = os.getenv("PIPELINE_LANGUAGE", "en")
        self.lang_config = get_language_config()
        
        self.logger = logging.getLogger(__name__)
    
    def get_recent_summaries(self, topic: str, days: int = 1, limit: int = 50, 
                             run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get summaries, optionally filtered by pipeline run."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # For daily digest (days=1), use start of current calendar day instead of rolling 24-hour window
        # This prevents cross-contamination from previous days and ensures all current day articles are included
        if days == 1:
            cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        else:
            # For weekly/other periods, use the original rolling window logic
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        if run_id:
            # Only summaries from this pipeline run
            cursor = conn.execute("""
                SELECT i.id, i.url, i.title, i.source, i.published_at,
                       s.summary, s.key_points_json, s.entities_json
                FROM items i
                JOIN summaries s ON i.id = s.item_id
                WHERE s.topic = ? 
                AND i.pipeline_run_id = ?
                AND (i.published_at >= ? OR s.created_at >= ?)
                AND COALESCE(s.topic_already_covered, 0) = 0
                ORDER BY i.selection_rank, i.triage_confidence DESC
                LIMIT ?
            """, (topic, run_id, cutoff_date, cutoff_date, limit))
        else:
            # Original query for all summaries
            cursor = conn.execute("""
                SELECT i.id, i.url, i.title, i.source, i.published_at,
                       s.summary, s.key_points_json, s.entities_json
                FROM items i
                JOIN summaries s ON i.id = s.item_id
                LEFT JOIN article_clusters ac ON i.id = ac.article_id
                WHERE s.topic = ? 
                AND (i.published_at >= ? OR s.created_at >= ?)
                AND COALESCE(s.topic_already_covered, 0) = 0
                AND (ac.is_primary = 1 OR ac.article_id IS NULL)
                ORDER BY i.triage_confidence DESC, s.created_at DESC
                LIMIT ?
            """, (topic, cutoff_date, cutoff_date, limit))
        
        summaries = []
        for row in cursor.fetchall():
            # Parse JSON fields
            key_points = json.loads(row['key_points_json']) if row['key_points_json'] else []
            entities = json.loads(row['entities_json']) if row['entities_json'] else {}
            
            summaries.append({
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
        return summaries
    
    def generate_topic_digest(self, topic: str, summaries: List[Dict[str, Any]], 
                            date_range: str = "today") -> Dict[str, Any]:
        """
        Generate a meta-summary digest for a topic.
        
        Args:
            topic: Topic name
            summaries: List of individual article summaries
            date_range: Description of time period (e.g., "today", "this week")
            
        Returns:
            Digest with headline, why_it_matters, bullets, and sources
        """
        try:
            if not summaries:
                return {
                    'topic': topic,
                    'date_range': date_range,
                    'headline': f'No recent {topic} news found',
                    'why_it_matters': 'No significant developments to report.',
                    'bullets': [],
                    'sources': [],
                    'article_count': 0
                }
            
            # Build system prompt
            system_prompt = self.lang_config.get_topic_digest_prompt(topic)
            
            # Prepare input data
            input_data = {
                'topic': topic,
                'date_range': date_range,
                'article_count': len(summaries),
                'articles': []
            }
            
            for summary in summaries:
                input_data['articles'].append({
                    'title': summary['title'],
                    'url': summary['url'],
                    'source': summary['source'],
                    'summary': summary['summary'],
                    'key_points': summary['key_points'][:3]  # Top 3 points only
                })
            
            # Define response schema
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
                        "name": "topic_digest",
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
                'date_range': date_range,
                'article_count': len(summaries),
                'generated_at': datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating digest for {topic}: {e}")
            return {
                'topic': topic,
                'date_range': date_range,
                'headline': f'Digest generation failed for {topic}',
                'why_it_matters': 'Technical error prevented analysis.',
                'bullets': [f'Error: {str(e)[:100]}'],
                'sources': [s['url'] for s in summaries[:5]],
                'article_count': len(summaries),
                'error': str(e)[:200]
            }
    
    def generate_daily_digests(self, topics: List[str] | None = None) -> Dict[str, Dict[str, Any]]:
        """
        Generate daily digest reports for topics.
        
        Args:
            topics: List of topics to analyze, or None for enabled topics only
            
        Returns:
            Dictionary with topic digests
        """
        results = {}
        
        # Get enabled topics if not specified
        if topics is None:
            # Load topics configuration to get only enabled topics
            import yaml
            try:
                topics_config_path = config_path('topics.yaml')
                with safe_open(topics_config_path, 'r', encoding='utf-8') as f:
                    topics_config = yaml.safe_load(f)
                
                # Get only enabled topics
                topics = [name for name, config in topics_config['topics'].items() 
                         if config.get('enabled', True)]
                
                if not topics:
                    self.logger.warning("No enabled topics found in topics.yaml")
                    return {}
                
            except FileNotFoundError:
                self.logger.warning("topics.yaml not found, querying database directly")
                conn = sqlite3.connect(self.db_path)
                cursor = conn.execute("SELECT DISTINCT topic FROM summaries")
                topics = [row[0] for row in cursor.fetchall()]
                conn.close()
        
        self.logger.info(f"Generating daily digests for {len(topics)} topics")
        
        for topic in topics:
            self.logger.info(f"Analyzing topic: {topic}")
            
            # Get recent summaries
            summaries = self.get_recent_summaries(topic, days=1)
            
            # Generate digest
            digest = self.generate_topic_digest(topic, summaries, "today")
            results[topic] = digest
            
            self.logger.debug(f"{topic}: {digest['article_count']} articles, "
                            f"headline: {digest['headline'][:100]}")
        
        return results
    
    def generate_weekly_digests(self, topics: List[str] | None = None) -> Dict[str, Dict[str, Any]]:
        """
        Generate weekly digest reports for topics.
        
        Args:
            topics: List of topics to analyze, or None for all topics
            
        Returns:
            Dictionary with topic digests
        """
        results = {}
        
        # Get available topics if not specified
        if topics is None:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT DISTINCT topic FROM summaries")
            topics = [row[0] for row in cursor.fetchall()]
            conn.close()
        
        self.logger.info(f"Generating weekly digests for {len(topics)} topics")
        
        for topic in topics:
            self.logger.info(f"Analyzing topic: {topic}")
            
            # Get recent summaries
            summaries = self.get_recent_summaries(topic, days=7, limit=100)
            
            # Generate digest
            digest = self.generate_topic_digest(topic, summaries, "this week")
            results[topic] = digest
            
            self.logger.debug(f"{topic}: {digest['article_count']} articles, "
                            f"headline: {digest['headline'][:100]}")
        
        return results
    
    def identify_trending_topics(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Identify trending topics based on recent article volume and entity mentions.
        Only includes enabled topics from configuration.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            List of trending topics with metrics
        """
        # Get enabled topics from configuration
        import yaml
        enabled_topics = []
        try:
            topics_config_path = config_path('topics.yaml')
            with safe_open(topics_config_path, 'r', encoding='utf-8') as f:
                topics_config = yaml.safe_load(f)
            
            enabled_topics = [name for name, config in topics_config['topics'].items() 
                             if config.get('enabled', True)]
        except FileNotFoundError:
            self.logger.warning("topics.yaml not found for trending analysis")
        
        if not enabled_topics:
            return []
        
        conn = sqlite3.connect(self.db_path)
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Create placeholders for enabled topics
        placeholders = ','.join('?' * len(enabled_topics))
        
        # Get article counts by topic, filtered to enabled topics only
        cursor = conn.execute(f"""
            SELECT s.topic, 
                   COUNT(*) as article_count,
                   AVG(i.triage_confidence) as avg_confidence,
                   COUNT(DISTINCT i.source) as source_count
            FROM summaries s
            JOIN items i ON s.item_id = i.id
            WHERE s.created_at >= ? 
            AND s.topic IN ({placeholders})
            GROUP BY s.topic
            HAVING article_count >= 3
            ORDER BY article_count DESC, avg_confidence DESC
        """, [cutoff_date] + enabled_topics)
        
        trending = []
        for row in cursor.fetchall():
            trending.append({
                'topic': row[0],
                'article_count': row[1],
                'avg_confidence': round(row[2], 3),
                'source_diversity': row[3],
                'trend_score': row[1] * row[2]  # Simple trending score
            })
        
        conn.close()
        
        # Sort by trend score
        trending.sort(key=lambda x: x['trend_score'], reverse=True)
        
        return trending[:10]  # Top 10 trending topics
    
    def export_daily_digest(self, output_file_path: str | None = None, format: str = "json", run_id: str | None = None) -> str:
        """
        Export daily digest to JSON file. Always generates German rating agency report automatically.
        Note: Markdown format has been disabled as the German rating report serves as the final output.
        
        Args:
            output_file_path: Output file path
            format: Export format (only "json" supported, markdown disabled)
            run_id: Optional pipeline run ID to filter summaries
            
        Returns:
            Path to exported file
        """
        # Force JSON format since markdown generation is disabled
        if format != "json":
            self.logger.warning(f"Format '{format}' not supported. Markdown generation disabled - using JSON format.")
            format = "json"
        
        # Check if there are any summaries to process BEFORE doing expensive operations
        conn = sqlite3.connect(self.db_path)
        
        if run_id:
            # Check for summaries from this specific pipeline run
            cursor = conn.execute("""
                SELECT COUNT(*) FROM summaries s
                JOIN items i ON s.item_id = i.id
                WHERE i.pipeline_run_id = ?
            """, (run_id,))
        else:
            # Check for summaries from today
            cutoff_date = (datetime.now() - timedelta(days=1)).isoformat()
            cursor = conn.execute("""
                SELECT COUNT(*) FROM summaries s
                JOIN items i ON s.item_id = i.id
                WHERE i.published_at >= ? OR s.created_at >= ?
            """, (cutoff_date, cutoff_date))
        
        summary_count = cursor.fetchone()[0]
        conn.close()
        
        if summary_count == 0:
            self.logger.info("No articles found with summaries - skipping digest and report generation")
            self.logger.info("Daily digest and German rating report creation skipped (0 articles selected and 0 scraped)")
            
            # Return a placeholder path to maintain API compatibility
            date_str = datetime.now().strftime('%Y-%m-%d')
            placeholder_path = f"out/digests/daily_digest_{date_str}.json"
            return placeholder_path
        
        # Generate fresh daily digests with summaries data
        digests = self.generate_daily_digests()
        
        # Determine output path using proper path utilities
        if output_file_path is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
            digest_output_path = str(output_path('digests', f'daily_digest_{date_str}.json'))
        else:
            digest_output_path = output_file_path
        
        # Ensure directory exists
        dir_path = os.path.dirname(digest_output_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        # Check if file exists for today and preserve original creation time
        original_created_at = None
        if os.path.exists(digest_output_path):
            try:
                with open(digest_output_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    # Preserve the original creation time from first run
                    if 'created_at' in existing_data:
                        original_created_at = existing_data['created_at']
                    elif 'generated_at' in existing_data:
                        original_created_at = existing_data['generated_at']
                self.logger.info(f"Updating existing digest for today (originally created: {original_created_at})")
            except Exception as e:
                self.logger.warning(f"Could not read existing digest file: {e}, creating new one")
                original_created_at = None
        
        # Get trending topics
        trending = self.identify_trending_topics(days=7)
        
        # Calculate total articles across all digests
        total_articles = sum(d.get('article_count', 0) for d in digests.values())
        
        # Combine all data with proper timestamps
        current_time = datetime.now().isoformat()
        export_data = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'created_at': original_created_at or current_time,  # Preserve original creation time
            'generated_at': current_time,  # Always update this to current time
            'total_articles': total_articles,  # Total count for metadata
            'trending_topics': trending,
            'topic_digests': digests
        }
        
        # Add update indicator if this is an update
        if original_created_at:
            export_data['updated'] = True
            export_data['last_updated'] = current_time
        
        # Export as JSON
        with open(digest_output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        action = "Updated" if original_created_at else "Created"
        self.logger.info(f"{action} daily digest: {digest_output_path}")
        
        # Auto-generate German rating report (this is the final desired output)
        try:
            from news_pipeline.german_rating_formatter import format_daily_digest_to_german_markdown
            german_report_path = format_daily_digest_to_german_markdown(digest_output_path)
            self.logger.info(f"Auto-generated German rating report: {german_report_path}")
        except Exception as e:
            self.logger.warning(f"Failed to generate German rating report: {e}")
        
        return digest_output_path
