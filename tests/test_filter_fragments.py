"""
Tests for filter.py fragment-based prompt composition.

Tests the hybrid architecture pattern where static fragments from YAML
are composed with dynamic runtime data using Python's .format().
"""

import pytest
import sys
import os

# Add parent directory to path to import news_pipeline
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from news_pipeline.filter import AIFilter
from news_pipeline.prompt_library import PromptLibrary
from news_pipeline.language_config import LanguageConfig


class TestFilterFragmentComposition:
    """Test fragment-based prompt composition in filter.py"""
    
    @pytest.fixture
    def filter_instance(self, tmp_path):
        """Create AIFilter instance for testing."""
        # Create temporary database
        db_path = tmp_path / "test.db"
        
        # Create minimal topics config
        topics_config = tmp_path / "topics.yaml"
        topics_config.write_text("""
topics:
  test_topic:
    enabled: true
    include:
      - keyword1
      - keyword2
    confidence_threshold: 0.75
  creditreform_insights:
    enabled: true
    description: "Test Creditreform description"
    confidence_threshold: 0.80
    focus_areas:
      regulatory:
        keywords: [credit, risk, compliance]
        priority: high
      market:
        keywords: [trends, competitors]
        priority: medium
""")
        
        # Create minimal pipeline config
        pipeline_config = tmp_path / "pipeline_config.yaml"
        pipeline_config.write_text("""
pipeline:
  filtering:
    confidence_threshold: 0.70
    max_articles_to_process: 35
""")
        
        return AIFilter(
            str(db_path),
            str(topics_config),
            str(pipeline_config)
        )
    
    def test_build_classification_prompt_basic(self, filter_instance):
        """Test basic classification prompt composition."""
        prompt = filter_instance._build_classification_prompt(
            topic='test_topic',
            keywords=['keyword1', 'keyword2']
        )
        
        # Check all fragments are included
        assert 'expert news classifier' in prompt.lower()
        assert 'test_topic' in prompt
        assert 'keyword1' in prompt
        assert 'keyword2' in prompt
        assert 'classify based on' in prompt.lower()
        assert 'return strict json' in prompt.lower()
    
    def test_build_classification_prompt_empty_keywords(self, filter_instance):
        """Test classification prompt with empty keywords list."""
        prompt = filter_instance._build_classification_prompt(
            topic='test_topic',
            keywords=[]
        )
        
        # Should still work with empty keywords
        assert 'test_topic' in prompt
        assert 'expert news classifier' in prompt.lower()
        assert 'return strict json' in prompt.lower()
    
    def test_format_focus_areas_basic(self, filter_instance):
        """Test basic focus areas formatting."""
        focus_areas = {
            'regulatory': {
                'keywords': ['credit', 'risk'],
                'priority': 'high'
            },
            'market': {
                'keywords': ['trends'],
                'priority': 'medium'
            }
        }
        
        result = filter_instance._format_focus_areas(focus_areas)
        
        assert 'regulatory' in result
        assert 'high priority' in result
        assert 'credit' in result
        assert 'risk' in result
        assert 'market' in result
        assert 'medium priority' in result
        assert 'trends' in result
    
    def test_format_focus_areas_empty(self, filter_instance):
        """Test focus areas formatting with empty dict."""
        result = filter_instance._format_focus_areas({})
        assert result == ""
    
    def test_format_focus_areas_none(self, filter_instance):
        """Test focus areas formatting with None."""
        result = filter_instance._format_focus_areas(None)
        assert result == ""
    
    def test_format_focus_areas_missing_keywords(self, filter_instance):
        """Test focus areas with missing keywords."""
        focus_areas = {
            'area1': {
                'priority': 'high'
                # No keywords
            },
            'area2': {
                'keywords': ['k1'],
                'priority': 'low'
            }
        }
        
        result = filter_instance._format_focus_areas(focus_areas)
        
        # area1 should be skipped (no keywords)
        assert 'area1' not in result
        # area2 should be included
        assert 'area2' in result
        assert 'k1' in result
    
    def test_build_creditreform_prompt_complete(self, filter_instance):
        """Test complete Creditreform prompt composition."""
        topic_config = {
            'description': 'Test Creditreform business description',
            'focus_areas': {
                'regulatory': {
                    'keywords': ['credit', 'risk'],
                    'priority': 'high'
                }
            }
        }
        
        prompt = filter_instance.build_creditreform_system_prompt(topic_config)
        
        # Check all components are present
        assert 'B2B credit risk assessment' in prompt
        assert 'Test Creditreform business description' in prompt
        assert 'KEY FOCUS AREAS' in prompt
        assert 'regulatory' in prompt
        assert 'high priority' in prompt
        assert 'credit' in prompt
        assert 'risk' in prompt
        assert 'CLASSIFICATION CRITERIA' in prompt
        assert 'HIGH RELEVANCE' in prompt
        assert 'return strict json' in prompt.lower()
    
    def test_build_creditreform_prompt_empty_config(self, filter_instance):
        """Test Creditreform prompt with empty config."""
        prompt = filter_instance.build_creditreform_system_prompt({})
        
        # Should still generate a valid prompt
        assert 'B2B credit risk assessment' in prompt
        assert 'KEY FOCUS AREAS' in prompt
        assert 'CLASSIFICATION CRITERIA' in prompt
    
    def test_build_creditreform_prompt_none_config(self, filter_instance):
        """Test Creditreform prompt with None config."""
        prompt = filter_instance.build_creditreform_system_prompt(None)
        
        # Should handle None gracefully
        assert 'B2B credit risk assessment' in prompt
        assert 'KEY FOCUS AREAS' in prompt
    
    def test_build_creditreform_prompt_none_focus_areas(self, filter_instance):
        """Test Creditreform prompt with None focus_areas."""
        topic_config = {
            'description': 'Test description',
            'focus_areas': None
        }
        
        prompt = filter_instance.build_creditreform_system_prompt(topic_config)
        
        # Should handle None focus_areas gracefully
        assert 'Test description' in prompt
        assert 'KEY FOCUS AREAS' in prompt
    
    def test_prompt_fragments_are_cached(self, filter_instance):
        """Test that fragments are cached for performance."""
        # Call get_fragment multiple times for same fragment
        frag1 = filter_instance.prompt_lib.get_fragment('filter', 'classifier_intro')
        frag2 = filter_instance.prompt_lib.get_fragment('filter', 'classifier_intro')
        
        # Should return the same cached instance
        assert frag1 is frag2
    
    def test_composed_prompts_are_strings(self, filter_instance):
        """Test that all composed prompts are strings."""
        # Classification prompt
        class_prompt = filter_instance._build_classification_prompt(
            'test', ['kw1']
        )
        assert isinstance(class_prompt, str)
        assert len(class_prompt) > 0
        
        # Creditreform prompt
        cr_prompt = filter_instance.build_creditreform_system_prompt({
            'description': 'test',
            'focus_areas': {}
        })
        assert isinstance(cr_prompt, str)
        assert len(cr_prompt) > 0
    
    def test_focus_areas_formatting_maintains_order(self, filter_instance):
        """Test that focus areas maintain predictable formatting."""
        focus_areas = {
            'area1': {'keywords': ['k1'], 'priority': 'high'},
            'area2': {'keywords': ['k2'], 'priority': 'low'}
        }
        
        result = filter_instance._format_focus_areas(focus_areas)
        
        # Should include both areas
        assert 'area1' in result
        assert 'area2' in result
        # Each on its own line
        assert '\n' in result


