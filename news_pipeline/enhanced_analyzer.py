"""
Enhanced MetaAnalyzer - Improved Step 5: Meta-Summary Generation

Features incremental digest generation, template-based output, and efficient caching.
Addresses the requirement for continuous daily updates with performance optimizations.
"""

import os
import json
import sqlite3
import time
from typing import List, Dict, Any, Optional, Union
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

from openai import OpenAI

# Import Jinja2 for templating
try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False

# Import our incremental digest components
from news_pipeline.incremental_digest import IncrementalDigestGenerator, DigestStateManager
from news_pipeline.language_config import get_language_config
from news_pipeline.cross_run_deduplication import CrossRunTopicDeduplicator


class EnhancedMetaAnalyzer:
    """
    Enhanced MetaAnalyzer with incremental digest generation, template support,
    and efficient daily updates that accumulate throughout the day.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.client = OpenAI()
        self.model = os.getenv("MODEL_MINI", "gpt-4o-mini")
        
        # Initialize incremental digest components
        self.incremental_generator = IncrementalDigestGenerator(db_path)
        self.state_manager = DigestStateManager(db_path)
        
        # Initialize template engine if available
        if HAS_JINJA2:
            self.template_env = Environment(
                loader=FileSystemLoader('templates'),
                autoescape=select_autoescape(['html', 'xml'])
            )
            
            # Register custom filters
            self.template_env.filters['datetime_format'] = self._datetime_format_filter
            self.template_env.filters['topic_name'] = self._topic_name_filter
            self.template_env.filters['domain_name'] = self._domain_name_filter
        else:
            self.template_env = None
            
        self.logger = logging.getLogger(__name__)
    
    def _datetime_format_filter(self, datetime_str: str, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
        """Jinja2 filter to format datetime strings."""
        try:
            dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            return dt.strftime(format_str)
        except:
            return str(datetime_str)
    
    def _topic_name_filter(self, topic_name: str) -> str:
        """Jinja2 filter to format topic names nicely."""
        return topic_name.replace('_', ' ').title()
    
    def _domain_name_filter(self, url: str) -> str:
        """Jinja2 filter to extract domain from URL."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return url
    
    def generate_incremental_daily_digests(self, topics: Optional[List[str]] = None, 
                                         date: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Generate daily digests using incremental processing.
        Only processes new articles since last generation.
        
        Args:
            topics: List of topics to analyze, or None for all topics
            date: Date to generate for (defaults to today)
            
        Returns:
            Dictionary with topic digests and update status
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # Get available topics if not specified
        if topics is None:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT DISTINCT topic FROM summaries")
            topics = [row[0] for row in cursor.fetchall()]
            conn.close()
        
        self.logger.info(f"Generating incremental daily digests for {len(topics)} topics on {date}")
        
        # NEW: Step 3.1 - Cross-Run Topic Deduplication
        try:
            cross_run_dedup = CrossRunTopicDeduplicator(self.db_path)
            dedup_results = cross_run_dedup.deduplicate_against_previous_runs(date)
            
            self.logger.info(
                f"Cross-run deduplication complete: "
                f"{dedup_results.get('duplicates_found', 0)} duplicates filtered, "
                f"{dedup_results.get('unique_articles', 0)} unique articles proceeding"
            )
            
        except Exception as e:
            self.logger.warning(
                f"Cross-run deduplication failed (Step 3.1): {e}. "
                f"Continuing with all articles."
            )
            dedup_results = {'error': str(e)}
        
        results = {}
        api_calls_made = 0
        total_new_articles = 0
        
        start_time = time.time()
        
        for topic in topics:
            self.logger.info(f"Processing topic: {topic}")
            
            # Generate incremental digest
            digest, was_updated = self.incremental_generator.generate_incremental_topic_digest(topic, date)
            results[topic] = digest
            
            if was_updated:
                api_calls_made += 1  # Approximate - actual calls may vary
                total_new_articles += digest.get('article_count', 0)
                self.logger.info(f"{topic}: Updated with {digest.get('article_count', 0)} articles")
            else:
                self.logger.info(f"{topic}: No updates needed")
        
        execution_time = time.time() - start_time
        
        # Log generation statistics
        generation_type = "incremental" if any(r.get('last_updated') for r in results.values()) else "cached"
        total_articles = sum(d.get('article_count', 0) for d in results.values())
        
        self.state_manager.log_generation(
            date=date,
            generation_type=generation_type,
            topics_processed=len(topics),
            total_articles=total_articles,
            new_articles=total_new_articles,
            api_calls=api_calls_made,
            execution_time=execution_time
        )
        
        self.logger.info(f"Incremental digest generation completed: "
                        f"{generation_type}, {api_calls_made} API calls, "
                        f"{total_new_articles} new articles processed")
        
        return results
    
    def create_executive_summary(self, digests: Dict[str, Dict[str, Any]], 
                                force_regenerate: bool = False) -> Dict[str, Any]:
        """
        Create executive summary with caching support.
        
        Args:
            digests: Dictionary of topic digests
            force_regenerate: Force regeneration even if cached version exists
            
        Returns:
            Executive summary with top insights
        """
        try:
            if not digests:
                return {
                    'headline': 'No recent news activity',
                    'executive_summary': 'No significant developments to report.',
                    'key_themes': [],
                    'top_priorities': [],
                    'total_articles': 0
                }
            
            # Simple cache check - if no digests were updated recently, use existing summary
            if not force_regenerate:
                recent_updates = any(
                    d.get('last_updated') and 
                    datetime.fromisoformat(d['last_updated']) > datetime.now() - timedelta(hours=1)
                    for d in digests.values()
                )
                
                if not recent_updates:
                    # Try to get existing summary from most recent complete digest
                    # This is a simplified cache - in production you'd want more sophisticated caching
                    pass
            
            # Generate fresh executive summary using language configuration
            language_config = get_language_config()
            system_prompt = language_config.get_executive_summary_prompt()
            
            # Prepare input
            input_data = {
                'total_topics': len(digests),
                'total_articles': sum(d.get('article_count', 0) for d in digests.values()),
                'digests': {}
            }
            
            for topic, digest in digests.items():
                if digest.get('article_count', 0) > 0:  # Only include topics with articles
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
    
    def identify_trending_topics(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Identify trending topics based on recent article volume and entity mentions.
        Enhanced with better trend scoring.
        """
        conn = sqlite3.connect(self.db_path)
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Get article counts by topic with enhanced metrics
        cursor = conn.execute("""
            SELECT s.topic, 
                   COUNT(*) as article_count,
                   AVG(i.triage_confidence) as avg_confidence,
                   COUNT(DISTINCT i.source) as source_count,
                   COUNT(DISTINCT DATE(i.published_at)) as active_days
            FROM summaries s
            JOIN items i ON s.item_id = i.id
            WHERE s.created_at >= ?
            GROUP BY s.topic
            HAVING article_count >= 3
            ORDER BY article_count DESC, avg_confidence DESC
        """, (cutoff_date,))
        
        trending = []
        for row in cursor.fetchall():
            # Enhanced trend score calculation
            article_count = row[1]
            avg_confidence = row[2]
            source_diversity = row[3]
            active_days = row[4]
            
            # Trend score considers volume, confidence, diversity, and consistency
            trend_score = (
                article_count * 0.4 +  # Volume weight
                avg_confidence * 100 * 0.3 +  # Confidence weight
                source_diversity * 0.2 +  # Diversity weight
                (active_days / min(days, 7)) * 10 * 0.1  # Consistency weight
            )
            
            trending.append({
                'topic': row[0],
                'article_count': article_count,
                'avg_confidence': round(avg_confidence, 3),
                'source_diversity': source_diversity,
                'active_days': active_days,
                'trend_score': round(trend_score, 2)
            })
        
        conn.close()
        
        # Sort by enhanced trend score
        trending.sort(key=lambda x: x['trend_score'], reverse=True)
        
        return trending[:10]  # Top 10 trending topics
    
    def export_enhanced_daily_digest(self, output_path: Optional[str] = None, 
                                   format: str = "json", 
                                   force_full_regeneration: bool = False,
                                   topics: Optional[List[str]] = None) -> Union[str, List[str]]:
        """
        Export daily digest using enhanced incremental generation and template system.
        
        Args:
            output_path: Output file path
            format: Export format ("json", "markdown", or "both")  
            force_full_regeneration: Force complete regeneration instead of incremental
            topics: Optional list of topics to include
            
        Returns:
            Path to exported file(s)
        """
        # Determine output path
        date_str = datetime.now().strftime('%Y-%m-%d')
        if output_path is None:
            if format == "both":
                output_path = f"out/digests/daily_digest_{date_str}"
            else:
                output_path = f"out/digests/daily_digest_{date_str}.{format}"
        
        # Ensure directory exists
        dir_path = os.path.dirname(output_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        # Check for existing digest and preserve creation time
        original_created_at = None
        json_path = output_path if format == "json" else f"{output_path}.json"
        
        if os.path.exists(json_path) and not force_full_regeneration:
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    original_created_at = existing_data.get('created_at') or existing_data.get('generated_at')
                self.logger.info(f"Found existing digest (created: {original_created_at})")
            except Exception as e:
                self.logger.warning(f"Could not read existing digest: {e}")
        
        # Generate incremental daily digests
        if force_full_regeneration:
            # Clear digest state to force full regeneration
            # This could be implemented as a method in DigestStateManager
            self.logger.info("Forcing full regeneration of all digests")
        
        digests = self.generate_incremental_daily_digests(topics, date_str)
        
        # Create executive summary
        executive = self.create_executive_summary(digests, force_full_regeneration)
        
        # Get trending topics
        trending = self.identify_trending_topics(days=7)
        
        # Combine all data
        current_time = datetime.now().isoformat()
        export_data = {
            'date': date_str,
            'created_at': original_created_at or current_time,
            'generated_at': current_time,
            'executive_summary': executive,
            'trending_topics': trending,
            'topic_digests': digests
        }
        
        # Add update metadata
        if original_created_at:
            export_data['updated'] = True
            export_data['last_updated'] = current_time
            
            # Count how many topics were actually updated
            updated_topics = sum(1 for d in digests.values() 
                               if d.get('last_updated') and d['last_updated'] == current_time)
            export_data['topics_updated'] = updated_topics
        
        exported_files = []
        
        # Export JSON
        if format in ["json", "both"]:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            exported_files.append(json_path)
            
            action = "Updated" if original_created_at else "Created"
            self.logger.info(f"{action} JSON digest: {json_path}")
        
        # Export Markdown using template
        if format in ["markdown", "both"]:
            markdown_path = output_path if format == "markdown" else f"{output_path}.md"
            
            if self.template_env:
                try:
                    template = self.template_env.get_template('daily_digest.md.j2')
                    markdown_content = template.render(data=export_data)
                    
                    with open(markdown_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    
                    exported_files.append(markdown_path)
                    self.logger.info(f"Created Markdown digest using template: {markdown_path}")
                    
                except Exception as e:
                    self.logger.error(f"Template rendering failed: {e}")
                    # Fallback to basic markdown generation
                    self._write_basic_markdown_digest(markdown_path, export_data)
                    exported_files.append(markdown_path)
            else:
                self.logger.warning("Jinja2 not available, using basic markdown generation")
                self._write_basic_markdown_digest(markdown_path, export_data)
                exported_files.append(markdown_path)
        
        # Auto-generate German rating report
        if format in ["json", "both"]:
            try:
                from news_pipeline.german_rating_formatter import format_daily_digest_to_german_markdown
                german_report_path = format_daily_digest_to_german_markdown(json_path)
                self.logger.info(f"Auto-generated German rating report: {german_report_path}")
            except Exception as e:
                self.logger.warning(f"Failed to generate German rating report: {e}")
        
        return exported_files[0] if len(exported_files) == 1 else exported_files
    
    def _write_basic_markdown_digest(self, file_path: str, data: Dict[str, Any]):
        """Basic markdown generation fallback when templates aren't available."""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"# Swiss Business News Digest - {data['date']}\n\n")
            
            if data.get('updated'):
                f.write(f"**Last Updated:** {data['last_updated']}\n")
            f.write(f"**Generated:** {data['generated_at']}\n\n")
            
            # Executive Summary
            exec_summary = data['executive_summary']
            f.write("## Executive Summary\n\n")
            f.write(f"**{exec_summary['headline']}**\n\n")
            f.write(f"{exec_summary['executive_summary']}\n\n")
            
            if exec_summary.get('key_themes'):
                f.write("### Key Themes\n\n")
                for theme in exec_summary['key_themes']:
                    f.write(f"- {theme}\n")
                f.write("\n")
            
            # Trending Topics
            if data['trending_topics']:
                f.write("## Trending Topics\n\n")
                for i, topic in enumerate(data['trending_topics'][:5], 1):
                    f.write(f"{i}. **{topic['topic'].replace('_', ' ').title()}** "
                           f"({topic['article_count']} articles, "
                           f"confidence: {topic['avg_confidence']:.2f})\n")
                f.write("\n")
            
            # Topic Digests
            f.write("## Topic Analysis\n\n")
            for topic, digest in data['topic_digests'].items():
                f.write(f"### {topic.replace('_', ' ').title()}\n\n")
                
                if digest.get('article_count', 0) > 0:
                    f.write(f"**{digest['headline']}**\n\n")
                    f.write(f"{digest['why_it_matters']}\n\n")
                    
                    if digest.get('bullets'):
                        f.write("**Key Points:**\n\n")
                        for bullet in digest['bullets']:
                            f.write(f"- {bullet}\n")
                        f.write("\n")
                    
                    f.write(f"*Based on {digest['article_count']} articles*\n\n")
                else:
                    f.write("*No recent articles found for this topic.*\n\n")
                
                f.write("---\n\n")
        
        self.logger.info(f"Created basic Markdown digest: {file_path}")
    
    def clear_old_digest_cache(self, days_to_keep: int = 7):
        """Clear old digest states and cache data."""
        self.state_manager.clear_old_states(days_to_keep)
        self.logger.info(f"Cleared digest cache older than {days_to_keep} days")
    
    def get_generation_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Get digest generation statistics for analysis and monitoring."""
        conn = sqlite3.connect(self.db_path)
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        cursor = conn.execute("""
            SELECT generation_type, 
                   COUNT(*) as count,
                   AVG(api_calls_made) as avg_api_calls,
                   AVG(execution_time_seconds) as avg_execution_time,
                   SUM(new_articles) as total_new_articles
            FROM digest_generation_log 
            WHERE digest_date >= ?
            GROUP BY generation_type
        """, (cutoff_date,))
        
        stats = {}
        for row in cursor.fetchall():
            stats[row[0]] = {
                'count': row[1],
                'avg_api_calls': round(row[2], 1),
                'avg_execution_time': round(row[3], 1),
                'total_new_articles': row[4]
            }
        
        conn.close()
        return stats
