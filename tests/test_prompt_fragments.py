"""
Tests for Fragment-Based Hybrid Prompt Architecture

Tests the PromptLibrary.get_fragment() method and fragment composition patterns.
"""

import pytest
from pathlib import Path
from news_pipeline.prompt_library import PromptLibrary
from news_pipeline.language_config import LanguageConfig


@pytest.fixture
def prompt_lib():
    """Create PromptLibrary instance for testing."""
    lang_config = LanguageConfig("de")
    return PromptLibrary(lang_config)


class TestFragmentRetrieval:
    """Test basic fragment retrieval functionality."""
    
    def test_get_fragment_returns_text(self, prompt_lib):
        """Test that get_fragment returns string content."""
        fragment = prompt_lib.get_fragment('common', 'analyst_role')
        assert isinstance(fragment, str)
        assert len(fragment) > 0
    
    def test_get_fragment_content_matches_yaml(self, prompt_lib):
        """Test that returned fragment matches expected content."""
        analyst_role = prompt_lib.get_fragment('common', 'analyst_role')
        assert 'expert' in analyst_role.lower() or 'analyst' in analyst_role.lower()
        assert 'Swiss' in analyst_role or 'swiss' in analyst_role.lower()
    
    def test_get_fragment_common_category(self, prompt_lib):
        """Test retrieval from common category."""
        fragments = [
            'classifier_header',
            'output_format',
            'swiss_context',
            'analyst_role',
            'structured_summary_format',
            'swiss_analysis_focus'
        ]
        
        for fragment_name in fragments:
            fragment = prompt_lib.get_fragment('common', fragment_name)
            assert isinstance(fragment, str)
            assert len(fragment) > 0
    
    def test_get_fragment_analysis_category(self, prompt_lib):
        """Test retrieval from analysis category."""
        fragment = prompt_lib.get_fragment('analysis', 'summarization_task')
        assert isinstance(fragment, str)
        assert len(fragment) > 0


class TestFragmentErrorHandling:
    """Test error handling for invalid fragment requests."""
    
    def test_invalid_category_raises_keyerror(self, prompt_lib):
        """Test that invalid category raises KeyError with helpful message."""
        with pytest.raises(KeyError) as exc_info:
            prompt_lib.get_fragment('nonexistent_category', 'some_fragment')
        
        error_msg = str(exc_info.value)
        assert 'nonexistent_category' in error_msg
        assert 'Available categories' in error_msg
    
    def test_invalid_fragment_raises_keyerror(self, prompt_lib):
        """Test that invalid fragment name raises KeyError with helpful message."""
        with pytest.raises(KeyError) as exc_info:
            prompt_lib.get_fragment('common', 'nonexistent_fragment')
        
        error_msg = str(exc_info.value)
        assert 'nonexistent_fragment' in error_msg
        assert 'Available fragments' in error_msg
        assert 'common' in error_msg
    
    def test_error_messages_list_available_options(self, prompt_lib):
        """Test that error messages include available options."""
        # Test category error lists categories
        try:
            prompt_lib.get_fragment('bad_category', 'fragment')
        except KeyError as e:
            assert 'common' in str(e)
            assert 'analysis' in str(e)
        
        # Test fragment error lists fragments
        try:
            prompt_lib.get_fragment('common', 'bad_fragment')
        except KeyError as e:
            assert 'analyst_role' in str(e) or 'classifier_header' in str(e)


class TestFragmentCaching:
    """Test lazy loading and caching behavior."""
    
    def test_fragments_loaded_lazily(self, prompt_lib):
        """Test that fragments aren't loaded until first use."""
        # Fragments should not be loaded at initialization
        assert not hasattr(prompt_lib, '_fragments')
        
        # First call should trigger loading
        prompt_lib.get_fragment('common', 'analyst_role')
        assert hasattr(prompt_lib, '_fragments')
    
    def test_fragments_cached_after_first_load(self, prompt_lib):
        """Test that fragments are cached after first retrieval."""
        # First call loads fragments
        fragment1 = prompt_lib.get_fragment('common', 'analyst_role')
        fragments_cache = prompt_lib._fragments
        
        # Second call should use cached version
        fragment2 = prompt_lib.get_fragment('common', 'swiss_context')
        assert prompt_lib._fragments is fragments_cache
        
        # Content should still be correct
        assert isinstance(fragment1, str)
        assert isinstance(fragment2, str)
    
    def test_multiple_fragments_from_same_category(self, prompt_lib):
        """Test retrieving multiple fragments from same category."""
        role = prompt_lib.get_fragment('common', 'analyst_role')
        context = prompt_lib.get_fragment('common', 'swiss_context')
        focus = prompt_lib.get_fragment('common', 'swiss_analysis_focus')
        
        # All should be valid strings
        assert all(isinstance(f, str) and len(f) > 0 for f in [role, context, focus])
        
        # All should be different
        assert role != context
        assert role != focus
        assert context != focus


