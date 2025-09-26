#!/usr/bin/env python3
"""
Test script for GPT-based title deduplication functionality.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from news_pipeline.gpt_deduplication import GPTTitleDeduplicator
import sqlite3


def test_gpt_deduplication():
    """Test the GPT deduplication functionality."""
    print("🔧 Testing GPT Title Deduplication System")
    print("=" * 60)
    
    try:
        # Initialize deduplicator
        dedup = GPTTitleDeduplicator('news.db')
        print('✅ GPTTitleDeduplicator initialized successfully')
        print(f'✅ Model configured: {dedup.model_mini}')
        
        # Test gathering articles
        articles = dedup.gather_scraped_articles_for_today()
        print(f'✅ Found {len(articles)} scraped articles from today')
        
        if len(articles) > 0:
            print('\n📰 Sample article titles:')
            for i, article in enumerate(articles[:3]):
                print(f'  {i+1}. {article["title"][:80]}...')
                print(f'      Source: {article["source"]}')
                print(f'      Content length: {article["content_length"]:,} chars')
            
            if len(articles) >= 2:
                print(f'\n🔍 Testing title clustering with {len(articles)} articles...')
                
                # Test creating clustering prompt
                system_prompt, user_prompt = dedup.create_clustering_prompt(articles[:5])  # Test with first 5
                print('✅ Created clustering prompt successfully')
                print(f'📝 System prompt: {system_prompt[:50]}...')
                print(f'📝 User prompt length: {len(user_prompt)} chars')
                
                # Test parsing (simulate GPT output)
                mock_output = "1, Group1\n2, Group1\n3, Group2\n4, Group2\n5, Group3"
                clusters = dedup.parse_clustering_output(mock_output, 5)
                print(f'✅ Parsed mock clustering output: {len(clusters)} duplicate clusters')
                
                for group, indices in clusters.items():
                    print(f'   {group}: articles {[i+1 for i in indices]}')
                    
            else:
                print('⚠️  Need at least 2 articles to test clustering')
                
        else:
            print('⚠️  No scraped articles found for today')
            print('💡 Try running the pipeline first to get some articles')
            
        print(f'\n✅ All tests completed successfully!')
        
    except Exception as e:
        print(f'❌ Error during testing: {e}')
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = test_gpt_deduplication()
    sys.exit(0 if success else 1)
