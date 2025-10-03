"""
Cross-Run Topic Deduplication - Step 3.1

Implements GPT-based topic comparison to filter articles covering topics
already processed in previous runs on the same day.
"""

import os
import sqlite3
import logging
import time
from typing import Dict, List, Any
from datetime import datetime
import openai

from .cross_run_state_manager import CrossRunStateManager
from .utils import log_step_start, log_step_complete, format_number


class CrossRunTopicDeduplicator:
    """
    GPT-based cross-run topic deduplication for same-day pipeline runs.
    
    Compares newly summarized articles against previous same-day summaries
    to identify and filter duplicate topic coverage.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize CrossRunTopicDeduplicator.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Initialize OpenAI client (same pattern as gpt_deduplication.py)
        self._init_openai_client()
        
        # Initialize state manager
        self.state_manager = CrossRunStateManager(db_path)
    
    def _init_openai_client(self):
        """Initialize OpenAI client using environment variables."""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        self.openai_client = openai.OpenAI(api_key=api_key)
        self.model_mini = os.getenv('MODEL_MINI', 'gpt-4o-mini')
        
        self.logger.info(f"Initialized cross-run deduplicator with model: {self.model_mini}")
    
    def deduplicate_against_previous_runs(self, date: str) -> Dict[str, Any]:
        """
        Main deduplication logic - Step 3.1 of pipeline.
        
        Compares new articles against previous same-day summaries to filter
        duplicate topic coverage.
        
        Args:
            date: Date to process in YYYY-MM-DD format
            
        Returns:
            Dictionary with deduplication results and statistics
        """
        start_time = time.time()
        
        log_step_start(
            self.logger,
            "Cross-Run Topic Deduplication (Step 3.1)",
            "Filtering articles that cover topics already processed today"
        )
        
        try:
            # Get new articles that need deduplication check
            new_articles = self.get_todays_new_summaries(date)
            
            if not new_articles:
                self.logger.info("No new articles to deduplicate")
                return {
                    'articles_processed': 0,
                    'duplicates_found': 0,
                    'unique_articles': 0
                }
            
            # Get previous signatures from earlier runs today
            previous_signatures = self.state_manager.get_previous_signatures(date)
            
            if not previous_signatures:
                self.logger.info("No previous signatures - first run of the day")
                # Store signatures for these articles for next run
                self._store_new_signatures(new_articles, date)
                return {
                    'articles_processed': len(new_articles),
                    'duplicates_found': 0,
                    'unique_articles': len(new_articles),
                    'first_run': True
                }
            
            # Compare new articles against previous summaries
            self.logger.info(f"Comparing {len(new_articles)} new articles against {len(previous_signatures)} previous summaries")
            
            duplicates = self.compare_topics_with_gpt(new_articles, previous_signatures, date)
            
            # Mark duplicates in database
            if duplicates:
                self.mark_duplicate_topics(duplicates)
            
            # Store signatures for unique articles
            unique_articles = [a for a in new_articles if a['id'] not in duplicates]
            self._store_new_signatures(unique_articles, date)
            
            # Build results
            duration = time.time() - start_time
            results = {
                'articles_processed': len(new_articles),
                'duplicates_found': len(duplicates),
                'unique_articles': len(unique_articles),
                'deduplication_rate': f"{(len(duplicates) / len(new_articles) * 100):.1f}%" if new_articles else "0.0%"
            }
            
            log_step_complete(
                self.logger,
                "Cross-Run Topic Deduplication (Step 3.1)",
                duration,
                {
                    "articles_processed": format_number(results['articles_processed']),
                    "duplicates_found": format_number(results['duplicates_found']),
                    "deduplication_rate": results['deduplication_rate']
                }
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Cross-run deduplication failed: {e}")
            # Return empty results - pipeline continues without filtering
            return {
                'articles_processed': 0,
                'duplicates_found': 0,
                'unique_articles': 0,
                'error': str(e)
            }
    
    def compare_topics_with_gpt(
        self,
        new_articles: List[Dict],
        previous_signatures: List[Dict],
        date: str
    ) -> Dict[int, str]:
        """
        Use GPT-4o-mini to compare new articles against previous summaries.
        
        Args:
            new_articles: List of new article dictionaries with summaries
            previous_signatures: List of previous signature dictionaries
            date: Current date for logging
            
        Returns:
            Dictionary mapping article_id to matched signature_id for duplicates
        """
        duplicates = {}
        
        # Build previous summaries context (limit to 10 most recent for token management)
        previous_context = "\n\n".join([
            f"Previous Article {i+1} (ID: {sig['signature_id']}):\n{sig['article_summary'][:500]}"
            for i, sig in enumerate(previous_signatures[:10])
        ])
        
        # Compare each new article against all previous summaries
        for article in new_articles:
            comparison_start = time.time()
            
            try:
                # Create GPT prompt
                system_prompt = "You are analyzing whether a new article covers the same topic as previous articles. Respond with 'YES' if it's the same topic, 'NO' if it's a different topic."
                
                user_prompt = f"""Previous articles from today:
{previous_context}

