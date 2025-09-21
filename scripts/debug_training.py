#!/usr/bin/env python3
"""
Debug the training process to understand why supervised mode isn't working.
"""

import pandas as pd
import numpy as np

def debug_training():
    """Debug the training CSV and process."""
    
    # Load and examine the training data
    df = pd.read_csv('data/real_training_data.csv')
    
    print("=== TRAINING DATA DEBUG ===")
    print(f"Shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")
    print()
    
    # Check for label column specifically
    has_label = "label" in df.columns
    print(f"Has 'label' column: {has_label}")
    
    if has_label:
        print(f"Label value counts:")
        print(df['label'].value_counts())
        print()
        
        # Sample some data
        print("=== SAMPLE POSITIVE EXAMPLES (label=1) ===")
        pos_samples = df[df['label'] == 1].head(3)
        for _, row in pos_samples.iterrows():
            print(f"- {row['title'][:60]}...")
        
        print("\n=== SAMPLE NEGATIVE EXAMPLES (label=0) ===")
        neg_samples = df[df['label'] == 0].head(3)
        for _, row in neg_samples.iterrows():
            print(f"- {row['title'][:60]}...")
    
    # Check if creditreform_seeds.txt exists
    try:
        with open('data/creditreform_seeds.txt', 'r', encoding='utf-8') as f:
            seeds = [line.strip() for line in f if line.strip()]
        print(f"\n=== FOUND SEEDS FILE ===")
        print(f"Seeds file has {len(seeds)} entries")
        print("First 3 seeds:")
        for seed in seeds[:3]:
            print(f"- {seed}")
    except FileNotFoundError:
        print("\n=== NO SEEDS FILE FOUND ===")
    
    # Check topics
    print(f"\n=== TOPICS ===")
    topics = df['topic'].unique()
    print(f"Unique topics: {topics}")
    for topic in topics:
        topic_data = df[df['topic'] == topic]
        print(f"Topic '{topic}': {len(topic_data)} articles")
        if has_label:
            label_dist = topic_data['label'].value_counts()
            print(f"  Label distribution: {dict(label_dist)}")

if __name__ == "__main__":
    debug_training()
