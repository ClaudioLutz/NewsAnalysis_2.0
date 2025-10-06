# Epic 011: PromptLibrary Centralization

**Epic ID:** 011  
**Epic Name:** Centralize GPT-5 System Prompts into PromptLibrary  
**Status:** Planning  
**Created:** 2025-10-05  
**Source Document:** docs/brainstorming-session-results.md

---

## Epic Summary

Centralize scattered GPT-5 system prompts across the news analysis pipeline into a dedicated PromptLibrary with YAML-based configuration, rich documentation, and separation of concerns from language configuration. This addresses the core discoverability problem where prompts are embedded across 7 different Python files, making them hard to find, modify, and maintain.

**Key Findings from Brainstorming Session:**
- ✅ Prompts scattered across 7 files: summarizer.py, gpt_deduplication.py, german_rating_formatter.py, filter.py, cross_run_deduplication.py, incremental_digest.py, analyzer.py
- ✅ Partial centralization exists in language_config.py (~40%) but mixes concerns
- ✅ Duplication discovered: german_rating_formatter duplicates language_config prompt
- ✅ Discoverability is the core pain point - developers can't easily find/modify prompts
- ✅ Pipeline stage organization matches developer mental model

**Solution Architecture:**
- Separate PromptLibrary class focused solely on prompt management
- YAML configuration files organized by pipeline stage
- Rich metadata (description, parameters, usage examples, cost estimates)
- Language integration via LanguageConfig dependency injection
- Method-based access with IDE support (autocomplete, type hints)

**Impact:**
- Improved discoverability through centralized, documented prompt catalog
- Cleaner separation of concerns (PromptLibrary vs LanguageConfig)
- Self-documenting system enables faster onboarding
- Foundation for future enhancements (versioning, A/B testing, analytics)
- Eliminates duplication and inconsistencies

---

## Business Value

### Developer Productivity
- **Discoverability:** All prompts in one place with clear documentation
- **Faster Modifications:** Change prompts without hunting through codebase
- **Better Onboarding:** Self-documenting YAML reduces "where is X?" questions
- **IDE Support:** Autocomplete and type hints for prompt access

### Code Quality
- **Separation of Concerns:** PromptLibrary (prompts) vs LanguageConfig (language switching)
- **Eliminated Duplication:** Single source of truth for each prompt
- **Maintainability:** Centralized changes vs scattered modifications
- **Testability:** Prompts can be validated independently

### Future Enablement
- **Versioning Foundation:** Track prompt changes, enable A/B testing
- **Analytics Ready:** Instrument prompt usage and performance
- **Cost Visibility:** Document per-prompt cost estimates
- **AI Optimization:** Enable future AI-powered prompt improvement

### Risk Profile
- **Risk Level:** MEDIUM
- Big bang migration requires careful validation
- Temporary dual systems avoided by clean cut-over
- Comprehensive testing required across all pipeline stages
- Rollback plan needed if issues discovered

---

## Technical Scope

### Current State Analysis

**Prompts Currently Scattered Across 7 Files:**

1. **summarizer.py** - Hardcoded system prompt for article summarization
2. **gpt_deduplication.py** - Clustering prompt for duplicate detection
3. **german_rating_formatter.py** - Rating prompt (DUPLICATES language_config!)
4. **filter.py** - Classification prompt + Creditreform system prompt builder
5. **cross_run_deduplication.py** - Cross-run deduplication prompt
6. **incremental_digest.py** - Uses language_config methods (already centralized)
7. **analyzer.py** - Uses language_config methods (already centralized)

**Partial Centralization Status:**
- ~40% prompts in language_config.py (analyzer.py, incremental_digest.py)
- ~60% prompts scattered in individual files
- Mixed responsibilities: language_config handles both language switching AND prompt management

### New Architecture

