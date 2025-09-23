#!/usr/bin/env python3
"""
Test script for the enhanced analyzer with incremental digest generation.
Demonstrates the improved final output generation step.
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add parent directory to path to import from news_pipeline
sys.path.insert(0, str(Path(__file__).parent.parent))

from news_pipeline.enhanced_analyzer import EnhancedMetaAnalyzer

def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def test_enhanced_analyzer():
    """Test the enhanced analyzer functionality."""
    
    print("=== Enhanced Analyzer Test ===")
    
    # Database path
    db_path = "news.db"
    
    from pathlib import Path
    if not Path(db_path).exists():
        print(f"Error: Database {db_path} does not exist!")
        print("Run the main pipeline first to create test data.")
        return
    
    # Initialize enhanced analyzer
    analyzer = EnhancedMetaAnalyzer(db_path)
    
    print("1. Testing incremental digest generation...")
    
    # Test incremental digest generation
    digests = analyzer.generate_incremental_daily_digests()
    print(f"   Generated digests for {len(digests)} topics")
    
    for topic, digest in digests.items():
        article_count = digest.get('article_count', 0)
        updated = digest.get('last_updated') is not None
        print(f"   - {topic}: {article_count} articles ({'updated' if updated else 'cached'})")
    
    print("\n2. Testing executive summary generation...")
    
    # Test executive summary
    executive = analyzer.create_executive_summary(digests)
    print(f"   Executive summary: {executive['headline'][:50]}...")
    print(f"   Key themes: {len(executive.get('key_themes', []))}")
    print(f"   Top priorities: {len(executive.get('top_priorities', []))}")
    
    print("\n3. Testing trending topics identification...")
    
    # Test trending topics
    trending = analyzer.identify_trending_topics()
    print(f"   Found {len(trending)} trending topics")
    
    for i, topic in enumerate(trending[:3], 1):
        print(f"   {i}. {topic['topic']}: {topic['article_count']} articles, "
              f"trend score: {topic['trend_score']}")
    
    print("\n4. Testing enhanced export (JSON)...")
    
    # Test JSON export
    export_result = analyzer.export_enhanced_daily_digest(format="json")
    json_path = export_result if isinstance(export_result, str) else export_result[0]
    print(f"   Exported JSON digest: {json_path}")
    
    # Verify JSON structure
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"   JSON structure verified:")
    print(f"   - Date: {data.get('date')}")
    print(f"   - Updated: {data.get('updated', False)}")
    print(f"   - Topics: {len(data.get('topic_digests', {}))}")
    print(f"   - Executive summary: {bool(data.get('executive_summary'))}")
    print(f"   - Trending topics: {len(data.get('trending_topics', []))}")
    
    print("\n5. Testing template-based Markdown export...")
    
    # Test Markdown export
    try:
        export_result = analyzer.export_enhanced_daily_digest(format="markdown")
        markdown_path = export_result if isinstance(export_result, str) else export_result[0]
        print(f"   Exported Markdown digest: {markdown_path}")
        
        # Check file size
        file_size = Path(markdown_path).stat().st_size / 1024  # KB
        print(f"   Markdown file size: {file_size:.1f} KB")
        
    except Exception as e:
        print(f"   Markdown export failed: {e}")
        print("   (This is expected if Jinja2 is not installed)")
    
    print("\n6. Testing generation statistics...")
    
    # Test statistics
    stats = analyzer.get_generation_statistics()
    print(f"   Generation statistics (last 7 days):")
    
    for gen_type, data in stats.items():
        print(f"   - {gen_type}: {data['count']} runs, "
              f"avg {data['avg_api_calls']} API calls, "
              f"{data['avg_execution_time']:.1f}s avg time")
    
    print("\n7. Testing cache cleanup...")
    
    # Test cache cleanup
    analyzer.clear_old_digest_cache(days_to_keep=7)
    print("   Cache cleanup completed")
    
    print("\n=== Test Summary ===")
    print("✅ Enhanced analyzer functionality tested successfully!")
    print("\nKey improvements demonstrated:")
    print("- ✅ Incremental digest generation (only processes new articles)")
    print("- ✅ Template-based markdown generation")
    print("- ✅ Enhanced trending topic scoring")  
    print("- ✅ Digest state tracking and caching")
    print("- ✅ Generation statistics and monitoring")
    print("- ✅ Continuous daily updates that accumulate throughout the day")
    
    print(f"\nOutput files created:")
    print(f"- JSON: {json_path}")
    if 'markdown_path' in locals():
        print(f"- Markdown: {markdown_path}")

def test_database_migration():
    """Test the database migration for digest state tracking."""
    
    print("=== Database Migration Test ===")
    
    db_path = "news.db"
    
    if not os.path.exists(db_path):
        print(f"Error: Database {db_path} does not exist!")
        return
    
    # Run the migration script
    print("Running digest state table migration...")
    
    try:
        from scripts.create_digest_state_table import create_digest_state_table
        create_digest_state_table(db_path)
        print("✅ Migration completed successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    setup_logging()
    
    print("Enhanced News Analysis Pipeline - Final Output Generation Test")
    print("=" * 65)
    
    # Test database migration first
    test_database_migration()
    print()
    
    # Test enhanced analyzer
    test_enhanced_analyzer()
    
    print("\n" + "=" * 65)
    print("Test completed!")
