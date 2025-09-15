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
from news_pipeline.utils import (
    setup_logging, log_step_start, log_step_complete, 
    log_error_with_context, format_number
)
import time


class NewsPipeline:
    """Main pipeline orchestrator for the 5-step news analysis workflow."""
    
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.getenv("DB_PATH", "./news.db")
        self.logger = setup_logging()
        
        # Initialize components
        self.collector = NewsCollector(self.db_path)
        self.filter = AIFilter(self.db_path)
        self.scraper = ContentScraper(self.db_path)
        self.summarizer = ArticleSummarizer(self.db_path)
        self.analyzer = MetaAnalyzer(self.db_path)
        
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
    
    def triage_with_model_mini(self) -> dict:
        """Step 2: AI-Powered Filtering using MODEL_MINI."""
        # Note: Detailed logging is now handled within filter.filter_all_topics()
        results = self.filter.filter_all_topics()
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
                         export_format: str = "json") -> dict:
        """
        Run the complete 5-step pipeline.
        
        Args:
            scrape_limit: Max articles to scrape
            summarize_limit: Max articles to summarize
            export_format: Export format ("json" or "markdown")
            
        Returns:
            Summary of all pipeline results
        """
        start_time = datetime.now()
        self.logger.info("Starting full news analysis pipeline...")
        
        results = {}
        
        try:
            # Step 1: Collect URLs
            results['step1_collection'] = self.collect_urls()
            
            # Step 2: AI Filter
            results['step2_filtering'] = self.triage_with_model_mini()
            
            # Step 3: Scrape Content  
            results['step3_scraping'] = self.scrape_selected(limit=scrape_limit)
            
            # Step 4: Summarize Articles
            results['step4_summarization'] = self.summarize_articles(limit=summarize_limit)
            
            # Step 5: Generate Meta-Analysis
            results['step5_export_path'] = self.build_topic_digest(export_format=export_format)
            
            # Calculate total time
            duration = datetime.now() - start_time
            results['total_duration'] = str(duration)
            
            self.logger.info(f"Pipeline completed successfully in {duration}")
            
        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}")
            results['error'] = str(e)
            raise
        
        finally:
            # Cleanup resources
            self.scraper.cleanup()
        
        return results
    
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
    
    args = parser.parse_args()
    
    # Set up logging level
    if args.debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize pipeline
    pipeline = NewsPipeline(db_path=args.db_path)
    
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
                results = pipeline.triage_with_model_mini()
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
            results = pipeline.run_full_pipeline(
                scrape_limit=args.limit,
                summarize_limit=args.limit,
                export_format=export_format
            )
            print(f"[SUCCESS] Pipeline completed in {results.get('total_duration', 'unknown')}")
            print(f"[EXPORT] Digest exported to: {results.get('step5_export_path', 'unknown')}")
            
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
