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
    ArticleSummarizer, MetaAnalyzer
)
from news_pipeline.state_manager import PipelineStateManager as StateManager
from news_pipeline.utils import (
    setup_logging, log_step_start, log_step_complete, 
    log_error_with_context, format_number, format_rate
)
import time
import sqlite3
from typing import Dict, Any


class NewsPipeline:
    """Main pipeline orchestrator for the 5-step news analysis workflow."""
    
    def __init__(self, db_path: str | None = None, enable_file_logging: bool = True):
        self.db_path = db_path or os.getenv("DB_PATH", "./news.db")
        self.logger = setup_logging(log_to_file=enable_file_logging, component="pipeline")
        
        # Initialize components
        self.collector = NewsCollector(self.db_path)
        self.filter = AIFilter(self.db_path)
        self.scraper = ContentScraper(self.db_path)
        self.summarizer = ArticleSummarizer(self.db_path)
        self.analyzer = MetaAnalyzer(self.db_path)
        self.state_manager = StateManager(self.db_path)
        
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
    
    def build_topic_digest(self, export_format: str = "json") -> str:
        """Step 5: Meta-Summary Generation and Export."""
        start_time = time.time()
        
        log_step_start(self.logger, "STEP 5: Daily Digest Generation", 
                      f"Creating comprehensive daily digest in {export_format} format")
        
        # Export daily digest
        output_path = self.analyzer.export_daily_digest(format=export_format)
        
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
            results['step1_collection'] = self.collector.collect_all()
            self.logger.info(f"Collected: {results['step1_collection'].get('total_collected', 0)} articles")
            
            # Mark collected articles with run_id
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                UPDATE items 
                SET pipeline_run_id = ?,
                    pipeline_stage = 'collected'
                WHERE pipeline_run_id IS NULL
            """, (self.current_run_id,))
            conn.commit()
            conn.close()
            
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
            
            # Step 4: Summarize ONLY scraped selected articles
            results['step4_summarization'] = self.summarizer.summarize_for_run(
                run_id=self.current_run_id,
                limit=limit
            )
            self.logger.info(f"Summarized: {results['step4_summarization'].get('summarized', 0)} articles")
            
            # Step 5: Generate Meta-Analysis
            results['step5_export_path'] = self.build_topic_digest(export_format=export_format)
            
            # Get comprehensive pipeline stats
            results['pipeline_stats'] = self.get_enhanced_pipeline_stats(self.current_run_id)
            
            # Complete the pipeline run (mark analysis step as complete)
            self.state_manager.complete_step(self.current_run_id, 'analysis', 
                                            results['step4_summarization'].get('summarized', 0),
                                            topic_results.get('matched', 0))
            
            # Calculate total time
            duration = datetime.now() - start_time
            results['total_duration'] = str(duration)
            
            # Print selection report
            self.print_selection_report(self.current_run_id)
            
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
                with open("config/pipeline_config.yaml", 'r') as f:
                    config = yaml.safe_load(f)
                
                if confidence_threshold:
                    config['pipeline']['filtering']['confidence_threshold'] = confidence_threshold
                    self.logger.info(f"Overriding confidence threshold to {confidence_threshold}")
                
                if max_articles:
                    config['pipeline']['filtering']['max_articles_to_process'] = max_articles
                    self.logger.info(f"Overriding max articles to {max_articles}")
                
                # Save updated config temporarily
                with open("config/pipeline_config.yaml", 'w') as f:
                    yaml.dump(config, f)
                
                # Reinitialize filter with new config
                self.filter = AIFilter(self.db_path)
                
            except Exception as e:
                self.logger.warning(f"Could not override config: {e}")
    
    def get_enhanced_pipeline_stats(self, run_id: str) -> dict:
        """Get detailed stats showing the confidence-based funnel."""
        conn = sqlite3.connect(self.db_path)
        
        stats = {}
        
        # Get stage counts
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
        
        # Build funnel summary
        stats['funnel'] = {
            'collected': stats.get('collected', {}).get('count', 0),
            'matched': stats['selection']['total_matched'],
            'selected': stats['selection']['selected_for_processing'],
            'scraped': stats.get('scraped', {}).get('count', 0),
            'summarized': stats.get('summarized', {}).get('count', 0)
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
    
    args = parser.parse_args()
    
    # Set up logging level
    if args.debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize pipeline with logging preference
    enable_file_logging = not args.no_file_logging
    pipeline = NewsPipeline(db_path=args.db_path, enable_file_logging=enable_file_logging)
    
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
            print(f"[EXPORT] Digest exported to: {results.get('step5_export_path', 'unknown')}")
            
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