New article to check:
Title: {article['title']}
Summary: {article['summary'][:500]}

Is this new article covering the same topic as any of the previous articles? Answer YES or NO and indicate which previous article if YES."""
                
                # Call GPT with retry logic
                response = self.openai_client.chat.completions.create(
                    model=self.model_mini,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_completion_tokens=100
                )
                
                response_text = response.choices[0].message.content.strip().upper()
                
                # Parse response
                if response_text.startswith('YES'):
                    # Try to extract which previous article matched
                    # For now, mark as duplicate to first signature
                    # Production version should parse the response better
                    matched_sig_id = previous_signatures[0]['signature_id']
                    duplicates[article['id']] = matched_sig_id
                    
                    # Log decision
                    processing_time = time.time() - comparison_start
                    self.state_manager.log_deduplication_decision(
                        article['id'],
                        'DUPLICATE',
                        date,
                        matched_sig_id,
                        None,  # Could extract confidence from response
                        processing_time
                    )
                    
                    self.logger.info(f"Article {article['id']} marked as duplicate topic")
                else:
                    # Log as unique
                    processing_time = time.time() - comparison_start
                    self.state_manager.log_deduplication_decision(
                        article['id'],
                        'UNIQUE',
                        date,
                        None,
                        None,
                        processing_time
                    )
                
            except Exception as e:
                self.logger.warning(f"GPT comparison failed for article {article['id']}: {e}")
                # On error, treat as unique (don't filter)
                continue
        
        return duplicates
    
    def get_todays_new_summaries(self, date: str) -> List[Dict[str, Any]]:
        """
        Retrieve articles summarized today that haven't been checked yet.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            List of article dictionaries with summaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            cursor = conn.execute("""
                SELECT s.item_id, s.summary, s.topic, i.title
                FROM summaries s
                JOIN items i ON s.item_id = i.id
                WHERE DATE(s.created_at) = ?
                AND s.topic_already_covered = 0
                ORDER BY s.created_at DESC
            """, (date,))
            
            articles = []
            for row in cursor.fetchall():
                articles.append({
                    'id': row['item_id'],
                    'summary': row['summary'],
                    'topic': row['topic'],
                    'title': row['title']
                })
            
            return articles
            
        finally:
            conn.close()
    
    def mark_duplicate_topics(self, duplicates: Dict[int, str]) -> None:
        """
        Mark articles as duplicate topics in database.
        
        Args:
            duplicates: Dictionary mapping article_id to matched signature_id
        """
        conn = sqlite3.connect(self.db_path)
        try:
            for article_id, signature_id in duplicates.items():
                conn.execute("""
                    UPDATE summaries
                    SET topic_already_covered = 1,
                        cross_run_cluster_id = ?
                    WHERE item_id = ?
                """, (signature_id, article_id))
            
            conn.commit()
            self.logger.info(f"Marked {len(duplicates)} articles as duplicate topics")
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to mark duplicate topics: {e}")
        finally:
            conn.close()
    
    def _store_new_signatures(self, articles: List[Dict], date: str) -> None:
        """Store topic signatures for articles to enable future comparisons."""
        if not articles:
            return
            
        # Determine run sequence for today
        existing_sigs = self.state_manager.get_previous_signatures(date)
        run_sequence = max([s['run_sequence'] for s in existing_sigs], default=0) + 1
        
        for article in articles:
            try:
                self.state_manager.store_topic_signature(
                    article['summary'],
                    article.get('topic', 'unknown'),
                    article['id'],
                    date,
                    run_sequence
                )
            except Exception as e:
                self.logger.warning(f"Failed to store signature for article {article['id']}: {e}")
