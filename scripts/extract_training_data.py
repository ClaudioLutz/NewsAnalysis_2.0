#!/usr/bin/env python3
"""
Extract real classified training data from the database for prefilter training.
"""

import sqlite3
import pandas as pd
import os

def extract_training_data():
    """Extract classified articles from database and create training CSV."""
    conn = sqlite3.connect('news.db')
    
    # Check distribution of classifications
    cursor = conn.cursor()
    cursor.execute("SELECT is_match, COUNT(*) FROM items WHERE is_match IS NOT NULL GROUP BY is_match;")
    distribution = cursor.fetchall()
    
    print("=== CLASSIFICATION DISTRIBUTION ===")
    total_classified = 0
    for match_value, count in distribution:
        print(f"is_match = {match_value}: {count} articles")
        total_classified += count
    print(f"Total classified articles: {total_classified}")
    
    # Extract all classified articles
    print("\n=== EXTRACTING TRAINING DATA ===")
    query = """
        SELECT title, is_match, triage_confidence, triage_topic
        FROM items 
        WHERE is_match IS NOT NULL 
        AND title IS NOT NULL 
        AND title != ''
        ORDER BY id DESC;
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"Extracted {len(df)} articles with classifications")
    print(f"Positive examples (is_match=1): {len(df[df['is_match'] == 1])}")
    print(f"Negative examples (is_match=0): {len(df[df['is_match'] == 0])}")
    
    # Show sample of positive and negative examples
    print("\n=== SAMPLE POSITIVE EXAMPLES (is_match=1) ===")
    positive_samples = df[df['is_match'] == 1].head(5)
    for _, row in positive_samples.iterrows():
        print(f"Title: {row['title'][:80]}...")
        print(f"  Confidence: {row['triage_confidence']}")
        print()
    
    print("=== SAMPLE NEGATIVE EXAMPLES (is_match=0) ===")
    negative_samples = df[df['is_match'] == 0].head(5)
    for _, row in negative_samples.iterrows():
        print(f"Title: {row['title'][:80]}...")
        print(f"  Confidence: {row['triage_confidence']}")
        print()
    
    # Create training CSV in the expected format
    # The prefilter expects: id,title,topic,label (supervised mode)
    training_df = pd.DataFrame({
        'id': range(len(df)),  # Generate sequential IDs
        'title': df['title'],
        'topic': 'creditreform_insights',  # All articles are for this topic
        'label': df['is_match']
    })
    
    # Save to data directory
    os.makedirs('data', exist_ok=True)
    training_file = 'data/real_training_data.csv'
    training_df.to_csv(training_file, index=False)
    
    print(f"\n=== TRAINING DATA SAVED ===")
    print(f"File: {training_file}")
    print(f"Total records: {len(training_df)}")
    print(f"Format: title,label (where label: 1=relevant, 0=irrelevant)")
    
    return training_file

if __name__ == "__main__":
    extract_training_data()
