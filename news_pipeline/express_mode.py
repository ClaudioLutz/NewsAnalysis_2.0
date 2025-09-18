"""
Express Mode Pipeline - Phase 6: Fast-Track Mode

Delivers quick daily insights in under 3 minutes by skipping intensive
processing steps and focusing on the most relevant, recent articles.
"""

import os
import json
import sqlite3
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import time

from .utils import log_step_start, log_step_complete, format_number, format_rate
from .filter import AIFilter
from .deduplication import ArticleDeduplicator
from .state_manager import PipelineStateManager, StepContext


class ExpressPipeline:
    """Fast-track news analysis pipeline for daily insights."""
    
    def __init__(self, db_path: str, topics_config_path: str = "config/topics.yaml"):
        self.db_path = db_path
        self.topics_config_path = topics_config_path
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.ai_filter = AIFilter(db_path, topics_config_path)
        self.deduplicator = ArticleDeduplicator(db_path, similarity_threshold=0.8)  # Stricter threshold
        self.state_manager = PipelineStateManager(db_path)
    
    def run_express_analysis(self, max_runtime_minutes: int = 3) -> Dict[str, Any]:
        """
        Run express analysis pipeline optimized for speed.
        
        Args:
            max_runtime_minutes: Maximum runtime before early termination
            
        Returns:
            Analysis results with top insights
        """
        start_time = time.time()
        max_runtime_seconds = max_runtime_minutes * 60
        
        # Start pipeline run
        run_id = self.state_manager.start_pipeline_run("express")
        
        self.logger.info(f"🚀 EXPRESS MODE: Starting fast-track analysis (max {max_runtime_minutes} min)")
        
        try:
            results = {
                'run_id': run_id,
                'mode': 'express',
                'started_at': datetime.now().isoformat(),
                'max_runtime_minutes': max_runtime_minutes,
                'insights': []
            }
            
            # Step 1: Quick article collection (recent articles only)
            with StepContext(self.state_manager, run_id, 'collection', 
                           "Collecting recent articles for express analysis") as step:
                
                recent_articles = self.get_recent_articles(hours_back=24, limit=200)
                step.update_progress(article_count=len(recent_articles))
                
                if not recent_articles:
                    self.logger.warning("No recent articles found for express analysis")
                    return self._finalize_results(results, start_time, "No recent articles")
                
                # Early termination check
                if self._check_timeout(start_time, max_runtime_seconds):
                    return self._finalize_results(results, start_time, "Timeout during collection")
            
            # Step 2: Express filtering (process only high-priority articles)
            with StepContext(self.state_manager, run_id, 'filtering', 
                           "Express AI filtering for high-relevance articles") as step:
                
                filtering_results = self.ai_filter.filter_for_creditreform("express")
                
                matched_count = 0
                for topic_results in filtering_results.values():
                    matched_count += topic_results.get('matched', 0)
                
                step.update_progress(article_count=len(recent_articles), match_count=matched_count)
                
                if matched_count == 0:
                    return self._finalize_results(results, start_time, "No relevant matches found")
                
                # Early termination check
                if self._check_timeout(start_time, max_runtime_seconds):
                    return self._finalize_results(results, start_time, "Timeout during filtering")
            
            # Step 3: Quick deduplication (basic clustering only)
            with StepContext(self.state_manager, run_id, 'analysis', 
                           "Quick deduplication and insight generation") as step:
                
                # Get matched articles and perform light deduplication
                matched_articles = self.ai_filter.get_matched_articles(limit=50)
                
                if matched_articles:
                    dedup_results = self.deduplicator.deduplicate_articles(limit=50)
                    primary_articles = self.deduplicator.get_primary_articles(limit=15)
                else:
                    primary_articles = matched_articles[:15]  # Fallback
                
                step.update_progress(article_count=len(matched_articles))
                
                # Early termination check
                if self._check_timeout(start_time, max_runtime_seconds):
                    return self._finalize_results(results, start_time, "Timeout during analysis")
            
            # Step 4: Generate express insights (lightweight summarization)
            insights = self.generate_express_insights(primary_articles[:10])
            results['insights'] = insights
            
            # Step 5: Skip heavy processing (scraping, detailed analysis)
            self.logger.info("⚡ EXPRESS MODE: Skipping scraping and detailed analysis for speed")
            
            return self._finalize_results(results, start_time, "Completed successfully")
            
        except KeyboardInterrupt:
            self.logger.warning("Express analysis interrupted by user")
            self.state_manager.pause_pipeline(run_id, "User interruption")
            return self._finalize_results(results, start_time, "Interrupted by user")
            
        except Exception as e:
            self.logger.error(f"Express analysis failed: {e}")
            return self._finalize_results(results, start_time, f"Error: {str(e)}")
    
    def get_recent_articles(self, hours_back: int = 24, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Get articles from recent hours with priority sorting.
        
        Args:
            hours_back: How many hours back to look for articles
            limit: Maximum articles to return
            
        Returns:
            List of recent articles sorted by priority
        """
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        cutoff_str = cutoff_time.isoformat()
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Get recent articles with priority to unfiltered ones
        cursor = conn.execute("""
            SELECT id, source, url, title, published_at, first_seen_at, triage_topic
            FROM items 
            WHERE (published_at > ? OR first_seen_at > ?)
            ORDER BY 
                CASE WHEN triage_topic IS NULL THEN 0 ELSE 1 END,  -- Unfiltered first
                published_at DESC,
                first_seen_at DESC
            LIMIT ?
        """, (cutoff_str, cutoff_str, limit))
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                'id': row['id'],
                'source': row['source'],
                'url': row['url'],
                'title': row['title'],
                'published_at': row['published_at'],
                'first_seen_at': row['first_seen_at'],
                'already_processed': row['triage_topic'] is not None
            })
        
        conn.close()
        
        self.logger.info(f"Found {format_number(len(articles))} articles from last {hours_back} hours")
        return articles
    
    def generate_express_insights(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate lightweight insights from top articles without full content extraction.
        
        Args:
            articles: List of primary articles to generate insights from
            
        Returns:
            List of insight summaries
        """
        insights = []
        
        if not articles:
            return insights
        
        self.logger.info(f"Generating express insights from {len(articles)} articles")
        
        # Group by source authority for better presentation
        tier_1_articles = []
        tier_2_articles = []
        tier_3_articles = []
        
        for article in articles:
            authority = self.deduplicator.get_source_authority_score(article.get('url', ''))
            if authority >= 8:
                tier_1_articles.append(article)
            elif authority >= 6:
                tier_2_articles.append(article)
            else:
                tier_3_articles.append(article)
        
        # Generate insights with priority order
        insight_sources = [
            ("High Priority Sources", tier_1_articles),
            ("Financial News", tier_2_articles),
            ("General News", tier_3_articles)
        ]
        
        for category, category_articles in insight_sources:
            for article in category_articles[:5]:  # Max 5 per category
                
                insight = self.create_express_insight(article, category)
                if insight:
                    insights.append(insight)
                
                # Limit total insights for express mode
                if len(insights) >= 10:
                    break
            
            if len(insights) >= 10:
                break
        
        self.logger.info(f"Generated {len(insights)} express insights")
        return insights
    
    def create_express_insight(self, article: Dict[str, Any], category: str) -> Optional[Dict[str, Any]]:
        """
        Create a lightweight insight from an article using title and metadata only.
        
        Args:
            article: Article data
            category: Source category
            
        Returns:
            Insight dictionary or None if creation fails
        """
        try:
            title = article.get('title', '')
            url = article.get('url', '')
            source_domain = self.deduplicator._extract_domain(url)
            
            if not title:
                return None
            
            # Determine relevance category based on title keywords
            relevance_category = self._classify_title_relevance(title)
            
            # Generate business context
            business_context = self._generate_business_context(title, relevance_category)
            
            insight = {
                'id': article.get('id'),
                'headline': title,
                'source': source_domain,
                'category': category,
                'relevance_category': relevance_category,
                'business_context': business_context,
                'url': url,
                'published_at': article.get('published_at'),
                'confidence': article.get('confidence', 0.0),
                'is_clustered': article.get('is_clustered', False)
            }
            
            return insight
            
        except Exception as e:
            self.logger.warning(f"Failed to create insight from article {article.get('id')}: {e}")
            return None
    
    def _classify_title_relevance(self, title: str) -> str:
        """Classify article relevance based on title keywords."""
        title_lower = title.lower()
        
        # High-priority keywords for Creditreform
        if any(keyword in title_lower for keyword in ['konkurs', 'insolvenz', 'betreibung', 'schkg']):
            return "Insolvency & Bankruptcy"
        
        if any(keyword in title_lower for keyword in ['bonität', 'rating', 'kreditscoring', 'score']):
            return "Credit Risk & Rating"
        
        if any(keyword in title_lower for keyword in ['finma', 'basel iii', 'swiss finish', 'regulierung']):
            return "Regulatory Changes"
        
        if any(keyword in title_lower for keyword in ['zahlungsmoral', 'zahlungsverzug', 'debitoren']):
            return "Payment Behavior"
        
        if any(keyword in title_lower for keyword in ['kreditversicherung', 'trade credit', 'warenkreditversicherung']):
            return "Credit Insurance"
        
        return "General Business"
    
    def _generate_business_context(self, title: str, relevance_category: str) -> str:
        """Generate business context explanation for Creditreform relevance."""
        
        context_map = {
            "Insolvency & Bankruptcy": "Directly impacts credit risk assessment and client portfolio management",
            "Credit Risk & Rating": "Core business relevance for credit scoring and risk evaluation services",
            "Regulatory Changes": "Affects compliance requirements and business operations",
            "Payment Behavior": "Influences B2B credit risk models and customer insights",
            "Credit Insurance": "Market intelligence for competitive landscape analysis",
            "General Business": "Background context for Swiss business environment"
        }
        
        return context_map.get(relevance_category, "Relevant to Swiss business and financial markets")
    
    def _check_timeout(self, start_time: float, max_seconds: float) -> bool:
        """Check if pipeline should terminate due to timeout."""
        elapsed = time.time() - start_time
        if elapsed > max_seconds:
            self.logger.warning(f"Express analysis approaching timeout limit ({elapsed:.1f}s / {max_seconds:.1f}s)")
            return True
        return False
    
    def _finalize_results(self, results: Dict[str, Any], start_time: float, status: str) -> Dict[str, Any]:
        """Finalize analysis results with timing and summary info."""
        duration = time.time() - start_time
        
        results.update({
            'completed_at': datetime.now().isoformat(),
            'duration_seconds': duration,
            'duration_formatted': f"{duration:.1f}s",
            'status': status,
            'total_insights': len(results.get('insights', [])),
            'efficiency_rating': "⚡ Express" if duration < 180 else "🐌 Slow"
        })
        
        # Log completion
        insight_count = len(results.get('insights', []))
        self.logger.info(f"🎯 EXPRESS COMPLETE: {insight_count} insights in {duration:.1f}s")
        
        return results
    
    def create_daily_briefing(self, insights: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a formatted daily briefing from express insights.
        
        Args:
            insights: List of insights from express analysis
            
        Returns:
            Formatted briefing suitable for presentation
        """
        if not insights:
            return {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'title': 'Daily Creditreform Briefing',
                'summary': 'No relevant insights found for today',
                'sections': []
            }
        
        # Group insights by category
        categories = {}
        for insight in insights:
            category = insight.get('relevance_category', 'General')
            if category not in categories:
                categories[category] = []
            categories[category].append(insight)
        
        # Create briefing sections
        sections = []
        priority_order = [
            "Insolvency & Bankruptcy",
            "Credit Risk & Rating", 
            "Regulatory Changes",
            "Payment Behavior",
            "Credit Insurance",
            "General Business"
        ]
        
        for category in priority_order:
            if category in categories:
                section_insights = categories[category]
                sections.append({
                    'category': category,
                    'count': len(section_insights),
                    'insights': section_insights[:5]  # Limit per section
                })
        
        # Generate executive summary
        high_priority_count = sum(1 for insight in insights 
                                 if insight.get('relevance_category') in priority_order[:3])
        
        summary = f"Today's analysis identified {len(insights)} relevant insights"
        if high_priority_count > 0:
            summary += f", including {high_priority_count} high-priority items"
        summary += " from Swiss business and financial news sources."
        
        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'title': 'Daily Creditreform Business Intelligence Briefing',
            'summary': summary,
            'sections': sections,
            'total_insights': len(insights),
            'high_priority_count': high_priority_count,
            'generated_at': datetime.now().isoformat()
        }
    
    def get_express_stats(self, run_id: str = None) -> Dict[str, Any]:
        """Get statistics for express mode runs."""
        conn = sqlite3.connect(self.db_path)
        
        if run_id:
            # Stats for specific run
            progress = self.state_manager.get_pipeline_progress(run_id)
            return {
                'run_specific': True,
                'run_id': run_id,
                'progress': progress
            }
        else:
            # General express mode stats
            cursor = conn.execute("""
                SELECT COUNT(*) as total_runs,
                       AVG(CASE WHEN status = 'completed' THEN article_count ELSE NULL END) as avg_articles,
                       AVG(CASE WHEN status = 'completed' THEN match_count ELSE NULL END) as avg_matches
                FROM pipeline_state 
                WHERE step_name = 'filtering' 
                AND JSON_EXTRACT(metadata, '$.mode') = 'express'
                AND started_at > datetime('now', '-7 days')
            """)
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'run_specific': False,
                    'recent_express_runs': result[0] or 0,
                    'avg_articles_processed': result[1] or 0,
                    'avg_matches_found': result[2] or 0
                }
            else:
                return {
                    'run_specific': False,
                    'recent_express_runs': 0,
                    'avg_articles_processed': 0,
                    'avg_matches_found': 0
                }