**PromptLibrary Structure:**
```python
news_pipeline/
  prompt_library.py          # Main PromptLibrary class
  
config/prompts/              # YAML configuration files
  filtering.yaml             # filter.py prompts
  deduplication.yaml         # gpt_deduplication.py, cross_run_deduplication.py
  analysis.yaml              # analyzer.py prompts
  formatting.yaml            # german_rating_formatter.py prompts
  digest.yaml                # incremental_digest.py, summarizer.py prompts
```

**Access Pattern:**
```python
# Initialize with language config
prompt_lib = PromptLibrary(language_config)

# Method-based access with pipeline stage organization
prompt = prompt_lib.filtering.classification_prompt(topic="creditreform")
prompt = prompt_lib.deduplication.clustering_prompt()
prompt = prompt_lib.formatting.rating_prompt()
```

**YAML Format (Example):**
```yaml
classification_prompt:
  description: "Classifies articles by topic relevance"
  purpose: "Initial filtering to identify creditreform-related articles"
  parameters:
    - name: topic
      required: true
      description: "Topic to filter by (e.g., 'creditreform')"
  template: |
    Classify the following article...
    Topic: {topic}
  cost_estimate: "~500 tokens per call"
  example_usage: |
    prompt = prompt_lib.filtering.classification_prompt(topic="creditreform")
```

### Files to Create

**New Files:**
- `news_pipeline/prompt_library.py` - Core PromptLibrary class
- `config/prompts/filtering.yaml` - Filtering stage prompts
- `config/prompts/deduplication.yaml` - Deduplication prompts
- `config/prompts/analysis.yaml` - Analysis stage prompts
- `config/prompts/formatting.yaml` - Formatting stage prompts
- `config/prompts/digest.yaml` - Digest generation prompts

### Files to Modify

**Major Refactoring:**
- `news_pipeline/summarizer.py` - Replace hardcoded prompt with prompt_lib
- `news_pipeline/gpt_deduplication.py` - Replace hardcoded prompt with prompt_lib
- `news_pipeline/german_rating_formatter.py` - Use prompt_lib, remove duplication
- `news_pipeline/filter.py` - Replace hardcoded prompts with prompt_lib
- `news_pipeline/cross_run_deduplication.py` - Replace hardcoded prompt with prompt_lib
- `news_pipeline/language_config.py` - Remove prompt management, keep language switching
- `news_pipeline/incremental_digest.py` - Update to use new prompt_lib (minor)
- `news_pipeline/analyzer.py` - Update to use new prompt_lib (minor)

**Testing:**
- Integration tests for each pipeline stage
- Validation that prompts match original functionality
- End-to-end pipeline test

---

## Stories

### Story 1: Create PromptLibrary Architecture & Core Implementation
**Priority:** #1 (Foundation)  
**Goal:** Build the core PromptLibrary infrastructure with pipeline stage organization

**Acceptance Criteria:**
1. `news_pipeline/prompt_library.py` created with main PromptLibrary class
2. Stage-specific subclasses implemented (FilteringPrompts, DeduplicationPrompts, AnalysisPrompts, FormattingPrompts, DigestPrompts)
3. YAML loading mechanism implemented with caching
4. Language integration with LanguageConfig completed
5. Example prompt validates architecture works end-to-end
6. Documentation in docstrings and example usage
7. Unit tests for PromptLibrary core functionality

**Technical Notes:**
- Follow existing patterns from language_config.py for consistency
- Use method-based access for IDE support
- Implement lazy loading with caching for performance
- Accept LanguageConfig via dependency injection
- Source: brainstorming-session-results.md "Action Planning #1"

**Estimated Effort:** Medium (~1-2 days)

---

### Story 2: Create YAML Files with Documented Prompts
**Priority:** #2 (Content)  
**Goal:** Extract all prompts from source files into well-documented YAML configuration

**Acceptance Criteria:**
1. `config/prompts/` directory created
2. All prompts extracted from 7 source files:
   - filtering.yaml (from filter.py)
   - deduplication.yaml (from gpt_deduplication.py, cross_run_deduplication.py)
   - analysis.yaml (from analyzer.py)
   - formatting.yaml (from german_rating_formatter.py)
   - digest.yaml (from incremental_digest.py, summarizer.py)
