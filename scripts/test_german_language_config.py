#!/usr/bin/env python3
"""
Test script to validate German language configuration functionality.

This script tests the language configuration system to ensure consistent
German output across all pipeline components.
"""

import os
import sys
import json
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from news_pipeline.language_config import LanguageConfig, get_language_config, set_language, is_german_mode


def test_language_config_creation():
    """Test creating language configurations directly."""
    print("=== Testing Language Configuration Creation ===")
    
    # Test German configuration
    german_config = LanguageConfig('de')
    assert german_config.is_german()
    assert not german_config.is_english()
    assert german_config.get_language_code() == 'de'
    assert german_config.get_language_name() == 'Deutsch'
    print("✓ German configuration created successfully")
    
    # Test English configuration
    english_config = LanguageConfig('en')
    assert english_config.is_english()
    assert not english_config.is_german()
    assert english_config.get_language_code() == 'en'
    assert english_config.get_language_name() == 'English'
    print("✓ English configuration created successfully")
    
    # Test invalid language
    try:
        LanguageConfig('fr')
        assert False, "Should have raised error for unsupported language"
    except ValueError:
        print("✓ Invalid language properly rejected")


def test_global_configuration():
    """Test global language configuration functions."""
    print("\n=== Testing Global Configuration ===")
    
    # Test setting German
    set_language('de')
    assert is_german_mode()
    assert get_language_config().is_german()
    print("✓ Global German configuration set successfully")
    
    # Test setting English
    set_language('en')
    assert not is_german_mode()
    assert get_language_config().is_english()
    print("✓ Global English configuration set successfully")


def test_prompt_differences():
    """Test that German and English prompts are different."""
    print("\n=== Testing Prompt Differences ===")
    
    # Test executive summary prompts
    german_config = LanguageConfig('de')
    english_config = LanguageConfig('en')
    
    german_exec_prompt = german_config.get_executive_summary_prompt()
    english_exec_prompt = english_config.get_executive_summary_prompt()
    
    assert german_exec_prompt != english_exec_prompt
    assert 'Sie sind' in german_exec_prompt
    assert 'You are' in english_exec_prompt
    print("✓ Executive summary prompts are properly localized")
    
    # Test partial digest prompts
    topic = "creditreform_insights"
    german_partial = german_config.get_partial_digest_prompt(topic)
    english_partial = english_config.get_partial_digest_prompt(topic)
    
    assert german_partial != english_partial
    assert 'Sie sind' in german_partial
    assert 'You are' in english_partial
    print("✓ Partial digest prompts are properly localized")
    
    # Test merge digest prompts
    german_merge = german_config.get_merge_digests_prompt(topic)
    english_merge = english_config.get_merge_digests_prompt(topic)
    
    assert german_merge != english_merge
    assert 'Sie sind' in german_merge
    assert 'You are' in english_merge
    print("✓ Merge digest prompts are properly localized")


def test_environment_variable_integration():
    """Test environment variable integration."""
    print("\n=== Testing Environment Variable Integration ===")
    
    # Save original value
    original_value = os.environ.get('PIPELINE_LANGUAGE')
    
    try:
        # Test German from environment
        os.environ['PIPELINE_LANGUAGE'] = 'de'
        config = LanguageConfig()
        assert config.is_german()
        print("✓ German configuration loaded from environment variable")
        
        # Test English from environment
        os.environ['PIPELINE_LANGUAGE'] = 'en'
        config = LanguageConfig()
        assert config.is_english()
        print("✓ English configuration loaded from environment variable")
        
        # Test default when not set
        if 'PIPELINE_LANGUAGE' in os.environ:
            del os.environ['PIPELINE_LANGUAGE']
        config = LanguageConfig()
        assert config.is_english()  # Default should be English
        print("✓ Default English configuration when environment variable not set")
        
    finally:
        # Restore original value
        if original_value is not None:
            os.environ['PIPELINE_LANGUAGE'] = original_value
        elif 'PIPELINE_LANGUAGE' in os.environ:
            del os.environ['PIPELINE_LANGUAGE']


def test_output_format_instructions():
    """Test output format instructions in different languages."""
    print("\n=== Testing Output Format Instructions ===")
    
    german_config = LanguageConfig('de')
    english_config = LanguageConfig('en')
    
    german_instructions = german_config.get_output_format_instructions()
    english_instructions = english_config.get_output_format_instructions()
    
    # Check that instructions exist and are different
    assert len(german_instructions) == len(english_instructions)
    for key in german_instructions.keys():
        assert key in english_instructions
        assert german_instructions[key] != english_instructions[key]
    
    # Check specific German content
    assert 'Antworten Sie' in german_instructions['json_instruction']
    assert 'Fettschrift' in german_instructions['emphasis']
    
    # Check specific English content
    assert 'Respond with' in english_instructions['json_instruction']
    assert 'bold' in english_instructions['emphasis']
    
    print("✓ Output format instructions properly localized")


def test_rating_analysis_prompt():
    """Test that rating analysis prompt is always in German."""
    print("\n=== Testing Rating Analysis Prompt ===")
    
    german_config = LanguageConfig('de')
    english_config = LanguageConfig('en')
    
    german_rating = german_config.get_rating_analysis_prompt()
    english_rating = english_config.get_rating_analysis_prompt()
    
    # Rating analysis should always be in German
    assert german_rating == english_rating
    assert 'Sie sind ein Senior-Produktmanager' in german_rating
    print("✓ Rating analysis prompt is always in German (as expected)")


def demonstrate_prompt_examples():
    """Demonstrate examples of German vs English prompts."""
    print("\n=== Demonstrating Prompt Examples ===")
    
    german_config = LanguageConfig('de')
    english_config = LanguageConfig('en')
    
    print("\n--- Executive Summary Prompts ---")
    print("GERMAN:")
    print(german_config.get_executive_summary_prompt()[:200] + "...")
    print("\nENGLISH:")
    print(english_config.get_executive_summary_prompt()[:200] + "...")
    
    print("\n--- Topic Digest Prompts ---")
    print("GERMAN:")
    print(german_config.get_topic_digest_prompt("schweizer_wirtschaft")[:200] + "...")
    print("\nENGLISH:")
    print(english_config.get_topic_digest_prompt("schweizer_wirtschaft")[:200] + "...")


def main():
    """Run all tests."""
    print("German Language Configuration Test Suite")
    print("=" * 50)
    
    try:
        test_language_config_creation()
        test_global_configuration()
        test_prompt_differences()
        test_environment_variable_integration()
        test_output_format_instructions()
        test_rating_analysis_prompt()
        
        print("\n" + "=" * 50)
        print("✅ ALL TESTS PASSED!")
        print("\nThe German language configuration system is working correctly.")
        print("To use German output, set environment variable: PIPELINE_LANGUAGE=de")
        
        demonstrate_prompt_examples()
        
        return 0
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
