#!/usr/bin/env python3
"""
AI-Powered News Analysis System

Main pipeline runner implementing the 5-step workflow:
1. URL Collection (RSS/Sitemap/HTML) 
2. AI-Powered Filtering (Title/URL Only)
3. Selective Content Scraping (Relevant Articles Only)
4. Individual Article Summarization 
5. Meta-Summary Generation

Usage:
    python news_analyzer.py                    # Run full pipeline
    python news_analyzer.py --step collect    # Run specific step
    python news_analyzer.py --export          # Export daily digest
    python news_analyzer.py --stats           # Show statistics
"""

import os
import sys
import argparse
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from news_pipeline import (
    NewsCollector, AIFilter, ContentScraper, 
    ArticleSummarizer
)
from news_pipeline.enhanced_analyzer import EnhancedMetaAnalyzer
from news_pipeline.deduplication import ArticleDeduplicator
from news_pipeline.gpt_deduplication import GPTTitleDeduplicator
from news_pipeline.state_manager import PipelineStateManager as StateManager
from news_pipeline.utils import (
    setup_logging, log_step_start, log_step_complete, 
    log_error_with_context, format_number, format_rate
)
from news_pipeline.paths import resource_path, config_path, safe_open
import time
import sqlite3
from typing import Dict, Any


