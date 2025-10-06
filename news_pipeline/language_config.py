"""
Language Configuration System for News Analysis Pipeline

Provides centralized language support for all AI-generated content,
ensuring consistent language selection across all pipeline components.

Note: Prompt management has been migrated to PromptLibrary (news_pipeline.prompt_library).
This module now focuses solely on language selection and configuration.
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


class LanguageConfig:
    """
    Centralized language configuration for the news analysis pipeline.
    
    Manages language selection (German/English) for the pipeline.
    Prompts are now handled by PromptLibrary which uses this configuration.
    """
    
    def __init__(self, language: str | None = None):
        """
        Initialize language configuration.
        
        Args:
            language: Language code ('de' for German, 'en' for English).
                     If None, reads from PIPELINE_LANGUAGE environment variable.
        """
        if language is None:
            language = os.getenv("PIPELINE_LANGUAGE", "en")
        
        self.language = language.lower()
        if self.language not in ['de', 'en']:
            raise ValueError(f"Unsupported language: {language}. Supported: 'de', 'en'")
    
    def is_german(self) -> bool:
        """Check if current language is German."""
        return self.language == 'de'
    
    def is_english(self) -> bool:
        """Check if current language is English."""
        return self.language == 'en'
    
    def get_language_code(self) -> str:
        """Get the current language code."""
        return self.language
    
    def get_language_name(self) -> str:
        """Get the current language name."""
        return "Deutsch" if self.language == 'de' else "English"
    
    def get_output_format_instructions(self) -> Dict[str, str]:
        """Get output format instructions in the configured language."""
        if self.language == 'de':
            return {
                "json_instruction": "Antworten Sie mit einem gültigen JSON-Objekt im angegebenen Schema.",
                "markdown_instruction": "Formatieren Sie die Ausgabe als gut strukturiertes Markdown.",
                "bullet_format": "Verwenden Sie Aufzählungszeichen (•) für Listen.",
                "emphasis": "Verwenden Sie **Fettschrift** für wichtige Begriffe."
            }
        else:
            return {
                "json_instruction": "Respond with a valid JSON object following the specified schema.",
                "markdown_instruction": "Format the output as well-structured Markdown.",
                "bullet_format": "Use bullet points (•) for lists.",
                "emphasis": "Use **bold** for important terms."
            }


# Global instance for easy access
_global_language_config = None

def get_language_config() -> LanguageConfig:
    """Get the global language configuration instance."""
    global _global_language_config
    if _global_language_config is None:
        _global_language_config = LanguageConfig()
    return _global_language_config

def set_language(language: str) -> None:
    """Set the global language configuration."""
    global _global_language_config
    _global_language_config = LanguageConfig(language)

def is_german_mode() -> bool:
    """Check if the pipeline is configured for German output."""
    return get_language_config().is_german()
