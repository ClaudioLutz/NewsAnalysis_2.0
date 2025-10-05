# Epic 010: Cost Optimization - Remove Unused Fields

**Epic ID:** 010  
**Epic Name:** Remove Unused Digest Bullets and Executive Summary  
**Status:** Planning  
**Created:** 2025-10-05  
**Source Document:** docs/cost_optimization_analysis.md

---

## Epic Summary

Eliminate unused AI-generated fields from the news analysis pipeline to reduce API costs by 20-40%. The current pipeline generates digest bullets (4-6 per topic) and executive summaries that are never used in the final German rating report output, resulting in wasted tokens and unnecessary API costs.

**Key Findings:**
- ✅ Digest-level bullets are generated but unused (waste: ~200-400 tokens per digest)
- ✅ Executive summary is generated but never appears in final output
- ✅ Article-level key points ARE used (generated separately in german_rating_formatter.py)
- ✅ Only `headline` and `why_it_matters` from digests reach final output
- 💰 Estimated savings: 20-40% reduction in digest generation costs (~$62-100/year)

**Impact:**
- Annual cost savings: $62-100 with current volume
- Scales linearly with volume increases
- Simplifies response schemas
- Improves code maintainability
- Zero impact on final output quality

---

## Business Value

### Cost Reduction
- Immediate 20-40% reduction in digest generation API costs
- Scales with increased usage (more topics, more frequent runs)
- With AI implementation: 1-month break-even period

### Code Quality
- Removes unused code paths
- Simplifies JSON schemas
- Easier maintenance and future modifications
- Establishes pattern for finding similar optimizations

### Risk Profile
- **Risk Level:** LOW to MEDIUM
- No functional impact (fields already unused)
- Easy rollback if needed
- Requires careful validation of all code references

---

## Technical Scope

### Files to Modify

**Schema Definitions:**
- `news_pipeline/analyzer.py` - Remove bullets from digest schema
- `news_pipeline/incremental_digest.py` - Remove bullets from merge schema
- `news_pipeline/analyzer.py` - Remove executive summary generation

**Configuration:**
- `news_pipeline/language_config.py` - Update German & English prompts

**State Management:**
- Clear cached digest state to force clean regeneration

### Critical Dependencies

**Executive Summary Dependency:**
- Line 349 of analyzer.py: Executive summary generation CONSUMES digest bullets
- Must remove executive summary before or simultaneously with digest bullets
- Order matters: Executive summary removal → then digest bullets removal

**Backward Compatibility:**
- Old cached digests have bullets field
- Incremental merge handles mixed formats (old + new)
- Solution: Clear all digest state before first run

---

## Stories

### Story 1: Validation and Code Reference Discovery
**Goal:** Identify all code locations that reference bullets or executive_summary fields

**Acceptance Criteria:**
1. All references to digest.bullets found in Python code
2. All references to executive_summary found in Python code
3. Database schema checked for digest storage
4. All JSON schema definition locations identified
5. Documentation created listing all findings
6. Zero Python code accessing these fields (except generation) confirmed

**Technical Notes:**
- Run grep searches across news_pipeline/ and templates/
- Check database schema: `sqlite3 news.db "SELECT sql FROM sqlite_master WHERE type='table';"`
- Document findings for next stories

**Estimated Effort:** Small (~1 hour)

---

### Story 2: Remove Executive Summary Generation
**Goal:** Remove executive summary generation from analyzer.py

**Acceptance Criteria:**
1. `create_executive_summary()` function call removed from analyzer.py
2. Executive summary schema removed from all response schemas
3. Any config references to executive summary removed
4. No errors when running digest generation
5. Final output unchanged (executive summary was already unused)
6. Unit tests pass

**Technical Notes:**
- Priority: Must be done before Story 3 (dependency on line 349)
- Estimated token savings: Higher than digest bullets (covers all topics)
- Source: analyzer.py, potentially language_config.py

**Estimated Effort:** Small (~1-2 hours)

---

### Story 3: Remove Digest Bullets from Schema
**Goal:** Remove bullets field from all digest generation schemas

**Acceptance Criteria:**
1. bullets field removed from analyzer.py response_schema
2. bullets field removed from incremental_digest.py merge_schema
3. bullets removed from all "required" arrays
4. German language config updated (remove "4-6 wichtige Erkenntnisse")
5. English language config updated (remove "4-6 key insights")
6. All language prompt updates applied atomically
7. Schema validation passes
8. No bullets field in generated JSON

**Technical Notes:**
- Files: analyzer.py, incremental_digest.py, language_config.py
- Update ALL schema files in single commit for atomicity
- Source references: Lines 126-137 (analyzer.py), Lines 169-177 (incremental_digest.py)

**Estimated Effort:** Medium (~2-3 hours)

---

### Story 4: State Management and Migration
**Goal:** Clear digest state and handle schema migration

**Acceptance Criteria:**
1. All cached digest state cleared before first run with new schema
2. Incremental merge handles graceful degradation if old state encountered
3. Documentation added: "Digest state cleared for schema migration"
4. First run with new schema completes successfully
5. Subsequent incremental updates work correctly
6. No schema validation errors in logs

