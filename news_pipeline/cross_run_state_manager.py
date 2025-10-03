"""
Cross-Run State Manager for Topic Signature Persistence

Manages storage, retrieval, and cleanup of topic signatures for cross-run
deduplication tracking. Follows existing StateManager patterns.
"""

import sqlite3
import hashlib
import logging
from datetime import datetime, timedelta
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
    
    def get_signature_by_id(self, signature_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve single signature by ID.
        
        Args:
            signature_id: Signature identifier
            
        Returns:
            Signature dictionary or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            cursor = conn.execute("""
                SELECT signature_id, date, article_summary, topic_theme,
                       source_article_id, created_at, run_sequence
                FROM cross_run_topic_signatures
                WHERE signature_id = ?
            """, (signature_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'signature_id': row['signature_id'],
                    'date': row['date'],
                    'article_summary': row['article_summary'],
                    'topic_theme': row['topic_theme'],
                    'source_article_id': row['source_article_id'],
                    'created_at': row['created_at'],
                    'run_sequence': row['run_sequence']
                }
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve signature {signature_id}: {e}")
            return None
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
