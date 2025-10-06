"""
Tests for german_rating_formatter.py using fragment-based architecture.

Validates that:
1. PromptLibrary integration works correctly
2. Fragment retrieval is successful
3. Prompt composition produces expected results
"""

import pytest
from news_pipeline.german_rating_formatter import GermanRatingFormatter
from news_pipeline.prompt_library import PromptLibrary
from news_pipeline.language_config import LanguageConfig


class TestGermanFormatterFragments:
    """Test fragment-based prompt architecture in german_rating_formatter.py"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.formatter = GermanRatingFormatter()
        
        # Direct access to prompt library for testing
        lang_config = LanguageConfig("de")
        self.prompt_lib = PromptLibrary(lang_config)
    
    def test_formatter_has_prompt_library(self):
        """Verify formatter initializes with PromptLibrary"""
        assert hasattr(self.formatter, 'prompt_lib')
        assert isinstance(self.formatter.prompt_lib, PromptLibrary)
    
    def test_rating_agency_fragment_exists(self):
        """Verify rating agency analyst role fragment exists"""
        fragment = self.prompt_lib.get_fragment('formatting', 'rating_agency_analyst_role')
        
        assert fragment is not None
        assert isinstance(fragment, str)
        assert len(fragment) > 0
    
    def test_rating_agency_fragment_content(self):
        """Verify rating agency fragment contains expected German content"""
        fragment = self.prompt_lib.get_fragment('formatting', 'rating_agency_analyst_role')
        
        # Should be in German
        assert 'Rating-Agentur' in fragment
        assert 'Bonität' in fragment or 'Kreditwürdigkeit' in fragment
        
        # Should mention key analysis areas
        assert 'Makroökonomische' in fragment or 'makroökonomische' in fragment
        assert 'Risiko' in fragment
    
    def test_rating_agency_fragment_structure(self):
        """Verify rating agency fragment has expected structure"""
        fragment = self.prompt_lib.get_fragment('formatting', 'rating_agency_analyst_role')
        
        # Should mention output structure
        assert 'executive_summary' in fragment
        assert 'risk_assessment' in fragment
        assert 'sector_implications' in fragment
        
        # Should request JSON output
        assert 'JSON' in fragment
    
    def test_fragment_caching(self):
        """Verify fragment caching works correctly"""
        # First call should load from YAML
        fragment1 = self.prompt_lib.get_fragment('formatting', 'rating_agency_analyst_role')
        
        # Second call should use cache
        fragment2 = self.prompt_lib.get_fragment('formatting', 'rating_agency_analyst_role')
        
        # Should be identical
        assert fragment1 == fragment2
        assert fragment1 is fragment2  # Same object (cached)
    
    def test_fragment_is_string(self):
        """Verify fragment returns proper string type"""
        fragment = self.prompt_lib.get_fragment('formatting', 'rating_agency_analyst_role')
        
        assert isinstance(fragment, str)
        assert not isinstance(fragment, bytes)
    
    def test_fragment_not_empty(self):
        """Verify fragment contains substantial content"""
        fragment = self.prompt_lib.get_fragment('formatting', 'rating_agency_analyst_role')
        
        # Should be a substantial prompt (at least 200 characters)
        assert len(fragment) > 200
        
        # Should have multiple lines
        assert '\n' in fragment
    
    def test_invalid_fragment_raises_error(self):
        """Verify accessing non-existent fragment raises appropriate error"""
        with pytest.raises((KeyError, ValueError)):
            self.prompt_lib.get_fragment('formatting', 'nonexistent_fragment')
    
    def test_invalid_category_raises_error(self):
        """Verify accessing non-existent category raises appropriate error"""
        with pytest.raises((KeyError, ValueError)):
            self.prompt_lib.get_fragment('nonexistent_category', 'some_fragment')


class TestGermanFormatterMigration:
    """Integration tests for German formatter migration"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.formatter = GermanRatingFormatter()
    
    def test_formatter_initialization(self):
        """Verify formatter initializes without errors"""
        assert self.formatter is not None
        assert hasattr(self.formatter, 'prompt_lib')
        assert hasattr(self.formatter, 'logger')
    
    def test_formatter_uses_german_language(self):
        """Verify formatter can retrieve German-specific fragments"""
        # Test that formatter can retrieve fragments (implicitly tests German config)
        fragment = self.formatter.prompt_lib.get_fragment('formatting', 'rating_agency_analyst_role')
        
        # Verify it contains German text
        assert 'Rating-Agentur' in fragment
        assert 'Kreditwürdigkeit' in fragment or 'Bonität' in fragment
    
    def test_generate_basic_analysis_no_errors(self):
        """Verify basic analysis generation works without errors"""
        # Create minimal digest data
        digest_data = {
            'date': '2025-10-05',
            'executive_summary': {
                'headline': 'Test Headline',
                'executive_summary': 'Test summary',
                'key_themes': ['Theme 1', 'Theme 2'],
                'top_priorities': ['Priority 1', 'Priority 2']
            }
        }
        
        result = self.formatter._generate_basic_analysis(digest_data)
        
        assert result is not None
        assert 'analysis_text' in result
        assert 'generated_at' in result
        assert 'method' in result
        assert result['method'] == 'basic_fallback'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
