"""
German Rating Agency Formatter - Specialized Markdown Generator

Creates German-language creditworthiness analysis reports from daily digest JSON files
using sequential thinking to provide rating agency perspective on market developments.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import MCP client functionality
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class GermanRatingFormatter:
    """
    Specialized formatter for creating German creditworthiness analysis from daily digests.
    Uses sequential thinking to provide rating agency perspective.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize OpenAI client for sequential thinking if available
        if OpenAI:
            try:
                self.client = OpenAI()
                self.model = os.getenv("MODEL_ANALYSIS", "gpt-4o")
            except Exception as e:
                self.logger.warning(f"OpenAI client initialization failed: {e}")
                self.client = None
        else:
            self.client = None
            self.logger.warning("OpenAI not available - sequential thinking disabled")
    
    def format_to_german_markdown(self, digest_json_path: str, output_dir: str = "rating_reports") -> str:
        """
        Convert daily digest JSON to German rating agency markdown report.
        
        Args:
            digest_json_path: Path to daily digest JSON file
            output_dir: Output directory for markdown files
            
        Returns:
            Path to generated markdown file
        """
        try:
            # Load digest data
            with open(digest_json_path, 'r', encoding='utf-8') as f:
                digest_data = json.load(f)
            
            # Check if there are any meaningful articles to process
            topic_digests = digest_data.get('topic_digests', {})
            total_article_count = sum(digest.get('article_count', 0) for digest in topic_digests.values())
            
            if total_article_count == 0:
                self.logger.info("No articles found in digest - skipping German rating report generation")
                
                # Return a placeholder path to maintain API compatibility
                report_date = digest_data.get('date', datetime.now().strftime('%Y-%m-%d'))
                output_filename = f"bonitaets_tagesanalyse_{report_date}.md"
                output_path = os.path.join(output_dir, output_filename)
                return output_path
            
            # Extract date from data
            report_date = digest_data.get('date', datetime.now().strftime('%Y-%m-%d'))
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate output filename
            output_filename = f"bonitaets_tagesanalyse_{report_date}.md"
            output_path = os.path.join(output_dir, output_filename)
            
            # Generate analysis using sequential thinking (if available)
            if self.client:
                analysis = self._generate_rating_analysis(digest_data)
            else:
                # Fallback analysis without AI
                analysis = self._generate_basic_analysis(digest_data)
            
            # Write markdown report
            self._write_german_markdown_report(output_path, digest_data, analysis)
            
            self.logger.info(f"Generated German rating report: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Error generating German rating report: {e}")
            raise
    
    def _generate_rating_analysis(self, digest_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate rating agency analysis using AI sequential thinking.
        
        Args:
            digest_data: Daily digest JSON data
            
        Returns:
            Analysis results
        """
        try:
            # Check if client is available
            if not self.client:
                return self._generate_basic_analysis(digest_data)
            
            system_prompt = """Du bist ein Senior-Produktmanager bei einer Schweizer Rating-Agentur, die sich auf die Bewertung der Bonität (Kreditwürdigkeit) von Unternehmen und Personen spezialisiert hat.

Analysiere die bereitgestellten Nachrichten aus Sicht der Kreditwürdigkeit und des Kreditrisikos. Fokussiere auf:

1. Makroökonomische Faktoren, die Kreditrisiken beeinflussen
2. Regulatorische Änderungen mit Auswirkungen auf Finanzinstitute
3. Sektorale Risiken und Chancen
4. Operative Risiken (Cyber, Compliance, Governance)
5. Liquiditäts- und Kapitalmarktentwicklungen

Erstelle eine professionelle Analyse in deutscher Sprache mit folgender Struktur:
- executive_summary: Kurze Zusammenfassung der wichtigsten Kreditrisiko-Implikationen
- risk_assessment: Detaillierte Risikoanalyse nach Kategorien
- sector_implications: Auswirkungen auf verschiedene Sektoren
- rating_methodology_updates: Empfehlungen für Rating-Methodik-Anpassungen
- immediate_actions: Sofortige Handlungsempfehlungen für das Rating-Team"""

            # Prepare digest data for analysis
            analysis_input = {
                "date": digest_data.get('date'),
                "executive_summary": digest_data.get('executive_summary', {}),
                "trending_topics": digest_data.get('trending_topics', []),
                "topic_digests": digest_data.get('topic_digests', {})
            }
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(analysis_input, ensure_ascii=False)}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            analysis_text = response.choices[0].message.content
            
            # Parse the analysis (simplified - in practice you'd want structured JSON)
            return {
                "analysis_text": analysis_text,
                "generated_at": datetime.now().isoformat(),
                "method": "ai_sequential_thinking"
            }
            
        except Exception as e:
            self.logger.error(f"Error in AI analysis: {e}")
            return self._generate_basic_analysis(digest_data)
    
    def _generate_basic_analysis(self, digest_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate basic analysis without AI as fallback.
        
        Args:
            digest_data: Daily digest JSON data
            
        Returns:
            Basic analysis results
        """
        exec_summary = digest_data.get('executive_summary', {})
        
        analysis_text = f"""
## Executive Summary
{exec_summary.get('headline', 'Keine Hauptschlagzeile verfügbar')}

{exec_summary.get('executive_summary', 'Keine detaillierte Zusammenfassung verfügbar.')}

## Schlüsselthemen
"""
        
        for theme in exec_summary.get('key_themes', []):
            analysis_text += f"- {theme}\n"
        
        analysis_text += "\n## Handlungsprioritäten\n"
        
        for priority in exec_summary.get('top_priorities', []):
            analysis_text += f"- {priority}\n"
        
        return {
            "analysis_text": analysis_text,
            "generated_at": datetime.now().isoformat(),
            "method": "basic_fallback"
        }
    
    def _write_german_markdown_report(self, output_path: str, digest_data: Dict[str, Any], 
                                    analysis: Dict[str, Any]):
        """
        Write the German markdown report to file.
        
        Args:
            output_path: Output file path
            digest_data: Original digest data
            analysis: Generated analysis
        """
        report_date = digest_data.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Bonität-Tagesanalyse: Schweizer Markt\n")
            f.write(f"**Datum:** {report_date}\n")
            f.write(f"**Erstellt von:** Produktmanagement Rating-Agentur\n")
            f.write(f"**Basierend auf:** Daily Digest {report_date}\n\n")
            f.write("---\n\n")
            
            # Main analysis content
            f.write(analysis.get('analysis_text', ''))
            
            # Add trending topics section
            trending_topics = digest_data.get('trending_topics', [])
            if trending_topics:
                f.write(f"\n## Trending-Themen (Top {min(5, len(trending_topics))})\n\n")
                for i, topic in enumerate(trending_topics[:5], 1):
                    f.write(f"{i}. **{topic.get('topic', 'Unbekannt')}** "
                           f"({topic.get('article_count', 0)} Artikel, "
                           f"Konfidenz: {topic.get('avg_confidence', 0):.2f})\n")
                f.write("\n")
            
            # Add detailed topic analysis
            topic_digests = digest_data.get('topic_digests', {})
            if topic_digests:
                f.write("## Detaillierte Themenanalyse\n\n")
                
                for topic_name, topic_data in topic_digests.items():
                    if topic_data.get('article_count', 0) > 0:
                        f.write(f"### {topic_name.replace('_', ' ').title()}\n\n")
                        f.write(f"**{topic_data.get('headline', 'Keine Schlagzeile verfügbar')}**\n\n")
                        f.write(f"{topic_data.get('why_it_matters', 'Keine Details verfügbar.')}\n\n")
                        
                        bullets = topic_data.get('bullets', [])
                        if bullets:
                            f.write("**Hauptpunkte:**\n\n")
                            for bullet in bullets:
                                f.write(f"- {bullet}\n")
                            f.write("\n")
                        
                        f.write(f"*Basierend auf {topic_data.get('article_count', 0)} Artikeln*\n\n")
            
            # Footer
            f.write("---\n\n")
            f.write(f"**Bericht generiert:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Methode:** {analysis.get('method', 'unbekannt')}\n")
            f.write(f"**Gesamtartikel:** {digest_data.get('executive_summary', {}).get('total_articles', 'unbekannt')}\n")


def format_daily_digest_to_german_markdown(digest_json_path: str, output_dir: str = "rating_reports") -> str:
    """
    Convenience function to format a daily digest JSON to German markdown.
    
    Args:
        digest_json_path: Path to daily digest JSON file
        output_dir: Output directory for markdown files
        
    Returns:
        Path to generated markdown file
    """
    formatter = GermanRatingFormatter()
    return formatter.format_to_german_markdown(digest_json_path, output_dir)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate German rating agency markdown from daily digest")
    parser.add_argument("digest_path", help="Path to daily digest JSON file")
    parser.add_argument("--output-dir", default="rating_reports", 
                       help="Output directory (default: rating_reports)")
    
    args = parser.parse_args()
    
    try:
        output_path = format_daily_digest_to_german_markdown(args.digest_path, args.output_dir)
        print(f"Generated German rating report: {output_path}")
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
