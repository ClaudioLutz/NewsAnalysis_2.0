#!/usr/bin/env python3
"""
Comprehensive test suite for cross-run topic deduplication.

Tests all new components and integration points for the cross-run
deduplication enhancement.
"""

import pytest
import sqlite3
import os
import sys
import time
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add parent directory to path to import from news_pipeline
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Now we can import normally, but we need to mock the problematic imports
# from news_pipeline.__init__.py to avoid dependency issues
import importlib.util

# First, create a minimal news_pipeline package in sys.modules
sys.modules['news_pipeline'] = type(sys)('news_pipeline')
sys.modules['news_pipeline'].__path__ = [str(parent_dir / 'news_pipeline')]

# Import our specific modules directly
spec = importlib.util.spec_from_file_location(
    "news_pipeline.cross_run_state_manager",
    parent_dir / "news_pipeline" / "cross_run_state_manager.py"
)
state_mgr_module = importlib.util.module_from_spec(spec)
sys.modules['news_pipeline.cross_run_state_manager'] = state_mgr_module
spec.loader.exec_module(state_mgr_module)

# Now import deduplication which has relative imports
spec = importlib.util.spec_from_file_location(
    "news_pipeline.cross_run_deduplication",
    parent_dir / "news_pipeline" / "cross_run_deduplication.py"
)
dedup_module = importlib.util.module_from_spec(spec)
sys.modules['news_pipeline.cross_run_deduplication'] = dedup_module
spec.loader.exec_module(dedup_module)

CrossRunStateManager = state_mgr_module.CrossRunStateManager
CrossRunTopicDeduplicator = dedup_module.CrossRunTopicDeduplicator


