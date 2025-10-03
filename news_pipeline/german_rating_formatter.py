"""
German Rating Agency Formatter - Specialized Markdown Generator

Creates German-language creditworthiness analysis reports from daily digest JSON files
using sequential thinking to provide rating agency perspective on market developments.
"""

import os
import sqlite3
from urllib.parse import urlparse
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

from .paths import template_path, resource_path

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
                self.model = os.getenv("MODEL_ANALYSIS", "gpt-5")
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

    # --- NEW: helpers -------------------------------------------------------
    def _resolve_source_metadata(self, source_urls: list[str]) -> list[dict]:
        """
        Map each URL to {'url': str, 'title': Optional[str], 'summary': Optional[str], 'key_points': Optional[list]} 
        using the SQLite DB (items and summaries tables).
        Generates key points from summary using GPT if available.
        Falls back to None title/summary if not resolvable.
        """
        results: list[dict] = []
        if not source_urls:
            return results

        db_path = os.getenv("DB_PATH", "news.db")
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            for url in source_urls:
                # Try to resolve by exact url or normalized_url; prefer newest hit
                cur.execute(
                    """
                    SELECT i.id, i.title, i.url
                    FROM items i
                    WHERE i.url = ? OR i.normalized_url = ?
                    ORDER BY i.id DESC
                    LIMIT 1
                    """,
                    (url, url),
                )
                row = cur.fetchone()
                if row:
                    title = row["title"].strip() if row["title"] else None
                    item_id = row["id"]
                    
                    # Get the summary for this item
                    cur.execute(
                        """
                        SELECT summary
                        FROM summaries
                        WHERE item_id = ?
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (item_id,),
                    )
                    summary_row = cur.fetchone()
                    summary = summary_row["summary"] if summary_row and summary_row["summary"] else None
                    
                    # Generate key points from summary
                    key_points = self._generate_article_key_points(summary) if summary else None
                    
                    if key_points:
                        self.logger.info(f"Generated {len(key_points)} key points for article: {title[:50] if title else url[:50]}")
                    else:
                        self.logger.warning(f"No key points generated for article: {title[:50] if title else url[:50]}")
                    
                    results.append({"url": url, "title": title, "summary": summary, "key_points": key_points})
                else:
                    results.append({"url": url, "title": None, "summary": None, "key_points": None})
        except Exception as e:
            self.logger.warning(f"Could not resolve titles/summaries from DB: {e}")
            results = [{"url": u, "title": None, "summary": None, "key_points": None} for u in source_urls]
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return results
    
    def _generate_article_key_points(self, summary: str) -> Optional[list[str]]:
        """
        Generate exactly 3 concise key bullet points from an article summary using GPT-5.
        
        Args:
            summary: Article summary text
            
        Returns:
            List of exactly 3 key points or None if generation fails
        """
        if not self.client or not summary:
            return None
        
        try:
            instructions = """Extract exactly 3 concise, easy-to-read bullet points from the article summary.

Requirements:
- Each point must be clear, direct, and understandable
- Use simple, concrete language - avoid jargon where possible
- Keep each point to 1-2 short sentences maximum
- Focus on the most important facts or implications
- Make it scannable and easy on the eyes

Return only the 3 bullet points, one per line, starting with a dash (-)."""

            response = self.client.responses.create(
                model=os.getenv("MODEL_ANALYSIS", "gpt-5"),
                instructions=instructions,
                input=[{"role": "user", "content": f"Article summary:\n{summary}"}],
                max_output_tokens=1000,
                reasoning={"effort": "low"}
            )
            
            content = (response.output_text or "").strip()
            if not content:
                self.logger.warning("GPT returned empty output_text for key points")
                return None
            
            self.logger.debug(f"GPT response for key points: {content[:200]}")
            
            # Parse bullet points from response
            lines = content.split('\n')
            key_points = []
            for line in lines:
                line = line.strip()
                # Skip empty lines
                if not line:
                    continue
                # Remove bullet markers if present
                if line.startswith('- ') or line.startswith('* '):
                    line = line[2:]
                elif line.startswith('• '):
                    line = line[2:]
                # Remove numbering if present
                import re
                line = re.sub(r'^\d+\.\s*', '', line)
                
                if line:
                    key_points.append(line)
            
            if not key_points:
                self.logger.warning(f"Could not parse any key points from GPT response: {content[:100]}")
            
            return key_points if key_points else None
            
        except Exception as e:
            self.logger.warning(f"Failed to generate key points: {e}")
            return None

    def _fetch_fulltext_by_url(self, url: str) -> Optional[str]:
        """
        Find the full extracted_text for an article URL via items -> articles.
        Returns None if not found or on error.
        """
        db_path = os.getenv("DB_PATH", "news.db")
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # Find the item id by url/normalized_url
            cur.execute(
                """
                SELECT id FROM items
                WHERE url = ? OR normalized_url = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (url, url),
            )
            row = cur.fetchone()
            if not row:
                return None
            item_id = row["id"]
            # Fetch the most recent extracted_text for that item
            cur.execute(
                """
                SELECT extracted_text
                FROM articles
                WHERE item_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (item_id,),
            )
            arow = cur.fetchone()
            return arow["extracted_text"] if arow and arow["extracted_text"] else None
        except Exception as e:
            self.logger.warning(f"Could not fetch full text for URL: {e}")
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass
    
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
- immediate_actions: Sofortige Handlungsempfehlungen für das Rating-Team

Bitte geben Sie die Ausgabe als JSON-Objekt zurück."""

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
                response_format={"type": "json_object"},
                max_completion_tokens=2000
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
        Write the German markdown report to file using a Jinja2 template.
        
        Args:
            output_path: Output file path
            digest_data: Original digest data
            analysis: Generated analysis
        """
        # Set up Jinja2 environment - use proper path resolution
        templates_dir = str(template_path())
        env = Environment(loader=FileSystemLoader(templates_dir))

        # Define custom filters
        def datetime_format(value, format='%Y-%m-%d %H:%M:%S'):
            try:
                return datetime.fromisoformat(value).strftime(format)
            except (ValueError, TypeError):
                return value

        def topic_name(value):
            return value.replace('_', ' ').title()

        def domain_name(value):
            try:
                return urlparse(value).netloc
            except:
                return value

        # Register custom filters
        env.filters['datetime_format'] = datetime_format
        env.filters['topic_name'] = topic_name
        env.filters['domain_name'] = domain_name

        template = env.get_template('daily_digest.md.j2')

        # Resolve source metadata
        for topic_name, topic_data in digest_data.get('topic_digests', {}).items():
            sources = topic_data.get('sources') or []
            if sources:
                seen = set()
                deduped = [u for u in sources if not (u in seen or seen.add(u))]
                meta = self._resolve_source_metadata(deduped)
                topic_data['sources_meta'] = meta

        # Combine data for the template
        context = {
            'data': digest_data,
            'analysis': analysis,
            'max_sources': int(os.getenv("GERMAN_REPORT_MAX_SOURCES", "20"))
        }
        
        # Render the template
        output = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output)


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
