"""
GPT-based Title Deduplication System - Step 4

Implements title-based clustering using GPT-5-mini to eliminate duplicate
news stories while selecting the most comprehensive article from each group.
This approach is more cost-effective than content-based similarity as it only
processes titles and makes a single GPT API call per batch.
"""

import os
import json
import sqlite3
import hashlib
import logging
import time
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, date
import openai

from .utils import log_step_start, log_step_complete, format_number


class GPTTitleDeduplicator:
    """GPT-based title clustering for news article deduplication."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Initialize OpenAI client
        self._init_openai_client()
        
    def _init_openai_client(self):
        """Initialize OpenAI client using environment variables."""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        self.openai_client = openai.OpenAI(api_key=api_key)
        self.model_mini = os.getenv('MODEL_MINI', 'gpt-4o-mini')
        
        self.logger.info(f"Initialized GPT deduplicator with model: {self.model_mini}")
    
    def gather_scraped_articles_for_today(self) -> List[Dict[str, Any]]:
        """
        Gather all articles that passed AI filter and have been scraped today.
        This includes articles from all pipeline runs today, not just the current run.
        """
        today = date.today().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Query to get all matched articles with scraped content from today
        cursor = conn.execute("""
            SELECT DISTINCT 
                i.id, i.title, i.url, i.source,
                i.published_at, i.first_seen_at,
                COALESCE(a.extracted_text, '') as content,
                LENGTH(COALESCE(a.extracted_text, '')) as content_length,
                i.triage_confidence
            FROM items i
            JOIN articles a ON i.id = a.item_id
            WHERE i.is_match = 1
            AND a.extracted_text IS NOT NULL 
            AND a.extracted_text != ''
            AND (
                DATE(i.published_at) = ?
                OR DATE(i.first_seen_at) = ?
            )
            ORDER BY i.triage_confidence DESC, content_length DESC
        """, (today, today))
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                'id': row['id'],
                'title': row['title'],
                'url': row['url'],
                'source': row['source'],
                'published_at': row['published_at'],
                'first_seen_at': row['first_seen_at'],
                'content_length': row['content_length'],
                'confidence': row['triage_confidence']
            })
        
        conn.close()
        
        self.logger.info(f"Found {len(articles)} scraped articles from today for deduplication")
        return articles
    
    def create_clustering_prompt(self, articles: List[Dict[str, Any]]) -> str:
        """Create the prompt for GPT-5-mini to cluster article titles."""
        
        # Build the titles list
        titles_list = []
        for i, article in enumerate(articles, 1):
            titles_list.append(f"{i}. {article['title']}")
        
        titles_text = '\n'.join(titles_list)
        
        system_prompt = """You are an AI assistant grouping news article titles that refer to the same event. Group titles by story."""
        
        user_prompt = f"""List the titles:
{titles_text}