class TestFragmentComposition:
    """Test composing prompts from fragments."""
    
    def test_simple_composition(self, prompt_lib):
        """Test basic fragment composition with f-strings."""
        role = prompt_lib.get_fragment('common', 'analyst_role')
        task = prompt_lib.get_fragment('analysis', 'summarization_task')
        
        composed = f"{role}\n\n{task}"
        
        assert role in composed
        assert task in composed
        assert len(composed) > len(role) + len(task)
    
    def test_multi_fragment_composition(self, prompt_lib):
        """Test composing prompt from multiple fragments."""
        analyst_role = prompt_lib.get_fragment('common', 'analyst_role')
        task_description = prompt_lib.get_fragment('analysis', 'summarization_task')
        output_format = prompt_lib.get_fragment('common', 'structured_summary_format')
        focus_areas = prompt_lib.get_fragment('common', 'swiss_analysis_focus')
        
        # This is the exact pattern used in summarizer.py
        system_prompt = f"{analyst_role}\n\n{task_description}\n\n{output_format}\n\n{focus_areas}"
        
        # Verify all fragments are present
        assert analyst_role in system_prompt
        assert task_description in system_prompt
        assert output_format in system_prompt
        assert focus_areas in system_prompt
        
        # Verify structure (newlines between sections)
        assert '\n\n' in system_prompt
    
    def test_composition_with_dynamic_content(self, prompt_lib):
        """Test mixing fragments with dynamic content."""
        header = prompt_lib.get_fragment('common', 'classifier_header')
        output_format = prompt_lib.get_fragment('common', 'output_format')
        
        # Add dynamic content
        dynamic_keywords = ["creditreform", "insolvency", "rating"]
        keywords_text = f"Keywords to watch: {', '.join(dynamic_keywords)}"
        
        composed = f"{header}\n\n{keywords_text}\n\n{output_format}"
        
        assert header in composed
        assert keywords_text in composed
        assert output_format in composed
        assert all(kw in composed for kw in dynamic_keywords)


class TestFragmentIntegrationWithSummarizer:
    """Test integration with ArticleSummarizer."""
    
    def test_summarizer_uses_fragments(self, tmp_path):
        """Test that ArticleSummarizer successfully uses fragment-based prompts."""
        from news_pipeline.summarizer import ArticleSummarizer
        
        # Create temporary test database
        db_path = tmp_path / "test.db"
        summarizer = ArticleSummarizer(str(db_path))
        
        # Verify prompt library is initialized
        assert hasattr(summarizer, 'prompt_lib')
        assert isinstance(summarizer.prompt_lib, PromptLibrary)
    
    def test_summarizer_can_retrieve_fragments(self, tmp_path):
        """Test that ArticleSummarizer can retrieve all needed fragments."""
        from news_pipeline.summarizer import ArticleSummarizer
        
        db_path = tmp_path / "test.db"
        summarizer = ArticleSummarizer(str(db_path))
        
        # These are the fragments used in summarize_article()
        analyst_role = summarizer.prompt_lib.get_fragment('common', 'analyst_role')
        task_description = summarizer.prompt_lib.get_fragment('analysis', 'summarization_task')
        output_format = summarizer.prompt_lib.get_fragment('common', 'structured_summary_format')
        focus_areas = summarizer.prompt_lib.get_fragment('common', 'swiss_analysis_focus')
        
        # All should be valid
        assert all(isinstance(f, str) and len(f) > 0 
                  for f in [analyst_role, task_description, output_format, focus_areas])


class TestFragmentFileStructure:
    """Test the fragments.yaml file structure."""
    
    def test_fragments_file_exists(self):
        """Test that fragments.yaml file exists."""
        fragments_path = Path("config/prompts/fragments.yaml")
        assert fragments_path.exists(), "fragments.yaml should exist"
    
    def test_fragments_file_has_required_categories(self, prompt_lib):
        """Test that fragments.yaml has all required categories."""
        # Force loading of fragments
        prompt_lib.get_fragment('common', 'analyst_role')
        
        required_categories = ['common', 'filter', 'analysis', 'deduplication', 'formatting', 'digest']
        for category in required_categories:
            assert category in prompt_lib._fragments, f"Category '{category}' should exist"
    
    def test_common_category_has_required_fragments(self, prompt_lib):
        """Test that common category has all expected fragments."""
        expected_fragments = [
            'classifier_header',
            'output_format',
            'swiss_context',
            'analyst_role',
            'structured_summary_format',
            'swiss_analysis_focus'
        ]
        
        for fragment_name in expected_fragments:
            # Should not raise error
            fragment = prompt_lib.get_fragment('common', fragment_name)
            assert isinstance(fragment, str)
            assert len(fragment) > 0


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
