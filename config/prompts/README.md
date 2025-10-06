# GPT Prompt Configuration Library

This directory contains centralized YAML configuration files for all GPT system prompts used across the news analysis pipeline.

## Purpose

- **Discoverability**: All prompts in one place instead of scattered across Python files
- **Documentation**: Rich metadata for each prompt including purpose, parameters, and cost estimates
- **Maintainability**: Easy to update prompts without code changes
- **Testing**: Isolated prompt testing and version control
- **Consistency**: Standardized format across all pipeline stages

## Directory Structure

```
config/prompts/
├── README.md              # This file
├── filtering.yaml         # Filtering stage prompts (classification, Creditreform context)
├── deduplication.yaml     # Deduplication stage prompts (clustering, cross-run comparison)
├── analysis.yaml          # Analysis stage prompts (topic analysis, meta-analysis)
├── formatting.yaml        # Formatting stage prompts (rating generation)
└── digest.yaml            # Digest stage prompts (summarization, digest generation)
```

## YAML Format

Each prompt follows this standard format:

```yaml
prompt_name:
  description: "Brief description of what this prompt does"
  purpose: "Why this prompt exists and when to use it"
  parameters:
    - name: parameter_name
      required: true/false
      type: string/int/list/etc
      description: "What this parameter controls"
  template: |
    The actual prompt text here.
    Can be multi-line.
    Use {parameter_name} for substitution.
  cost_estimate: "~XXX tokens per call"
  example_usage: |
    # Python code showing how to use this prompt
    from news_pipeline.prompt_library import PromptLibrary
    from news_pipeline.language_config import LanguageConfig
    
    lang_config = LanguageConfig("de")
    prompt_lib = PromptLibrary(lang_config)
    
    prompt = prompt_lib.stage.prompt_name(parameter_name="value")
```

## Usage

Prompts are accessed through the `PromptLibrary` class:

```python
from news_pipeline.prompt_library import PromptLibrary
from news_pipeline.language_config import LanguageConfig

# Initialize with language config
lang_config = LanguageConfig("de")
prompt_lib = PromptLibrary(lang_config)

# Access prompts via pipeline stage methods
classification = prompt_lib.filtering.classification_prompt(topic="creditreform")
clustering = prompt_lib.deduplication.clustering_prompt()
rating = prompt_lib.formatting.rating_prompt()
```

## Pipeline Stages

### Filtering (`filtering.yaml`)
- Article classification by topic relevance
- Creditreform-specific business context
- Confidence threshold validation

### Deduplication (`deduplication.yaml`)
- Title-based clustering for duplicate detection
- Cross-run topic comparison
- Summary-based duplicate identification

### Analysis (`analysis.yaml`)
- Topic analysis and categorization
- Meta-analysis for insights extraction
- Confidence scoring

### Formatting (`formatting.yaml`)
- German rating report generation
- Structured output formatting
- Consistency validation

### Digest (`digest.yaml`)
- Article summarization
- Daily digest generation
- Incremental updates

## Migration Notes

This directory was created as part of Epic 011 (Prompt Centralization):
- **Story 011.1**: Created PromptLibrary architecture
- **Story 011.2**: Extracted prompts from 7 Python files into YAML
- **Story 011.3**: Migrated code to use PromptLibrary (planned)

## Original Locations

Prompts were extracted from these files:
- `news_pipeline/filter.py` → filtering.yaml
- `news_pipeline/gpt_deduplication.py` → deduplication.yaml
- `news_pipeline/cross_run_deduplication.py` → deduplication.yaml
- `news_pipeline/analyzer.py` → analysis.yaml
- `news_pipeline/german_rating_formatter.py` → formatting.yaml
- `news_pipeline/incremental_digest.py` → digest.yaml
- `news_pipeline/summarizer.py` → digest.yaml

## Validation

All YAML files are validated for:
- Syntax correctness (`yaml.safe_load()`)
- Required fields presence (description, purpose, template, etc.)
- Parameter specification completeness
- Template parameter matching

Run validation:
```bash
python scripts/test_yaml_prompts.py
```

## Contributing

