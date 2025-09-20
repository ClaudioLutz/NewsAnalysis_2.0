"""
MetaAnalyzer - Step 5: Meta-Summary Generation

Aggregate intelligence using MODEL_MINI for comprehensive topic analysis.
"""

import os
import json
import sqlite3
from typing import List, Dict, Any
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

from openai import OpenAI


class MetaAnalyzer:
    """Aggregate analysis and meta-summary generation using MODEL_MINI."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.client = OpenAI()
        self.model = os.getenv("MODEL_MINI", "gpt-5-mini")
        
        self.logger = logging.getLogger(__name__)
    
    def get_recent_summaries(self, topic: str, days: int = 1, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent article summaries for a topic.
        
        Args:
            topic: Topic to analyze
            days: Number of days back to look
            limit: Maximum number of summaries
            
        Returns:
            List of article summaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Calculate date threshold
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor = conn.execute("""
            SELECT i.id, i.url, i.title, i.source, i.published_at,
                   s.summary, s.key_points_json, s.entities_json
            FROM items i
            JOIN summaries s ON i.id = s.item_id
            LEFT JOIN article_clusters ac ON i.id = ac.article_id
            WHERE s.topic = ? 
            AND (i.published_at >= ? OR s.created_at >= ?)
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
            system_prompt = f"""You are a senior Swiss business analyst creating executive briefings.

Create a comprehensive digest of {topic} news for {date_range}.

Analyze the provided article summaries and create:
- headline: Compelling 1-2 sentence headline capturing the main story/trend
- why_it_matters: 2-3 sentences explaining business impact and significance
- bullets: 4-6 key bullet points with specific insights, numbers, and implications
- sources: List of article URLs for reference

Focus on:
1. Major trends and patterns across articles
2. Business and financial implications
3. Key stakeholders and market impacts
4. Strategic significance for Swiss economy
5. Forward-looking insights and implications

Be analytical, concise, and executive-focused. Synthesize rather than just summarize."""
            
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
                    "bullets": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
                    "sources": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["headline", "why_it_matters", "bullets", "sources"],
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
        
        Args:
            days: Number of days to analyze
            
        Returns:
            List of trending topics with metrics
        """
        conn = sqlite3.connect(self.db_path)
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Get article counts by topic
        cursor = conn.execute("""
            SELECT s.topic, 
                   COUNT(*) as article_count,
                   AVG(i.triage_confidence) as avg_confidence,
                   COUNT(DISTINCT i.source) as source_count
            FROM summaries s
            JOIN items i ON s.item_id = i.id
            WHERE s.created_at >= ?
            GROUP BY s.topic
            HAVING article_count >= 3
            ORDER BY article_count DESC, avg_confidence DESC
        """, (cutoff_date,))
        
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
    
    def create_executive_summary(self, digests: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create an executive summary across all topic digests.
        
        Args:
            digests: Dictionary of topic digests
            
        Returns:
            Executive summary with top insights
        """
        try:
            if not digests:
                return {
                    'headline': 'No recent news activity',
                    'executive_summary': 'No significant developments to report.',
                    'key_themes': [],
                    'total_articles': 0
                }
            
            system_prompt = """You are a C-level executive briefing analyst.

Create an executive summary from multiple topic digests covering Swiss business news.

Provide:
- headline: Single compelling headline for the day/period
- executive_summary: 3-4 sentences with the most critical insights
- key_themes: 3-5 major themes/patterns across all topics
- top_priorities: 2-3 items requiring executive attention

Focus on strategic implications, cross-topic patterns, and actionable insights."""
            
            # Prepare input
            input_data = {
                'total_topics': len(digests),
                'total_articles': sum(d.get('article_count', 0) for d in digests.values()),
                'digests': {}
            }
            
            for topic, digest in digests.items():
                input_data['digests'][topic] = {
                    'headline': digest.get('headline', ''),
                    'why_it_matters': digest.get('why_it_matters', ''),
                    'bullets': digest.get('bullets', [])[:3],  # Top 3 bullets
                    'article_count': digest.get('article_count', 0)
                }
            
            response_schema = {
                "type": "object",
                "properties": {
                    "headline": {"type": "string"},
                    "executive_summary": {"type": "string"},
                    "key_themes": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                    "top_priorities": {"type": "array", "items": {"type": "string"}, "maxItems": 3}
                },
                "required": ["headline", "executive_summary", "key_themes", "top_priorities"],
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
                        "name": "executive_summary",
                        "schema": response_schema,
                        "strict": True
                    }
                }
            )
            
            response_content = response.choices[0].message.content
            if response_content is None:
                raise ValueError("OpenAI response content is None")
            
            result = json.loads(response_content)
            result.update({
                'total_articles': input_data['total_articles'],
                'total_topics': input_data['total_topics'],
                'generated_at': datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error creating executive summary: {e}")
            return {
                'headline': 'Executive summary generation failed',
                'executive_summary': f'Technical error: {str(e)[:100]}',
                'key_themes': [],
                'top_priorities': [],
                'total_articles': sum(d.get('article_count', 0) for d in digests.values()),
                'error': str(e)[:200]
            }
    
    def export_daily_digest(self, output_path: str | None = None, format: str = "json") -> str:
        """
        Export daily digest to file. If file exists for today, update with accumulated data.
        Also generates German rating agency report automatically.
        
        Args:
            output_path: Output file path
            format: Export format ("json" or "markdown")
            
        Returns:
            Path to exported file
        """
        # Determine output path
        if output_path is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
            output_path = f"out/digests/daily_digest_{date_str}.{format}"
        
        # Ensure directory exists
        dir_path = os.path.dirname(output_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        # Check if file exists for today and preserve original creation time
        original_created_at = None
        if os.path.exists(output_path) and format == "json":
            try:
                with open(output_path, 'r', encoding='utf-8') as f:
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
        
        # Generate fresh daily digests with ALL of today's data
        digests = self.generate_daily_digests()
        
        # Create executive summary
        executive = self.create_executive_summary(digests)
        
        # Get trending topics
        trending = self.identify_trending_topics(days=7)
        
        # Combine all data with proper timestamps
        current_time = datetime.now().isoformat()
        export_data = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'created_at': original_created_at or current_time,  # Preserve original creation time
            'generated_at': current_time,  # Always update this to current time
            'executive_summary': executive,
            'trending_topics': trending,
            'topic_digests': digests
        }
        
        # Add update indicator if this is an update
        if original_created_at:
            export_data['updated'] = True
            export_data['last_updated'] = current_time
        
        if format == "json":
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        elif format == "markdown":
            with open(output_path, 'w', encoding='utf-8') as f:
                self._write_markdown_digest(f, export_data)
        
        action = "Updated" if original_created_at else "Created"
        self.logger.info(f"{action} daily digest: {output_path}")
        
        # Auto-generate German rating report after JSON export
        if format == "json":
            try:
                from news_pipeline.german_rating_formatter import format_daily_digest_to_german_markdown
                german_report_path = format_daily_digest_to_german_markdown(output_path)
                self.logger.info(f"Auto-generated German rating report: {german_report_path}")
            except Exception as e:
                self.logger.warning(f"Failed to generate German rating report: {e}")
        
        return output_path
    
    def _write_markdown_digest(self, file, data: Dict[str, Any]):
        """Write digest data in markdown format."""
        file.write(f"# Swiss Business News Digest - {data['date']}\n\n")
        
        # Executive Summary
        exec_summary = data['executive_summary']
        file.write("## Executive Summary\n\n")
        file.write(f"**{exec_summary['headline']}**\n\n")
        file.write(f"{exec_summary['executive_summary']}\n\n")
        
        if exec_summary.get('key_themes'):
            file.write("### Key Themes\n\n")
            for theme in exec_summary['key_themes']:
                file.write(f"- {theme}\n")
            file.write("\n")
        
        # Trending Topics
        if data['trending_topics']:
            file.write("## Trending Topics\n\n")
            for i, topic in enumerate(data['trending_topics'][:5], 1):
                file.write(f"{i}. **{topic['topic']}** ({topic['article_count']} articles, "
                          f"confidence: {topic['avg_confidence']:.2f})\n")
            file.write("\n")
        
        # Topic Digests
        file.write("## Topic Analysis\n\n")
        for topic, digest in data['topic_digests'].items():
            file.write(f"### {topic.replace('_', ' ').title()}\n\n")
            file.write(f"**{digest['headline']}**\n\n")
            file.write(f"{digest['why_it_matters']}\n\n")
            
            if digest.get('bullets'):
                file.write("**Key Points:**\n\n")
                for bullet in digest['bullets']:
                    file.write(f"- {bullet}\n")
                file.write("\n")
            
            file.write(f"*Based on {digest['article_count']} articles*\n\n")
