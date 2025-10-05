"""
Language Configuration System for News Analysis Pipeline

Provides centralized language support for all AI-generated content,
ensuring consistent German output across all pipeline components.
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


class LanguageConfig:
    """
    Centralized language configuration for the news analysis pipeline.
    Provides language-specific prompts and configurations for all AI operations.
    """
    
    def __init__(self, language: str = None):
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
    
    def get_partial_digest_prompt(self, topic: str) -> str:
        """Get partial digest generation prompt for new articles."""
        if self.language == 'de':
            return f"""Sie sind ein Senior-Analyst für Schweizer Wirtschaftsnachrichten und erstellen fokussierte Updates.

Erstellen Sie ein fokussiertes Digest-Update nur für NEUE {topic}-Artikel.

Erstellen Sie:
- key_insights: 3-5 neue Schlüsselerkenntnisse aus diesen Artikeln
- important_developments: Wichtige neue Entwicklungen zum Hervorheben
- new_sources: URLs der analysierten neuen Artikel
- entities_mentioned: Erwähnte Schlüsselunternehmen/Organisationen

Fokussieren Sie auf das, was NEU und bedeutend ist. Dies wird mit bestehenden Analysen zusammengeführt."""
        else:
            return f"""You are a senior Swiss business analyst creating focused updates.

Generate a focused digest update for NEW {topic} articles only.

Create:
- key_insights: 3-5 new key insights from these articles
- important_developments: Major new developments to highlight  
- new_sources: URLs of the new articles analyzed
- entities_mentioned: Key entities/companies mentioned

