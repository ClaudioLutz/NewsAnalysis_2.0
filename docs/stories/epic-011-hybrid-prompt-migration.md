# Epic 011: Hybrid Prompt Architecture Migration

**Epic ID:** 011  
**Created:** 2025-10-05  
**Status:** In Progress  
**Priority:** High  
**Confidence:** 88%

---

## Epic Overview

Migrate remaining prompt management code to a Fragment-Based Hybrid Architecture, enabling centralized prompt management while supporting both static and dynamic prompt patterns.

### Problem Statement

Story 011.3 (Big Bang Migration) delivered 30% value by successfully migrating `language_config.py`, but revealed a critical architectural challenge: some prompts are static (easily centralized in YAML), while others require dynamic runtime data (keywords, focus areas) that don't map to static templates.

Attempting to force all prompts into static YAML creates an architectural mismatch that blocks progress.

### Solution: Fragment-Based Hybrid Architecture

**Core Concept:** Static prompt fragments in YAML, dynamic assembly in Python

**Benefits:**
- ✅ No new dependencies (uses Python's native `.format()`)
- ✅ Clear separation of concerns (YAML = data, Python = logic)
- ✅ Incrementally adoptable (migrate file by file)
- ✅ Easy to test (fragments testable independently)
- ✅ Maintainable (common fragments reused across prompts)
- ✅ Future-proof (can add Jinja2 later if needed)
- ✅ Low risk (clear fallback options)

### Success Metrics

**Prompt Centralization Rate:** 80%+ of prompt text lives in YAML  
**Maintenance Burden:** <5 files to edit for prompt changes  
**Development Velocity:** Prompt changes don't require code changes (for static parts)  
**Quality:** Zero behavior regressions (validated against baseline.db)

---

## Related Documents

- **Analysis:** `docs/stories/011.3-elicitation-findings.md` (comprehensive 88-page analysis)
- **Summary:** `docs/stories/011.3-elicitation-summary.md` (executive summary)
- **Previous Work:** `docs/stories/011.3.big-bang-migration.md` (30% complete)
- **Architecture:** `docs/stories/011.1.prompt-library-architecture.md`
- **YAML Extraction:** `docs/stories/011.2.yaml-extraction-documentation.md`

---

## Architecture Pattern

### YAML Fragment Structure

```yaml
# config/prompts/fragments.yaml
common:
  classifier_header: "You are an expert news classifier for Swiss business..."
  output_format: "Return strict JSON with is_match, confidence, reason..."
  
filter:
  classify_base: |
    {classifier_header}
    
    Your task is to determine if an article is relevant to: {topic}
    {dynamic_context}
    
    Classify based on:
    1. Title content and keywords
    2. URL structure and domain
    3. Relevance to Swiss business/financial context
    
    {output_format}
```

### Python Implementation

```python
# filter.py
class AIFilter:
    def build_classifier_prompt(self, topic, keywords, focus_areas):
        # Get reusable fragments
        header = self.prompt_lib.get_fragment('common', 'classifier_header')
        output_format = self.prompt_lib.get_fragment('common', 'output_format')
        base = self.prompt_lib.get_prompt('filter', 'classify_base')
        
        # Build dynamic context (runtime data)
        dynamic_context = f"""Topic keywords: {', '.join(keywords)}

KEY FOCUS AREAS:
{self._format_focus_areas(focus_areas)}"""
        
        # Compose final prompt
        return base.format(
            classifier_header=header,
            topic=topic,
            dynamic_context=dynamic_context,
            output_format=output_format
        )
```

---

## Epic Stories

### ✅ Completed: Story 011.3 (30%)
- language_config.py successfully migrated
- Baseline created for validation (baseline.db, baseline_output.md)
- Architectural blocker identified and analyzed

### Story 011.4: Establish Fragment-Based Architecture
**Status:** Ready  
**Effort:** 2-3 days  
**Confidence:** 95%

Establish the fragment-based hybrid architecture pattern with proof-of-concept migration.

**Key Deliverables:**
- `config/prompts/fragments.yaml` structure
- Enhanced PromptLibrary with `get_fragment()` method
- One simple file migrated as proof (e.g., deduplication.py)
- Pattern documentation

### Story 011.5: Migrate filter.py Using Hybrid Pattern
**Status:** Blocked by 011.4  
**Effort:** 2 days  
**Confidence:** 85%

Migrate filter.py to use fragment-based composition for both classification and Creditreform prompts.

**Key Deliverables:**
- Static fragments extracted to YAML
- Dynamic context builders in Python
- Baseline validation passing
- Tests updated

### Story 011.6: Complete Remaining File Migrations
**Status:** Blocked by 011.5  
**Effort:** 3-5 days  
**Confidence:** 90%

Migrate remaining files using established pattern.

**Files to Migrate:**
- analyzer.py (likely dynamic prompts)
- deduplication.py (probably static - unless already done in 011.4)
- summarizer.py (probably static)
- incremental_digest.py (might have dynamic parts)
- german_rating_formatter.py (check if has prompts)

---

## Timeline

**Total Estimated Time:** 7-10 days

**Week 1:**
- Day 1-3: Story 011.4 (establish architecture)
- Day 4-5: Story 011.5 (filter.py migration)

**Week 2:**
- Day 1-5: Story 011.6 (remaining files)

---

## Risk Assessment

### Low Risk ✅
- Fragment-based approach is proven pattern
- No new dependencies for core functionality
- Incremental migration = easy rollback
- Baseline exists for validation

### Medium Risk ⚠️
- Time estimation might be optimistic (could take 12-15 days)
- Some prompts might have hidden complexity
- Team learning curve for new pattern

### High Risk 🔴
- (None identified with current approach)

---

## Mitigation Strategies

1. **Start with simplest file** - Builds confidence and pattern
2. **Validate at each step** - baseline.db is your safety net
3. **Document as you go** - Future you will thank present you
4. **One file at a time** - Don't try to parallelize
5. **Keep git commits atomic** - Easy revert if needed

---

## Decision Points & Fallback Plans

### Decision Point 1: Fragment Approach Too Complex?
**Trigger:** If fragment composition becomes harder than direct prompts  
**Fallback:** Simplify to basic hybrid (full prompts in YAML with {placeholders})  
**Cost:** Less reusability, more duplication  
**Benefit:** Faster completion

### Decision Point 2: Validation Fails Repeatedly?
**Trigger:** Migrated prompts produce different output than baseline  
**Fallback:** Keep dynamic prompts in code (partial migration only)  
**Cost:** Less centralization (maybe 60% instead of 90%)  
**Benefit:** Zero risk to production behavior

### Decision Point 3: Timeline Slipping?
**Trigger:** Taking longer than 10 days total  
**Fallback:** Ship what's done, document remaining work  
**Cost:** Incomplete migration  
**Benefit:** Incremental value delivery

### Decision Point 4: Team Wants More Power Later?
**Trigger:** Requirements emerge for complex conditional logic in prompts  
**Evolution:** Add Jinja2 for specific prompts that need it  
**Cost:** New dependency  
**Benefit:** Future-proof, but only when actually needed

---

## Epic Acceptance Criteria

- [ ] 90%+ of prompt text lives in YAML or fragments
- [ ] Full pipeline baseline comparison passes
- [ ] All files migrated or documented as no-migration-needed
- [ ] Architecture pattern documented
- [ ] Tests updated and passing
- [ ] No behavior regressions

---

## Definition of Done

- All stories completed with acceptance criteria met
- Baseline validation confirms no behavior changes
- Documentation updated
- Code reviewed
- Tests passing
- Pattern established for future work

---

**Epic Created:** 2025-10-05  
**Created By:** Bob (Scrum Master) 🏃  
**Based On:** Elicitation findings from Mary (Business Analyst)