@pytest.fixture
def test_db():
    """Create a test database with schema."""
    db_path = 'test_cross_run_dedup.db'
    
    # Remove if exists
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            # Windows file locking - wait and retry
            import time
            time.sleep(0.1)
            try:
                os.remove(db_path)
            except:
                pass  # Will be removed in next test run
    
    # Create base tables needed for testing
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        -- Create items table
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pipeline_run_id TEXT,
            pipeline_stage TEXT,
            is_match INTEGER DEFAULT 0,
            selected_for_processing INTEGER DEFAULT 0
        );
        
        -- Create summaries table
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            summary TEXT NOT NULL,
            topic TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            topic_already_covered INTEGER DEFAULT 0,
            cross_run_cluster_id TEXT,
            FOREIGN KEY (item_id) REFERENCES items(id)
        );
    """)
    conn.commit()
    conn.close()
    
    # Run migration to add cross-run tables
    from scripts.add_cross_run_schema import migrate_schema
    migrate_schema(db_path, create_if_missing=True)
    
    yield db_path
    
    # Cleanup - ensure all connections are closed
    import gc
    gc.collect()  # Force garbage collection to close any lingering connections
    
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except PermissionError:
        # Windows file locking - not critical for tests
        pass


@pytest.fixture
def populated_db(test_db):
    """Create a database with sample data."""
    conn = sqlite3.connect(test_db)
    
    # Insert sample articles
    conn.execute("""
        INSERT INTO items (id, title, url, pipeline_stage, is_match)
        VALUES 
            (1, 'UBS announces new CEO', 'http://example.com/1', 'summarized', 1),
            (2, 'Credit Suisse merger update', 'http://example.com/2', 'summarized', 1),
            (3, 'Swiss franc strengthens', 'http://example.com/3', 'summarized', 1)
    """)
    
    # Insert sample summaries
    conn.execute("""
        INSERT INTO summaries (item_id, summary, topic, created_at)
        VALUES 
            (1, 'UBS has appointed a new chief executive officer', 'banking', ?),
            (2, 'Credit Suisse merger with UBS progresses', 'banking', ?),
            (3, 'The Swiss franc gained strength against Euro', 'currency', ?)
    """, (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ))
    
    conn.commit()
    conn.close()
    
    return test_db


class TestCrossRunStateManager:
    """Test suite for CrossRunStateManager."""
    
    def test_initialization(self, test_db):
        """Test StateManager initializes correctly."""
        manager = CrossRunStateManager(test_db)
        assert manager.db_path == test_db
        assert manager.logger is not None
    
    def test_store_and_retrieve_signatures(self, test_db):
        """Test storing and retrieving topic signatures."""
        manager = CrossRunStateManager(test_db)
        
        # Store signature
        sig_id = manager.store_topic_signature(
            article_summary="Test article about Swiss banking sector changes",
            topic_theme="banking",
            source_article_id=1,
            date="2025-10-03",
            run_sequence=1
        )
        
        assert sig_id is not None
        assert len(sig_id) == 16  # MD5 hash truncated to 16 chars
        
        # Retrieve signatures
        signatures = manager.get_previous_signatures("2025-10-03")
        assert len(signatures) == 1
        assert signatures[0]['topic_theme'] == "banking"
        assert signatures[0]['source_article_id'] == 1
        assert signatures[0]['run_sequence'] == 1
        assert signatures[0]['article_summary'] == "Test article about Swiss banking sector changes"
    
    def test_store_multiple_signatures_same_day(self, test_db):
        """Test storing multiple signatures for same day."""
        manager = CrossRunStateManager(test_db)
        
        # Store multiple signatures
        sig1 = manager.store_topic_signature(
            "Banking article 1", "banking", 1, "2025-10-03", 1
        )
        sig2 = manager.store_topic_signature(
            "Banking article 2", "banking", 2, "2025-10-03", 1
        )
        sig3 = manager.store_topic_signature(
            "Currency article", "currency", 3, "2025-10-03", 2
        )
        
        signatures = manager.get_previous_signatures("2025-10-03")
        assert len(signatures) == 3
        
        # Check ordering by run_sequence then created_at
        assert signatures[0]['run_sequence'] <= signatures[-1]['run_sequence']
    
    def test_retrieve_signatures_empty_day(self, test_db):
        """Test retrieving signatures when none exist."""
        manager = CrossRunStateManager(test_db)
        
        signatures = manager.get_previous_signatures("2025-01-01")
        assert len(signatures) == 0
        assert isinstance(signatures, list)
    
    def test_get_signature_by_id(self, test_db):
        """Test retrieving single signature by ID."""
        manager = CrossRunStateManager(test_db)
        
        # Store signature
        sig_id = manager.store_topic_signature(
            "Test article", "test_topic", 1, "2025-10-03", 1
        )
        
        # Retrieve by ID
        signature = manager.get_signature_by_id(sig_id)
        assert signature is not None
        assert signature['signature_id'] == sig_id
        assert signature['topic_theme'] == "test_topic"
        
        # Try non-existent ID
        missing = manager.get_signature_by_id("nonexistent")
        assert missing is None
    
    def test_signature_cleanup(self, test_db):
        """Test cleanup of old signatures."""
        manager = CrossRunStateManager(test_db)
        
        # Store old signatures (10 days ago)
        old_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        manager.store_topic_signature(
            "Old article 1", "old_topic", 1, old_date, 1
        )
        manager.store_topic_signature(
            "Old article 2", "old_topic", 2, old_date, 1
        )
        
        # Store recent signature
        recent_date = datetime.now().strftime('%Y-%m-%d')
        manager.store_topic_signature(
            "Recent article", "recent_topic", 3, recent_date, 1
        )
        
        # Verify all exist
        conn = sqlite3.connect(test_db)
        cursor = conn.execute("SELECT COUNT(*) FROM cross_run_topic_signatures")
        assert cursor.fetchone()[0] == 3
        conn.close()
        
        # Cleanup signatures older than 7 days
        deleted = manager.cleanup_old_signatures(days_to_keep=7)
        assert deleted == 2
        
        # Verify only recent signature remains
        signatures = manager.get_previous_signatures(recent_date)
        assert len(signatures) == 1
        assert signatures[0]['topic_theme'] == "recent_topic"
        
        # Verify old signatures are gone
        old_signatures = manager.get_previous_signatures(old_date)
        assert len(old_signatures) == 0
    
    def test_cleanup_no_old_signatures(self, test_db):
        """Test cleanup when no old signatures exist."""
        manager = CrossRunStateManager(test_db)
        
        # Store only recent signatures
        recent_date = datetime.now().strftime('%Y-%m-%d')
        manager.store_topic_signature(
            "Recent article", "recent_topic", 1, recent_date, 1
        )
        
        # Cleanup should delete nothing
        deleted = manager.cleanup_old_signatures(days_to_keep=7)
        assert deleted == 0
        
        # Signature should still exist
        signatures = manager.get_previous_signatures(recent_date)
        assert len(signatures) == 1
    
    def test_deduplication_logging(self, test_db):
        """Test audit log entries."""
        manager = CrossRunStateManager(test_db)
        
        # Log duplicate decision
        manager.log_deduplication_decision(
            article_id=1,
            decision='DUPLICATE',
            date='2025-10-03',
            matched_signature_id='abc123',
            confidence_score=0.95,
            processing_time=0.5
        )
        
        # Verify log entry exists
        conn = sqlite3.connect(test_db)
        cursor = conn.execute("""
            SELECT * FROM cross_run_deduplication_log 
            WHERE new_article_id = 1
        """)
        log_entry = cursor.fetchone()
        assert log_entry is not None
        
        # Verify fields
        cursor = conn.execute("""
            SELECT decision, matched_signature_id, confidence_score, processing_time
            FROM cross_run_deduplication_log 
            WHERE new_article_id = 1
        """)
        row = cursor.fetchone()
        assert row[0] == 'DUPLICATE'
        assert row[1] == 'abc123'
        assert row[2] == 0.95
        assert row[3] == 0.5
        
        conn.close()
    
    def test_log_unique_decision(self, test_db):
        """Test logging unique article decision."""
        manager = CrossRunStateManager(test_db)
        
        manager.log_deduplication_decision(
            article_id=2,
            decision='UNIQUE',
            date='2025-10-03',
            matched_signature_id=None,
            confidence_score=None,
            processing_time=0.3
        )
        
        # Verify log entry
        conn = sqlite3.connect(test_db)
        cursor = conn.execute("""
            SELECT decision, matched_signature_id 
            FROM cross_run_deduplication_log 
            WHERE new_article_id = 2
        """)
        row = cursor.fetchone()
        assert row[0] == 'UNIQUE'
        assert row[1] is None
        conn.close()


class TestCrossRunTopicDeduplicator:
    """Test suite for CrossRunTopicDeduplicator."""
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-123'})
    def test_initialization(self, test_db):
        """Test Deduplicator initializes correctly."""
        with patch('news_pipeline.cross_run_deduplication.openai.OpenAI'):
            deduplicator = CrossRunTopicDeduplicator(test_db)
            assert deduplicator.db_path == test_db
            assert deduplicator.state_manager is not None
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-123'})
    @patch('news_pipeline.cross_run_deduplication.openai.OpenAI')
    def test_compare_identical_topics(self, mock_openai, populated_db):
        """Test GPT identifies identical topics correctly."""
        # Mock GPT response indicating duplicate
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="YES - Article 1 covers the same banking CEO topic"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        deduplicator = CrossRunTopicDeduplicator(populated_db)
        
        # New article about same topic
        new_articles = [{
            'id': 4,
            'summary': 'UBS appoints new chief executive, announces strategic changes',
            'topic': 'banking',
            'title': 'UBS Leadership Change'
        }]
        
        # Previous signature
        previous_sigs = [{
            'signature_id': 'sig1',
            'article_summary': 'UBS has appointed a new chief executive officer',
            'topic_theme': 'banking',
            'run_sequence': 1
        }]
        
        duplicates = deduplicator.compare_topics_with_gpt(
            new_articles,
            previous_sigs,
            '2025-10-03'
        )
        
        assert 4 in duplicates
        assert duplicates[4] == 'sig1'
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-123'})
    @patch('news_pipeline.cross_run_deduplication.openai.OpenAI')
    def test_compare_different_topics(self, mock_openai, populated_db):
        """Test GPT distinguishes different topics."""
        # Mock GPT response indicating different topic
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="NO - different topics entirely"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        deduplicator = CrossRunTopicDeduplicator(populated_db)
        
        # New article about different topic
        new_articles = [{
            'id': 4,
            'summary': 'Swiss franc strengthens against Euro to new high',
            'topic': 'currency',
            'title': 'CHF Gains'
        }]
        
        # Previous signature about banking
        previous_sigs = [{
            'signature_id': 'sig1',
            'article_summary': 'UBS has appointed a new chief executive officer',
            'topic_theme': 'banking',
            'run_sequence': 1
        }]
        
        duplicates = deduplicator.compare_topics_with_gpt(
            new_articles,
            previous_sigs,
            '2025-10-03'
        )
        
        assert 4 not in duplicates
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-123'})
    @patch('news_pipeline.cross_run_deduplication.openai.OpenAI')
    def test_gpt_api_failure_handling(self, mock_openai, populated_db):
        """Test graceful degradation when GPT fails."""
        # Mock GPT to raise exception
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai.return_value = mock_client
        
        deduplicator = CrossRunTopicDeduplicator(populated_db)
        
        new_articles = [{
            'id': 4,
            'summary': 'Test article',
            'topic': 'test',
            'title': 'Test'
        }]
        
        previous_sigs = [{
            'signature_id': 'sig1',
            'article_summary': 'Previous article',
            'topic_theme': 'test',
            'run_sequence': 1
        }]
        
        # Should not crash, return empty results
        duplicates = deduplicator.compare_topics_with_gpt(
            new_articles,
            previous_sigs,
            '2025-10-03'
        )
        
        # On error, article should NOT be marked as duplicate (safe default)
        assert 4 not in duplicates
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-123'})
    @patch('news_pipeline.cross_run_deduplication.openai.OpenAI')
    def test_first_run_scenario(self, mock_openai, populated_db):
        """Test when no previous signatures exist."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        deduplicator = CrossRunTopicDeduplicator(populated_db)
        
        # First run - no previous signatures
        result = deduplicator.deduplicate_against_previous_runs('2025-10-03')
        
        # Should process but not filter anything
        assert result.get('first_run') == True or result['duplicates_found'] == 0
        assert result['articles_processed'] > 0
        assert result['unique_articles'] == result['articles_processed']
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-123'})
    @patch('news_pipeline.cross_run_deduplication.openai.OpenAI')
    def test_mark_duplicate_topics(self, mock_openai, populated_db):
        """Test marking articles as duplicates in database."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        deduplicator = CrossRunTopicDeduplicator(populated_db)
        
        # Mark article 1 as duplicate
        duplicates = {1: 'sig123'}
        deduplicator.mark_duplicate_topics(duplicates)
        
        # Verify database update
        conn = sqlite3.connect(populated_db)
        cursor = conn.execute("""
            SELECT topic_already_covered, cross_run_cluster_id 
            FROM summaries WHERE item_id = 1
        """)
        row = cursor.fetchone()
        assert row[0] == 1  # topic_already_covered
        assert row[1] == 'sig123'  # cross_run_cluster_id
        conn.close()
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-123'})
    @patch('news_pipeline.cross_run_deduplication.openai.OpenAI')
    def test_get_todays_new_summaries(self, mock_openai, populated_db):
        """Test retrieving new summaries for deduplication."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        deduplicator = CrossRunTopicDeduplicator(populated_db)
        
        today = datetime.now().strftime('%Y-%m-%d')
        articles = deduplicator.get_todays_new_summaries(today)
        
        # Should get articles created today
        assert len(articles) == 3
        assert all('id' in a for a in articles)
        assert all('summary' in a for a in articles)
        assert all('topic' in a for a in articles)