Identify which titles describe the same news. Assign a group label (e.g., Group1, Group2, ...) to each title that belongs to the same story. Output each title's index with its group label, one per line (format: index, groupX)."""
        
        return system_prompt, user_prompt
    
    def call_gpt_for_clustering(self, system_prompt: str, user_prompt: str) -> str:
        """Make API call to GPT-5-mini for title clustering."""
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model_mini,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                # Using default temperature as custom values not supported by this model
                max_completion_tokens=1000  # Updated parameter for newer models
            )
            
            output_text = response.choices[0].message.content
            self.logger.debug(f"GPT clustering response: {output_text}")
            return output_text
            
        except Exception as e:
            self.logger.error(f"GPT API call failed: {e}")
            raise
    
    def parse_clustering_output(self, gpt_output: str, num_articles: int) -> Dict[str, List[int]]:
        """
        Parse GPT output to identify clusters of duplicate articles.
        
        Args:
            gpt_output: Raw output from GPT
            num_articles: Expected number of articles
            
        Returns:
            Dictionary mapping group names to lists of article indices
        """
        clusters = {}
        
        for line in gpt_output.strip().split('\n'):
            line = line.strip()
            if not line or ',' not in line:
                continue
            
            try:
                # Parse format: "index, groupX"
                parts = line.split(',', 1)
                index_str = parts[0].strip()
                group_str = parts[1].strip()
                
                # Extract index (handle various formats like "1" or "1.")
                index = int(index_str.rstrip('.'))
                
                # Validate index range
                if 1 <= index <= num_articles:
                    if group_str not in clusters:
                        clusters[group_str] = []
                    clusters[group_str].append(index - 1)  # Convert to 0-based
                    
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Could not parse line: '{line}' - {e}")
                continue
        
        # Filter to only groups with multiple articles (duplicates)
        duplicate_clusters = {group: indices for group, indices in clusters.items() 
                            if len(indices) > 1}
        
        self.logger.info(f"Parsed {len(duplicate_clusters)} duplicate clusters from GPT output")
        return duplicate_clusters
    
    def select_primary_article_by_length(self, cluster_articles: List[Dict[str, Any]]) -> Tuple[int, str]:
        """
        Select the primary article from a cluster based on content length.
        
        Args:
            cluster_articles: List of articles in the cluster
            
        Returns:
            (index_of_primary, selection_reason)
        """
        if not cluster_articles:
            return 0, "Default selection"
        
        if len(cluster_articles) == 1:
            return 0, "Only article in cluster"
        
        # Find article with longest content
        max_length = 0
        best_idx = 0
        
        for i, article in enumerate(cluster_articles):
            content_length = article.get('content_length', 0)
            if content_length > max_length:
                max_length = content_length
                best_idx = i
        
        # Build selection reason
        primary_article = cluster_articles[best_idx]
        reason = f"Longest content ({max_length:,} chars) from {primary_article.get('source', 'unknown')}"
        
        return best_idx, reason
    
    def store_clusters_in_database(self, articles: List[Dict[str, Any]], 
                                 clusters: Dict[str, List[int]]) -> Dict[str, Any]:
        """Store clustering results in the article_clusters table."""
        
        conn = sqlite3.connect(self.db_path)
        
        total_duplicates_marked = 0
        cluster_results = []
        
        try:
            for group_name, article_indices in clusters.items():
                # Get articles in this cluster
                cluster_articles = [articles[i] for i in article_indices]
                
                # Generate cluster ID
                cluster_id = hashlib.md5(
                    f"gpt_cluster_{group_name}_{len(cluster_articles)}".encode()
                ).hexdigest()[:12]
                
                # Select primary article
                primary_idx, selection_reason = self.select_primary_article_by_length(cluster_articles)
                primary_article = cluster_articles[primary_idx]
                
                # Store cluster in database
                for i, article in enumerate(cluster_articles):
                    is_primary = (i == primary_idx)
                    
                    conn.execute("""
                        INSERT OR REPLACE INTO article_clusters
                        (cluster_id, article_id, is_primary, similarity_score, clustering_method)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        cluster_id,
                        article['id'],
                        1 if is_primary else 0,
                        1.0,  # GPT clustering is binary (same story or not)
                        'gpt_title_clustering'
                    ))
                    
                    if not is_primary:
                        total_duplicates_marked += 1
                
                # Track results
                cluster_results.append({
                    'cluster_id': cluster_id,
                    'group_name': group_name,
                    'size': len(cluster_articles),
                    'primary_title': primary_article['title'][:60] + "...",
                    'primary_source': primary_article.get('source', 'unknown'),
                    'primary_length': primary_article.get('content_length', 0),
                    'selection_reason': selection_reason
                })
                
                self.logger.debug(f"Cluster {cluster_id}: {len(cluster_articles)} articles, "
                                f"primary: {primary_article.get('source', 'unknown')} "
                                f"({primary_article.get('content_length', 0):,} chars)")
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Database error storing clusters: {e}")
            raise
        finally:
            conn.close()
        
        return {
            'clusters_stored': len(clusters),
            'duplicates_marked': total_duplicates_marked,
            'cluster_details': cluster_results
        }
    
    def deduplicate_articles(self) -> Dict[str, Any]:
        """
        Perform GPT-based title deduplication on scraped articles from today.
        
        Returns:
            Results summary including clusters found and primary articles selected
        """
        start_time = time.time()
        
        log_step_start(self.logger, "GPT Title-Based Deduplication", 
                      "Eliminating duplicate stories using GPT-5-mini title clustering")
        
        # Step 1: Gather scraped articles from today
        articles = self.gather_scraped_articles_for_today()
        
        if not articles:
            self.logger.info("No scraped articles found for today - skipping deduplication")
            return {
                "articles_processed": 0,
                "clusters_found": 0,
                "duplicates_marked": 0,
                "primary_articles": 0,
                "deduplication_rate": "0.0%"
            }
        
        if len(articles) < 2:
            self.logger.info("Only one article found - no deduplication needed")
            return {
                "articles_processed": len(articles),
                "clusters_found": 0,
                "duplicates_marked": 0,
                "primary_articles": len(articles),
                "deduplication_rate": "0.0%"
            }
        
        self.logger.info(f"Processing {len(articles)} scraped articles for GPT-based deduplication")
        
        # Step 2: Create clustering prompt
        system_prompt, user_prompt = self.create_clustering_prompt(articles)
        
        # Step 3: Call GPT-5-mini for clustering
        try:
            gpt_output = self.call_gpt_for_clustering(system_prompt, user_prompt)
        except Exception as e:
            self.logger.error(f"GPT clustering failed: {e}")
            return {
                "articles_processed": len(articles),
                "clusters_found": 0,
                "duplicates_marked": 0,
                "primary_articles": len(articles),
                "deduplication_rate": "0.0%",
                "error": str(e)
            }
        
        # Step 4: Parse clustering output
        clusters = self.parse_clustering_output(gpt_output, len(articles))
        
        if not clusters:
            self.logger.info("No duplicate clusters found by GPT")
            return {
                "articles_processed": len(articles),
                "clusters_found": 0,
                "duplicates_marked": 0,
                "primary_articles": len(articles),
                "deduplication_rate": "0.0%"
            }
        
        # Step 5: Store clusters in database
        try:
            storage_results = self.store_clusters_in_database(articles, clusters)
        except Exception as e:
            self.logger.error(f"Failed to store clusters: {e}")
            return {
                "articles_processed": len(articles),
                "clusters_found": len(clusters),
                "duplicates_marked": 0,
                "primary_articles": len(articles),
                "deduplication_rate": "0.0%",
                "error": str(e)
            }
        
        # Build final results
        duration = time.time() - start_time
        
        results = {
            'articles_processed': len(articles),
            'clusters_found': len(clusters),
            'duplicates_marked': storage_results['duplicates_marked'],
            'primary_articles': len(clusters),  # One primary per cluster
            'unclustered_articles': len(articles) - sum(len(indices) for indices in clusters.values()),
            'effective_articles': len(articles) - storage_results['duplicates_marked'],
            'deduplication_rate': f"{(storage_results['duplicates_marked'] / len(articles) * 100):.1f}%",
            'cluster_details': storage_results['cluster_details']
        }
        
        log_step_complete(self.logger, "GPT Title-Based Deduplication", duration, {
            "articles_processed": format_number(results['articles_processed']),
            "clusters_found": format_number(results['clusters_found']),
            "duplicates_marked": format_number(results['duplicates_marked']),
            "deduplication_rate": results['deduplication_rate']
        })
        
        return results
    
    def get_primary_articles(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get deduplicated articles for summarization (primary articles from each cluster + unclustered).
        This method ensures only unique stories proceed to summarization.
        
        Args:
            limit: Maximum number of articles to return
            
        Returns:
            List of primary/unique articles ready for summarization
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT DISTINCT i.id, i.source, i.url, i.title, i.published_at, 
                   i.triage_confidence, ac.cluster_id, ac.is_primary
            FROM items i
            LEFT JOIN article_clusters ac ON i.id = ac.article_id AND ac.clustering_method = 'gpt_title_clustering'
            WHERE i.is_match = 1 
            AND EXISTS (SELECT 1 FROM articles a WHERE a.item_id = i.id AND a.extracted_text IS NOT NULL)
            AND (ac.is_primary = 1 OR ac.article_id IS NULL)
            ORDER BY i.triage_confidence DESC, i.first_seen_at DESC
            LIMIT ?
        """, (limit,))
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                'id': row['id'],
                'source': row['source'],
                'url': row['url'],
                'title': row['title'],
                'published_at': row['published_at'],
                'confidence': row['triage_confidence'],
                'cluster_id': row['cluster_id'],
                'is_clustered': row['cluster_id'] is not None
            })
        
        conn.close()
        
        self.logger.info(f"Retrieved {len(articles)} primary/unclustered articles for summarization")
        return articles
