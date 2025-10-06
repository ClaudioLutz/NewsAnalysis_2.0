"""
PromptLibrary - Centralized System Prompt Management for News Analysis Pipeline

Provides organized access to all GPT system prompts used throughout the pipeline,
organized by pipeline stage for intuitive discovery and maintenance.

Architecture:
- Main PromptLibrary class handles YAML loading and caching
- Pipeline stage subclasses (FilteringPrompts, DeduplicationPrompts, etc.) provide
  stage-specific prompt access methods
- Language integration via LanguageConfig dependency injection
- Simple Python string template format for parameter substitution

Usage:
    from news_pipeline.prompt_library import PromptLibrary
    from news_pipeline.language_config import LanguageConfig
    
    # Initialize with language configuration
    lang_config = LanguageConfig("de")
    prompt_lib = PromptLibrary(lang_config)
    
    # Access prompts via pipeline stage methods
    classification = prompt_lib.filtering.classification_prompt(topic="creditreform")
    clustering = prompt_lib.deduplication.clustering_prompt()
    rating = prompt_lib.formatting.rating_prompt()
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from news_pipeline.language_config import LanguageConfig

# Set up logger for this module
logger = logging.getLogger(__name__)


class PromptLibrary:
    """
    Central repository for GPT system prompts organized by pipeline stage.
    
    Manages YAML-based prompt configurations with caching for performance.
    Provides access to prompts through pipeline-stage-specific subclasses.
    
    Attributes:
        filtering: Prompts for the filtering pipeline stage
        deduplication: Prompts for the deduplication pipeline stage
        analysis: Prompts for the analysis pipeline stage
        formatting: Prompts for the formatting pipeline stage
        digest: Prompts for the digest generation pipeline stage
    
    Example:
        >>> from news_pipeline.language_config import LanguageConfig
        >>> lang_config = LanguageConfig("de")
        >>> prompt_lib = PromptLibrary(lang_config)
        >>> prompt = prompt_lib.filtering.classification_prompt(topic="creditreform")
    """
    
    def __init__(self, language_config: 'LanguageConfig') -> None:
        """
        Initialize PromptLibrary with language configuration.
        
        Args:
            language_config: LanguageConfig instance for language-aware prompt retrieval
        """
        self._language_config = language_config
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._prompts_dir = Path("config/prompts")
        
        # Initialize pipeline stage subclasses
        self.filtering = FilteringPrompts(self, language_config)
        self.deduplication = DeduplicationPrompts(self, language_config)
        self.analysis = AnalysisPrompts(self, language_config)
        self.formatting = FormattingPrompts(self, language_config)
        self.digest = DigestPrompts(self, language_config)
        
        logger.info(f"PromptLibrary initialized with language: {language_config.get_language_name()}")
    
    def get_fragment(self, category: str, fragment_name: str) -> str:
        """
        Get reusable prompt fragment for hybrid prompt composition.
        
        Fragments are stored in config/prompts/fragments.yaml and organized by category.
        Use this method to retrieve static prompt components that can be combined
        with dynamic content using Python's .format() method.
        
        Args:
            category: Fragment category (e.g., 'common', 'filter', 'analysis')
            fragment_name: Specific fragment name within the category
            
        Returns:
            Fragment text ready for composition
            
        Raises:
            KeyError: If category or fragment not found
            
        Example:
            >>> header = prompt_lib.get_fragment('common', 'analyst_role')
            >>> focus = prompt_lib.get_fragment('common', 'swiss_analysis_focus')
            >>> prompt = f"{header}\n\n{focus}\n\nArticle: {article_text}"
        """
        # Lazy load fragments on first use
        if not hasattr(self, '_fragments'):
            fragments_path = self._prompts_dir / "fragments.yaml"
            
            if not fragments_path.exists():
                raise FileNotFoundError(
                    f"Fragments file not found: {fragments_path}. "
                    f"Please ensure config/prompts/fragments.yaml exists."
                )
            
            try:
                with open(fragments_path, 'r', encoding='utf-8') as f:
                    self._fragments = yaml.safe_load(f) or {}
                    logger.debug(f"Loaded {len(self._fragments)} fragment categories")
            except yaml.YAMLError as e:
                logger.error(f"Error parsing fragments YAML: {e}")
                raise
            except Exception as e:
                logger.error(f"Error loading fragments file: {e}")
                raise
        
        # Validate category exists
        if category not in self._fragments:
            available = ', '.join(self._fragments.keys())
            raise KeyError(
                f"Fragment category '{category}' not found. "
                f"Available categories: {available}"
            )
        
        # Validate fragment exists in category
        if fragment_name not in self._fragments[category]:
            available = ', '.join(self._fragments[category].keys())
            raise KeyError(
                f"Fragment '{fragment_name}' not found in category '{category}'. "
                f"Available fragments: {available}"
            )
        
        return self._fragments[category][fragment_name]
    
    def get_prompt(self, stage: str, prompt_name: str) -> str:
        """
        Retrieve a prompt template from YAML configuration.
        
        Args:
            stage: Pipeline stage name (e.g., 'filtering', 'deduplication')
            prompt_name: Name of the prompt to retrieve
            
        Returns:
            Prompt template string with {parameter} placeholders
            
        Raises:
            KeyError: If prompt_name not found in stage configuration
            FileNotFoundError: If stage YAML file doesn't exist
            
        Example:
            >>> template = prompt_lib.get_prompt("filtering", "classification_prompt")
            >>> prompt = template.format(topic="creditreform")
        """
        stage_prompts = self._load_stage_prompts(stage)
        
        if prompt_name not in stage_prompts:
            available = ", ".join(stage_prompts.keys())
            raise KeyError(
                f"Prompt '{prompt_name}' not found in {stage}.yaml. "
                f"Available prompts: {available}"
            )
        
        prompt_config = stage_prompts[prompt_name]
        
        # Handle both simple string templates and dictionary configs
        if isinstance(prompt_config, dict):
            return prompt_config.get("template", "")
        return prompt_config
    
    def _load_stage_prompts(self, stage: str) -> Dict[str, Any]:
        """
        Load and cache prompts for a pipeline stage.
        
        Implements caching to avoid repeated file reads. YAML files are only
        loaded once per stage during the lifetime of the PromptLibrary instance.
        
        Args:
            stage: Pipeline stage name (e.g., 'filtering', 'deduplication')
            
        Returns:
            Dictionary of prompt configurations for the stage
            
        Raises:
            FileNotFoundError: If YAML file for stage doesn't exist
        """
        if stage not in self._cache:
            filepath = self._prompts_dir / f"{stage}.yaml"
            
            if not filepath.exists():
                logger.error(f"Prompt configuration file not found: {filepath}")
                raise FileNotFoundError(
                    f"Prompt file not found: {filepath}. "
                    f"Please ensure config/prompts/{stage}.yaml exists."
                )
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    self._cache[stage] = yaml.safe_load(f) or {}
                    logger.debug(f"Loaded {len(self._cache[stage])} prompts from {stage}.yaml")
            except yaml.YAMLError as e:
                logger.error(f"Error parsing YAML file {filepath}: {e}")
                raise
            except Exception as e:
                logger.error(f"Error loading prompt file {filepath}: {e}")
                raise
        
        return self._cache[stage]
    
    def get_prompt_metadata(self, stage: str, prompt_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a prompt (description, parameters, examples, cost estimates).
        
        Args:
            stage: Pipeline stage name
            prompt_name: Name of the prompt
            
        Returns:
            Dictionary with prompt metadata or None if not found
            
        Example:
            >>> metadata = prompt_lib.get_prompt_metadata("filtering", "classification_prompt")
            >>> print(metadata["description"])
            >>> print(metadata["parameters"])
        """
        stage_prompts = self._load_stage_prompts(stage)
        
        if prompt_name not in stage_prompts:
            return None
        
        prompt_config = stage_prompts[prompt_name]
        
        if isinstance(prompt_config, dict):
            return {
                "description": prompt_config.get("description", ""),
                "purpose": prompt_config.get("purpose", ""),
                "parameters": prompt_config.get("parameters", []),
                "cost_estimate": prompt_config.get("cost_estimate", "Unknown"),
                "example_usage": prompt_config.get("example_usage", "")
            }
        
        return None
    
    def clear_cache(self) -> None:
        """Clear the prompt cache. Useful for testing or reloading configurations."""
        self._cache.clear()
        logger.debug("Prompt cache cleared")


