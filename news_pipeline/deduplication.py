"""
Semantic Deduplication System - Phase 4: Article Clustering

Implements content similarity detection and clustering to eliminate duplicate
stories from multiple sources while preserving the best quality articles.
"""

import os
import json
import sqlite3
import hashlib
import logging
import time
from typing import Dict, List, Any, Tuple, Optional
import re
from datetime import datetime
from dateutil import parser

# Optional dependencies for enhanced similarity detection
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from .utils import log_step_start, log_step_complete, format_number


class ArticleDeduplicator:
    """Semantic deduplication system for eliminating duplicate news articles."""
    
    def __init__(self, db_path: str, similarity_threshold: float = 0.75):
        self.db_path = db_path
        self.similarity_threshold = similarity_threshold
        self.logger = logging.getLogger(__name__)
        
        # Initialize similarity model
        self._init_similarity_model()
        
        # Source authority rankings for cluster selection
        self.source_authority = {
            # Tier 1: Government and regulatory
            'admin.ch': 10, 'finma.ch': 10, 'snb.ch': 10, 'seco.admin.ch': 10, 'bfs.admin.ch': 10,
            
            # Tier 2: Financial news
            'handelszeitung.ch': 8, 'finews.ch': 8, 'fuw.ch': 8, 'cash.ch': 7,
            
            # Tier 3: General news
            'nzz.ch': 6, 'srf.ch': 5,
            
            # Default for unknown sources
            'unknown': 1
        }
    
    def _init_similarity_model(self):
        """Initialize the similarity detection model."""
        self.use_sentence_transformers = False
        self.use_tfidf = False
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Try to load a multilingual model suitable for German/English
                self.sentence_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                self.use_sentence_transformers = True
                self.logger.info("Using SentenceTransformers for semantic similarity")
            except Exception as e:
                self.logger.warning(f"Failed to load SentenceTransformers: {e}")
        
        if not self.use_sentence_transformers and SKLEARN_AVAILABLE:
            # Fallback to TF-IDF with cosine similarity
            self.tfidf_vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words='english',  # Basic English stopwords
                ngram_range=(1, 2),
                lowercase=True
            )
            self.use_tfidf = True
            self.logger.info("Using TF-IDF + cosine similarity for text similarity")
        
        if not self.use_sentence_transformers and not self.use_tfidf:
            self.logger.warning("No similarity models available - falling back to basic text matching")
    
    def calculate_content_fingerprint(self, title: str, url: str = "") -> str:
        """
        Generate a content fingerprint for quick duplicate detection.
        
        Args:
            title: Article title
            url: Article URL (optional)
            
        Returns:
            Hex string fingerprint
        """
        # Normalize title for fingerprinting
        normalized = self._normalize_text(title)
        
        # Create fingerprint from normalized content
        content = f"{normalized}|{self._extract_domain(url)}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""
        
        # Convert to lowercase
        normalized = text.lower()
        
        # Remove common noise patterns in news titles
        noise_patterns = [
            r'\s*\|\s*[^|]*$',  # Remove " | Source Name" suffixes
            r'\s*-\s*[^-]*$',   # Remove " - Source Name" suffixes
            r'^\s*\w+:\s*',     # Remove "City:" or "CITY:" prefixes
            r'\s*\([^)]*\)\s*', # Remove parenthetical content
            r'\s*\[[^\]]*\]\s*', # Remove bracketed content
        ]
        
        for pattern in noise_patterns:
            normalized = re.sub(pattern, '', normalized)
        
        # Clean up whitespace and punctuation
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        if not url:
            return "unknown"
        
        # Simple domain extraction
        domain = url.lower()
        if '://' in domain:
            domain = domain.split('://')[1]
        if '/' in domain:
            domain = domain.split('/')[0]
        if domain.startswith('www.'):
            domain = domain[4:]
        
        return domain
    
    def calculate_similarity(self, title1: str, title2: str, url1: str = "", url2: str = "") -> float:
        """
        Calculate semantic similarity between two articles.
        
        Args:
            title1, title2: Article titles to compare
            url1, url2: Article URLs (optional, for domain comparison)
            
        Returns:
            Similarity score from 0.0 to 1.0
        """
        if not title1 or not title2:
            return 0.0
        
        # Quick exact match check
        if title1.strip() == title2.strip():
            return 1.0
        
        # Normalize titles
        norm1 = self._normalize_text(title1)
        norm2 = self._normalize_text(title2)
        
        # Quick normalized match check
        if norm1 == norm2:
            return 0.95
        
        # Use best available similarity method
        if self.use_sentence_transformers:
            return self._calculate_sentence_similarity(norm1, norm2)
        elif self.use_tfidf:
            return self._calculate_tfidf_similarity(norm1, norm2)
        else:
            return self._calculate_basic_similarity(norm1, norm2)
    
    def _calculate_sentence_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity using SentenceTransformers."""
        try:
            embeddings = self.sentence_model.encode([text1, text2])
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            return max(0.0, min(1.0, similarity))
        except Exception as e:
            self.logger.warning(f"SentenceTransformers similarity failed: {e}")
            return self._calculate_basic_similarity(text1, text2)
    
    def _calculate_tfidf_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity using TF-IDF and cosine similarity."""
        try:
            # Fit and transform both texts
            tfidf_matrix = self.tfidf_vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return max(0.0, min(1.0, similarity))
        except Exception as e:
            self.logger.warning(f"TF-IDF similarity failed: {e}")
            return self._calculate_basic_similarity(text1, text2)
    
    def _calculate_basic_similarity(self, text1: str, text2: str) -> float:
        """Basic word-based similarity calculation."""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def get_source_authority_score(self, url: str) -> int:
        """Get authority score for a source based on URL."""
        domain = self._extract_domain(url)
        
        # Check for exact domain matches
        for source_domain, score in self.source_authority.items():
            if source_domain in domain:
                return score
        
        return self.source_authority['unknown']
    
    def calculate_article_quality_score(self, article: Dict[str, Any]) -> float:
        """
        Calculate overall quality score for article selection in clusters.
        
        Factors:
        - Source authority
        - Content completeness
        - Publication timing
        - URL quality
        """
        score = 0.0
        
        # Source authority (0-10 points)
        authority_score = self.get_source_authority_score(article.get('url', ''))
        score += authority_score
        
        # Content completeness
        title = article.get('title', '')
        if title:
            title_length = len(title)
            if title_length > 50:  # Reasonable title length
                score += 2
            elif title_length > 20:
                score += 1
        
        # URL quality indicators
        url = article.get('url', '')
        if '/artikel/' in url or '/news/' in url:
            score += 1  # Looks like proper article URL
        
        if '?' not in url:
            score += 0.5  # Clean URL without parameters
        
        # Publication timing (newer is better)
        pub_date = article.get('published_at') or article.get('first_seen_at')
        if pub_date:
            try:
                parsed_date = parser.parse(pub_date)
                days_old = (datetime.now() - parsed_date.replace(tzinfo=None)).days
                
                if days_old == 0:
                    score += 2  # Today
                elif days_old == 1:
                    score += 1  # Yesterday
                elif days_old <= 7:
                    score += 0.5  # This week
            except:
                pass  # Ignore date parsing errors
        
        return score
    
    def find_similar_articles(self, articles: List[Dict[str, Any]]) -> List[List[int]]:
        """
        Group articles into similarity clusters.
        
        Args:
            articles: List of articles with id, title, url fields
            
        Returns:
            List of clusters, where each cluster is a list of article IDs
        """
        if not articles:
            return []
        
        self.logger.info(f"Finding similar articles in {format_number(len(articles))} articles")
        
        clusters = []
        processed = set()
        
        for i, article1 in enumerate(articles):
            if i in processed:
                continue
            
            # Start new cluster with this article
            current_cluster = [i]
            processed.add(i)
            
            # Find similar articles
            for j, article2 in enumerate(articles[i + 1:], i + 1):
                if j in processed:
                    continue
                
                similarity = self.calculate_similarity(
                    article1.get('title', ''),
                    article2.get('title', ''),
                    article1.get('url', ''),
                    article2.get('url', '')
                )
                
                if similarity >= self.similarity_threshold:
                    current_cluster.append(j)
                    processed.add(j)
            
            # Only keep clusters with more than one article
            if len(current_cluster) > 1:
                clusters.append(current_cluster)
        
        self.logger.info(f"Found {len(clusters)} similarity clusters")
        return clusters
    
    def select_primary_article(self, cluster_articles: List[Dict[str, Any]]) -> Tuple[int, str]:
        """
        Select the best (primary) article from a cluster.
        
        Args:
            cluster_articles: List of articles in the cluster
            
        Returns:
            (index_of_primary, selection_reason)
        """
        if not cluster_articles:
            return 0, "Default selection"
        
        if len(cluster_articles) == 1:
            return 0, "Only article in cluster"
        
        # Calculate quality scores
        scores = []
        for article in cluster_articles:
            score = self.calculate_article_quality_score(article)
            scores.append(score)
        
        # Select highest scoring article
        best_idx = scores.index(max(scores))
        best_score = scores[best_idx]
        
        # Build reason string
        best_article = cluster_articles[best_idx]
        domain = self._extract_domain(best_article.get('url', ''))
        authority = self.get_source_authority_score(best_article.get('url', ''))
        
        reason = f"Highest quality score {best_score:.1f} (source: {domain}, authority: {authority})"
        
        return best_idx, reason
    
    def deduplicate_articles(self, limit: int = 1000) -> Dict[str, Any]:
        """
        Perform semantic deduplication on matched articles.
        
        Args:
            limit: Maximum number of articles to process for performance
            
        Returns:
            Results summary including clusters found and primary articles selected
        """
        start_time = time.time()
        
        log_step_start(self.logger, "Semantic Article Deduplication", 
                      f"Eliminating duplicates from matched articles (limit: {limit})")
        
        # Get matched articles that haven't been clustered yet
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT id, source, url, title, published_at, first_seen_at, triage_confidence
            FROM items 
            WHERE is_match = 1 
            AND id NOT IN (SELECT article_id FROM article_clusters)
            ORDER BY triage_confidence DESC, first_seen_at DESC
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
                'first_seen_at': row['first_seen_at'],
                'confidence': row['triage_confidence']
            })
        
        conn.close()
        
        if not articles:
            self.logger.info("No articles found for deduplication")
            return {"clusters": 0, "articles_processed": 0}
        
        self.logger.info(f"Processing {format_number(len(articles))} matched articles for deduplication")
        
        # Find similarity clusters
        clusters = self.find_similar_articles(articles)
        
        if not clusters:
            self.logger.info("No duplicate clusters found")
            return {"clusters": 0, "articles_processed": len(articles)}
        
        # Process each cluster
        total_duplicates_marked = 0
        cluster_results = []
        
        conn = sqlite3.connect(self.db_path)
        
        for cluster_idx, cluster_indices in enumerate(clusters):
            cluster_articles = [articles[i] for i in cluster_indices]
            cluster_id = hashlib.md5(
                f"cluster_{cluster_idx}_{len(cluster_articles)}".encode()
            ).hexdigest()[:12]
            
            # Select primary article
            primary_idx, selection_reason = self.select_primary_article(cluster_articles)
            primary_article = cluster_articles[primary_idx]
            
            # Store cluster information
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
                    1.0 if is_primary else self.similarity_threshold,
                    'title_similarity'
                ))
                
                if not is_primary:
                    total_duplicates_marked += 1
            
            cluster_results.append({
                'cluster_id': cluster_id,
                'size': len(cluster_articles),
                'primary_title': primary_article['title'][:60] + "...",
                'primary_source': self._extract_domain(primary_article['url']),
                'selection_reason': selection_reason
            })
            
            self.logger.debug(f"Cluster {cluster_id}: {len(cluster_articles)} articles, "
                            f"primary: {self._extract_domain(primary_article['url'])}")
        
        conn.commit()
        conn.close()
        
        # Results summary
        duration = time.time() - start_time
        
        results = {
            'articles_processed': len(articles),
            'clusters_found': len(clusters),
            'duplicates_marked': total_duplicates_marked,
            'primary_articles': len(clusters),
            'deduplication_rate': f"{(total_duplicates_marked / len(articles) * 100):.1f}%",
            'cluster_details': cluster_results
        }
        
        log_step_complete(self.logger, "Semantic Article Deduplication", duration, {
            "articles_processed": format_number(results['articles_processed']),
            "clusters_found": format_number(results['clusters_found']),
            "duplicates_marked": format_number(results['duplicates_marked']),
            "deduplication_rate": results['deduplication_rate']
        })
        
        return results
    
    def get_cluster_info(self, article_id: int) -> Optional[Dict[str, Any]]:
        """Get cluster information for a specific article."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT ac.cluster_id, ac.is_primary, ac.similarity_score,
                   COUNT(*) as cluster_size
            FROM article_clusters ac
            WHERE ac.cluster_id IN (
                SELECT cluster_id FROM article_clusters WHERE article_id = ?
            )
            GROUP BY ac.cluster_id
        """, (article_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'cluster_id': result['cluster_id'],
                'is_primary': bool(result['is_primary']),
                'cluster_size': result['cluster_size'],
                'similarity_score': result['similarity_score']
            }
        
        return None
    
    def get_primary_articles(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get deduplicated articles (primary articles from each cluster + unclustered articles).
        
        Args:
            limit: Maximum number of articles to return
            
        Returns:
            List of primary/unique articles
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT DISTINCT i.id, i.source, i.url, i.title, i.published_at, 
                   i.triage_confidence, ac.cluster_id, ac.is_primary
            FROM items i
            LEFT JOIN article_clusters ac ON i.id = ac.article_id
            WHERE i.is_match = 1 
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
        return articles
    
    def get_deduplication_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics."""
        conn = sqlite3.connect(self.db_path)
        
        # Total matched articles
        cursor = conn.execute("SELECT COUNT(*) FROM items WHERE is_match = 1")
        total_matched = cursor.fetchone()[0]
        
        # Clustered articles
        cursor = conn.execute("SELECT COUNT(*) FROM article_clusters")
        total_clustered = cursor.fetchone()[0]
        
        # Primary articles
        cursor = conn.execute("SELECT COUNT(*) FROM article_clusters WHERE is_primary = 1")
        primary_articles = cursor.fetchone()[0]
        
        # Duplicates marked
        cursor = conn.execute("SELECT COUNT(*) FROM article_clusters WHERE is_primary = 0")
        duplicates_marked = cursor.fetchone()[0]
        
        # Clusters
        cursor = conn.execute("SELECT COUNT(DISTINCT cluster_id) FROM article_clusters")
        total_clusters = cursor.fetchone()[0]
        
        conn.close()
        
        # Calculate effective articles (primary + unclustered)
        unclustered = total_matched - total_clustered
        effective_articles = primary_articles + unclustered
        
        return {
            'total_matched_articles': total_matched,
            'total_clustered': total_clustered,
            'total_clusters': total_clusters,
            'primary_articles': primary_articles,
            'duplicates_marked': duplicates_marked,
            'unclustered_articles': unclustered,
            'effective_articles': effective_articles,
            'deduplication_rate': f"{(duplicates_marked / total_matched * 100):.1f}%" if total_matched > 0 else "0%"
        }
