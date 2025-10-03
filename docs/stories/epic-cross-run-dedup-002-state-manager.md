# Story: Implement CrossRunStateManager

**Epic:** Cross-Run Topic Deduplication Enhancement
**Story ID:** epic-cross-run-dedup-002
**Status:** Draft
**Priority:** High
**Estimated Effort:** 3-4 hours
**Depends On:** epic-cross-run-dedup-001 (schema migration must be complete)

## Story

As a **Cross-Run Deduplication Component**
I need **a state manager to handle topic signature storage and retrieval**
So that **the system can persist and query topic signatures across multiple daily pipeline runs**

## Acceptance Criteria

### Core Functionality
- [ ] CrossRunStateManager class created in `news_pipeline/cross_run_state_manager.py`
- [ ] Initialization follows same pattern as existing StateManager (db_path parameter)
- [ ] All methods include comprehensive type hints
- [ ] All methods have Google-style docstrings

### Topic Signature Storage
- [ ] `store_topic_signature()` method stores signature with all required fields
  - Generates unique signature_id (using hashlib similar to existing patterns)
  - Stores article_summary, topic_theme, source_article_id
  - Records date, created_at, run_sequence
  - Uses transactional database operations with proper error handling
- [ ] Method returns signature_id for tracking
- [ ] Database operations use context managers (`with` statements)

### Topic Signature Retrieval
- [ ] `get_previous_signatures(date: str)` retrieves all signatures for specified date
  - Returns List[Dict] with all signature fields
  - Orders by run_sequence for chronological processing
  - Handles case when no signatures exist (returns empty list)
- [ ] `get_signature_by_id(signature_id: str)` retrieves single signature
  - Returns Dict or None if not found

### Cleanup Operations
- [ ] `cleanup_old_signatures(days_to_keep: int)` removes signatures older than threshold
  - Defaults to 7 days retention
  - Logs number of signatures deleted
  - Uses transactional operations

### Audit Logging
- [ ] `log_deduplication_decision()` records decision details
  - Stores article_id, matched_signature_id (if any), decision, confidence_score
  - Records processing_time and timestamp
  - Handles both DUPLICATE and UNIQUE decisions