class FilteringPrompts:
    """
    Prompts for the filtering pipeline stage.
    
    Provides access to prompts used in filter.py for initial article classification
    and relevance filtering based on topic criteria.
    """
    
    def __init__(self, library: PromptLibrary, language_config: 'LanguageConfig') -> None:
        """
        Initialize FilteringPrompts.
        
        Args:
            library: Parent PromptLibrary instance
            language_config: LanguageConfig for language-aware prompts
        """
        self._library = library
        self._language_config = language_config
    
    def classification_prompt(self, topic: str) -> str:
        """
        Get the article classification prompt for topic-based filtering.
        
        Args:
            topic: Topic to filter articles by (e.g., 'creditreform', 'business')
            
        Returns:
            Formatted prompt ready for GPT API
            
        Example:
            >>> prompt = prompt_lib.filtering.classification_prompt(topic="creditreform")
        """
        template = self._library.get_prompt("filtering", "classification_prompt")
        return template.format(topic=topic)


class DeduplicationPrompts:
    """
    Prompts for the deduplication pipeline stage.
    
    Provides access to prompts used in gpt_deduplication.py and 
    cross_run_deduplication.py for identifying duplicate or similar articles.
    """
    
    def __init__(self, library: PromptLibrary, language_config: 'LanguageConfig') -> None:
        """
        Initialize DeduplicationPrompts.
        
        Args:
            library: Parent PromptLibrary instance
            language_config: LanguageConfig for language-aware prompts
        """
        self._library = library
        self._language_config = language_config
    
    def clustering_prompt(self) -> str:
        """
        Get the clustering prompt for grouping similar articles.
        
        Returns:
            Formatted prompt ready for GPT API
            
        Example:
            >>> prompt = prompt_lib.deduplication.clustering_prompt()
        """
        template = self._library.get_prompt("deduplication", "clustering_prompt")
        return template


