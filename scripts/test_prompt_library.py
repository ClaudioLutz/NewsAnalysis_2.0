"""
Unit tests for PromptLibrary architecture and core functionality.

Tests cover:
- YAML loading and parsing
- Caching mechanism
- Error handling for missing files/prompts
- Parameter substitution
- Language integration
- Pipeline stage subclasses
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from news_pipeline.prompt_library import (
    PromptLibrary, 
    FilteringPrompts, 
    DeduplicationPrompts,
    AnalysisPrompts,
    FormattingPrompts,
    DigestPrompts
)
from news_pipeline.language_config import LanguageConfig


class TestPromptLibraryBasics:
    """Test basic PromptLibrary functionality."""
    
    def test_initialization(self):
        """Test PromptLibrary initializes correctly with LanguageConfig."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        assert prompt_lib._language_config == lang_config
        assert isinstance(prompt_lib.filtering, FilteringPrompts)
        assert isinstance(prompt_lib.deduplication, DeduplicationPrompts)
        assert isinstance(prompt_lib.analysis, AnalysisPrompts)
        assert isinstance(prompt_lib.formatting, FormattingPrompts)
        assert isinstance(prompt_lib.digest, DigestPrompts)
    
    def test_load_example_yaml(self):
        """Test loading example YAML file works correctly."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        # Load from example.yaml
        prompt = prompt_lib.get_prompt("example", "test_prompt")
        assert prompt is not None
        assert "test prompt" in prompt.lower()
    
    def test_missing_yaml_file_error(self):
        """Test error handling for missing YAML files."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        with pytest.raises(FileNotFoundError) as exc_info:
            prompt_lib.get_prompt("nonexistent_stage", "some_prompt")
        
        assert "nonexistent_stage" in str(exc_info.value)
    
    def test_missing_prompt_name_error(self):
        """Test error handling for missing prompt names."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        with pytest.raises(KeyError) as exc_info:
            prompt_lib.get_prompt("example", "nonexistent_prompt")
        
        assert "nonexistent_prompt" in str(exc_info.value)
        assert "Available prompts" in str(exc_info.value)


class TestPromptCaching:
    """Test caching mechanism."""
    
    def test_caching_works(self):
        """Test that prompts are cached after first load."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        # First load
        prompt1 = prompt_lib.get_prompt("example", "test_prompt")
        
        # Second load (should use cache)
        prompt2 = prompt_lib.get_prompt("example", "test_prompt")
        
        assert prompt1 == prompt2
        assert "example" in prompt_lib._cache
    
    def test_clear_cache(self):
        """Test cache clearing functionality."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        # Load a prompt to populate cache
        prompt_lib.get_prompt("example", "test_prompt")
        assert "example" in prompt_lib._cache
        
        # Clear cache
        prompt_lib.clear_cache()
        assert len(prompt_lib._cache) == 0


class TestParameterSubstitution:
    """Test parameter substitution in prompts."""
    
    def test_simple_substitution(self):
        """Test that parameter substitution works correctly."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        template = prompt_lib.get_prompt("example", "classification_prompt")
        prompt = template.format(topic="creditreform")
        
        assert "creditreform" in prompt
        assert "{topic}" not in prompt
    
    def test_multiple_substitutions(self):
        """Test multiple parameter substitutions in same template."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        template = prompt_lib.get_prompt("example", "classification_prompt")
        # Template has {topic} twice
        prompt = template.format(topic="creditreform")
        
        # Both occurrences should be replaced
        assert prompt.count("creditreform") == 2
        assert "{topic}" not in prompt


class TestPromptMetadata:
    """Test prompt metadata retrieval."""
    
    def test_get_metadata(self):
        """Test getting prompt metadata."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        metadata = prompt_lib.get_prompt_metadata("example", "classification_prompt")
        
        assert metadata is not None
        assert "description" in metadata
        assert "parameters" in metadata
        assert "cost_estimate" in metadata
        assert len(metadata["parameters"]) > 0
    
    def test_metadata_for_nonexistent_prompt(self):
        """Test metadata returns None for nonexistent prompts."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        metadata = prompt_lib.get_prompt_metadata("example", "nonexistent")
        assert metadata is None


class TestLanguageIntegration:
    """Test language configuration integration."""
    
    def test_german_initialization(self):
        """Test initialization with German language."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        assert prompt_lib._language_config.is_german()
        assert not prompt_lib._language_config.is_english()
    
    def test_english_initialization(self):
        """Test initialization with English language."""
        lang_config = LanguageConfig("en")
        prompt_lib = PromptLibrary(lang_config)
        
        assert prompt_lib._language_config.is_english()
        assert not prompt_lib._language_config.is_german()