3. Each prompt documented with:
   - Description and purpose
   - Parameter specifications
   - Usage examples
   - Cost estimates
4. Duplicate prompt removed (german_rating_formatter)
5. YAML syntax validated
6. All prompts accounted for (100% extraction)

**Technical Notes:**
- Carefully preserve exact prompt text during extraction
- Mark duplicates for removal
- Validate parameterization works with Python string templates
- Cross-reference with current codebase for accuracy
- Source: brainstorming-session-results.md "Action Planning #2"

**Estimated Effort:** Medium (~2-3 days for extraction and documentation)

---

### Story 3: Big Bang Migration with Validation
**Priority:** #3 (Migration)  
**Goal:** Migrate all 7 files to use PromptLibrary in single clean cut-over

**Acceptance Criteria:**
1. All 7 files updated to use PromptLibrary:
   - summarizer.py migrated
   - gpt_deduplication.py migrated
   - german_rating_formatter.py migrated (duplicate removed)
   - filter.py migrated
   - cross_run_deduplication.py migrated
   - incremental_digest.py migrated
   - analyzer.py migrated
2. language_config.py refactored:
   - Prompt management removed
   - Language switching logic preserved
   - Works with new PromptLibrary
3. Integration tests pass for each pipeline stage
4. End-to-end pipeline test completes successfully
5. Output validation: results match pre-migration baseline
6. Migration documentation created
7. Rollback plan documented and tested

**Technical Notes:**
- Test each stage individually before full pipeline test
- Compare outputs byte-by-byte where possible
- Monitor for prompt parameter mismatches
- Validate all language configurations work (German/English)
- Keep git commit atomic for easy rollback
- Source: brainstorming-session-results.md "Action Planning #3"

**Estimated Effort:** Large (~2-3 days for migration and validation)

---

## Implementation Order

**CRITICAL: Follow this sequence:**

1. **Story 1:** PromptLibrary Architecture (MUST DO FIRST)
   - Creates foundation for all subsequent work
   - Validates architecture decisions early
   - Enables parallel work on Story 2

2. **Story 2:** YAML Extraction & Documentation (MUST COMPLETE BEFORE Story 3)
   - Provides content for migration
   - Documents all prompts for validation
   - Identifies duplicates and issues

3. **Story 3:** Big Bang Migration (DEPENDS ON Stories 1 & 2)
   - Requires working PromptLibrary infrastructure
   - Needs documented YAML files
   - Clean cut-over avoids dual systems

**Rationale:**
- Infrastructure → Content → Migration is logical progression
- Story 1 and 2 can partially overlap once architecture is validated
- Story 3 requires both 1 and 2 complete for clean execution
- Big bang approach avoids long-term technical debt of dual systems

**Alternative Considered (Hybrid Migration):**
The brainstorming session identified a hybrid migration by pipeline stage as lower risk, but the decision was made for big bang to avoid:
- Long-term maintenance of dual systems
- Complex migration logic
- Inconsistent developer experience during transition

**Risk Mitigation:** Comprehensive testing and rollback plan compensate for big bang risk.

---

## Risk Mitigation

### Pre-Implementation (Story 1)
- [ ] Validate architecture with single example prompt end-to-end
- [ ] Confirm language_config integration approach
- [ ] Test YAML loading performance with caching
- [ ] Verify IDE autocomplete works with stage-based organization
- [ ] Document any architectural issues discovered

### During Extraction (Story 2)
- [ ] Verify extracted prompts match source exactly (character-for-character)
- [ ] Identify all parameterization points
- [ ] Test parameter substitution with Python string templates
- [ ] Validate YAML syntax before proceeding to migration
- [ ] Cross-reference with all known prompt usages

### During Migration (Story 3)
- [ ] Migrate and test each file individually first
- [ ] Create baseline outputs before migration for comparison
- [ ] Test full pipeline in isolated environment
- [ ] Byte-by-byte comparison of outputs where possible
- [ ] Monitor logs for parameter mismatches or errors
- [ ] Keep atomic commit for easy rollback