class AnalysisPrompts:
    """
    Prompts for the analysis pipeline stage.
    
    Provides access to prompts used in analyzer.py for article summarization,
    key point extraction, and entity recognition.
    """
    
    def __init__(self, library: PromptLibrary, language_config: 'LanguageConfig') -> None:
        """
        Initialize AnalysisPrompts.
        
        Args:
            library: Parent PromptLibrary instance
            language_config: LanguageConfig for language-aware prompts
        """
        self._library = library
        self._language_config = language_config
    
    def summarization_prompt(self) -> str:
        """
        Get the article summarization prompt.
        
        Returns:
            Formatted prompt ready for GPT API
            
        Example:
            >>> prompt = prompt_lib.analysis.summarization_prompt()
        """
        template = self._library.get_prompt("analysis", "summarization_prompt")
        return template
    
    def key_points_prompt(self) -> str:
        """
        Get the key points extraction prompt.
        
        Returns:
            Formatted prompt ready for GPT API
            
        Example:
            >>> prompt = prompt_lib.analysis.key_points_prompt()
        """
        template = self._library.get_prompt("analysis", "key_points_prompt")
        return template
    
    def entity_extraction_prompt(self) -> str:
        """
        Get the entity extraction prompt for identifying companies, people, locations.
        
        Returns:
            Formatted prompt ready for GPT API
            
        Example:
            >>> prompt = prompt_lib.analysis.entity_extraction_prompt()
        """
        template = self._library.get_prompt("analysis", "entity_extraction_prompt")
        return template


class FormattingPrompts:
    """
    Prompts for the formatting pipeline stage.
    
    Provides access to prompts used in german_rating_formatter.py for
    generating formatted rating agency reports and analyses.
    """
    
    def __init__(self, library: PromptLibrary, language_config: 'LanguageConfig') -> None:
        """
        Initialize FormattingPrompts.
        
        Args:
            library: Parent PromptLibrary instance
            language_config: LanguageConfig for language-aware prompts
        """
        self._library = library
        self._language_config = language_config
    
    def rating_prompt(self) -> str:
        """
        Get the German rating agency analysis prompt.
        
        Note: This prompt is always in German for rating agency reports,
        regardless of the configured language.
        
        Returns:
            Formatted prompt ready for GPT API
            
        Example:
            >>> prompt = prompt_lib.formatting.rating_prompt()
        """
        template = self._library.get_prompt("formatting", "rating_prompt")
        return template


class DigestPrompts:
    """
    Prompts for the digest generation pipeline stage.
    
    Provides access to prompts used in incremental_digest.py and summarizer.py
    for creating topic digests and merging updates.
    """
    
    def __init__(self, library: PromptLibrary, language_config: 'LanguageConfig') -> None:
        """
        Initialize DigestPrompts.
        
        Args:
            library: Parent PromptLibrary instance
            language_config: LanguageConfig for language-aware prompts
        """
        self._library = library
        self._language_config = language_config
    
    def partial_digest_prompt(self, topic: str) -> str:
        """
        Get the partial digest generation prompt for new articles.
        
        Args:
            topic: Topic for the digest (e.g., 'creditreform', 'business')
            
        Returns:
            Formatted prompt ready for GPT API
            
        Example:
            >>> prompt = prompt_lib.digest.partial_digest_prompt(topic="creditreform")
        """
        template = self._library.get_prompt("digest", "partial_digest_prompt")
        return template.format(topic=topic)
    
    def merge_digests_prompt(self, topic: str) -> str:
        """
        Get the digest merging prompt for combining existing and new content.
        
        Args:
            topic: Topic for the digest (e.g., 'creditreform', 'business')
            
        Returns:
            Formatted prompt ready for GPT API
            
        Example:
            >>> prompt = prompt_lib.digest.merge_digests_prompt(topic="creditreform")
        """
        template = self._library.get_prompt("digest", "merge_digests_prompt")
        return template.format(topic=topic)
    
    def topic_digest_prompt(self, topic: str) -> str:
        """
        Get the topic digest generation prompt.
        
        Args:
            topic: Topic for the digest (e.g., 'creditreform', 'business')
            
        Returns:
            Formatted prompt ready for GPT API
            
        Example:
            >>> prompt = prompt_lib.digest.topic_digest_prompt(topic="creditreform")
        """
        template = self._library.get_prompt("digest", "topic_digest_prompt")
        return template.format(topic=topic)