**Technical Notes:**
- Clear state: `rm -f .digest_state_*` or similar mechanism
- Test scenario: Ensure old format + new format doesn't crash
- May need temporary backward compatibility code

**Estimated Effort:** Small (~1-2 hours)

---

### Story 5: Testing, Validation & Monitoring
**Goal:** Comprehensive testing and establish monitoring for cost savings

**Acceptance Criteria:**
1. Full pipeline run completes without errors
2. bullets field absent in all generated JSON outputs
3. executive_summary field absent in all generated JSON outputs
4. Final markdown output byte-identical to baseline (except timestamps)
5. Token usage logged and compared to baseline
6. Cost reduction documented (target: 20-40%)
7. Error logs clean for 48 hours post-deployment
8. Regression tests pass
9. Documentation updated in architecture docs

**Technical Notes:**
- Create baseline output before changes for comparison
- Monitor token counts: `grep -r '"bullets"' outputs/ || echo "Success"`
- Track actual savings vs. projected savings
- Document in docs/architecture/ or similar

**Test Scenarios:**
```bash
# Run pipeline with modified schema
python news_analyzer.py

# Verify bullets field ABSENT
grep -r '"bullets"' outputs/ || echo "Success: No bullets in outputs"

# Compare outputs
diff baseline_output.md new_output.md  # Should be identical
```

**Estimated Effort:** Medium (~3-4 hours)

---

## Implementation Order

**CRITICAL: Follow this sequence:**

1. **Story 1:** Validation (MUST DO FIRST) - Confirm assumptions
2. **Story 2:** Remove Executive Summary (Higher priority due to dependency)
3. **Story 3:** Remove Digest Bullets (Dependent on Story 2 completion)
4. **Story 4:** State Management (Prepare for clean migration)
5. **Story 5:** Testing & Monitoring (Validate and measure results)

**Rationale:**
- Story 1 validates assumptions and identifies risks
- Story 2 must precede Story 3 due to line 349 dependency
- Story 4 ensures clean state for new schema
- Story 5 confirms success and quantifies savings

---

## Risk Mitigation

### Pre-Implementation Validation (Story 1)
- [ ] Verify no Python code accesses digest.bullets
- [ ] Verify no Python code accesses executive_summary
- [ ] Check database schema for digest storage
- [ ] Identify ALL schema definition locations
- [ ] Confirm external APIs don't expect these fields

### During Implementation (Stories 2-4)
- [ ] Update ALL schema files atomically (single commit)
- [ ] Update ALL language configs simultaneously
- [ ] Clear digest state before first run
- [ ] Test incremental merge with mixed formats
- [ ] Maintain rollback capability

### Post-Implementation (Story 5)
- [ ] Assert bullets/executive_summary fields absent in JSON
- [ ] Compare outputs byte-by-byte with baseline
- [ ] Monitor error logs for 48 hours
- [ ] Track token usage reduction
- [ ] Document in architecture

---

## Success Metrics

### Primary Metrics
- 20-40% reduction in digest generation output tokens ✅
- Zero errors in production logs for 48 hours ✅
- Final markdown output unchanged (byte-identical) ✅

### Secondary Metrics
- Simplified schema (fewer required fields) ✅
- Improved code clarity (unused fields removed) ✅
- Pattern established for future optimizations ✅

### Cost Metrics
- Current daily cost: ~$0.17 (bullets only)
- Target daily cost: ~$0.10-0.14
- Break-even: ~1 month with AI implementation
- Annual savings: $62-100

---

## Future Opportunities

After this epic, consider systematic audit of:
1. **All Generated Fields:** Check usage of every field in schemas
2. **Template-Driven Generation:** Only generate what templates need
3. **Lazy Generation:** Generate expensive fields on-demand
4. **Model Tier Optimization:** Use cheaper models where quality permits

---

## References

- **Analysis Document:** docs/cost_optimization_analysis.md
- **Code References:**
  - analyzer.py (lines 126-137, 349)
  - incremental_digest.py (lines 169-177)
  - language_config.py (German & English configs)
  - templates/daily_digest.md.j2 (lines 31-55)
- **Template Usage:** digest.headline, digest.why_it_matters, source.key_points
- **Architecture Docs:** (To be updated in Story 5)

---

## Epic Owner

- **Product Manager:** [TBD]
- **Technical Lead:** [TBD]
- **Estimated Total Effort:** 8-12 hours (across all stories)
- **Expected Completion:** [TBD]

---

## Notes

**AI Implementation Advantage:**
- Human implementation cost: $500 labor → 8-year break-even → NOT VIABLE
- AI implementation cost: $5-10 API calls → 1-month break-even → VIABLE
- This demonstrates how AI changes economics of "small" optimizations

**Strategic Insight:**
The system generates comprehensive data structures but only uses a subset in outputs. This pattern suggests systematic optimization opportunities across the entire pipeline.
