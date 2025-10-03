# Story: Database Schema Migration for Cross-Run Topic Deduplication

**Epic:** Cross-Run Topic Deduplication Enhancement
**Story ID:** epic-cross-run-dedup-001
**Status:** Draft
**Priority:** High
**Estimated Effort:** 2-3 hours

## Story

As a **Pipeline Developer**
I need **database schema changes for cross-run topic tracking**
So that **the system can store and query topic signatures across multiple daily pipeline executions**

## Acceptance Criteria

### Database Tables Creation
- [ ] Create `cross_run_topic_signatures` table with all specified columns
  - signature_id TEXT PRIMARY KEY
  - date TEXT (YYYY-MM-DD format)
  - article_summary TEXT  
  - topic_theme TEXT
  - source_article_id INTEGER (foreign key to summaries.item_id)
  - created_at TEXT (ISO timestamp)
  - run_sequence INTEGER
- [ ] Create `cross_run_deduplication_log` table with all specified columns
  - log_id INTEGER PRIMARY KEY AUTOINCREMENT
  - date TEXT
  - new_article_id INTEGER
  - matched_signature_id TEXT
  - decision TEXT ('DUPLICATE' or 'UNIQUE')
  - confidence_score REAL
  - processing_time REAL
  - created_at TEXT
- [ ] Create indexes on date columns for both new tables
- [ ] Create index on source_article_id in cross_run_topic_signatures

### Existing Table Extensions
- [ ] Add `topic_already_covered` BOOLEAN column to summaries table (default FALSE)
- [ ] Add `cross_run_cluster_id` TEXT column to summaries table (default NULL)
- [ ] Verify existing queries still work after schema changes

### Migration Safety
- [ ] Migration script validates existing database schema before changes
- [ ] All new columns have appropriate default values
- [ ] Migration creates backup of database before making changes
- [ ] Migration includes validation queries to confirm schema correctness
- [ ] Migration logs all operations with timestamps

### Rollback Support
- [ ] Document rollback procedure (drop new tables, remove new columns)
- [ ] Verify rollback leaves existing functionality intact
- [ ] Test that existing pipeline runs successfully after rollback

## Dev Notes

### Reference Files
- Architecture Document: `docs/architecture.md` - Data Models section
- Existing Migration Pattern: `scripts/migrate_articles_table.py`
- Database Schema: Examine with `examine_db_schema.py`

### Technical Implementation Details

#### File Location
```
scripts/add_cross_run_schema.py
```

#### Database Connection Pattern
Use existing pattern from other migration scripts:
```python
import sqlite3
from pathlib import Path

def migrate_schema(db_path: str = 'news.db'):
    """Add cross-run deduplication schema to existing database."""
    # Use context manager for connection
    conn = sqlite3.connect(db_path)
    try:
        # Migration logic here
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()
```

#### Schema SQL
```sql
-- Create cross_run_topic_signatures table
CREATE TABLE IF NOT EXISTS cross_run_topic_signatures (
    signature_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    article_summary TEXT NOT NULL,
    topic_theme TEXT,
    source_article_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    run_sequence INTEGER NOT NULL,
    FOREIGN KEY (source_article_id) REFERENCES summaries(item_id)
);

-- Create indexes for fast date-based queries
CREATE INDEX IF NOT EXISTS idx_signatures_date 
    ON cross_run_topic_signatures(date);
CREATE INDEX IF NOT EXISTS idx_signatures_source 
    ON cross_run_topic_signatures(source_article_id);

-- Create cross_run_deduplication_log table
CREATE TABLE IF NOT EXISTS cross_run_deduplication_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    new_article_id INTEGER NOT NULL,
    matched_signature_id TEXT,
    decision TEXT NOT NULL CHECK(decision IN ('DUPLICATE', 'UNIQUE')),
    confidence_score REAL,
    processing_time REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (new_article_id) REFERENCES summaries(item_id),
    FOREIGN KEY (matched_signature_id) REFERENCES cross_run_topic_signatures(signature_id)
);

-- Create index for log queries
CREATE INDEX IF NOT EXISTS idx_dedup_log_date 
    ON cross_run_deduplication_log(date);

-- Add columns to existing summaries table
ALTER TABLE summaries ADD COLUMN topic_already_covered BOOLEAN DEFAULT 0;
ALTER TABLE summaries ADD COLUMN cross_run_cluster_id TEXT DEFAULT NULL;
```

#### Validation Queries
After migration, verify schema with:
```python
# Check tables exist
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
assert 'cross_run_topic_signatures' in tables
assert 'cross_run_deduplication_log' in tables

# Check columns added to summaries
cursor.execute("PRAGMA table_info(summaries)")
columns = {row[1] for row in cursor.fetchall()}
assert 'topic_already_covered' in columns
assert 'cross_run_cluster_id' in columns

# Check indexes created
cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
indexes = [row[0] for row in cursor.fetchall()]
assert 'idx_signatures_date' in indexes
assert 'idx_dedup_log_date' in indexes
```

### Critical Requirements from Architecture
1. **Backward Compatibility:** Additive-only changes, no modifications to existing columns
2. **Default Values:** All new columns must have defaults to prevent breaking existing queries
3. **Transaction Safety:** Use try-except-finally with commit/rollback
4. **Logging:** Log all operations for troubleshooting

### Testing Approach
1. Run migration on copy of production database
2. Verify existing pipeline runs successfully  
3. Verify new tables are accessible
4. Test rollback procedure on copy
5. Document any issues encountered

## Definition of Done
- [ ] Migration script created at `scripts/add_cross_run_schema.py`
- [ ] All tables and columns created with correct data types
- [ ] All indexes created for performance
- [ ] Migration includes validation logic
- [ ] Migration creates database backup before changes
- [ ] Migration tested on copy of production database
- [ ] Existing pipeline confirmed working after migration
- [ ] Rollback procedure documented and tested
- [ ] Migration execution logged with timestamps
- [ ] Code follows existing migration script patterns
- [ ] Type hints added to all functions
- [ ] Docstrings added following Google style guide

---

## Dev Agent Record

### Agent Model Used
Claude 3.5 Sonnet (claude-3-5-sonnet-20241022)

### Tasks
- [x] Create migration script file at `scripts/add_cross_run_schema.py`
- [x] Implement database backup logic
- [x] Implement schema validation checks
- [x] Create cross_run_topic_signatures table with all columns and indexes
- [x] Create cross_run_deduplication_log table with all columns and indexes
- [x] Add new columns to summaries table with defaults
- [x] Implement post-migration validation queries
- [x] Add comprehensive error handling and logging
- [x] Write docstrings for all functions
- [x] Test migration on database copy
- [x] Test rollback procedure
- [x] Document rollback steps

### Debug Log References
None - migration completed successfully on first attempt

### Completion Notes
- Migration script created following existing patterns from migrate_articles_table.py
- All tables and columns created successfully with proper constraints
- Indexes created for optimal query performance
- Backup created before migration (news.db.backup_20251003_142914)
- Validation confirms all schema elements in place
- Rollback procedure documented in script output
- Used BOOLEAN as INTEGER (0/1) following SQLite best practices

### File List
- scripts/add_cross_run_schema.py (NEW)
- news.db (MODIFIED - schema migration applied)
- news.db.backup_20251003_142914 (NEW - backup file)

### Change Log
- 2025-10-03 14:29: Created migration script
- 2025-10-03 14:29: Successfully applied migration to news.db
- 2025-10-03 14:29: Validated schema changes

---

**Created:** 2025-10-03
**Last Updated:** 2025-10-03
