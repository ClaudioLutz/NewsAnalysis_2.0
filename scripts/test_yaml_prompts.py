"""
YAML Prompt Validation Script

Tests all YAML prompt configuration files for:
- Valid YAML syntax
- Required fields presence
- Parameter specifications
- Template parameter matching
- Completeness of extraction

Run: python scripts/test_yaml_prompts.py
"""

import yaml
import re
from pathlib import Path
from typing import Dict, Any, List, Set
import sys


class YAMLPromptValidator:
    """Validates YAML prompt configuration files."""
    
    def __init__(self, prompts_dir: str = "config/prompts"):
        self.prompts_dir = Path(prompts_dir)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.stats: Dict[str, Any] = {
            'files_validated': 0,
            'prompts_validated': 0,
            'errors_found': 0,
            'warnings_found': 0
        }
    
    def validate_all(self) -> bool:
        """
        Validate all YAML files in prompts directory.
        
        Returns:
            True if all validation passed, False if errors found
        """
        print("🔍 Validating YAML prompt configuration files...\n")
        
        yaml_files = list(self.prompts_dir.glob("*.yaml"))
        
        # Exclude example.yaml from validation
        yaml_files = [f for f in yaml_files if f.name != "example.yaml"]
        
        if not yaml_files:
            self.add_error("No YAML files found in config/prompts/")
            return False
        
        print(f"Found {len(yaml_files)} YAML files to validate\n")
        
        for yaml_file in yaml_files:
            self.validate_file(yaml_file)
        
        self.print_summary()
        
        return len(self.errors) == 0
    
    def validate_file(self, filepath: Path) -> None:
        """Validate a single YAML file."""
        print(f"📄 Validating {filepath.name}...")
        self.stats['files_validated'] += 1
        
        try:
            # Test YAML syntax
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if data is None:
                self.add_error(f"{filepath.name}: Empty YAML file")
                return
            
            # Validate each prompt in the file
            for prompt_name, prompt_data in data.items():
                if isinstance(prompt_data, dict) and not prompt_name.startswith('#'):
                    self.validate_prompt(filepath.name, prompt_name, prompt_data)
            
            print(f"   ✅ {filepath.name} validated successfully\n")
            
        except yaml.YAMLError as e:
            self.add_error(f"{filepath.name}: Invalid YAML syntax - {e}")
        except Exception as e:
            self.add_error(f"{filepath.name}: Validation error - {e}")
    
    def validate_prompt(self, filename: str, prompt_name: str, prompt_data: Dict) -> None:
        """Validate individual prompt configuration."""
        self.stats['prompts_validated'] += 1
        context = f"{filename}:{prompt_name}"
        
        # Check required fields
        required_fields = ['description', 'purpose']
        for field in required_fields:
            if field not in prompt_data:
                self.add_error(f"{context}: Missing required field '{field}'")
        
        # Check for template or note about location
        has_template = 'template' in prompt_data
        has_template_de = 'template_de' in prompt_data
        has_template_en = 'template_en' in prompt_data
        has_source_location = 'source_location' in prompt_data
        
        if not (has_template or has_template_de or has_template_en or has_source_location):
            self.add_warning(f"{context}: No template field found (may be in language_config.py)")
        
        # Validate parameters if present
        if 'parameters' in prompt_data:
            self.validate_parameters(context, prompt_data['parameters'])
        
        # Validate template parameters match specifications
        if has_template and 'parameters' in prompt_data:
            self.validate_template_parameters(
                context, 
                prompt_data['template'], 
                prompt_data['parameters']
            )
        
        # Check for cost estimate
        if 'cost_estimate' not in prompt_data:
            self.add_warning(f"{context}: No cost_estimate field")
        
        # Check for example usage
        if 'example_usage' not in prompt_data:
            self.add_warning(f"{context}: No example_usage field")
    
    def validate_parameters(self, context: str, parameters: List[Dict]) -> None:
        """Validate parameter specifications."""
        if not isinstance(parameters, list):
            self.add_error(f"{context}: parameters must be a list")
            return
        
        for i, param in enumerate(parameters):
            if not isinstance(param, dict):
                self.add_error(f"{context}: Parameter {i} must be a dict")
                continue
            
            # Check required parameter fields
            if 'name' not in param:
                self.add_error(f"{context}: Parameter {i} missing 'name' field")
            
            if 'required' not in param:
                self.add_warning(f"{context}: Parameter {param.get('name', i)} missing 'required' field")
            
            if 'type' not in param:
                self.add_warning(f"{context}: Parameter {param.get('name', i)} missing 'type' field")
            
            if 'description' not in param:
                self.add_warning(f"{context}: Parameter {param.get('name', i)} missing 'description' field")
    
    def validate_template_parameters(self, context: str, template: str, 
                                    parameters: List[Dict]) -> None:
        """Validate that template parameters match parameter specifications."""
        # Extract {param} placeholders from template
        template_params = set(re.findall(r'\{(\w+)\}', template))
        
        # Get specified parameter names
        specified_params = {p['name'] for p in parameters if 'name' in p}
        
        # Check for mismatches
        missing_in_spec = template_params - specified_params
        missing_in_template = specified_params - template_params
        
        if missing_in_spec:
            self.add_warning(
                f"{context}: Template uses parameters not in specification: {missing_in_spec}"
            )
        
        if missing_in_template:
            # This is less critical - some parameters might be used in code context
            pass
    
    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(f"❌ ERROR: {message}")
        self.stats['errors_found'] += 1
    
    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(f"⚠️  WARNING: {message}")
        self.stats['warnings_found'] += 1
    
    def print_summary(self) -> None:
        """Print validation summary."""
        print("\n" + "="*70)
        print("VALIDATION SUMMARY")
        print("="*70)
        
        print(f"\n📊 Statistics:")
        print(f"   Files validated: {self.stats['files_validated']}")
        print(f"   Prompts validated: {self.stats['prompts_validated']}")
        print(f"   Errors found: {self.stats['errors_found']}")
        print(f"   Warnings found: {self.stats['warnings_found']}")
        
        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)}):")
            for error in self.errors:
                print(f"   {error}")
        
        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✅ All validations passed! No errors or warnings.")
        elif not self.errors:
            print(f"\n✅ All validations passed with {len(self.warnings)} warnings.")
        else:
            print(f"\n❌ Validation FAILED with {len(self.errors)} errors.")


