#!/usr/bin/env python3

"""
Test script to verify that skip_prefilter: true properly disables BOTH:
1. Priority-based pre-filtering 
2. Embedding-based prefilter

Expected behavior: When skip_prefilter=True, both prefilters should be disabled.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from news_pipeline.filter import AIFilter
from news_pipeline.utils import setup_logging
import logging

def test_skip_prefilter():
    """Test that skip_prefilter=True disables both prefilter types."""
    
    # Setup logging to see detailed output
    setup_logging(level="INFO")
    logger = logging.getLogger(__name__)
    
    logger.info("="*60)
    logger.info("TESTING skip_prefilter: true functionality")
    logger.info("="*60)
    
    # Initialize the filter
    ai_filter = AIFilter("news.db")
    
    # Test with explicit skip_prefilter=True
    logger.info("\n🧪 TEST: Calling filter_for_creditreform with skip_prefilter=True")
    logger.info("-" * 50)
    
    results = ai_filter.filter_for_creditreform(mode="express", skip_prefilter=True)
    
    logger.info("\n📊 RESULTS:")
    for topic, topic_results in results.items():
        logger.info(f"   Topic: {topic}")
        logger.info(f"   Processed: {topic_results.get('processed', 0)}")
        logger.info(f"   Matched: {topic_results.get('matched', 0)}")
        logger.info(f"   Duration: {topic_results.get('duration', 'N/A')}")
    
    logger.info("\n✅ Test completed!")
    logger.info("="*60)
    logger.info("Check the logs above for these expected messages:")
    logger.info("1. 'Skipping priority-based pre-filtering - processing all deduplicated articles'")
    logger.info("2. '⚠️  PREFILTER: Embedding-based prefilter DISABLED via skip_prefilter parameter'")
    logger.info("="*60)
    
    return results

if __name__ == "__main__":
    test_skip_prefilter()