class TestDatabaseMigration:
    """Test database migration script."""
    
    def test_migration_creates_tables(self):
        """Test migration creates all required tables."""
        db_path = 'test_migration_new.db'
        
        # Remove if exists
        if os.path.exists(db_path):
            os.remove(db_path)
        
        from scripts.add_cross_run_schema import migrate_schema
        migrate_schema(db_path, create_if_missing=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        
        assert 'cross_run_topic_signatures' in tables
        assert 'cross_run_deduplication_log' in tables
        
        conn.close()
        os.remove(db_path)
    
    def test_migration_creates_indexes(self):
        """Test migration creates required indexes."""
        db_path = 'test_migration_indexes.db'
        
        if os.path.exists(db_path):
            os.remove(db_path)
        
        from scripts.add_cross_run_schema import migrate_schema
        migrate_schema(db_path, create_if_missing=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        
        # Check for date index on signatures table
        assert any('date' in idx.lower() for idx in indexes)
        
        conn.close()
        os.remove(db_path)
    
    def test_migration_idempotent(self):
        """Test migration can be run multiple times safely."""
        db_path = 'test_migration_idempotent.db'
        
        if os.path.exists(db_path):
            os.remove(db_path)
        
        from scripts.add_cross_run_schema import migrate_schema
        
        # Run migration twice
        migrate_schema(db_path, create_if_missing=True)
        migrate_schema(db_path, create_if_missing=True)  # Should not fail
        
        # Verify tables exist
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        )
        count = cursor.fetchone()[0]
        assert count >= 2  # At least our two new tables
        
        conn.close()
        os.remove(db_path)


class TestPipelineIntegration:
    """Integration tests for full pipeline with Step 3.1."""
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-123'})
    @patch('news_pipeline.cross_run_deduplication.openai.OpenAI')
    def test_end_to_end_deduplication(self, mock_openai, populated_db):
        """Test end-to-end deduplication workflow."""
        # Mock GPT to return duplicate for first article
        mock_client = Mock()
        responses = [
            Mock(choices=[Mock(message=Mock(content="YES - same topic"))]),
            Mock(choices=[Mock(message=Mock(content="NO - different topic"))]),
        ]
        mock_client.chat.completions.create.side_effect = responses
        mock_openai.return_value = mock_client
        
        # Store initial signature
        state_manager = CrossRunStateManager(populated_db)
        sig_id = state_manager.store_topic_signature(
            "UBS announces new CEO appointment",
            "banking",
            1,
            "2025-10-03",
            1
        )
        
        # Run deduplication
        deduplicator = CrossRunTopicDeduplicator(populated_db)
        result = deduplicator.deduplicate_against_previous_runs("2025-10-03")
        
        # Verify results
        assert result['articles_processed'] > 0
        assert 'duplicates_found' in result
        assert 'unique_articles' in result
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-123'})
    @patch('news_pipeline.cross_run_deduplication.openai.OpenAI')
    def test_multiple_runs_same_day(self, mock_openai, populated_db):
        """Test multiple runs on same day accumulate signatures."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        deduplicator = CrossRunTopicDeduplicator(populated_db)
        state_manager = CrossRunStateManager(populated_db)
        
        # First run
        result1 = deduplicator.deduplicate_against_previous_runs("2025-10-03")
        assert result1.get('first_run') == True
        
        # Check signatures stored
        sigs_after_run1 = state_manager.get_previous_signatures("2025-10-03")
        assert len(sigs_after_run1) > 0
        
        # Second run would compare against first run signatures
        # (In real scenario, new articles would be added to database first)


class TestPerformance:
    """Performance tests for cross-run deduplication."""
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-123'})
    @patch('news_pipeline.cross_run_deduplication.openai.OpenAI')
    def test_processing_time_acceptable(self, mock_openai, populated_db):
        """Test that processing time is reasonable."""
        # Mock fast GPT responses
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="NO"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        deduplicator = CrossRunTopicDeduplicator(populated_db)
        
        start = time.time()
        result = deduplicator.deduplicate_against_previous_runs('2025-10-03')
        duration = time.time() - start
        
        # With mocked GPT, should be very fast
        assert duration < 5, f"Processing took {duration}s, expected <5s with mocks"
    
    def test_database_query_performance(self, populated_db):
        """Test query performance with indexes."""
        state_manager = CrossRunStateManager(populated_db)
        
        # Insert many signatures
        today = datetime.now().strftime('%Y-%m-%d')
        for i in range(100):
            state_manager.store_topic_signature(
                f"Article {i}", f"topic_{i % 10}", i, today, 1
            )
        
        # Time retrieval
        start = time.time()
        signatures = state_manager.get_previous_signatures(today)
        duration = time.time() - start
        
        assert len(signatures) == 100
        assert duration < 0.5, f"Query took {duration}s, expected <0.5s"
    
    def test_cleanup_performance(self, test_db):
        """Test cleanup performance with many records."""
        state_manager = CrossRunStateManager(test_db)
        
        # Insert signatures across multiple days
        for days_ago in range(30):
            date_str = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
            for i in range(10):
                state_manager.store_topic_signature(
                    f"Article {i}", f"topic_{i}", i, date_str, 1
                )
        
        # Time cleanup
        start = time.time()
        deleted = state_manager.cleanup_old_signatures(days_to_keep=7)
        duration = time.time() - start
        
        assert deleted > 0
        assert duration < 2, f"Cleanup took {duration}s, expected <2s"


class TestErrorScenarios:
    """Test error handling and edge cases."""
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-123'})
    @patch('news_pipeline.cross_run_deduplication.openai.OpenAI')
    def test_empty_database(self, mock_openai, test_db):
        """Test handling of empty database."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        deduplicator = CrossRunTopicDeduplicator(test_db)
        result = deduplicator.deduplicate_against_previous_runs('2025-10-03')
        
        assert result['articles_processed'] == 0
        assert result['duplicates_found'] == 0
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-123'})
    @patch('news_pipeline.cross_run_deduplication.openai.OpenAI')
    def test_database_error_handling(self, mock_openai, test_db):
        """Test handling of database errors."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        deduplicator = CrossRunTopicDeduplicator(test_db)
        
        # Try to mark duplicates with invalid article ID
        duplicates = {99999: 'sig123'}
        
        # Should not crash
        try:
            deduplicator.mark_duplicate_topics(duplicates)
        except Exception as e:
            pytest.fail(f"Should handle database errors gracefully: {e}")
    
    def test_missing_api_key(self, test_db):
        """Test error when API key is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                CrossRunTopicDeduplicator(test_db)


def run_manual_tests():
    """Manual test scenarios described in the story."""
    print("\n" + "="*60)
    print("MANUAL TEST SCENARIOS")
    print("="*60)
    
    print("\n📋 Manual Test Checklist:")
    print("  1. First Run of Day - Clear data and run pipeline")
    print("  2. Second Run Same Day - Add new articles, run again")
    print("  3. Component Failure - Test with invalid API key")
    print("  4. Output Format - Verify digest format")
    print("  5. Performance - Time full pipeline execution")
    
    print("\n✅ Automated tests cover core functionality")
    print("   Run these manual tests in a real environment")
    print("   with actual pipeline and data")


if __name__ == '__main__':
    print("="*60)
    print("Cross-Run Deduplication Test Suite")
    print("="*60)
    
    # Run pytest with verbose output
    exit_code = pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '-W', 'ignore::DeprecationWarning'
    ])
    
    # Show manual test info
    run_manual_tests()
    
    sys.exit(exit_code)