class NewsPipeline:
    """Main pipeline orchestrator for the 5-step news analysis workflow."""
    
    def __init__(self, db_path: str | None = None, enable_file_logging: bool = True):
        # Use robust path resolution for database
        if db_path:
            self.db_path = db_path
        else:
            # Check environment variable first, then use default location
            env_db_path = os.getenv("DB_PATH")
            if env_db_path:
                self.db_path = env_db_path
            else:
                # Default to news.db in project root
                self.db_path = str(resource_path("news.db"))
        
        self.logger = setup_logging(log_to_file=enable_file_logging, component="pipeline")
        
        # Initialize components
        self.collector = NewsCollector(self.db_path)
        self.filter = AIFilter(self.db_path)
        self.scraper = ContentScraper(self.db_path)
        self.summarizer = ArticleSummarizer(self.db_path)
        self.analyzer = EnhancedMetaAnalyzer(self.db_path)
        self.state_manager = StateManager(self.db_path)
        self.deduplicator = ArticleDeduplicator(self.db_path)
        self.gpt_deduplicator = GPTTitleDeduplicator(self.db_path)
        
        # Track current pipeline run
        self.current_run_id = None
        
        self.logger.info("News Analysis Pipeline initialized")
    
    def collect_urls(self) -> dict:
        """Step 1: URL Collection from RSS/Sitemap/HTML sources."""
        start_time = time.time()
        
        log_step_start(self.logger, "STEP 1: URL Collection", 
                      "Collecting URLs from RSS feeds, sitemaps, and HTML sources")
        
        results = self.collector.collect_all()
        
        duration = time.time() - start_time
        log_results = {
            'Total collected': format_number(results.get('total_collected', 0)),
            'After deduplication': format_number(results.get('after_dedup', 0)),
            'RSS articles': format_number(results.get('rss', 0)),
            'Sitemap articles': format_number(results.get('sitemaps', 0)),
            'HTML articles': format_number(results.get('html', 0)),
            'Google News articles': format_number(results.get('google_news', 0))
        }
        
        log_step_complete(self.logger, "URL Collection", duration, log_results)
        return results
    
    def triage_with_model_mini(self, skip_prefilter: bool = False) -> dict:
        """Step 2: AI-Powered Filtering using MODEL_MINI."""
        # Note: Detailed logging is now handled within filter.filter_for_creditreform()
        results = self.filter.filter_for_creditreform(mode="standard", skip_prefilter=skip_prefilter)
        return results
    
    def scrape_selected(self, limit: int = 50) -> dict:
        """Step 3: Selective Content Scraping of relevant articles."""
        start_time = time.time()
        
        log_step_start(self.logger, "STEP 3: Content Scraping", 
                      f"Scraping content from top {limit} matched articles")
        
        results = self.scraper.scrape_selected_articles(limit=limit)
        
        duration = time.time() - start_time
        log_results = {
            'Articles scraped': format_number(results.get('scraped', 0)),
            'Success rate': f"{results.get('extraction_rate', 0):.1%}",
            'Average content length': f"{results.get('avg_content_length', 0)} chars"
        }
        
        log_step_complete(self.logger, "Content Scraping", duration, log_results)
        return results
    
    def summarize_articles(self, limit: int = 50) -> dict:
        """Step 4: Individual Article Summarization."""
        start_time = time.time()
        
        log_step_start(self.logger, "STEP 4: Article Summarization", 
                      f"Generating AI summaries for up to {limit} articles")
        
        results = self.summarizer.summarize_articles(limit=limit)
        
        duration = time.time() - start_time
        log_results = {
            'Articles summarized': format_number(results.get('summarized', 0)),
            'Average summary length': f"{results.get('avg_summary_length', 0)} chars",
            'Processing rate': f"{results.get('summarized', 0) / (duration/60):.1f} articles/min" if duration > 0 else "N/A"
        }
        
        log_step_complete(self.logger, "Article Summarization", duration, log_results)
        return results
    
    def build_topic_digest(self, export_format: str = "json", run_id: str | None = None) -> str:
        """Step 5: Meta-Summary Generation and Export."""
        start_time = time.time()
        
        log_step_start(self.logger, "STEP 5: Daily Digest Generation", 
                      f"Creating comprehensive daily digest in {export_format} format")
        
        # Export daily digest with run_id context
        output_path = self.analyzer.export_daily_digest(format=export_format, run_id=run_id)
        
        duration = time.time() - start_time
        log_results = {
            'Output format': export_format,
            'Export path': output_path,
            'File size': self._get_file_size(output_path)
        }
        
        log_step_complete(self.logger, "Daily Digest Generation", duration, log_results)
        return output_path
    
    def _get_file_size(self, file_path: str) -> str:
        """Get human-readable file size."""
        try:
            size = os.path.getsize(file_path)
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size/1024:.1f} KB"
            else:
                return f"{size/(1024*1024):.1f} MB"
        except:
            return "Unknown"
    
    def run_full_pipeline(self, scrape_limit: int = 50, summarize_limit: int = 50, 
                         export_format: str = "json", skip_prefilter: bool = False,
                         confidence_threshold: float | None = None, max_articles: int | None = None) -> dict:
        """
        Run the complete 5-step pipeline with confidence-based selection.
        
        Args:
            scrape_limit: Max articles to scrape (deprecated, use max_articles)
            summarize_limit: Max articles to summarize (deprecated, use max_articles)
            export_format: Export format ("json" or "markdown")
            skip_prefilter: If True, bypass priority-based pre-filtering
            confidence_threshold: Minimum confidence for article selection
            max_articles: Maximum number of articles to process through pipeline
            
        Returns:
            Summary of all pipeline results
        """
        start_time = datetime.now()
        self.logger.info("Starting full news analysis pipeline with confidence-based selection...")
        
        # Override config if parameters provided
        if confidence_threshold or max_articles:
            self._override_config(confidence_threshold, max_articles)
        
        # Use max_articles if provided, otherwise fall back to scrape_limit
        limit = max_articles or scrape_limit
        
        # Start a new pipeline run
        self.current_run_id = self.state_manager.start_pipeline_run("standard")
        self.logger.info(f"Pipeline run ID: {self.current_run_id}")
        
        results: Dict[str, Any] = {
            'run_id': self.current_run_id,
            'start_time': start_time.isoformat()
        }
        
        try:
            # Step 1: Collect URLs
            # Track what's new before collection
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT MAX(id) FROM items")
            max_id_before = cursor.fetchone()[0] or 0
            conn.close()
            
            results['step1_collection'] = self.collector.collect_all()
            self.logger.info(f"Collected: {results['step1_collection'].get('total_collected', 0)} articles")
            
            # Mark ONLY newly collected articles (avoid updating articles already in 'collected' state)
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    UPDATE items 
                    SET pipeline_run_id = ?,
                        pipeline_stage = 'collected'
                    WHERE id > ?
                    AND pipeline_run_id IS NULL
                    AND (pipeline_stage IS NULL OR pipeline_stage != 'collected')
                """, (self.current_run_id, max_id_before))
                conn.commit()
            except Exception as e:
                self.logger.error(f"Error updating pipeline stage: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()
            
            # Step 1.5: Deduplication (NEW - integrate existing module)
            try:
                self.logger.info("Running semantic deduplication on newly collected articles...")
                dedup_results = self.deduplicator.deduplicate_articles(limit=1000)
                results['step1_5_deduplication'] = dedup_results
                self.logger.info(f"Deduplication: {dedup_results.get('duplicates_marked', 0)} duplicates marked from {dedup_results.get('clusters_found', 0)} clusters")
            except Exception as e:
                self.logger.warning(f"Deduplication failed: {e}, continuing pipeline...")
                results['step1_5_deduplication'] = {"error": str(e)}
            
            # Step 2: AI Filter AND Select top N
            results['step2_filtering'] = self.filter.filter_for_run(
                run_id=self.current_run_id,
                mode='standard'
            )
            
            # Get the main topic results (creditreform_insights)
            topic_results = results['step2_filtering'].get('creditreform_insights', {})
            self.logger.info(f"Matched: {topic_results.get('matched', 0)} articles")
            self.logger.info(f"Selected for processing: {topic_results.get('selected_for_processing', 0)} articles")
            
            # Step 3: Scrape ONLY selected articles  
            results['step3_scraping'] = self.scraper.scrape_for_run(
                run_id=self.current_run_id,
                limit=limit
            )
            self.logger.info(f"Scraped: {results['step3_scraping'].get('extracted', 0)} articles")
            
            # Step 4: GPT Title-Based Deduplication (NEW)
            try:
                results['step4_gpt_deduplication'] = self.gpt_deduplicator.deduplicate_articles()
                self.logger.info(f"GPT Deduplication: {results['step4_gpt_deduplication'].get('duplicates_marked', 0)} duplicates marked from {results['step4_gpt_deduplication'].get('clusters_found', 0)} title clusters")
            except Exception as e:
                self.logger.warning(f"GPT deduplication failed: {e}, continuing with all scraped articles...")
                results['step4_gpt_deduplication'] = {"error": str(e)}
            
            # Step 5: Summarize ONLY unique articles (primary + unclustered)
            results['step5_summarization'] = self.summarizer.summarize_for_run(
                run_id=self.current_run_id,
                limit=limit
            )
            self.logger.info(f"Summarized: {results['step5_summarization'].get('summarized', 0)} articles")
            
            # Step 6: Generate Meta-Analysis using EnhancedMetaAnalyzer
            results['step6_export_path'] = self.analyzer.export_enhanced_daily_digest(
                output_path=None,
                format=export_format,
                force_full_regeneration=False
            )
            
            # Get comprehensive pipeline stats
            results['pipeline_stats'] = self.get_enhanced_pipeline_stats(self.current_run_id)
            
            # Complete the pipeline run (mark analysis step as complete)
            self.state_manager.complete_step(self.current_run_id, 'analysis', 
                                            results['step5_summarization'].get('summarized', 0),
                                            topic_results.get('matched', 0))
            
            # Calculate total time
            duration = datetime.now() - start_time
            results['total_duration'] = str(duration)
            
            # Print selection report
            self.print_selection_report(self.current_run_id)
            
            # Validate pipeline flow
            validation = self.validate_pipeline_flow(self.current_run_id)
            results['pipeline_validation'] = validation
            
            self.logger.info(f"Pipeline completed successfully in {duration}")
            
        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}")
            if self.current_run_id:
                self.state_manager.fail_step(self.current_run_id, 'current', str(e))
            results['error'] = str(e)
            raise
        
        finally:
            # Cleanup resources
            self.scraper.cleanup()
        
        return results
    
    def _override_config(self, confidence_threshold: float | None = None, max_articles: int | None = None):
        """Override pipeline configuration at runtime."""
        if confidence_threshold or max_articles:
            import yaml
            try:
                pipeline_config_path = config_path("pipeline_config.yaml")
                with safe_open(pipeline_config_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                if confidence_threshold:
                    config['pipeline']['filtering']['confidence_threshold'] = confidence_threshold
                    self.logger.info(f"Overriding confidence threshold to {confidence_threshold}")
                
                if max_articles:
                    config['pipeline']['filtering']['max_articles_to_process'] = max_articles
                    self.logger.info(f"Overriding max articles to {max_articles}")
                
                # Save updated config temporarily
                with safe_open(pipeline_config_path, 'w') as f:
                    yaml.dump(config, f)
                
                # Reinitialize filter with new config
                self.filter = AIFilter(self.db_path)
                
            except Exception as e:
                self.logger.warning(f"Could not override config: {e}")
    
    def get_enhanced_pipeline_stats(self, run_id: str) -> dict:
        """
        Get detailed stats showing the confidence-based funnel.
        FIXED: Proper counting of articles through all pipeline stages.
        """
        conn = sqlite3.connect(self.db_path)
        
        stats = {}
        
        # Get stage counts (articles assigned to this run)
        stages_query = """
            SELECT 
                pipeline_stage,
                COUNT(*) as count,
                AVG(triage_confidence) as avg_confidence,
                MIN(triage_confidence) as min_confidence,
                MAX(triage_confidence) as max_confidence
            FROM items 
            WHERE pipeline_run_id = ?
            GROUP BY pipeline_stage
        """
        
        cursor = conn.execute(stages_query, (run_id,))
        for row in cursor.fetchall():
            stage = row[0] or 'unprocessed'
            stats[stage] = {
                'count': row[1],
                'avg_confidence': row[2],
                'min_confidence': row[3],
                'max_confidence': row[4]
            }
        
        # Get selection details
        selection_query = """
            SELECT 
                COUNT(*) as total_matched,
                SUM(CASE WHEN selected_for_processing = 1 THEN 1 ELSE 0 END) as selected,
                MIN(CASE WHEN selected_for_processing = 1 THEN triage_confidence END) as selection_threshold_actual,
                MAX(selection_rank) as max_rank
            FROM items 
            WHERE pipeline_run_id = ?
            AND is_match = 1
        """
        
        cursor = conn.execute(selection_query, (run_id,))
        row = cursor.fetchone()
        
        stats['selection'] = {
            'total_matched': row[0] or 0,
            'selected_for_processing': row[1] or 0,
            'actual_threshold_used': row[2],
            'selection_rate': (row[1] / row[0]) if row[0] and row[0] > 0 else 0
        }
        
        # FIXED: Get accurate counts for each funnel stage
        # Count collected articles (all articles assigned to this run)
        cursor = conn.execute("SELECT COUNT(*) FROM items WHERE pipeline_run_id = ?", (run_id,))
        collected_count = cursor.fetchone()[0] or 0
        
        # Count scraped articles (have content extraction)
        cursor = conn.execute("""
            SELECT COUNT(*) FROM items i
            JOIN articles a ON i.id = a.item_id
            WHERE i.pipeline_run_id = ? AND a.extracted_text IS NOT NULL AND a.extracted_text != ''
        """, (run_id,))
        scraped_count = cursor.fetchone()[0] or 0
        
        # Count summarized articles (have summaries)
        cursor = conn.execute("""
            SELECT COUNT(*) FROM items i
            JOIN summaries s ON i.id = s.item_id
            WHERE i.pipeline_run_id = ?
        """, (run_id,))
        summarized_count = cursor.fetchone()[0] or 0
        
        # Build accurate funnel summary
        stats['funnel'] = {
            'collected': collected_count,
            'matched': stats['selection']['total_matched'],
            'selected': stats['selection']['selected_for_processing'],
            'scraped': scraped_count,
            'summarized': summarized_count
        }
        
        conn.close()
        return stats
    
    def print_selection_report(self, run_id: str):
        """Print detailed report of article selection."""
        conn = sqlite3.connect(self.db_path)
        
        print("\n" + "="*70)
        print("ARTICLE SELECTION REPORT")
        print("="*70)
        
        # Top selected articles
        cursor = conn.execute("""
            SELECT selection_rank, title, triage_confidence, source
            FROM items
            WHERE pipeline_run_id = ?
            AND selected_for_processing = 1
            ORDER BY selection_rank
            LIMIT 10
        """, (run_id,))
        
        print("\n📈 Top 10 Selected Articles:")
        print("-" * 70)
        for rank, title, conf, source in cursor.fetchall():
            print(f"  #{rank:2d} [{conf:.2%}] {title[:55]}...")
            print(f"      Source: {source}")
        
        # Articles just below threshold
        cursor = conn.execute("""
            SELECT title, triage_confidence, source
            FROM items
            WHERE pipeline_run_id = ?
            AND is_match = 1
            AND selected_for_processing = 0
            ORDER BY triage_confidence DESC
            LIMIT 5
        """, (run_id,))
        
        below_threshold = cursor.fetchall()
        if below_threshold:
            print("\n⚠️ Not Selected (below threshold or outside top N):")
            print("-" * 70)
            for title, conf, source in below_threshold:
                print(f"  [{conf:.2%}] {title[:55]}... ({source})")
        
        # Pipeline funnel
        stats = self.get_enhanced_pipeline_stats(run_id)
        funnel = stats['funnel']
        
        print("\n📊 Pipeline Funnel:")
        print("-" * 70)
        print(f"  Collected:  {funnel['collected']:4d} articles")
        print(f"  ↓ Filtered")
        print(f"  Matched:    {funnel['matched']:4d} articles ({format_rate(funnel['matched'], funnel['collected'])})")
        print(f"  ↓ Selected (confidence-based)")
        print(f"  Selected:   {funnel['selected']:4d} articles ({format_rate(funnel['selected'], funnel['matched'])})")
        print(f"  ↓ Scraped")
        print(f"  Scraped:    {funnel['scraped']:4d} articles")
        print(f"  ↓ Summarized") 
        print(f"  Summarized: {funnel['summarized']:4d} articles")
        
        if stats['selection']['actual_threshold_used']:
            print(f"\n  Actual confidence threshold used: {stats['selection']['actual_threshold_used']:.2%}")
        
        conn.close()
        print("="*70 + "\n")
    
    def validate_pipeline_flow(self, run_id: str) -> Dict[str, Any]:
        """Validate pipeline flow and detect issues."""
        conn = sqlite3.connect(self.db_path)
        
        validation = {}
        
        # Check for already-summarized articles being selected (MOST CRITICAL CHECK)
        cursor = conn.execute("""
            SELECT COUNT(*) FROM items i
            JOIN summaries s ON i.id = s.item_id
            WHERE i.pipeline_run_id = ? 
            AND i.selected_for_processing = 1
        """, (run_id,))
        validation['error_selected_but_summarized'] = cursor.fetchone()[0]
        
        if validation['error_selected_but_summarized'] > 0:
            self.logger.error(f"CRITICAL: {validation['error_selected_but_summarized']} "
                             f"articles selected despite having summaries!")
        
        # Check stage consistency
        cursor = conn.execute("""
            SELECT pipeline_stage, COUNT(*) as count
            FROM items 
            WHERE pipeline_run_id = ?
            GROUP BY pipeline_stage
            ORDER BY pipeline_stage
        """, (run_id,))
        
        validation['stage_counts'] = {}
        for stage, count in cursor.fetchall():
            validation['stage_counts'][stage or 'unknown'] = count
        
        # Overall validation status
        validation['has_errors'] = validation['error_selected_but_summarized'] > 0
        validation['has_warnings'] = False
        validation['status'] = 'ERROR' if validation['has_errors'] else 'OK'
        
        conn.close()
        
        if validation['status'] != 'OK':
            self.logger.info(f"Pipeline validation status: {validation['status']}")
        
        return validation
    
    def _reset_todays_articles(self):
        """Reset today's matched articles for complete reprocessing."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        
        TZ = ZoneInfo("Europe/Zurich")
        today = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        today_iso = today.isoformat()
        
        conn = sqlite3.connect(self.db_path)
        
        # Get article IDs to reset
        cursor = conn.execute("""
            SELECT id FROM items
            WHERE triage_topic = 'creditreform_insights'
            AND is_match = 1
            AND (published_at >= ? OR (published_at IS NULL AND first_seen_at >= ?))
        """, (today_iso, today_iso))
        
        article_ids = [row[0] for row in cursor.fetchall()]
        
        if not article_ids:
            self.logger.info("No articles found to reset")
            conn.close()
            return
        
        # Delete summaries for these articles
        placeholders = ','.join('?' * len(article_ids))
        cursor = conn.execute(f"""
            DELETE FROM summaries WHERE item_id IN ({placeholders})
        """, article_ids)
        summaries_deleted = cursor.rowcount
        
        # Delete scraped content for these articles
        cursor = conn.execute(f"""
            DELETE FROM articles WHERE item_id IN ({placeholders})
        """, article_ids)
        articles_deleted = cursor.rowcount
        
        # Delete cross-run topic signatures for these articles
        cursor = conn.execute(f"""
            DELETE FROM cross_run_topic_signatures WHERE source_article_id IN ({placeholders})
        """, article_ids)
        signatures_deleted = cursor.rowcount
        
        # Reset article state
        cursor = conn.execute(f"""
            UPDATE items 
            SET selected_for_processing = 0,
                selection_rank = NULL,
                pipeline_run_id = NULL,
                pipeline_stage = 'matched',
                topic_already_covered = 0,
                cross_run_cluster_id = NULL
            WHERE id IN ({placeholders})
        """, article_ids)
        
        reset_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        self.logger.info(f"RERUN MODE: Reset {reset_count} articles from today")
        self.logger.info(f"  - Deleted {summaries_deleted} summaries")
        self.logger.info(f"  - Deleted {articles_deleted} scraped content entries")
        self.logger.info(f"  - Deleted {signatures_deleted} cross-run topic signatures")
        self.logger.info("Articles will be re-selected, re-scraped, and re-summarized")
    
    def show_stats(self) -> dict:
        """Show comprehensive pipeline statistics."""
        self.logger.info("=== Pipeline Statistics ===")
        
        stats = {
            'collection': self.collector.collect_all(),  # Will show counts without actually collecting
            'filtering': self.filter.get_stats(),
            'scraping': self.scraper.get_scraping_stats(),
            'summarization': self.summarizer.get_summarization_stats(),
        }
        
        # Add trending topics
        stats['trending_topics'] = self.analyzer.identify_trending_topics(days=7)
        
        # Print formatted stats
        print("\n[STATS] News Pipeline Statistics")
        print("=" * 50)
        
        # Filtering stats
        filter_stats = stats['filtering']
        print(f"[TOTAL] Total articles: {filter_stats['total_articles']}")
        print(f"[FILTERED] Filtered articles: {filter_stats['filtered_articles']}")  
        print(f"[MATCHED] Matched articles: {filter_stats['matched_articles']}")
        print(f"[RATE] Match rate: {filter_stats['match_rate']:.1%}")
        
        # Scraping stats  
        scraping_stats = stats['scraping']
        print(f"[EXTRACT] Extraction rate: {scraping_stats['extraction_rate']:.1%}")
        
        # Summarization stats
        summary_stats = stats['summarization']
        print(f"[SUMMARY] Summarized articles: {summary_stats['summarized_articles']}")
        print(f"[LENGTH] Avg summary length: {summary_stats['avg_summary_length']} chars")
        
        # Trending topics
        print(f"\n[TRENDING] Top 5 Trending Topics:")
        for i, topic in enumerate(stats['trending_topics'][:5], 1):
            print(f"  {i}. {topic['topic']} ({topic['article_count']} articles)")
        
        return stats


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AI-Powered News Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python news_analyzer.py                           # Run full pipeline
  python news_analyzer.py --step collect           # Run URL collection only
  python news_analyzer.py --step filter            # Run filtering only  
  python news_analyzer.py --step scrape            # Run scraping only
  python news_analyzer.py --step summarize         # Run summarization only
  python news_analyzer.py --step digest            # Generate digest only
  python news_analyzer.py --export --format md     # Export as markdown
  python news_analyzer.py --stats                  # Show statistics
  python news_analyzer.py --debug                  # Enable debug logging
        """
    )
    
    parser.add_argument(
        "--step", 
        choices=["collect", "filter", "scrape", "summarize", "digest"],
        help="Run specific pipeline step"
    )
    
    parser.add_argument(
        "--export", 
        action="store_true",
        help="Export daily digest"
    )
    
    parser.add_argument(
        "--format", 
        choices=["json", "markdown", "md"],
        default="json",
        help="Export format (default: json)"
    )
    
    parser.add_argument(
        "--stats", 
        action="store_true",
        help="Show pipeline statistics"
    )
    
    parser.add_argument(
        "--limit", 
        type=int, 
        default=50,
        help="Limit for scraping/summarizing (default: 50)"
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Enable debug logging"
    )
    
    parser.add_argument(
        "--db-path",
        default=None,
        help="Database path (default: from environment)"
    )
    
    parser.add_argument(
        "--no-file-logging",
        action="store_true",
        help="Disable file logging (console output only)"
    )
    
    parser.add_argument(
        "--enable-prefilter",
        action="store_true",
        help="Enable priority-based pre-filtering (process only top ~100 articles) - by default disabled"
    )
    
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=None,
        help="Minimum confidence threshold for processing (default: from config)"
    )
    
    parser.add_argument(
        "--max-articles",
        type=int,
        default=None,
        help="Maximum number of articles to process (default: 35)"
    )
    
    parser.add_argument(
        "--rerun-today",
        action="store_true",
        help="Reprocess all matched articles from today (useful for testing fixes)"
    )
    
    args = parser.parse_args()
    
    # Set up logging level
    if args.debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize pipeline with logging preference
    enable_file_logging = not args.no_file_logging
    pipeline = NewsPipeline(db_path=args.db_path, enable_file_logging=enable_file_logging)
    
    # Handle rerun-today flag
    if args.rerun_today:
        pipeline.logger.info("RERUN MODE: Resetting today's articles for reprocessing...")
        pipeline._reset_todays_articles()
    
    # Export format handling
    export_format = "markdown" if args.format in ["markdown", "md"] else "json"
    
    try:
        if args.stats:
            # Show statistics
            pipeline.show_stats()
            
        elif args.export:
            # Export digest only
            output_path = pipeline.build_topic_digest(export_format=export_format)
            print(f"[DONE] Digest exported to: {output_path}")
            
        elif args.step:
            # Run specific step
            if args.step == "collect":
                results = pipeline.collect_urls()
                print(f"[DONE] Collection complete: {results}")
                
            elif args.step == "filter":
                results = pipeline.triage_with_model_mini(skip_prefilter=not args.enable_prefilter)
                print(f"[DONE] Filtering complete: {results}")
                
            elif args.step == "scrape":
                results = pipeline.scrape_selected(limit=args.limit)
                print(f"[DONE] Scraping complete: {results}")
                
            elif args.step == "summarize":
                results = pipeline.summarize_articles(limit=args.limit)
                print(f"[DONE] Summarization complete: {results}")
                
            elif args.step == "digest":
                output_path = pipeline.build_topic_digest(export_format=export_format)
                print(f"[DONE] Digest generated: {output_path}")
        
        else:
            # Run full pipeline
            print("Starting AI News Analysis Pipeline...")
            print(f"Configuration: confidence_threshold={args.confidence_threshold}, max_articles={args.max_articles}")
            results = pipeline.run_full_pipeline(
                scrape_limit=args.limit,  # This becomes redundant with max_articles
                summarize_limit=args.limit,  # This becomes redundant with max_articles
                export_format=export_format,
                skip_prefilter=not args.enable_prefilter,
                confidence_threshold=args.confidence_threshold,
                max_articles=args.max_articles
            )
            print(f"\n[SUCCESS] Pipeline completed in {results.get('total_duration', 'unknown')}")
            print(f"[EXPORT] Digest exported to: {results.get('step6_export_path', 'unknown')}")
            
            # Show funnel summary
            if 'pipeline_stats' in results:
                funnel = results['pipeline_stats']['funnel']
                print(f"\n[FUNNEL] Pipeline Results:")
                print(f"  Collected → Matched → Selected → Scraped → Summarized")
                print(f"  {funnel['collected']:^9} → {funnel['matched']:^7} → {funnel['selected']:^8} → {funnel['scraped']:^7} → {funnel['summarized']:^10}")
            
    except KeyboardInterrupt:
        print("\n[STOP] Pipeline interrupted by user")
        sys.exit(1)
        
    except Exception as e:
        print(f"[ERROR] Pipeline failed: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
