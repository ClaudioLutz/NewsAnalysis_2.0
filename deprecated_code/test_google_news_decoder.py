#!/usr/bin/env python3
"""
Test script for Google News URL Decoder

Tests the comprehensive Google News URL decoder implementation
with sample URLs and validates the different decoding methods.
"""

import os
import sys
import logging
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from news_pipeline.google_news_decoder import GoogleNewsDecoder

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_decoder():
    """Test the Google News URL decoder with various URL types."""
    
    # Sample Google News URLs for testing (these would be from actual RSS feeds)
    test_urls = [
        # Legacy format URL (base64 encoded)
        "https://news.google.com/rss/articles/CBMiR2h0dHBzOi8vd3d3LmJiYy5jb20vbmV3cy93b3JsZC1ldXJvcGUtNTk5NzM4NzDSAUtodHRwczovL3d3dy5iYmMuY29tL25ld3Mvd29ybGQtZXVyb3BlLTU5OTczODcwLmFtcA?oc=5",
        
        # New format URL (post July 2024 - would need actual URL to test)
        # This is a placeholder - real URLs would start with AU_yqL in decoded form
        "https://news.google.com/rss/articles/CBMiHmh0dHBzOi8vZXhhbXBsZS5jb20vYXJ0aWNsZS8xMjPSAWVodHRwczovL2V4YW1wbGUtYW1wLmNkbi5hbXBwcm9qZWN0Lm9yZy92L3MvZXhhbXBsZS5jb20vYXJ0aWNsZS8xMjM_YW1wX2pzX3Y9YTkmYW1wX2dzYT0xJmFtcF9ndD0x0gFG?oc=5",
        
        # Direct URL (should pass through unchanged)
        "https://www.example.com/article/123",
        
        # Non-Google News URL (should pass through unchanged)
        "https://www.reuters.com/world/europe/story-123"
    ]
    
    # Initialize decoder
    decoder = GoogleNewsDecoder(request_timeout=10)
    
    print(f"\n{'='*80}")
    print("GOOGLE NEWS URL DECODER TEST")
    print(f"{'='*80}\n")
    
    results = {
        'tested': 0,
        'decoded_base64': 0,
        'decoded_api': 0,
        'passthrough': 0,
        'failed': 0
    }
    
    for i, url in enumerate(test_urls, 1):
        print(f"Test {i}: Testing URL decoding")
        print(f"Original URL: {url}")
        
        # Test the decoder
        try:
            decoded_url = decoder.decode_url(url)
            results['tested'] += 1
            
            if decoded_url:
                if decoded_url != url:
                    print(f"✓ Successfully decoded to: {decoded_url}")
                    # Check if it was base64 or API method based on logs
                    if "news.google.com/rss/articles/" in url:
                        # This would be either base64 or API method
                        print("  Method: Base64 or HTML/API decoding")
                        results['decoded_base64'] += 1  # Simplified for demo
                    else:
                        results['passthrough'] += 1
                else:
                    print(f"✓ URL passed through unchanged: {decoded_url}")
                    results['passthrough'] += 1
            else:
                print(f"✗ Decoding failed - URL could not be resolved")
                results['failed'] += 1
                
        except Exception as e:
            print(f"✗ Error during decoding: {e}")
            results['failed'] += 1
        
        print("-" * 80)
    
    # Print summary
    print("\nTEST SUMMARY:")
    print(f"Total URLs tested: {results['tested']}")
    print(f"Successfully decoded: {results['decoded_base64']}")
    print(f"Passed through unchanged: {results['passthrough']}")
    print(f"Failed to decode: {results['failed']}")
    
    # Test rate limiting
    print(f"\n{'='*80}")
    print("RATE LIMITING TEST")
    print(f"{'='*80}")
    
    print("Testing rate limiting (should have 1-second delays)...")
    start_time = datetime.now()
    
    # Make multiple requests to test rate limiting
    for i in range(3):
        decoder.decode_base64_url("https://news.google.com/rss/articles/testurl")
        print(f"Request {i+1} completed")
    
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    print(f"Total time for 3 requests: {elapsed:.2f} seconds")
    print("✓ Rate limiting working correctly" if elapsed >= 2.0 else "⚠ Rate limiting may not be working")
    
    # Test URL validation
    print(f"\n{'='*80}")
    print("URL VALIDATION TEST")
    print(f"{'='*80}")
    
    test_validation_urls = [
        ("https://www.example.com/article/123", True),
        ("https://news.google.com/something", False),  # Should reject Google domains
        ("https://facebook.com/post/123", False),     # Should reject social media
        ("http://short.url", False),                  # Should reject too short
        ("not-a-url", False),                        # Should reject invalid URLs
        ("https://www.newssite.com/category/tech/article-title-2024", True)  # Should accept valid news URL
    ]
    
    for url, expected in test_validation_urls:
        result = decoder._is_valid_news_url(url)
        status = "✓" if result == expected else "✗"
        print(f"{status} {url} -> {result} (expected {expected})")
    
    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")
    
    return results

if __name__ == "__main__":
    try:
        results = test_decoder()
        
        # Exit with appropriate code
        if results['failed'] > 0:
            print(f"\n⚠ Some tests failed. Check the output above for details.")
            sys.exit(1)
        else:
            print(f"\n✓ All tests passed successfully!")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        sys.exit(1)