Focus on what's NEW and significant. This will be merged with existing analysis."""
    
    def get_merge_digests_prompt(self, topic: str) -> str:
        """Get digest merging prompt for combining existing and new content."""
        if self.language == 'de':
            return f"""Sie sind ein Senior-Analyst für Schweizer Wirtschaftsnachrichten und führen Digest-Updates zusammen.

Führen Sie das bestehende {topic}-Digest mit neuen Erkenntnissen zusammen, um ein umfassendes aktualisiertes Digest zu erstellen.

Nehmen Sie das bestehende Digest und neue Erkenntnisse und erstellen Sie:
- headline: Aktualisierte überzeugende Schlagzeile mit allen Informationen
- why_it_matters: Aktualisierte Bedeutungserklärung
- sources: Kombinierte Quellen-URLs (dedupliziert)

Priorisieren Sie die wichtigsten und neuesten Erkenntnisse unter Beibehaltung des Kontexts."""
        else:
            return f"""You are a senior Swiss business analyst merging digest updates.

Merge existing {topic} digest with new insights to create comprehensive updated digest.

Take the existing digest and new insights, then create:
- headline: Updated compelling headline reflecting all information
- why_it_matters: Updated significance explanation
- sources: Combined source URLs (deduplicated)

Prioritize the most important and recent insights while maintaining context."""
    
    def get_rating_analysis_prompt(self) -> str:
        """Get German rating agency analysis prompt (always in German for rating reports)."""
        return """Sie sind ein Senior-Produktmanager bei einer Schweizer Rating-Agentur, die sich auf die Bewertung der Bonität (Kreditwürdigkeit) von Unternehmen und Personen spezialisiert hat.

Analysieren Sie die bereitgestellten Nachrichten aus Sicht der Kreditwürdigkeit und des Kreditrisikos. Fokussieren Sie auf:

1. Makroökonomische Faktoren, die Kreditrisiken beeinflussen
2. Regulatorische Änderungen mit Auswirkungen auf Finanzinstitute
3. Sektorale Risiken und Chancen
4. Operative Risiken (Cyber, Compliance, Governance)
5. Liquiditäts- und Kapitalmarktentwicklungen

Erstellen Sie eine professionelle Analyse in deutscher Sprache mit folgender Struktur:
- executive_summary: Kurze Zusammenfassung der wichtigsten Kreditrisiko-Implikationen
- risk_assessment: Detaillierte Risikoanalyse nach Kategorien
- sector_implications: Auswirkungen auf verschiedene Sektoren
- rating_methodology_updates: Empfehlungen für Rating-Methodik-Anpassungen
- immediate_actions: Sofortige Handlungsempfehlungen für das Rating-Team"""
    
    def get_topic_digest_prompt(self, topic: str) -> str:
        """Get topic digest generation prompt."""
        if self.language == 'de':
            return f"""Sie sind ein Senior-Wirtschaftsanalyst für Schweizer Unternehmensnachrichten.

Analysieren Sie die bereitgestellten {topic}-Artikel und erstellen Sie ein umfassendes Digest.

Erstellen Sie:
- headline: Überzeugende Hauptschlagzeile für diese Sammlung von Artikeln
- why_it_matters: Warum diese Entwicklungen für Schweizer Unternehmen und Stakeholder wichtig sind
- sources: Liste der analysierten Artikel-URLs

Fokussieren Sie auf Geschäftsimplikationen, Marktauswirkungen und strategische Erkenntnisse."""
        else:
            return f"""You are a senior business analyst for Swiss corporate news.

Analyze the provided {topic} articles and create a comprehensive digest.

Create:
- headline: Compelling main headline for this collection of articles
- why_it_matters: Why these developments matter for Swiss businesses and stakeholders
- sources: List of analyzed article URLs

Focus on business implications, market impact, and strategic insights."""
    
    def get_article_summary_prompt(self) -> str:
        """Get individual article summarization prompt."""
        if self.language == 'de':
            return """Sie sind ein erfahrener Wirtschaftsjournalist, der sich auf Schweizer Unternehmensnachrichten spezialisiert hat.

Erstellen Sie eine prägnante, gut strukturierte Zusammenfassung dieses Artikels.

Die Zusammenfassung sollte:
- Die wichtigsten Fakten und Entwicklungen hervorheben
- Den Geschäfts- oder Wirtschaftskontext erklären
- Mögliche Auswirkungen oder Implikationen identifizieren
- Objektiv und sachlich bleiben

Fokussieren Sie auf die Informationen, die für Geschäftsentscheider und Investoren am relevantesten sind."""
        else:
            return """You are an experienced business journalist specializing in Swiss corporate news.

Create a concise, well-structured summary of this article.

The summary should:
- Highlight key facts and developments
- Explain the business or economic context
- Identify potential impacts or implications
- Remain objective and factual

Focus on information most relevant to business decision-makers and investors."""
    
    def get_key_points_extraction_prompt(self) -> str:
        """Get key points extraction prompt."""
        if self.language == 'de':
            return """Extrahieren Sie die wichtigsten Punkte aus diesem Artikel als strukturierte Liste.

Jeder Punkt sollte:
- Eine spezifische Entwicklung oder Information darstellen
- Geschäfts- oder marktrelevant sein
- Prägnant und klar formuliert sein (1-2 Sätze)
- Auf Fakten basieren, nicht auf Spekulationen

Priorisieren Sie Informationen über Unternehmensaktivitäten, Marktveränderungen, regulatorische Entwicklungen und wirtschaftliche Indikatoren."""
        else:
            return """Extract the most important points from this article as a structured list.

Each point should:
- Represent a specific development or piece of information
- Be business or market-relevant
- Be concise and clearly stated (1-2 sentences)
- Be based on facts, not speculation

Prioritize information about corporate activities, market changes, regulatory developments, and economic indicators."""
    
    def get_entity_extraction_prompt(self) -> str:
        """Get entity extraction prompt."""
        if self.language == 'de':
            return """Identifizieren Sie die wichtigsten Entitäten (Unternehmen, Personen, Organisationen, Standorte) aus diesem Artikel.

Kategorisieren Sie sie als:
- companies: Unternehmen und Organisationen
- people: Schlüsselpersonen (Namen und Rollen)
- locations: Geografische Standorte
- financial_instruments: Aktien, Anleihen, Währungen etc.
- other: Andere relevante Entitäten

Fokussieren Sie auf Entitäten, die für Geschäfts- und Investitionsentscheidungen relevant sind."""
        else:
            return """Identify the key entities (companies, people, organizations, locations) from this article.

Categorize them as:
- companies: Companies and organizations
- people: Key individuals (names and roles)
- locations: Geographic locations
- financial_instruments: Stocks, bonds, currencies etc.
- other: Other relevant entities

Focus on entities relevant for business and investment decisions."""
    
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