When adding or modifying prompts:
1. Follow the standard YAML format
2. Include all required metadata fields
3. Document parameters with types and descriptions
4. Provide usage examples
5. Estimate token costs
6. Test parameter substitution
7. Validate YAML syntax

## Cost Optimization

Cost estimates help identify expensive prompts:
- Classification: ~500-800 tokens
- Summarization: ~1000-2000 tokens
- Deduplication: ~800-1500 tokens
- Rating generation: ~1500-2500 tokens

Monitor costs and optimize prompts that exceed budget targets.

## Fragment-Based Architecture (Story 011.4)

### Overview

The Fragment-Based Hybrid Architecture combines static prompt fragments with dynamic runtime data composition. This solves the limitation of fully static YAML prompts while maintaining centralized management.

### When to Use

- **Use fragments**: For reusable prompt components and static text sections
- **Use full prompts**: For file-specific prompts with no reuse potential
- **Use hybrid approach**: For prompts requiring runtime data injection (keywords, topics, etc.)

### fragments.yaml Structure

```yaml
common:
  # Reusable fragments across all pipeline stages
  analyst_role: "You are an expert Swiss business and financial news analyst."
  swiss_context: "Focus on Swiss business, financial, and regulatory context."
  # ... more common fragments

filter:
  # Fragments specific to filtering stage

analysis:
  # Fragments specific to analysis stage
```

### Fragment Composition Pattern

```python
from news_pipeline.prompt_library import PromptLibrary
from news_pipeline.language_config import LanguageConfig

# Initialize library
lang_config = LanguageConfig("de")
prompt_lib = PromptLibrary(lang_config)

# Get reusable fragments
header = prompt_lib.get_fragment('common', 'analyst_role')
task = prompt_lib.get_fragment('analysis', 'summarization_task')
output_format = prompt_lib.get_fragment('common', 'structured_summary_format')
focus = prompt_lib.get_fragment('common', 'swiss_analysis_focus')

# Build dynamic content
keywords = ["creditreform", "insolvency", "rating"]
keywords_text = f"Keywords: {', '.join(keywords)}"

# Compose final prompt using Python's native .format()
system_prompt = f"{header}\n\n{task}\n\n{keywords_text}\n\n{output_format}\n\n{focus}"
```

### Best Practices

1. **Keep fragments atomic and focused**: Each fragment should represent one concept
2. **Use descriptive fragment names**: Names should clearly indicate purpose
3. **Document parameter expectations**: Note what dynamic data each fragment expects
4. **Test fragment composition**: Verify composed prompts work as expected
5. **Avoid duplication**: Extract common patterns into shared fragments

### Benefits

✅ **No new dependencies**: Uses Python's native `.format()` method
✅ **Incremental migration**: Migrate one file at a time
✅ **Clear separation**: Static fragments in YAML, dynamic assembly in Python
✅ **Easy testing**: Fragments testable independently
✅ **Future-proof**: Can add Jinja2 later if more complex templating needed

### Example: summarizer.py

```python
# Before (hardcoded prompt):
system_prompt = """You are an expert Swiss business and financial news analyst.

Your task is to create a comprehensive summary of the article...

Return strict JSON with:
- title: cleaned/enhanced article title
- summary: concise 150-200 word summary...

Focus on:
1. Swiss business context and implications
2. Financial impacts and market relevance..."""

# After (fragment-based):
analyst_role = self.prompt_lib.get_fragment('common', 'analyst_role')
task = self.prompt_lib.get_fragment('analysis', 'summarization_task')
output = self.prompt_lib.get_fragment('common', 'structured_summary_format')
focus = self.prompt_lib.get_fragment('common', 'swiss_analysis_focus')

system_prompt = f"{analyst_role}\n\n{task}\n\n{output}\n\n{focus}"
```

### Testing

Run fragment tests:
```bash
python -m pytest tests/test_prompt_fragments.py -v
```

### Migration Status

- ✅ **Story 011.4**: Fragment architecture established, summarizer.py migrated
- ⏳ **Story 011.5**: filter.py migration (next)
- ⏳ **Story 011.6**: Remaining files (analyzer.py, incremental_digest.py, etc.)
