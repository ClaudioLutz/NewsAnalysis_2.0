#!/usr/bin/env python3
"""
Digest State Migration Cleanup Script

Clears all cached digest state to enable schema migration from old format
(with bullets/executive_summary) to new format (headline/why_it_matters only).

This is a one-time migration script for Epic 010 - Cost Optimization.
"""

import sqlite3
import json
from datetime import datetime

def main():
    db_path = 'news.db'
    
    print("=" * 80)
    print("Digest State Migration Cleanup")
    print("Epic 010: Cost Optimization - Schema Migration")
    print("=" * 80)
    print()
    print("This will clear all cached digest state to enable clean migration to new schema.")
    print("Old format (bullets + executive_summary) → New format (headline + why_it_matters)")
    print()
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Show current state
    print("Current digest state entries:")
    print("-" * 80)
    
    cursor = conn.execute("""
        SELECT digest_date, topic, article_count, 
               LENGTH(digest_content) as content_size,
               created_at, updated_at
        FROM digest_state 
        ORDER BY digest_date DESC, topic
    """)
    
    rows = cursor.fetchall()
    
    if not rows:
        print("No digest state found. Nothing to clean.")
        conn.close()
        return 0
    
    total_articles = 0
    for row in rows:
        print(f"Date: {row['digest_date']}, Topic: {row['topic']}")
        print(f"  Articles: {row['article_count']}, Size: {row['content_size']} bytes")
        print(f"  Created: {row['created_at']}, Updated: {row['updated_at']}")
        
        # Check if old format
        cursor2 = conn.execute(
            "SELECT digest_content FROM digest_state WHERE digest_date = ? AND topic = ?",
            (row['digest_date'], row['topic'])
        )
        content_row = cursor2.fetchone()
        if content_row:
            try:
                digest_data = json.loads(content_row['digest_content'])
                has_old_format = 'bullets' in digest_data or 'executive_summary' in digest_data
                if has_old_format:
                    print(f"  ⚠️  OLD FORMAT DETECTED (contains bullets/executive_summary)")
            except:
                pass
        
        total_articles += row['article_count']
        print()
    
    print(f"Total: {len(rows)} digest state(s), {total_articles} articles tracked")
    print()
    
    # Confirmation
    print("⚠️  WARNING: This action will DELETE all digest state entries.")
    print("   The next pipeline run will regenerate digests from scratch.")
    print()
    response = input("Type 'yes' to confirm deletion: ")
    
    if response.lower() != 'yes':
        print("Cleanup cancelled.")
        conn.close()
        return 1
    
    # Perform deletion
    print()
    print("Deleting digest state...")
    
    cursor = conn.execute("DELETE FROM digest_state")
    deleted_count = cursor.rowcount
    
    conn.commit()
    
    # Verify deletion
    cursor = conn.execute("SELECT COUNT(*) FROM digest_state")
    remaining = cursor.fetchone()[0]
    
    conn.close()
    
    # Log completion
    timestamp = datetime.now().isoformat()
    print()
    print("✅ Digest state cleared successfully")
    print(f"   Deleted: {deleted_count} entries")
    print(f"   Remaining: {remaining} entries")
    print(f"   Timestamp: {timestamp}")
    print()
    print("Migration preparation complete. Ready for first run with new schema.")
    print()
    
    # Document the cleanup
    migration_note = f"""# Digest State Cleanup - {timestamp.split('T')[0]}

## Migration Event
- **Epic:** 010 - Cost Optimization  
- **Story:** 010.4 - State Management Migration
- **Timestamp:** {timestamp}

## Action Taken
Cleared all digest state entries to enable schema migration.

## Details
- **Entries deleted:** {deleted_count}
- **Total articles tracked:** {total_articles}
- **Reason:** Migration from old format (bullets/executive_summary) to new format (headline/why_it_matters)

## Old Format
- `bullets`: Array of 4-6 key insights
- `executive_summary`: Text summary
- Cost: ~150-200 tokens/digest

## New Format
- `headline`: Single impactful headline
- `why_it_matters`: Concise explanation
- Expected savings: 15-20% reduction in tokens

## Status
- ✅ State cleanup complete
- ⏭️ Ready for first run with new schema
- 📝 Next: Run pipeline to verify migration success

## Verification Required
1. Run pipeline: `python news_analyzer.py`
2. Check logs for schema validation errors
3. Verify digests generated without bullets
4. Test incremental update (run pipeline again)
"""
    
    with open('docs/migration-notes/digest-state-cleanup.md', 'w', encoding='utf-8') as f:
        f.write(migration_note)
    
    print(f"📝 Migration notes saved to: docs/migration-notes/digest-state-cleanup.md")
    print()
    
    return 0

if __name__ == "__main__":
    exit(main())
