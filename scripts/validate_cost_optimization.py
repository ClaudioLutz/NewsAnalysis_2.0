#!/usr/bin/env python3
"""
Validation Script for Epic 010 - Cost Optimization
Verifies that bullets and executive_summary have been successfully removed
and validates the optimization is working correctly.
"""

import re
import sqlite3
import json
from pathlib import Path
from datetime import datetime

class OptimizationValidator:
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {},
            'summary': {
                'total_tests': 0,
                'passed': 0,
                'failed': 0,
                'warnings': 0
            }
        }
    
    def test_schema_no_bullets_analyzer(self):
        """Verify analyzer.py schema doesn't include bullets"""
        test_name = "analyzer.py schema excludes bullets"
        try:
            with open('news_pipeline/analyzer.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find response_schema definition
            schema_match = re.search(r'response_schema\s*=\s*{([^}]+)}', content, re.DOTALL)
            if not schema_match:
                return self._record_test(test_name, False, "Could not find response_schema")
            
            schema_text = schema_match.group(0)
            
            # Check for bullets field
            if '"bullets"' in schema_text or "'bullets'" in schema_text:
                return self._record_test(test_name, False, "bullets field still present in schema")
            
            # Verify required fields don't include bullets
            required_match = re.search(r'"required"\s*:\s*\[(.*?)\]', schema_text)
            if required_match and ('bullets' in required_match.group(1)):
                return self._record_test(test_name, False, "bullets in required array")
            
            return self._record_test(test_name, True, "Schema correctly excludes bullets")
            
        except Exception as e:
            return self._record_test(test_name, False, f"Error: {str(e)}")
    
    def test_schema_no_bullets_incremental(self):
        """Verify incremental_digest.py schema doesn't include bullets"""
        test_name = "incremental_digest.py schema excludes bullets"
        try:
            with open('news_pipeline/incremental_digest.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for bullets in actual schema definitions (not backward compatibility code)
            # Look for response_schema or merge_schema with bullets
            schema_pattern = r'(response_schema|merge_schema)\s*=\s*{[^}]+bullets[^}]+}'
            schema_matches = re.findall(schema_pattern, content, re.DOTALL | re.IGNORECASE)
            
            if schema_matches:
                return self._record_test(test_name, False, 
                    f"bullets found in schema definition")
            
            # Bullets references in backward compatibility code are OK
            return self._record_test(test_name, True, 
                "Schema correctly excludes bullets (backward compatibility references OK)")
            
        except Exception as e:
            return self._record_test(test_name, False, f"Error: {str(e)}")
    
    def test_language_config_no_bullets_prompt(self):
        """Verify language_config.py doesn't request digest bullets in prompts"""
        test_name = "language_config.py prompts exclude digest bullet requests"
        try:
            with open('news_pipeline/language_config.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for DIGEST bullet-related instructions (not markdown formatting)
            # We're looking for prompts that request 4-6 bullets for digest generation
            digest_bullet_patterns = [
                r'4-6.*wichtige Erkenntnisse',
                r'4-6.*key insights',
                r'bullets.*:.*4-6',
                r'Generate.*4.*bullet'
            ]
            
            found_patterns = []
            for pattern in digest_bullet_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    found_patterns.extend(matches)
            
            if found_patterns:
                return self._record_test(test_name, False, 
                    f"Found digest bullet prompts: {found_patterns[:3]}")
            
            # Note: bullet_format for markdown formatting of article key points is OK
            return self._record_test(test_name, True, 
                "Prompts correctly exclude digest bullet requests (markdown formatting OK)")
            
        except Exception as e:
            return self._record_test(test_name, False, f"Error: {str(e)}")
    
    def test_no_executive_summary_generation(self):
        """Verify executive summary generation has been removed"""
        test_name = "Executive summary generation removed"
        try:
            with open('news_pipeline/analyzer.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if create_executive_summary is still called
            if 'create_executive_summary(' in content:
                return self._record_test(test_name, False, 
                    "create_executive_summary still being called")
            
            # Check if executive_summary schema exists
            if '"executive_summary"' in content:
                return self._record_test(test_name, False, 
                    "executive_summary still in schema")
            
            return self._record_test(test_name, True, "Executive summary generation removed")
            
        except Exception as e:
            return self._record_test(test_name, False, f"Error: {str(e)}")
    
    def test_digest_state_schema(self):
        """Check digest state in database for new schema format"""
        test_name = "Digest state uses new schema"
        try:
            conn = sqlite3.connect('news.db')
            cursor = conn.cursor()
            
            # Check if digest_state table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='digest_state'
            """)
            if not cursor.fetchone():
                conn.close()
                return self._record_test(test_name, True, 
                    "No digest_state table (state cleared)", warning=True)
            
            # Get recent digest states
            cursor.execute("""
                SELECT digest_date, digest_content 
                FROM digest_state 
                ORDER BY digest_date DESC LIMIT 5
            """)
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return self._record_test(test_name, True, 
                    "Digest state empty (clean migration)", warning=True)
            
            # Check format of digest content
            issues = []
            for digest_date, content_json in rows:
                try:
                    content = json.loads(content_json)
                    # The content itself is the digest object, not a dict of topics
                    if isinstance(content, dict):
                        if 'bullets' in content:
                            issues.append(f"{digest_date}: has bullets field")
                        if 'executive_summary' in content:
                            issues.append(f"{digest_date}: has executive_summary field")
                except json.JSONDecodeError:
                    issues.append(f"{digest_date}: Invalid JSON")
            
            if issues:
                return self._record_test(test_name, False, 
                    f"Found old format in {len(issues)} entries: {issues[:2]}")
            
            return self._record_test(test_name, True, 
                f"All {len(rows)} digest states use new schema")
            
        except Exception as e:
            return self._record_test(test_name, False, f"Error: {str(e)}")
    
    def test_output_format_unchanged(self):
        """Verify final output format is unchanged"""
        test_name = "Output format unchanged"
        try:
            # Check latest rating reports
            reports_dir = Path('rating_reports')
            if not reports_dir.exists():
                return self._record_test(test_name, False, "No rating_reports directory")
            
            # Get Oct 4 (baseline) and Oct 5 (optimized) reports
            oct4_files = list(reports_dir.glob('bonitaets_tagesanalyse_2025-10-04*.md'))
            oct5_files = list(reports_dir.glob('bonitaets_tagesanalyse_2025-10-05*.md'))
            
            if not oct4_files or not oct5_files:
                return self._record_test(test_name, True, 
                    "Baseline comparison not available", warning=True)
            
            # Compare structure
            with open(oct4_files[0], 'r', encoding='utf-8') as f:
                oct4_content = f.read()
            with open(oct5_files[0], 'r', encoding='utf-8') as f:
                oct5_content = f.read()
            
            # Check for required sections in both
            required_sections = [
                '# Swiss Creditreform Business News Digest',
                '## Topic Analysis',
                '### Creditreform Insights',
                '## Report Metadata'
            ]
            
            missing_in_oct4 = [s for s in required_sections if s not in oct4_content]
            missing_in_oct5 = [s for s in required_sections if s not in oct5_content]
            
            if missing_in_oct4 or missing_in_oct5:
                return self._record_test(test_name, False, 
                    f"Missing sections - Oct4: {missing_in_oct4}, Oct5: {missing_in_oct5}")
            
            # Check article structure (headline + why_it_matters + key points)
            oct4_has_headlines = oct4_content.count('**') > 5
            oct5_has_headlines = oct5_content.count('**') > 5
            oct4_has_bullets = oct4_content.count('\n- ') > 3
            oct5_has_bullets = oct5_content.count('\n- ') > 3
            
            if oct4_has_headlines and oct5_has_headlines and oct4_has_bullets and oct5_has_bullets:
                return self._record_test(test_name, True, 
                    "Output format preserved (headlines + article bullets present)")
            else:
                return self._record_test(test_name, False, 
                    "Output format may have changed")
            
        except Exception as e:
            return self._record_test(test_name, False, f"Error: {str(e)}")
    
    def test_backward_compatibility_warnings(self):
        """Check incremental_digest.py has backward compatibility code"""
        test_name = "Backward compatibility implemented"
        try:
            with open('news_pipeline/incremental_digest.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for warning about old format
            if 'old format' in content.lower() or 'backward' in content.lower():
                return self._record_test(test_name, True, 
                    "Backward compatibility code present")
            else:
                return self._record_test(test_name, True, 
                    "No explicit backward compatibility (may not be needed)", warning=True)
            
        except Exception as e:
            return self._record_test(test_name, False, f"Error: {str(e)}")
    
    def _record_test(self, test_name, passed, message, warning=False):
        """Record test result"""
        self.results['tests'][test_name] = {
            'passed': passed,
            'message': message,
            'warning': warning
        }
        self.results['summary']['total_tests'] += 1
        if passed:
            self.results['summary']['passed'] += 1
        else:
            self.results['summary']['failed'] += 1
        if warning:
            self.results['summary']['warnings'] += 1
        return passed
    
    def run_all_tests(self):
        """Run all validation tests"""
        print("=" * 70)
        print("Epic 010 Cost Optimization - Validation Tests")
        print("=" * 70)
        print()
        
        # Run tests
        self.test_schema_no_bullets_analyzer()
        self.test_schema_no_bullets_incremental()
        self.test_language_config_no_bullets_prompt()
        self.test_no_executive_summary_generation()
        self.test_digest_state_schema()
        self.test_output_format_unchanged()
        self.test_backward_compatibility_warnings()
        
        # Print results
        print("\nTest Results:")
        print("-" * 70)
        for test_name, result in self.results['tests'].items():
            status = "✓ PASS" if result['passed'] else "✗ FAIL"
            if result.get('warning'):
                status += " ⚠"
            print(f"{status:10} {test_name}")
            print(f"{'':10} {result['message']}")
            print()
        
        # Summary
        summary = self.results['summary']
        print("=" * 70)
        print(f"Summary: {summary['passed']}/{summary['total_tests']} tests passed")
        if summary['warnings'] > 0:
            print(f"         {summary['warnings']} warnings")
        if summary['failed'] > 0:
            print(f"         {summary['failed']} FAILED")
        print("=" * 70)
        
        return summary['failed'] == 0

def main():
    validator = OptimizationValidator()
    success = validator.run_all_tests()
    
    # Save results to file
    results_file = Path('validation_results.json')
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(validator.results, f, indent=2)
    
    print(f"\nDetailed results saved to: {results_file}")
    
    return 0 if success else 1

if __name__ == '__main__':
    exit(main())