class TestFragmentIntegration:
    """Test integration of fragments with actual classification."""
    
    @pytest.fixture
    def prompt_lib(self):
        """Create PromptLibrary instance."""
        lang_config = LanguageConfig()
        return PromptLibrary(lang_config)
    
    def test_all_required_filter_fragments_exist(self, prompt_lib):
        """Test that all required filter fragments are defined."""
        required_fragments = [
            'classifier_intro',
            'classification_task',
            'classification_criteria',
            'classification_output',
            'creditreform_analyst_role',
            'creditreform_context_template',
            'focus_areas_header',
            'relevance_scale',
            'creditreform_output'
        ]
        
        for fragment_name in required_fragments:
            fragment = prompt_lib.get_fragment('filter', fragment_name)
            assert fragment is not None, f"Fragment 'filter.{fragment_name}' not found"
            assert len(fragment) > 0, f"Fragment 'filter.{fragment_name}' is empty"
    
    def test_classification_task_has_placeholders(self, prompt_lib):
        """Test that classification_task fragment has placeholders."""
        fragment = prompt_lib.get_fragment('filter', 'classification_task')
        
        # Should have {topic} and {keywords} placeholders
        assert '{topic}' in fragment
        assert '{keywords}' in fragment
    
    def test_creditreform_context_has_placeholder(self, prompt_lib):
        """Test that creditreform_context has {description} placeholder."""
        fragment = prompt_lib.get_fragment('filter', 'creditreform_context_template')
        
        # Should have {description} placeholder
        assert '{description}' in fragment
    
    def test_fragments_are_non_empty_strings(self, prompt_lib):
        """Test that all fragments are non-empty strings."""
        fragment_names = [
            'classifier_intro',
            'classification_criteria',
            'classification_output',
            'creditreform_analyst_role',
            'focus_areas_header',
            'relevance_scale',
            'creditreform_output'
        ]
        
        for name in fragment_names:
            fragment = prompt_lib.get_fragment('filter', name)
            assert isinstance(fragment, str)
            assert len(fragment.strip()) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