### Post-Migration
- [ ] Run full pipeline for 48 hours monitoring errors
- [ ] Validate all language configurations (German/English)
- [ ] Check prompt parameter usage in production
- [ ] Document any discovered issues or improvements
- [ ] Update architecture documentation

---

## Success Metrics

### Primary Metrics
- All 7 files successfully migrated to PromptLibrary ✅
- Zero functional regressions (outputs match baseline) ✅
- All prompts discoverable in config/prompts/ ✅
- Rich documentation for each prompt ✅

### Code Quality Metrics
- Separation of concerns achieved (PromptLibrary vs LanguageConfig) ✅
- Duplication eliminated (german_rating_formatter) ✅
- Single source of truth for all prompts ✅
- IDE autocomplete working for prompt access ✅

### Adoption Metrics
- Developer feedback: Faster prompt discovery ✅
- Time to modify prompt reduced (no code hunting) ✅
- Onboarding time reduced (self-documenting YAML) ✅

### Future Readiness
- Foundation for prompt versioning ✅
- Analytics instrumentation points identified ✅
- Cost estimates documented per prompt ✅

---

## Future Opportunities

After this epic, the PromptLibrary foundation enables:

1. **Prompt Versioning System**
   - Track changes over time
   - Enable A/B testing of prompt variations
   - Safe rollback capabilities

2. **Automated Prompt Testing**
   - Test fixtures with expected outputs
   - Validation in CI/CD pipeline
   - Regression detection

3. **Prompt Performance Analytics**
   - Track usage patterns
   - Monitor costs per prompt
   - Measure success rates and quality

4. **AI-Powered Optimization**
   - Use AI to suggest prompt improvements
   - Continuous quality enhancement
   - Cost reduction opportunities

5. **Multi-Language Expansion**
   - Extend beyond German/English
   - Dynamic language support
   - Internationalization ready

---

## References

### Source Documents
- **Brainstorming Session:** docs/brainstorming-session-results.md
- **Advanced Elicitation Results:** (Summary provided by Business Analyst)

### Current Implementation
- **Scattered Prompts:**
  - news_pipeline/summarizer.py
  - news_pipeline/gpt_deduplication.py
  - news_pipeline/german_rating_formatter.py
  - news_pipeline/filter.py
  - news_pipeline/cross_run_deduplication.py
  - news_pipeline/incremental_digest.py
  - news_pipeline/analyzer.py
  
- **Partial Centralization:**
  - news_pipeline/language_config.py (mixed responsibilities)

### Architecture Documents
- To be updated post-migration with PromptLibrary documentation

---

## Epic Owner

- **Product Manager:** [TBD]
- **Technical Lead:** [TBD]
- **Business Analyst:** Mary (Brainstorming facilitator)
- **Estimated Total Effort:** 5-8 days (across all stories)
- **Expected Completion:** [TBD]

---

## Notes

**Brainstorming Session Insights:**

*"Discoverability drives design: The core problem wasn't organization but finding prompts when needed. This insight shaped every subsequent decision."*

*"Existing patterns matter: Matching the existing language_config pattern improved adoption likelihood and reduced cognitive load."*

*"Simplicity over power: Simple string templates beat Jinja2 templates because they're 'good enough' without added complexity."*

*"Documentation is feature one: Self-documenting YAML with rich metadata turns the library from code to knowledge base."*

*"Big Bang is brave but clean: While risky, migrating all at once avoids long-term technical debt of dual systems."*

**Strategic Decision:**
The brainstorming session initially explored a hybrid migration approach (by pipeline stage) which offered lower risk through incremental validation. However, the decision was made for big bang migration to:
- Avoid dual systems during transition
- Prevent long-term technical debt
- Provide clean, consistent developer experience
- Enable immediate benefits across entire pipeline

The risk is mitigated through comprehensive testing, baseline comparisons, and documented rollback procedures.
