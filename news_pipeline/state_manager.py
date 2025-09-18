"""
Pipeline State Manager - Phase 5: Resume/Checkpoint System

Provides pipeline state tracking, checkpointing, and resume functionality
to allow interruption and restart at any point in the news analysis pipeline.
"""

import os
import json
import sqlite3
import uuid
import signal
import time
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime, timezone

from .utils import log_step_start, log_step_complete, format_number


class PipelineStateManager:
    """Manages pipeline execution state with checkpoint and resume capabilities."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.current_run_id: Optional[str] = None
        self.interrupted = False
        
        # Register signal handlers for graceful interruption
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle interruption signals gracefully."""
        self.logger.warning(f"Received signal {signum} - initiating graceful shutdown...")
        self.interrupted = True
        
        if self.current_run_id:
            self.pause_pipeline(self.current_run_id, "User interruption")
            self.logger.info(f"Pipeline {self.current_run_id} paused. Use --resume {self.current_run_id} to continue.")
    
    def start_pipeline_run(self, mode: str = "standard") -> str:
        """
        Start a new pipeline run with unique ID.
        
        Args:
            mode: Pipeline mode ("express", "standard", "deep")
            
        Returns:
            Unique run ID for this pipeline execution
        """
        run_id = str(uuid.uuid4())
        self.current_run_id = run_id
        
        conn = sqlite3.connect(self.db_path)
        
        # Initialize pipeline steps
        steps = ['collection', 'filtering', 'scraping', 'summarization', 'analysis']
        
        for step in steps:
            conn.execute("""
                INSERT INTO pipeline_state 
                (run_id, step_name, status, metadata) 
                VALUES (?, ?, 'pending', ?)
            """, (run_id, step, json.dumps({"mode": mode})))
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"Started new pipeline run: {run_id} (mode: {mode})")
        return run_id
    
    def get_incomplete_runs(self) -> List[Dict[str, Any]]:
        """Get list of incomplete pipeline runs that can be resumed."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT DISTINCT ps.run_id, 
                   MIN(ps.started_at) as started_at,
                   COUNT(*) as total_steps,
                   SUM(CASE WHEN ps.status = 'completed' THEN 1 ELSE 0 END) as completed_steps,
                   SUM(ps.article_count) as total_articles,
                   SUM(ps.match_count) as total_matches,
                   MAX(ps.metadata) as last_metadata
            FROM pipeline_state ps 
            WHERE ps.run_id IN (
                SELECT run_id FROM pipeline_state 
                WHERE status IN ('running', 'paused', 'failed', 'pending')
                GROUP BY run_id
            )
            GROUP BY ps.run_id
            ORDER BY started_at DESC
        """)
        
        runs = []
        for row in cursor.fetchall():
            metadata = json.loads(row['last_metadata'] or '{}')
            runs.append({
                'run_id': row['run_id'],
                'started_at': row['started_at'],
                'progress': f"{row['completed_steps']}/{row['total_steps']} steps",
                'articles': row['total_articles'],
                'matches': row['total_matches'],
                'mode': metadata.get('mode', 'unknown')
            })
        
        conn.close()
        return runs
    
    def can_resume_run(self, run_id: str) -> Tuple[bool, str]:
        """
        Check if a pipeline run can be resumed.
        
        Returns:
            (can_resume: bool, reason: str)
        """
        conn = sqlite3.connect(self.db_path)
        
        # Check if run exists
        cursor = conn.execute("""
            SELECT COUNT(*) as step_count,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count,
                   SUM(CASE WHEN status IN ('running', 'paused', 'pending', 'failed') THEN 1 ELSE 0 END) as resumable_count,
                   MIN(can_resume) as can_resume_flag
            FROM pipeline_state 
            WHERE run_id = ?
        """, (run_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result or result[0] == 0:
            return False, f"Pipeline run {run_id} not found"
        
        if result[3] == 0:  # can_resume_flag is 0
            return False, "Pipeline run is marked as non-resumable"
        
        if result[1] == result[0]:  # All steps completed
            return False, "Pipeline run already completed"
        
        if result[2] == 0:  # No resumable steps
            return False, "No resumable steps found"
        
        return True, f"Can resume from step with {result[2]} remaining steps"
    
    def resume_pipeline_run(self, run_id: str) -> Optional[str]:
        """
        Resume a paused or failed pipeline run.
        
        Returns:
            Next step to execute, or None if cannot resume
        """
        can_resume, reason = self.can_resume_run(run_id)
        if not can_resume:
            self.logger.error(f"Cannot resume run {run_id}: {reason}")
            return None
        
        self.current_run_id = run_id
        
        # Find next step to execute
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT step_name, status, metadata 
            FROM pipeline_state 
            WHERE run_id = ? AND status IN ('pending', 'failed', 'paused')
            ORDER BY 
                CASE step_name 
                    WHEN 'collection' THEN 1
                    WHEN 'filtering' THEN 2
                    WHEN 'scraping' THEN 3
                    WHEN 'summarization' THEN 4
                    WHEN 'analysis' THEN 5
                END
            LIMIT 1
        """, (run_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            self.logger.error(f"No resumable steps found for run {run_id}")
            return None
        
        next_step = result[0]
        self.logger.info(f"Resuming pipeline run {run_id} from step: {next_step}")
        
        return next_step
    
    def start_step(self, run_id: str, step_name: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark a pipeline step as started.
        
        Args:
            run_id: Pipeline run ID
            step_name: Name of the step starting
            metadata: Optional metadata for the step
            
        Returns:
            True if step started successfully
        """
        if metadata is None:
            metadata = {}
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            conn.execute("""
                UPDATE pipeline_state 
                SET status = 'running', 
                    started_at = datetime('now'),
                    metadata = ?
                WHERE run_id = ? AND step_name = ?
            """, (json.dumps(metadata), run_id, step_name))
            
            rows_affected = conn.total_changes
            conn.commit()
            
            if rows_affected > 0:
                self.logger.debug(f"Started step '{step_name}' for run {run_id}")
                return True
            else:
                self.logger.error(f"Failed to start step '{step_name}' for run {run_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting step '{step_name}': {e}")
            return False
        finally:
            conn.close()
    
    def complete_step(self, run_id: str, step_name: str, 
                     article_count: int = 0, match_count: int = 0, 
                     metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark a pipeline step as completed.
        
        Args:
            run_id: Pipeline run ID
            step_name: Name of the completed step
            article_count: Number of articles processed
            match_count: Number of matches found
            metadata: Optional step results metadata
            
        Returns:
            True if step completed successfully
        """
        if metadata is None:
            metadata = {}
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            conn.execute("""
                UPDATE pipeline_state 
                SET status = 'completed',
                    completed_at = datetime('now'),
                    article_count = ?,
                    match_count = ?,
                    metadata = ?
                WHERE run_id = ? AND step_name = ?
            """, (article_count, match_count, json.dumps(metadata), run_id, step_name))
            
            rows_affected = conn.total_changes
            conn.commit()
            
            if rows_affected > 0:
                self.logger.debug(f"Completed step '{step_name}' for run {run_id}")
                return True
            else:
                self.logger.error(f"Failed to complete step '{step_name}' for run {run_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error completing step '{step_name}': {e}")
            return False
        finally:
            conn.close()
    
    def fail_step(self, run_id: str, step_name: str, error_message: str) -> bool:
        """
        Mark a pipeline step as failed.
        
        Args:
            run_id: Pipeline run ID
            step_name: Name of the failed step
            error_message: Error description
            
        Returns:
            True if step marked as failed successfully
        """
        conn = sqlite3.connect(self.db_path)
        
        try:
            conn.execute("""
                UPDATE pipeline_state 
                SET status = 'failed',
                    completed_at = datetime('now'),
                    error_message = ?
                WHERE run_id = ? AND step_name = ?
            """, (error_message, run_id, step_name))
            
            rows_affected = conn.total_changes
            conn.commit()
            
            if rows_affected > 0:
                self.logger.error(f"Failed step '{step_name}' for run {run_id}: {error_message}")
                return True
            else:
                self.logger.error(f"Failed to mark step '{step_name}' as failed for run {run_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error failing step '{step_name}': {e}")
            return False
        finally:
            conn.close()
    
    def pause_pipeline(self, run_id: str, reason: str = "User request") -> bool:
        """
        Pause a pipeline run for later resumption.
        
        Args:
            run_id: Pipeline run ID
            reason: Reason for pausing
            
        Returns:
            True if paused successfully
        """
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Mark running steps as paused
            conn.execute("""
                UPDATE pipeline_state 
                SET status = 'paused',
                    error_message = ?
                WHERE run_id = ? AND status = 'running'
            """, (reason, run_id))
            
            rows_affected = conn.total_changes
            conn.commit()
            
            if rows_affected > 0:
                self.logger.info(f"Paused pipeline run {run_id}: {reason}")
                return True
            else:
                self.logger.warning(f"No running steps found to pause for run {run_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error pausing pipeline {run_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_pipeline_progress(self, run_id: str) -> Dict[str, Any]:
        """
        Get detailed progress information for a pipeline run.
        
        Returns:
            Progress information including steps, timings, and counts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT step_name, status, started_at, completed_at, 
                   article_count, match_count, error_message, metadata
            FROM pipeline_state 
            WHERE run_id = ?
            ORDER BY 
                CASE step_name 
                    WHEN 'collection' THEN 1
                    WHEN 'filtering' THEN 2
                    WHEN 'scraping' THEN 3
                    WHEN 'summarization' THEN 4
                    WHEN 'analysis' THEN 5
                END
        """, (run_id,))
        
        steps = []
        total_articles = 0
        total_matches = 0
        
        for row in cursor.fetchall():
            metadata = json.loads(row['metadata'] or '{}')
            
            step_info = {
                'name': row['step_name'],
                'status': row['status'],
                'started_at': row['started_at'],
                'completed_at': row['completed_at'],
                'article_count': row['article_count'] or 0,
                'match_count': row['match_count'] or 0,
                'error_message': row['error_message'],
                'metadata': metadata
            }
            
            # Calculate duration
            if row['started_at'] and row['completed_at']:
                start_dt = datetime.fromisoformat(row['started_at'].replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(row['completed_at'].replace('Z', '+00:00'))
                step_info['duration_seconds'] = (end_dt - start_dt).total_seconds()
            
            steps.append(step_info)
            total_articles += step_info['article_count']
            total_matches += step_info['match_count']
        
        conn.close()
        
        # Calculate overall progress
        completed_steps = sum(1 for step in steps if step['status'] == 'completed')
        total_steps = len(steps)
        progress_percent = (completed_steps / total_steps * 100) if total_steps > 0 else 0
        
        return {
            'run_id': run_id,
            'steps': steps,
            'progress': {
                'completed_steps': completed_steps,
                'total_steps': total_steps,
                'percent': progress_percent,
                'total_articles': total_articles,
                'total_matches': total_matches
            }
        }
    
    def cleanup_old_runs(self, days_old: int = 7) -> int:
        """
        Clean up old completed pipeline runs.
        
        Args:
            days_old: Remove runs older than this many days
            
        Returns:
            Number of runs cleaned up
        """
        conn = sqlite3.connect(self.db_path)
        
        cursor = conn.execute("""
            DELETE FROM pipeline_state 
            WHERE run_id IN (
                SELECT DISTINCT run_id FROM pipeline_state 
                WHERE started_at < datetime('now', '-{} days')
                AND run_id NOT IN (
                    SELECT run_id FROM pipeline_state 
                    WHERE status IN ('running', 'paused')
                )
            )
        """.format(days_old))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            self.logger.info(f"Cleaned up {deleted_count} old pipeline state records")
        
        return deleted_count
    
    def is_interrupted(self) -> bool:
        """Check if pipeline has been interrupted."""
        return self.interrupted
    
    def reset_interrupted(self):
        """Reset interrupted flag (for testing/recovery)."""
        self.interrupted = False


class StepContext:
    """Context manager for pipeline steps with automatic checkpointing."""
    
    def __init__(self, state_manager: PipelineStateManager, run_id: str, 
                 step_name: str, step_description: str = ""):
        self.state_manager = state_manager
        self.run_id = run_id
        self.step_name = step_name
        self.step_description = step_description
        self.logger = logging.getLogger(__name__)
        self.start_time = None
        self.article_count = 0
        self.match_count = 0
    
    def __enter__(self):
        """Start the step and begin timing."""
        self.start_time = time.time()
        
        # Start step in state manager
        self.state_manager.start_step(self.run_id, self.step_name, {
            "description": self.step_description,
            "started_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Log step start
        log_step_start(self.logger, self.step_name.title(), self.step_description)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Complete or fail the step based on exception status."""
        duration = time.time() - self.start_time if self.start_time else 0
        
        if exc_type is None:
            # Step completed successfully
            self.state_manager.complete_step(
                self.run_id, self.step_name, 
                self.article_count, self.match_count,
                {
                    "description": self.step_description,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "duration_seconds": duration
                }
            )
            
            # Log step completion
            log_step_complete(self.logger, self.step_name.title(), duration, {
                "articles_processed": format_number(self.article_count),
                "matches_found": format_number(self.match_count)
            })
        else:
            # Step failed with exception
            error_msg = f"{exc_type.__name__}: {str(exc_val)}"
            self.state_manager.fail_step(self.run_id, self.step_name, error_msg)
            
            self.logger.error(f"Step '{self.step_name}' failed after {duration:.1f}s: {error_msg}")
            
    def update_progress(self, article_count: Optional[int] = None, match_count: Optional[int] = None):
        """Update progress counters."""
        if article_count is not None:
            self.article_count = article_count
        if match_count is not None:
            self.match_count = match_count
    
    def check_interrupted(self) -> bool:
        """Check if pipeline has been interrupted and raise KeyboardInterrupt if so."""
        if self.state_manager.is_interrupted():
            raise KeyboardInterrupt("Pipeline interrupted by user")
        return False