### Error Handling
- [ ] All database errors caught and logged (don't crash)
- [ ] Returns appropriate default values on error (empty list, None, etc.)
- [ ] Uses existing logging patterns from `utils.py`

## Dev Notes

### Reference Files
- Architecture: `docs/architecture.md` - Component Architecture section
- Pattern Reference: `news_pipeline/state_manager.py` for existing state management patterns
- Database Patterns: `news_pipeline/gpt_deduplication.py` for connection handling

### Technical Implementation Details

#### File Location
```
news_pipeline/cross_run_state_manager.py
```

#### Class Structure
```python
"""
Cross-Run State Manager for Topic Signature Persistence

Manages storage, retrieval, and cleanup of topic signatures for cross-run
deduplication tracking. Follows existing StateManager patterns.
"""

import sqlite3
import hashlib
import logging
from datetime import datetime, timedelta, date as date_type
from typing import List, Dict, Any, Optional


class CrossRunStateManager:
    """
    Manages topic signature storage and retrieval for cross-run deduplication.
    
    Provides persistence layer for topic signatures that enable cross-run
    topic comparison and deduplication tracking across multiple daily
    pipeline executions.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize CrossRunStateManager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
    
    def store_topic_signature(
        self,
        article_summary: str,
        topic_theme: str,
        source_article_id: int,
        date: str,
        run_sequence: int
    ) -> str:
        """
        Store topic signature for cross-run comparison.
        
        Args:
            article_summary: Rich summary content for GPT comparison
            topic_theme: Extracted topic/theme identifier
            source_article_id: Reference to source article in summaries table
            date: Date in YYYY-MM-DD format
            run_sequence: Run number within the day (1, 2, 3...)
            
        Returns:
            signature_id: Unique identifier for stored signature
            
        Raises:
            sqlite3.Error: If database operation fails
        """
        # Generate signature_id from content + timestamp
        signature_id = hashlib.md5(
            f"{date}_{source_article_id}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO cross_run_topic_signatures
                (signature_id, date, article_summary, topic_theme, 
                 source_article_id, created_at, run_sequence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                signature_id,
                date,
                article_summary,
                topic_theme,
                source_article_id,
                datetime.now().isoformat(),
                run_sequence
            ))
            conn.commit()
            
            self.logger.debug(f"Stored topic signature {signature_id} for article {source_article_id}")
            return signature_id
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to store topic signature: {e}")
            raise
        finally:
            conn.close()
    
    def get_previous_signatures(self, date: str) -> List[Dict[str, Any]]:
        """
        Retrieve all topic signatures for specified date.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            List of signature dictionaries with all fields
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            cursor = conn.execute("""
                SELECT signature_id, date, article_summary, topic_theme,
                       source_article_id, created_at, run_sequence
                FROM cross_run_topic_signatures
                WHERE date = ?
                ORDER BY run_sequence, created_at
            """, (date,))
            
            signatures = []
            for row in cursor.fetchall():
                signatures.append({
                    'signature_id': row['signature_id'],
                    'date': row['date'],
                    'article_summary': row['article_summary'],
                    'topic_theme': row['topic_theme'],
                    'source_article_id': row['source_article_id'],
                    'created_at': row['created_at'],
                    'run_sequence': row['run_sequence']
                })
            
            self.logger.info(f"Retrieved {len(signatures)} signatures for {date}")
            return signatures
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve signatures for {date}: {e}")
            return []
        finally:
            conn.close()
    
    def cleanup_old_signatures(self, days_to_keep: int = 7) -> int:
        """
        Remove topic signatures older than specified threshold.
        
        Args:
            days_to_keep: Number of days to retain signatures (default 7)
            
        Returns:
            Number of signatures deleted
        """
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                DELETE FROM cross_run_topic_signatures
                WHERE date < ?
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            self.logger.info(f"Cleaned up {deleted_count} signatures older than {days_to_keep} days")
            return deleted_count
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to cleanup old signatures: {e}")
            return 0
        finally:
            conn.close()
    
    def log_deduplication_decision(
        self,
        article_id: int,
        decision: str,
        date: str,
        matched_signature_id: Optional[str] = None,
        confidence_score: Optional[float] = None,
        processing_time: float = 0.0
    ) -> None:
        """
        Log deduplication decision for audit trail.
        
        Args:
            article_id: Article being evaluated
            decision: 'DUPLICATE' or 'UNIQUE'
            date: Processing date
            matched_signature_id: Signature matched against (if duplicate)
            confidence_score: GPT comparison confidence (if available)
            processing_time: Time taken for comparison in seconds
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO cross_run_deduplication_log
                (date, new_article_id, matched_signature_id, decision,
                 confidence_score, processing_time, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                date,
                article_id,
                matched_signature_id,
                decision,
                confidence_score,
                processing_time,
                datetime.now().isoformat()
            ))
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to log deduplication decision: {e}")
        finally:
            conn.close()
```

### Critical Requirements from Architecture
1. **Pattern Consistency:** Match existing StateManager initialization and method signatures
2. **Context Managers:** All database operations use `with` statements or try-except-finally
3. **Type Hints:** Comprehensive type hints on all methods
4. **Error Handling:** Log errors but return defaults, don't crash
5. **Logging:** Use self.logger for all logging operations

### Testing Approach
Create unit tests in `scripts/test_cross_run_dedup.py`:
```python
def test_store_and_retrieve_signatures():
    """Test storing and retrieving topic signatures."""
    # Create manager, store signature, retrieve and verify
    
def test_signature_cleanup():
    """Test cleanup of old signatures."""
    # Store signatures with old dates, run cleanup, verify deletion
    
def test_deduplication_logging():
    """Test audit log entries."""
    # Log decisions, query log table, verify entries
    
def test_error_handling():
    """Test error handling with invalid data."""
    # Test with missing database, invalid data, verify graceful handling
```

## Definition of Done
- [ ] CrossRunStateManager class created with all required methods
- [ ] All methods have type hints following existing patterns
- [ ] All methods have comprehensive Google-style docstrings
- [ ] Database operations use context managers
- [ ] Error handling implemented for all database operations
- [ ] Signature ID generation uses hashlib (similar to existing code)
- [ ] Unit tests created and passing (>80% coverage)
- [ ] Tested with actual database (not just mocks)
- [ ] Logging uses existing logger patterns
- [ ] Code follows PEP 8 style guide
- [ ] No pylint warnings or errors

---

## Dev Agent Record

### Agent Model Used
Claude 3.5 Sonnet (claude-3-5-sonnet-20241022)

### Tasks
- [x] Create `news_pipeline/cross_run_state_manager.py` file
- [x] Implement CrossRunStateManager class with __init__
- [x] Implement store_topic_signature method
- [x] Implement get_previous_signatures method  
- [x] Implement get_signature_by_id method
- [x] Implement cleanup_old_signatures method
- [x] Implement log_deduplication_decision method
- [x] Add type hints to all methods
- [x] Write comprehensive docstrings
- [x] Add error handling and logging
- [ ] Create unit tests in scripts/test_cross_run_dedup.py (deferred to Story 6)
- [ ] Test with actual database (deferred to Story 6)

### Debug Log References
None - implementation completed following existing patterns

### Completion Notes
- CrossRunStateManager created following PipelineStateManager patterns
- All methods implement proper error handling with try-except-finally
- Type hints added for all parameters and return values
- Google-style docstrings for all methods
- Database operations use context management pattern
- Signature ID generation uses hashlib MD5 (consistent with existing code)
- Logging integrated throughout using self.logger
- Returns defaults on error (empty list, None) to enable graceful degradation
- Unit tests will be created in Story 6 comprehensive testing

### File List
- news_pipeline/cross_run_state_manager.py (NEW)

### Change Log
- 2025-10-03 14:30: Created CrossRunStateManager class
- 2025-10-03 14:30: Implemented all required methods with error handling

---

**Created:** 2025-10-03
**Last Updated:** 2025-10-03