class TestFilteringPrompts:
    """Test FilteringPrompts stage class."""
    
    def test_filtering_prompts_initialization(self):
        """Test FilteringPrompts initializes correctly."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        assert prompt_lib.filtering._library == prompt_lib
        assert prompt_lib.filtering._language_config == lang_config
    
    def test_classification_prompt_method(self):
        """Test classification_prompt method with parameter."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        prompt = prompt_lib.filtering.classification_prompt(topic="creditreform")
        
        assert "creditreform" in prompt
        assert len(prompt) > 0


class TestDeduplicationPrompts:
    """Test DeduplicationPrompts stage class."""
    
    def test_deduplication_prompts_initialization(self):
        """Test DeduplicationPrompts initializes correctly."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        assert prompt_lib.deduplication._library == prompt_lib
        assert prompt_lib.deduplication._language_config == lang_config


class TestAnalysisPrompts:
    """Test AnalysisPrompts stage class."""
    
    def test_analysis_prompts_initialization(self):
        """Test AnalysisPrompts initializes correctly."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        assert prompt_lib.analysis._library == prompt_lib
        assert prompt_lib.analysis._language_config == lang_config


class TestFormattingPrompts:
    """Test FormattingPrompts stage class."""
    
    def test_formatting_prompts_initialization(self):
        """Test FormattingPrompts initializes correctly."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        assert prompt_lib.formatting._library == prompt_lib
        assert prompt_lib.formatting._language_config == lang_config


class TestDigestPrompts:
    """Test DigestPrompts stage class."""
    
    def test_digest_prompts_initialization(self):
        """Test DigestPrompts initializes correctly."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        assert prompt_lib.digest._library == prompt_lib
        assert prompt_lib.digest._language_config == lang_config


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""
    
    def test_complete_workflow(self):
        """Test complete workflow: initialize, load, substitute, retrieve."""
        # Step 1: Initialize with language config
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        # Step 2: Access via pipeline stage
        template = prompt_lib.get_prompt("example", "classification_prompt")
        
        # Step 3: Parameter substitution
        prompt = template.format(topic="creditreform")
        
        # Step 4: Validate result
        assert "creditreform" in prompt
        assert len(prompt) > 50  # Should be a substantial prompt
        assert "{topic}" not in prompt
        
        # Step 5: Verify caching worked
        assert "example" in prompt_lib._cache
    
    def test_multiple_stage_access(self):
        """Test accessing multiple pipeline stages in sequence."""
        lang_config = LanguageConfig("de")
        prompt_lib = PromptLibrary(lang_config)
        
        # Access filtering stage
        filtering_prompt = prompt_lib.filtering.classification_prompt(topic="test")
        assert len(filtering_prompt) > 0
        
        # Verify all stages are accessible
        assert prompt_lib.filtering is not None
        assert prompt_lib.deduplication is not None
        assert prompt_lib.analysis is not None
        assert prompt_lib.formatting is not None
        assert prompt_lib.digest is not None


def run_tests():
    """Run all tests with pytest."""
    import subprocess
    import sys
    
    # Run pytest on this file
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    return result.returncode


if __name__ == "__main__":
    print("=" * 60)
    print("PromptLibrary Unit Tests")
    print("=" * 60)
    
    exit_code = run_tests()
    
    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code {exit_code}")
    
    sys.exit(exit_code)
