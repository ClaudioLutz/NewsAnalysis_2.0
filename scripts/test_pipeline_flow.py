#!/usr/bin/env python3
"""
Pipeline Flow Validation Test

Tests the complete pipeline flow to ensure articles progress correctly
through all stages with proper run_id tracking and validation.
"""

import os
import sys
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def test_pipeline_flow():
    """Test that articles flow correctly through all pipeline stages."""
    
    db_path = os.getenv("DB_PATH", "./news.db")
    
    print("=== Pipeline Flow Validation Test ===")
    print(f"Database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    # Get recent pipeline runs
    cursor = conn.execute("""
        SELECT DISTINCT pipeline_run_id, COUNT(*) as articles
        FROM items 
        WHERE pipeline_run_id IS NOT NULL
        AND pipeline_run_id != ''
        GROUP BY pipeline_run_id
        ORDER BY MAX(first_seen_at) DESC
        LIMIT 5
    """)
    
    recent_runs = cursor.fetchall()
    
    if not recent_runs:
        print("❌ No pipeline runs found in database")
        print("   Run the pipeline first: python news_analyzer.py")
        conn.close()
        return False
    
    print(f"\n📊 Found {len(recent_runs)} recent pipeline runs:")
    for run_id, count in recent_runs:
        print(f"   {run_id}: {count} articles")
    
    # Test the most recent run
    test_run_id = recent_runs[0][0]
    print(f"\n🔍 Testing pipeline run: {test_run_id}")
    
    # Test 1: Stage progression validation
    print("\n1. Stage Progression Validation")
    cursor = conn.execute("""
        SELECT pipeline_stage, COUNT(*) as count
        FROM items 
        WHERE pipeline_run_id = ?
        GROUP BY pipeline_stage
        ORDER BY 
            CASE pipeline_stage
                WHEN 'collected' THEN 1
                WHEN 'matched' THEN 2
                WHEN 'selected' THEN 3
                WHEN 'scraped' THEN 4
                WHEN 'summarized' THEN 5
                WHEN 'filtered_out' THEN 6
                ELSE 7
            END
    """, (test_run_id,))
    
    stage_counts = cursor.fetchall()
    funnel_valid = True
    
    stage_dict = {stage: count for stage, count in stage_counts}
    
    for stage, count in stage_counts:
        print(f"   {stage}: {count} articles")
    
    # Validate funnel logic: collected >= matched >= selected >= scraped >= summarized
    collected = stage_dict.get('collected', 0)
    matched = stage_dict.get('matched', 0)
    selected = stage_dict.get('selected', 0)  
    scraped = stage_dict.get('scraped', 0)
    summarized = stage_dict.get('summarized', 0)
    
    if not (collected >= matched >= selected >= scraped >= summarized):
        print("   ❌ FAIL: Invalid funnel progression")
        funnel_valid = False
    else:
        print("   ✅ PASS: Valid funnel progression")
    
    # Test 2: Selection rank validation
    print("\n2. Selection Rank Validation")
    cursor = conn.execute("""
        SELECT selection_rank, COUNT(*) as count
        FROM items
        WHERE pipeline_run_id = ? 
        AND selected_for_processing = 1
        AND selection_rank IS NOT NULL
        GROUP BY selection_rank
        ORDER BY selection_rank
    """, (test_run_id,))
    
    ranks = cursor.fetchall()
    rank_valid = True
    
    if ranks:
        expected_rank = 1
        for rank, count in ranks:
            if rank != expected_rank:
                print(f"   ❌ FAIL: Gap in selection ranks - found rank {rank}, expected {expected_rank}")
                rank_valid = False
                break
            if count != 1:
                print(f"   ❌ FAIL: Duplicate selection rank {rank} ({count} articles)")
                rank_valid = False
                break
            expected_rank += 1
        
        if rank_valid:
            print(f"   ✅ PASS: Selection ranks 1-{len(ranks)} are continuous and unique")
    else:
        print("   ⚠️  WARNING: No articles have selection ranks")
    
    # Test 3: Critical error detection
    print("\n3. Critical Error Detection")
    
    # Check for selected articles that already have summaries
    cursor = conn.execute("""
        SELECT COUNT(*) 
        FROM items i
        JOIN summaries s ON i.id = s.item_id
        WHERE i.pipeline_run_id = ? 
        AND i.selected_for_processing = 1
    """, (test_run_id,))
    
    already_summarized = cursor.fetchone()[0]
    
    if already_summarized > 0:
        print(f"   ❌ CRITICAL: {already_summarized} selected articles already have summaries!")
        funnel_valid = False
    else:
        print("   ✅ PASS: No selected articles have existing summaries")
    
    # Check for selection without matching
    cursor = conn.execute("""
        SELECT COUNT(*) 
        FROM items
        WHERE pipeline_run_id = ?
        AND selected_for_processing = 1
        AND is_match != 1
    """, (test_run_id,))
    
    selected_not_matched = cursor.fetchone()[0]
    
    if selected_not_matched > 0:
        print(f"   ❌ ERROR: {selected_not_matched} selected articles are not marked as matches!")
        funnel_valid = False
    else:
        print("   ✅ PASS: All selected articles are properly matched")
    
    # Test 4: Run ID consistency
    print("\n4. Run ID Consistency")
    cursor = conn.execute("""
        SELECT 
            COUNT(CASE WHEN pipeline_run_id IS NULL THEN 1 END) as no_run_id,
            COUNT(CASE WHEN pipeline_run_id = ? THEN 1 END) as correct_run_id,
            COUNT(CASE WHEN pipeline_run_id IS NOT NULL AND pipeline_run_id != ? THEN 1 END) as other_run_id
        FROM items
        WHERE pipeline_stage IN ('collected', 'matched', 'selected', 'scraped', 'summarized')
        AND first_seen_at > datetime('now', '-1 day')
    """, (test_run_id, test_run_id))
    
    run_id_stats = cursor.fetchone()
    
    print(f"   Articles with correct run_id: {run_id_stats[1]}")
    print(f"   Articles with no run_id: {run_id_stats[0]}")  
    print(f"   Articles with other run_id: {run_id_stats[2]}")
    
    if run_id_stats[0] > 0:
        print("   ⚠️  WARNING: Some recent articles have no run_id")
    else:
        print("   ✅ PASS: All processed articles have run_id")
    
    # Test 5: Deduplication validation
    print("\n5. Deduplication Validation")
    cursor = conn.execute("""
        SELECT COUNT(*) FROM article_clusters
    """)
    
    clusters = cursor.fetchone()[0]
    
    if clusters > 0:
        cursor = conn.execute("""
            SELECT 
                COUNT(CASE WHEN is_primary = 1 THEN 1 END) as primary_articles,
                COUNT(CASE WHEN is_primary = 0 THEN 1 END) as duplicate_articles,
                COUNT(DISTINCT cluster_id) as total_clusters
            FROM article_clusters
        """)
        
        dedup_stats = cursor.fetchone()
        print(f"   ✅ PASS: Deduplication active - {dedup_stats[2]} clusters, {dedup_stats[1]} duplicates marked")
    else:
        print("   ⚠️  INFO: No deduplication clusters found (may be first run)")
    
    # Final summary
    print(f"\n{'='*50}")
    print("VALIDATION SUMMARY")
    print(f"{'='*50}")
    
    all_tests_passed = funnel_valid and rank_valid and already_summarized == 0 and selected_not_matched == 0
    
    if all_tests_passed:
        print("✅ ALL TESTS PASSED - Pipeline flow is working correctly!")
        print(f"\n📈 Pipeline Efficiency for run {test_run_id}:")
        if collected > 0:
            print(f"   Collection → Matching: {(matched/collected)*100:.1f}% ({matched}/{collected})")
        if matched > 0:
            print(f"   Matching → Selection: {(selected/matched)*100:.1f}% ({selected}/{matched})")
        if selected > 0:
            print(f"   Selection → Scraping: {(scraped/selected)*100:.1f}% ({scraped}/{selected})")
        if scraped > 0:
            print(f"   Scraping → Summarization: {(summarized/scraped)*100:.1f}% ({summarized}/{scraped})")
    else:
        print("❌ SOME TESTS FAILED - Pipeline flow has issues that need attention!")
        print("\nRecommended actions:")
        if not funnel_valid:
            print("   - Check pipeline stage transitions")
        if not rank_valid:
            print("   - Validate selection ranking logic")
        if already_summarized > 0:
            print("   - Fix selection logic to exclude already-summarized articles")
        if selected_not_matched > 0:
            print("   - Ensure only matched articles can be selected")
    
    conn.close()
    return all_tests_passed

def monitor_pipeline_performance():
    """Monitor pipeline performance across recent runs."""
    
    db_path = os.getenv("DB_PATH", "./news.db")
    conn = sqlite3.connect(db_path)
    
    print("\n=== Pipeline Performance Monitor ===")
    
    # Get performance metrics for last 5 runs
    cursor = conn.execute("""
        SELECT 
            pipeline_run_id,
            COUNT(*) as total_articles,
            SUM(CASE WHEN is_match = 1 THEN 1 ELSE 0 END) as matched,
            SUM(CASE WHEN selected_for_processing = 1 THEN 1 ELSE 0 END) as selected,
            SUM(CASE WHEN pipeline_stage = 'scraped' THEN 1 ELSE 0 END) as scraped,
            SUM(CASE WHEN pipeline_stage = 'summarized' THEN 1 ELSE 0 END) as summarized,
            MIN(first_seen_at) as run_start
        FROM items
        WHERE pipeline_run_id IS NOT NULL
        GROUP BY pipeline_run_id
        ORDER BY run_start DESC
        LIMIT 5
    """)
    
    runs = cursor.fetchall()
    
    if runs:
        print("\n📊 Recent Pipeline Performance:")
        print("-" * 80)
        print(f"{'Run ID':<20} {'Total':<7} {'Match%':<7} {'Sel%':<6} {'Scr%':<6} {'Sum%':<6}")
        print("-" * 80)
        
        for run in runs:
            run_id, total, matched, selected, scraped, summarized, _ = run
            
            match_rate = (matched/total)*100 if total > 0 else 0
            sel_rate = (selected/matched)*100 if matched > 0 else 0  
            scr_rate = (scraped/selected)*100 if selected > 0 else 0
            sum_rate = (summarized/scraped)*100 if scraped > 0 else 0
            
            print(f"{run_id[:18]:<20} {total:<7} {match_rate:<6.1f}% {sel_rate:<5.1f}% {scr_rate:<5.1f}% {sum_rate:<5.1f}%")
    
    conn.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test pipeline flow validation")
    parser.add_argument("--monitor", action="store_true", help="Show performance monitoring")
    
    args = parser.parse_args()
    
    success = test_pipeline_flow()
    
    if args.monitor:
        monitor_pipeline_performance()
    
    sys.exit(0 if success else 1)
