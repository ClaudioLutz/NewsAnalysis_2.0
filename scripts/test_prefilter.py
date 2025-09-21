#!/usr/bin/env python3
"""
Test script for the embedding-based prefilter system.
Demonstrates both unsupervised tuning and runtime filtering.
"""

import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_sample_articles_from_db():
    """Extract real articles from the database for testing."""
    db_path = "news.db"
    if not os.path.exists(db_path):
        print("Database not found. Using sample CSV instead.")
        return None
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Get recent articles with titles
        query = """
        SELECT i.id, i.title, 'creditreform_insights' as topic
        FROM items i
        WHERE i.title IS NOT NULL 
        AND i.published_at >= date('now', '-7 days')
        ORDER BY i.published_at DESC
        LIMIT 50
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if len(df) == 0:
            print("No recent articles found in database. Using sample CSV instead.")
            return None
        
        # Save to temporary CSV
        csv_path = "data/db_articles_sample.csv"
        df.to_csv(csv_path, index=False)
        print(f"✓ Extracted {len(df)} articles from database → {csv_path}")
        return csv_path
        
    except Exception as e:
        print(f"Error extracting from database: {e}")
        return None

def test_prefilter_system():
    """Test the complete prefilter system."""
    print("\n🔍 Testing Embedding-Based Prefilter System")
    print("=" * 60)
    
    # Check if we can use real data from DB, otherwise use sample
    csv_path = create_sample_articles_from_db()
    if not csv_path:
        csv_path = "data/sample_last_week.csv"
        print(f"Using sample data: {csv_path}")
    
    if not os.path.exists(csv_path):
        print(f"❌ CSV file not found: {csv_path}")
        return False
    
    # Step 1: Train the prefilter model (unsupervised mode)
    print(f"\n📚 Step 1: Training prefilter model (unsupervised mode)")
    print("-" * 50)
    
    train_cmd = f"""python prefilter/tune_prefilter.py \
  --csv {csv_path} \
  --model text-embedding-3-small \
  --dims 512 \
  --alpha 0.7 \
  --seeds_file data/creditreform_seeds.txt \
  --unsup_quantile 0.85 \
  --out_model outputs/prefilter_model.json \
  --out_scores outputs/debug_scores.csv"""
    
    print(f"Command: {train_cmd.replace('  ', ' ')}")
    
    try:
        import subprocess
        result = subprocess.run(train_cmd.split(), capture_output=True, text=True, cwd=".")
        
        if result.returncode == 0:
            print("✓ Prefilter model training completed successfully")
            print(result.stdout)
        else:
            print("❌ Prefilter model training failed")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error running training command: {e}")
        return False
    
    # Step 2: Test runtime filtering
    print(f"\n🏃 Step 2: Testing runtime prefilter")
    print("-" * 50)
    
    try:
        from prefilter.prefilter_runtime import prefilter_titles
        
        # Load sample articles for filtering
        df = pd.read_csv(csv_path)
        articles = []
        for _, row in df.iterrows():
            articles.append({
                "id": str(row["id"]),
                "title": row["title"],
                "topic": row["topic"]
            })
        
        print(f"📄 Input: {len(articles)} articles")
        
        # Apply prefilter
        survivors, scores = prefilter_titles(articles, "outputs/prefilter_model.json")
        
        print(f"✅ Output: {len(survivors)} articles survived prefilter")
        print(f"📊 Retention rate: {len(survivors)/len(articles)*100:.1f}%")
        
        # Show top scoring articles
        print(f"\n🏆 Top 5 Articles by Prefilter Score:")
        print("-" * 50)
        scores_sorted = sorted(scores, key=lambda x: x[1], reverse=True)
        for i, (article_id, score) in enumerate(scores_sorted[:5], 1):
            # Find the article title
            article = next(a for a in articles if a["id"] == article_id)
            print(f"{i}. Score: {score:.3f} | {article['title']}")
        
        # Show bottom scoring articles that were filtered out
        filtered_out = [a for a in articles if a not in survivors]
        if filtered_out:
            print(f"\n❌ Bottom 3 Articles (Filtered Out):")
            print("-" * 50)
            for i, (article_id, score) in enumerate(scores_sorted[-3:], 1):
                article = next(a for a in articles if a["id"] == article_id)
                if article in filtered_out:
                    print(f"{i}. Score: {score:.3f} | {article['title']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing runtime prefilter: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("🚀 Embedding-Based Prefilter System Test")
    print("This will demonstrate cost-effective article filtering using OpenAI embeddings")
    print("before expensive LLM classification.")
    
    # Check dependencies
    try:
        import numpy as np
        import pandas as pd
        from openai import OpenAI
        print("✓ Required dependencies found")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please install: pip install numpy pandas openai")
        return False
    
    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY environment variable not set")
        return False
    
    print("✓ OpenAI API key found")
    
    # Run the test
    success = test_prefilter_system()
    
    if success:
        print(f"\n🎉 Prefilter system test completed successfully!")
        print("\nNext steps:")
        print("1. Integrate prefilter_titles() into your news pipeline")
        print("2. Monitor API cost savings vs. LLM classification")
        print("3. Retrain model weekly with fresh data")
        print("4. Consider using FAISS for large article volumes (>50k)")
    else:
        print(f"\n❌ Prefilter system test failed")
    
    return success

if __name__ == "__main__":
    main()
