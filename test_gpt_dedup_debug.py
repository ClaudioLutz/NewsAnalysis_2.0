#!/usr/bin/env python3
"""
Debug script for GPT-based title deduplication functionality.
Tests the system with real scraped articles and shows detailed output.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from news_pipeline.gpt_deduplication import GPTTitleDeduplicator
import sqlite3


def main():
    """Main debug function for GPT deduplication testing."""
    print("🔧 Testing GPT Title Deduplication - Debug Mode")
    print("=" * 60)
    
    try:
        # Initialize deduplicator
        dedup = GPTTitleDeduplicator('news.db')
        print('✅ GPTTitleDeduplicator initialized successfully')
        print(f'✅ Model configured: {dedup.model_mini}')
        
        # Get scraped articles from today
        articles = dedup.gather_scraped_articles_for_today()
        print(f'✅ Found {len(articles)} scraped articles from today')
        
        if len(articles) == 0:
            print('⚠️  No scraped articles found for today')
            print('💡 Try running the pipeline first to get some articles')
            return
        
        print('\n📰 All article titles:')
        for i, article in enumerate(articles):
            print(f'  {i+1}. [{article["source"]}] {article["title"]}')
            print(f'      Content length: {article["content_length"]:,} chars')
            print(f'      Confidence: {article["confidence"]:.3f}')
            print()
        
        if len(articles) >= 2:
            print('\n🔍 Testing prompt generation...')
            
            # Test creating clustering prompt
            system_prompt, user_prompt = dedup.create_clustering_prompt(articles)
            print('✅ Created clustering prompt successfully')
            print(f'📝 System prompt: {system_prompt}')
            print(f'\n📝 User prompt:')
            print(user_prompt)
            
            print(f'\n🎯 You can see the duplicate UBS articles that should be grouped:')
            ubs_articles = [i+1 for i, article in enumerate(articles) 
                          if 'UBS' in article['title'] or 'ubs' in article['title'].lower()]
            if ubs_articles:
                print(f'   UBS articles: {ubs_articles}')
            else:
                print('   No obvious UBS duplicates found in titles')
            
            # Test parsing with mock output
            mock_output = "1, Group1\n2, Group1\n3, Group2\n4, Group2\n5, Group3"
            print(f'\n🧪 Testing parser with mock GPT output:')
            print(f'Mock output: {mock_output}')
            
            clusters = dedup.parse_clustering_output(mock_output, min(5, len(articles)))
            print(f'✅ Parsed {len(clusters)} duplicate clusters:')
            for group, indices in clusters.items():
                print(f'   {group}: articles {[i+1 for i in indices]}')
            
            # Test article selection
            if clusters:
                first_cluster = list(clusters.values())[0]
                cluster_articles = [articles[i] for i in first_cluster]
                primary_idx, reason = dedup.select_primary_article_by_length(cluster_articles)
                print(f'\n🏆 Primary article selection test:')
                print(f'   Selected article {first_cluster[primary_idx]+1}: {reason}')
            
            print(f'\n⚠️  Not running actual GPT API call to avoid costs')
            print(f'💡 Run with --live to make real GPT API calls')
            
        else:
            print('⚠️  Need at least 2 articles to test clustering')
            
        # Check database state
        conn = sqlite3.connect('news.db')
        cursor = conn.execute('SELECT COUNT(*) FROM article_clusters')
        existing_clusters = cursor.fetchone()[0]
        cursor = conn.execute('SELECT COUNT(*) FROM article_clusters WHERE clustering_method = "gpt_title_clustering"')
        gpt_clusters = cursor.fetchone()[0]
        conn.close()
        
        print(f'\n💾 Database state:')
        print(f'   Total clustered articles: {existing_clusters}')
        print(f'   GPT-clustered articles: {gpt_clusters}')
        
        print(f'\n✅ Debug test completed successfully!')
        
    except Exception as e:
        print(f'❌ Error during testing: {e}')
        import traceback
        traceback.print_exc()
        return False
    
    return True


def test_real_gpt_call():
    """Test with actual GPT API call (costs money!)"""
    print("🎯 Running REAL GPT API test...")
    print("⚠️  This will make actual API calls and cost money!")
    
    dedup = GPTTitleDeduplicator('news.db')
    articles = dedup.gather_scraped_articles_for_today()
    
    if len(articles) < 2:
        print("Need at least 2 articles for real test")
        return
    
    # Run actual deduplication
    results = dedup.deduplicate_articles()
    
    print(f'\n📊 GPT Deduplication Results:')
    print(f'  Articles processed: {results["articles_processed"]}')
    print(f'  Clusters found: {results["clusters_found"]}')  
    print(f'  Duplicates marked: {results["duplicates_marked"]}')
    print(f'  Deduplication rate: {results["deduplication_rate"]}')
    
    if results.get('cluster_details'):
        print(f'\n🔍 Cluster details:')
        for i, cluster in enumerate(results['cluster_details'][:3]):
            print(f'  Cluster {i+1}: {cluster["size"]} articles')
            print(f'    Primary: {cluster["primary_title"]}')
            print(f'    Source: {cluster["primary_source"]}')
            print(f'    Reason: {cluster["selection_reason"]}')


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test GPT-based article deduplication")
    parser.add_argument('--live', action='store_true', 
                       help='Make real GPT API calls (costs money!)')
    
    args = parser.parse_args()
    
    if args.live:
        test_real_gpt_call()
    else:
        success = main()
        sys.exit(0 if success else 1)