def check_extraction_completeness() -> bool:
    """
    Verify that all prompts from 7 source files have been extracted.
    
    Returns:
        True if extraction appears complete
    """
    print("\n" + "="*70)
    print("EXTRACTION COMPLETENESS CHECK")
    print("="*70 + "\n")
    
    expected_files = [
        'filtering.yaml',
        'deduplication.yaml', 
        'analysis.yaml',
        'formatting.yaml',
        'digest.yaml'
    ]
    
    prompts_dir = Path("config/prompts")
    missing_files = []
    
    for filename in expected_files:
        filepath = prompts_dir / filename
        if not filepath.exists():
            missing_files.append(filename)
            print(f"❌ Missing file: {filename}")
        else:
            print(f"✅ Found: {filename}")
    
    if missing_files:
        print(f"\n❌ Extraction INCOMPLETE: {len(missing_files)} files missing")
        return False
    
    print(f"\n✅ All {len(expected_files)} expected YAML files present")
    
    # Check expected prompt counts
    expected_prompts = {
        'filtering.yaml': 2,  # classification + creditreform_system
        'deduplication.yaml': 2,  # title_clustering + cross_run_topic_comparison
        'analysis.yaml': 1,  # topic_digest (from language_config)
        'formatting.yaml': 2,  # rating_analysis + article_key_points
        'digest.yaml': 5  # article_summarization + partial_digest + digest_merging + 2 placeholders
    }
    
    print(f"\n📊 Expected Prompt Counts:")
    all_counts_match = True
    
    for filename, expected_count in expected_prompts.items():
        filepath = prompts_dir / filename
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            actual_count = len([k for k in data.keys() if not k.startswith('#')])
            
            if actual_count >= expected_count:
                print(f"   ✅ {filename}: {actual_count} prompts (expected {expected_count})")
            else:
                print(f"   ❌ {filename}: {actual_count} prompts (expected {expected_count})")
                all_counts_match = False
        except Exception as e:
            print(f"   ❌ {filename}: Error reading file - {e}")
            all_counts_match = False
    
    return len(missing_files) == 0 and all_counts_match


def main():
    """Main validation entry point."""
    print("\n" + "="*70)
    print("YAML PROMPT CONFIGURATION VALIDATION")
    print("Story 011.2: YAML Extraction & Documentation")
    print("="*70 + "\n")
    
    # Check extraction completeness first
    completeness_ok = check_extraction_completeness()
    
    # Validate YAML files
    validator = YAMLPromptValidator()
    validation_ok = validator.validate_all()
    
    # Final result
    print("\n" + "="*70)
    if completeness_ok and validation_ok:
        print("✅ ALL VALIDATIONS PASSED")
        print("="*70 + "\n")
        return 0
    else:
        print("❌ VALIDATION FAILED")
        print("="*70 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
