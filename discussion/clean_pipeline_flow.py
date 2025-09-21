"""
Clean Pipeline Flow - Consistent data flow across all 5 steps
"""

import sqlite3
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

class CleanPipelineManager:
    """Manages consistent data flow across all pipeline steps."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    def get_articles_for_step(self, step: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get articles ready for a specific pipeline step.
        Ensures consistent selection criteria across all steps.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        queries = {
            'filtering': """
                SELECT id, url, title, source, published_at 
                FROM items 
                WHERE pipeline_status = 'collected'
                AND filtering_attempted_at IS NULL
                ORDER BY published_at DESC, id DESC
            """,
            
            'scraping': """
                SELECT id, url, title, source, triage_topic
                FROM items 
                WHERE pipeline_status = 'filtered' 
                AND is_match = 1
                AND scraping_attempted_at IS NULL
                AND id NOT IN (SELECT item_id FROM articles)
                ORDER BY triage_confidence DESC, id DESC
            """,
            
            'summarization': """
                SELECT i.id, i.url, i.title, i.source, i.triage_topic,
                       a.extracted_text, a.word_count
                FROM items i
                JOIN articles a ON i.id = a.item_id
                WHERE i.pipeline_status = 'scraped'
                AND i.summarization_attempted_at IS NULL
                AND a.word_count >= 600
                AND i.id NOT IN (SELECT item_id FROM summaries)
                ORDER BY i.triage_confidence DESC, i.id DESC
            """,
            
            'analysis': """
                SELECT i.id, i.url, i.title, i.source, i.triage_topic,
                       s.summary, s.key_points_json, s.entities_json
                FROM items i
                JOIN summaries s ON i.id = s.item_id
                WHERE i.pipeline_status = 'summarized'
                AND i.included_in_digest_at IS NULL
                AND (i.cluster_id IS NULL OR i.is_cluster_primary = 1)
                ORDER BY i.triage_confidence DESC, i.id DESC
            """
        }
        
        query = queries.get(step)
        if not query:
            raise ValueError(f"Unknown step: {step}")
            
        if limit:
            query += f" LIMIT {limit}"
            
        cursor = conn.execute(query)
        articles = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return articles
    
    def mark_step_started(self, step: str, article_ids: List[int]):
        """Mark articles as processing started for a step."""
        if not article_ids:
            return
            
        conn = sqlite3.connect(self.db_path)
        now = datetime.now().isoformat()
        
        step_columns = {
            'filtering': 'filtering_attempted_at',
            'scraping': 'scraping_attempted_at', 
            'summarization': 'summarization_attempted_at'
        }
        
        column = step_columns.get(step)
        if column:
            placeholders = ','.join('?' * len(article_ids))
            conn.execute(f"""
                UPDATE items 
                SET {column} = ?
                WHERE id IN ({placeholders})
            """, [now] + article_ids)
        
        conn.commit()
        conn.close()
    
    def mark_step_completed(self, step: str, article_id: int, success: bool = True, 
                          error_msg: str = None, **step_data):
        """Mark single article as completed (success or failure) for a step."""
        conn = sqlite3.connect(self.db_path)
        now = datetime.now().isoformat()
        
        if success:
            updates = {
                'filtering': {
                    'filtering_completed_at': now,
                    'pipeline_status': 'filtered',
                    'triage_topic': step_data.get('topic'),
                    'triage_confidence': step_data.get('confidence'),
                    'is_match': step_data.get('is_match', 0)
                },
                'scraping': {
                    'scraping_completed_at': now,
                    'pipeline_status': 'scraped',
                    'extraction_method': step_data.get('method'),
                    'content_length': step_data.get('content_length')
                },
                'summarization': {
                    'summarization_completed_at': now,
                    'pipeline_status': 'summarized',
                    'summarization_model': step_data.get('model')
                },
                'analysis': {
                    'included_in_digest_at': now,
                    'pipeline_status': 'analyzed'
                }
            }
            
            update_dict = updates.get(step, {})
            if update_dict:
                set_clause = ', '.join(f"{k} = ?" for k in update_dict.keys())
                values = list(update_dict.values()) + [article_id]
                
                conn.execute(f"""
                    UPDATE items 
                    SET {set_clause}
                    WHERE id = ?
                """, values)
        else:
            # Mark as failed
            error_columns = {
                'filtering': 'filtering_error',
                'scraping': 'scraping_error',
                'summarization': 'summarization_error'
            }
            
            error_column = error_columns.get(step)
            if error_column:
                conn.execute(f"""
                    UPDATE items 
                    SET {error_column} = ?,
                        pipeline_status = 'failed',
                        failed_at_step = ?
                    WHERE id = ?
                """, (error_msg, step, article_id))
        
        conn.commit()
        conn.close()
    
    def get_pipeline_stats(self, run_id: str = None) -> Dict[str, int]:
        """Get consistent pipeline statistics."""
        conn = sqlite3.connect(self.db_path)
        
        # Base statistics
        stats = {}
        
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN pipeline_status = 'collected' THEN 1 ELSE 0 END) as collected,
                SUM(CASE WHEN pipeline_status = 'filtered' THEN 1 ELSE 0 END) as filtered,
                SUM(CASE WHEN is_match = 1 THEN 1 ELSE 0 END) as matched,
                SUM(CASE WHEN pipeline_status = 'scraped' THEN 1 ELSE 0 END) as scraped,
                SUM(CASE WHEN pipeline_status = 'summarized' THEN 1 ELSE 0 END) as summarized,
                SUM(CASE WHEN pipeline_status = 'analyzed' THEN 1 ELSE 0 END) as analyzed,
                SUM(CASE WHEN pipeline_status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM items
        """)
        
        row = cursor.fetchone()
        if row:
            stats.update({
                'total_articles': row[0],
                'step1_collected': row[1], 
                'step2_filtered': row[2],
                'step2_matched': row[3],
                'step3_scraped': row[4],
                'step4_summarized': row[5],
                'step5_analyzed': row[6],
                'failed_articles': row[7]
            })
        
        # Calculate processing rates
        if stats['step1_collected'] > 0:
            stats['filtering_rate'] = stats['step2_filtered'] / stats['step1_collected']
            stats['match_rate'] = stats['step2_matched'] / stats['step2_filtered'] if stats['step2_filtered'] > 0 else 0
        
        if stats['step2_matched'] > 0:
            stats['scraping_rate'] = stats['step3_scraped'] / stats['step2_matched']
        
        if stats['step3_scraped'] > 0:
            stats['summarization_rate'] = stats['step4_summarized'] / stats['step3_scraped']
        
        conn.close()
        return stats
    
    def perform_deduplication(self, similarity_threshold: float = 0.85) -> Dict[str, int]:
        """
        Perform deduplication on scraped articles before summarization.
        This ensures we don't waste resources on duplicate content.
        """
        from news_pipeline.deduplication import ArticleDeduplicator
        
        # Get articles ready for deduplication (scraped but not deduplicated)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT id, title, url, triage_confidence
            FROM items 
            WHERE pipeline_status = 'scraped'
            AND cluster_id IS NULL
            ORDER BY triage_confidence DESC
        """)
        
        articles = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not articles:
            return {'processed': 0, 'clusters': 0, 'duplicates_marked': 0}
        
        # Perform clustering
        deduplicator = ArticleDeduplicator(self.db_path, similarity_threshold)
        clusters = deduplicator.find_similar_articles(articles)
        
        # Update database with cluster information
        conn = sqlite3.connect(self.db_path)
        duplicates_marked = 0
        
        for cluster_idx, cluster_indices in enumerate(clusters):
            cluster_id = f"cluster_{cluster_idx}_{len(cluster_indices)}"
            cluster_articles = [articles[i] for i in cluster_indices]
            
            # Select primary article (highest confidence)
            primary_idx = max(range(len(cluster_articles)), 
                            key=lambda i: cluster_articles[i]['triage_confidence'])
            
            # Update all articles in cluster
            for i, article in enumerate(cluster_articles):
                is_primary = (i == primary_idx)
                
                conn.execute("""
                    UPDATE items 
                    SET cluster_id = ?, 
                        is_cluster_primary = ?,
                        similarity_score = ?
                    WHERE id = ?
                """, (cluster_id, 1 if is_primary else 0, 1.0 if is_primary else similarity_threshold, article['id']))
                
                if not is_primary:
                    duplicates_marked += 1
        
        conn.commit()
        conn.close()
        
        return {
            'processed': len(articles),
            'clusters': len(clusters),
            'duplicates_marked': duplicates_marked
        }
    
    def cleanup_failed_articles(self, max_age_hours: int = 24):
        """Clean up old failed articles to allow retry."""
        conn = sqlite3.connect(self.db_path)
        
        conn.execute("""
            UPDATE items 
            SET pipeline_status = 'collected',
                filtering_attempted_at = NULL,
                filtering_error = NULL,
                failed_at_step = NULL
            WHERE pipeline_status = 'failed'
            AND filtering_attempted_at < datetime('now', '-{} hours')
        """.format(max_age_hours))
        
        conn.commit()
        cleaned = conn.total_changes
        conn.close()
        
        return cleaned


class CleanPipelineExecutor:
    """Executes the clean pipeline with consistent data flow."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.manager = CleanPipelineManager(db_path)
        
    def run_full_pipeline(self, limit_per_step: int = 100) -> Dict[str, Any]:
        """Run the complete pipeline with consistent data flow."""
        results = {}
        
        # Step 1: Collection (handled separately by NewsCollector)
        # This populates items with pipeline_status = 'collected'
        
        # Step 2: Filtering
        articles_to_filter = self.manager.get_articles_for_step('filtering', limit_per_step)
        if articles_to_filter:
            self.manager.mark_step_started('filtering', [a['id'] for a in articles_to_filter])
            filtering_results = self._run_filtering_step(articles_to_filter)
            results['step2_filtering'] = filtering_results
        
        # Step 2.5: Deduplication (before scraping to save resources)
        dedup_results = self.manager.perform_deduplication()
        results['deduplication'] = dedup_results
        
        # Step 3: Scraping (only primary articles from clusters)
        articles_to_scrape = self.manager.get_articles_for_step('scraping', limit_per_step)
        if articles_to_scrape:
            self.manager.mark_step_started('scraping', [a['id'] for a in articles_to_scrape])
            scraping_results = self._run_scraping_step(articles_to_scrape)
            results['step3_scraping'] = scraping_results
        
        # Step 4: Summarization
        articles_to_summarize = self.manager.get_articles_for_step('summarization', limit_per_step)
        if articles_to_summarize:
            self.manager.mark_step_started('summarization', [a['id'] for a in articles_to_summarize])
            summary_results = self._run_summarization_step(articles_to_summarize)
            results['step4_summarization'] = summary_results
        
        # Step 5: Analysis (meta-summary generation)
        articles_for_analysis = self.manager.get_articles_for_step('analysis')
        if articles_for_analysis:
            analysis_results = self._run_analysis_step(articles_for_analysis)
            results['step5_analysis'] = analysis_results
        
        # Get final statistics
        results['final_stats'] = self.manager.get_pipeline_stats()
        
        return results
    
    def _run_filtering_step(self, articles: List[Dict[str, Any]]) -> Dict[str, int]:
        """Run filtering step with consistent error handling."""
        from news_pipeline.filter import AIFilter
        
        ai_filter = AIFilter(self.db_path)
        results = {'processed': 0, 'matched': 0, 'failed': 0}
        
        for article in articles:
            try:
                # Perform classification
                classification = ai_filter.classify_article(
                    article['title'], article['url'], 'creditreform_insights'
                )
                
                # Mark as completed
                self.manager.mark_step_completed(
                    'filtering', article['id'], success=True,
                    topic=classification['topic'],
                    confidence=classification['confidence'],
                    is_match=classification['is_match']
                )
                
                results['processed'] += 1
                if classification['is_match']:
                    results['matched'] += 1
                    
            except Exception as e:
                self.manager.mark_step_completed(
                    'filtering', article['id'], success=False,
                    error_msg=str(e)
                )
                results['failed'] += 1
        
        return results
    
    def _run_scraping_step(self, articles: List[Dict[str, Any]]) -> Dict[str, int]:
        """Run scraping step with consistent error handling."""
        from news_pipeline.scraper import ContentScraper
        
        scraper = ContentScraper(self.db_path)
        results = {'processed': 0, 'scraped': 0, 'failed': 0}
        
        for article in articles:
            try:
                # Extract content
                extracted_text, method = scraper.extract_content(article['url'])
                
                if extracted_text and len(extracted_text) >= 600:
                    # Save to articles table
                    conn = sqlite3.connect(self.db_path)
                    conn.execute("""
                        INSERT OR REPLACE INTO articles (item_id, extracted_text, word_count)
                        VALUES (?, ?, ?)
                    """, (article['id'], extracted_text, len(extracted_text.split())))
                    conn.commit()
                    conn.close()
                    
                    # Mark as completed
                    self.manager.mark_step_completed(
                        'scraping', article['id'], success=True,
                        method=method,
                        content_length=len(extracted_text)
                    )
                    
                    results['scraped'] += 1
                else:
                    self.manager.mark_step_completed(
                        'scraping', article['id'], success=False,
                        error_msg="Content too short or extraction failed"
                    )
                    results['failed'] += 1
                
                results['processed'] += 1
                
            except Exception as e:
                self.manager.mark_step_completed(
                    'scraping', article['id'], success=False,
                    error_msg=str(e)
                )
                results['failed'] += 1
        
        return results
    
    def _run_summarization_step(self, articles: List[Dict[str, Any]]) -> Dict[str, int]:
        """Run summarization step with consistent error handling."""
        from news_pipeline.summarizer import ArticleSummarizer
        
        summarizer = ArticleSummarizer(self.db_path)
        results = {'processed': 0, 'summarized': 0, 'failed': 0}
        
        for article in articles:
            try:
                # Generate summary
                summary_data = summarizer.summarize_article(
                    article['extracted_text'], article['title'], article['url']
                )
                
                if 'error' not in summary_data:
                    # Save summary
                    if summarizer.save_summary(article['id'], summary_data, article['triage_topic']):
                        self.manager.mark_step_completed(
                            'summarization', article['id'], success=True,
                            model=summarizer.model
                        )
                        results['summarized'] += 1
                    else:
                        results['failed'] += 1
                else:
                    self.manager.mark_step_completed(
                        'summarization', article['id'], success=False,
                        error_msg=summary_data.get('error', 'Unknown error')
                    )
                    results['failed'] += 1
                
                results['processed'] += 1
                
            except Exception as e:
                self.manager.mark_step_completed(
                    'summarization', article['id'], success=False,
                    error_msg=str(e)
                )
                results['failed'] += 1
        
        return results
    
    def _run_analysis_step(self, articles: List[Dict[str, Any]]) -> Dict[str, int]:
        """Run analysis step and mark articles as included in digest."""
        from news_pipeline.analyzer import MetaAnalyzer
        
        analyzer = MetaAnalyzer(self.db_path)
        
        # Generate daily digest
        digest_path = analyzer.export_daily_digest()
        
        # Mark all articles as included in analysis
        article_ids = [a['id'] for a in articles]
        if article_ids:
            conn = sqlite3.connect(self.db_path)
            placeholders = ','.join('?' * len(article_ids))
            conn.execute(f"""
                UPDATE items 
                SET included_in_digest_at = datetime('now'),
                    pipeline_status = 'analyzed'
                WHERE id IN ({placeholders})
            """, article_ids)
            conn.commit()
            conn.close()
        
        return {
            'processed': len(articles),
            'digest_path': digest_path
        }
