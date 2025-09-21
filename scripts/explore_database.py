#!/usr/bin/env python3
"""
Script to explore the database structure and extract classified data for prefilter training.
"""

import sqlite3
import pandas as pd

def explore_database():
    """Explore the database schema and show sample data."""
    conn = sqlite3.connect('news.db')
    
    # Get all tables
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print("=== DATABASE TABLES ===")
    for table in tables:
        print(f"- {table[0]}")
    
    # Explore all key table structures
    key_tables = ['items', 'summaries', 'articles']
    
    for table_name in key_tables:
        print(f"\n=== {table_name.upper()} TABLE SCHEMA ===")
        try:
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            for col in columns:
                print(f"- {col[1]} ({col[2]})")
            
            # Count records
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"Total records: {count}")
        except Exception as e:
            print(f"Error exploring {table_name}: {e}")
    
    # Check for classification columns in items table
    print("\n=== LOOKING FOR CLASSIFICATION DATA ===")
    
    # Check items table for classification columns
    try:
        cursor.execute("PRAGMA table_info(items);")
        item_columns = [col[1] for col in cursor.fetchall()]
        print(f"Items table columns: {item_columns}")
        
        # Look for classification-related columns
        classification_cols = [col for col in item_columns if any(keyword in col.lower() for keyword in ['match', 'triage', 'relevance', 'selected', 'classified'])]
        print(f"Potential classification columns: {classification_cols}")
        
        if classification_cols:
            # Sample some data
            print("\n=== SAMPLE CLASSIFICATION DATA FROM ITEMS ===")
            sample_cols = ['id', 'title']
            sample_cols.extend(classification_cols[:3])  # Add up to 3 classification columns
            
            query = f"SELECT {', '.join(sample_cols)} FROM items WHERE {classification_cols[0]} IS NOT NULL ORDER BY id DESC LIMIT 5;"
            cursor.execute(query)
            samples = cursor.fetchall()
            
            for sample in samples:
                for i, col in enumerate(sample_cols):
                    if col == 'title' and sample[i]:
                        print(f"  {col}: {sample[i][:80]}...")
                    else:
                        print(f"  {col}: {sample[i]}")
                print()
    
    except Exception as e:
        print(f"Error checking items table: {e}")
    
    # Check summaries table for classification data
    try:
        cursor.execute("PRAGMA table_info(summaries);")
        summary_columns = [col[1] for col in cursor.fetchall()]
        print(f"\nSummaries table columns: {summary_columns}")
        
        # Look for classification-related columns
        classification_cols = [col for col in summary_columns if any(keyword in col.lower() for keyword in ['match', 'triage', 'relevance', 'selected', 'classified'])]
        print(f"Potential classification columns: {classification_cols}")
        
        if classification_cols:
            print("\n=== SAMPLE CLASSIFICATION DATA FROM SUMMARIES ===")
            cursor.execute(f"SELECT item_id, {classification_cols[0]} FROM summaries WHERE {classification_cols[0]} IS NOT NULL LIMIT 5;")
            summary_samples = cursor.fetchall()
            for sample in summary_samples:
                print(f"  item_id: {sample[0]}, {classification_cols[0]}: {sample[1]}")
    
    except Exception as e:
        print(f"Error checking summaries table: {e}")
    
    conn.close()

if __name__ == "__main__":
    explore_database()
