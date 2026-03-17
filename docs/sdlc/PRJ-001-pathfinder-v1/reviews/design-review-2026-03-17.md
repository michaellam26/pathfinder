# Design Review — PRJ-001 PathFinder v1.0

**Review Phase**: Phase 2 — Tech Design
**Date**: 2026-03-17
**Review Target**: `docs/sdlc/PRJ-001-pathfinder-v1/tech-design.md`
**Review Type**: Retroactive review (code already complete, 485+ tests passing)

---

## Overall Conclusion: Conditional Pass

4 review Agents unanimously gave **Conditional Pass**, 0 blocking items. tech-design.md is highly consistent with code and architecture documentation. 33 tasks cover all 63 REQs. Testing and deployment plans are practical and actionable. Main findings focus on document structure optimization and maintainability improvements, with no functional defects.

| Review Agent | Conclusion | Finding Count | Key Findings |
|--------------|------------|---------------|--------------|
| TPM | Conditional Pass | 7 (0 blocking/1 medium/4 low/2 very low) | Risk table coverage incomplete (D-04), missing inter-Agent data flow sequence description (D-03) |
| Agent Reviewer | Conditional Pass | 7 (1 medium/4 low/2 informational) | Match/Tailored read functions use hardcoded column numbers (RED-01), cross-Agent duplicate functions (YEL-01~03) |
| Schema Validator | Conditional Pass | 2 (0 functional defects) | 5-table Schema 100% consistent; same RED-01 hardcoded column numbers |
| Eval Engineer | Conditional Pass | 5 (2 medium/1 low-medium/2 low) | Fine Prompt missing score range declaration, semantic quality test 0% coverage |

---

## Section 1: TPM Design Review

### Review Conclusion: Conditional Pass

tech-design.md overall quality is excellent. Document positioning is clear (supplements SDLC perspective without duplicating ARCHITECTURE.md). 33 task breakdowns cover all 63 REQs. Testing strategy and deployment plan are practical and actionable.

### Per-Dimension Assessment

#### Requirement Coverage — Pass

Appendix "REQ to Task Mapping Matrix" lists REQ-001~063 mapped to 33 tasks line by line. Cross-checked with no omissions. REQ-001~004 correctly marked as "implied" as architecture-level constraints.

#### Task Dependencies — Pass

4-layer dependency structure (L0 Shared Foundation -> L1 Persistence -> L2 Agent -> L3 Tooling) is clear and sound. No circular dependencies within L0. L2 Agents exchange data via Excel rather than code imports. L3 is decoupled from runtime.

**Finding D-03 (Low)**: Inter-Agent data flow sequence dependency (company->job->match->optimizer) not explicitly annotated at L2.

#### Risk Identification — Conditional Pass

Section 4 identifies 5 technical risks (BUG-12/33/38 etc.), all mitigated. However, compared to BRD Section 7's 9 risks:

**Finding D-04 (Medium)**: API quota exhaustion (Gemini/Tavily/Firecrawl) and model retirement risks are only in Section 3.6 fault recovery table, not elevated to Section 4 risk table, resulting in incomplete risk view. Substance is covered; this is a document structure issue.

#### Testing Strategy — Pass

Three-layer test stratification is sound (unit 485+ / integration / end-to-end). Mock strategy is thorough (all 6 types of external dependencies fully mocked). Regression tests cover 5 key Bugs.

**Finding D-05 (Low)**: Only 5 representative Bug regression tests listed; coverage status for the remaining 50 fixes not stated.

#### Deployment Plan — Pass

Environment initialization 5 steps are clear and executable. API quota budget 240-370 RPD within 500 limit (safety margin 26-48%). 6 fault recovery mechanisms are comprehensive.

#### Consistency with ARCHITECTURE.md — Pass

Agent list, Shared Modules, Excel Schema, external services, Custom Agent/Skill counts all fully consistent with ARCHITECTURE.md.

### TPM Action Items

| # | Description | Priority |
|---|-------------|----------|
| DA-01 | Add API quota exhaustion and model retirement risks to Section 4 risk table | P2 |
| DA-02 | Add L2 inter-Agent data flow sequence dependency description to Section 1.2 | P3 |
| DA-03 | Add cross-Agent data contract summary table (writer-reader-worksheet mapping) to Section 5.2 | P2 |
| DA-04 | Add "remaining Bugs indirectly covered by module unit tests" statement to Section 2.4 | P3 |

---

## Section 2: Agent Reviewer — Design Review

### Review Conclusion: Conditional Pass

Code is highly consistent with technical design documentation. Core architecture is correctly implemented.

### Per-Dimension Assessment

#### Code vs Design Consistency — Consistent

- Module dependency graph fully matches actual code
- All 33 tasks have corresponding implementations found in code
- Data file layout matches actual code

**Minor deviation**: tech-design Section 3.4 describes JD cache as `{md5}_raw.md`, actual code uses `{md5}.md` (no `_raw` suffix).

#### Code Quality — Good

**Finding RED-01 (Medium)**: `excel_store.py` functions `get_match_pairs()`, `get_scored_matches()`, `get_tailored_match_pairs()` use hardcoded column numbers (3/8/9/6/11), unlike JD_Tracker's `_JD_COL` which uses dynamic mapping. Currently functionally correct, but requires manual synchronization when Schema changes.

#### Cross-Agent Consistency — Good

- Gemini Pool initialization/call pattern fully unified across all four Agents (GRN-04)
- Rate Limiting called outside Semaphore, pattern correct after BUG-38 fix (GRN-05)
- All Excel operations go through `shared/excel_store.py` unified interface (GRN-06)
- `_FINE_SYSTEM_PROMPT` character-identical between two Agents, REQ-052 satisfied (GRN-07)

**Finding YEL-01~03 (Low)**: `load_resume()`, `_load_jd_markdown()`, `JD_CACHE_DIR` are duplicated across multiple Agents; recommend extracting to shared/.

**Finding YEL-05 (Informational)**: job_agent RPM=10 vs other Agents RPM=13, missing explanatory comment.

#### Prompt Design — Good

- MatchResult Pydantic Schema fully aligned between two Agents (GRN-08)
- Scoring calibration anchors are clear (GRN-09)
- All Gemini calls use `response_schema` to constrain JSON output (GRN-10)

### Agent Reviewer Recommendations

1. **[Recommended]** Create `_MATCH_COL` / `_TAILORED_COL` dynamic mapping for Match_Results / Tailored_Match_Results
2. **[Recommended]** Extract duplicate functions to `shared/` module
3. **[Optional]** Add explanatory comment for job_agent RPM=10

---

## Section 3: Schema Validator — Design Review

### Validation Conclusion: Conditional Pass

5-worksheet Schema 100% consistent, 4 inter-Agent data flow contracts all clear, no field misalignment.

### Validation Results

| Dimension | Conclusion |
|-----------|------------|
| Schema document vs code consistency | 5 worksheets 100% consistent |
| Actual Excel file vs code consistency | 5 worksheets 100% consistent |
| Inter-Agent data flow contracts | All 4 data flows clear |
| Field completeness | All write functions cover all Schema fields |
| Migration compatibility | All 10 historical changes have corresponding migration logic |
| Cross-Agent shared Schema | MatchResult, _FINE_SYSTEM_PROMPT, JD_CACHE_DIR — all three consistent |

### Findings

Same as Agent Reviewer RED-01: `get_match_pairs` / `get_scored_matches` / `get_tailored_match_pairs` use hardcoded column numbers. Recommend defining `_MATCH_COL` / `_TAILORED_COL` dynamic mapping. No functional defects currently.

---

## Section 4: Eval Engineer — Design Review

### Review Conclusion: Conditional Pass

8 Gemini Prompt designs are overall sound. Core mechanisms (scoring calibration, hallucination protection, REQ-052 consistency) are all implemented.

### Prompt Inventory

| # | Prompt | Agent | Temperature | Purpose |
|---|--------|-------|-------------|---------|
| 1 | Company info extraction | company_agent | 0.1 | Extract company info from search results, do not generate URLs |
| 2 | LLM job filtering | job_agent | 0.0 | Filter AI/TPM related job URLs |
| 3 | JD structured extraction | job_agent | 0.05 | Extract structured JD fields |
| 4 | _COARSE_SYSTEM_PROMPT | match_agent | 0.0 | Batch coarse screening 1-100 score |
| 5 | _FINE_SYSTEM_PROMPT | match_agent + resume_optimizer | 0.0 | 4-dimension weighted fine evaluation |
| 6 | _TAILOR_SYSTEM_PROMPT | resume_optimizer | 0.3 | Resume customization rewriting |
| 7 | _BATCH_TAILOR_SYSTEM_PROMPT | resume_optimizer | 0.3 | Batch customization (inherits #6) |
| 8 | _BATCH_FINE_SYSTEM_PROMPT | resume_optimizer | 0.0 | Batch re-scoring (inherits #5) |

### Scoring Calibration Status

- **Coarse**: Three-tier anchors complete (1-30/31-60/61-100), minimum score 1 constraint explicit — **Pass**
- **Fine**: 4-dimension weights correct (30+30+20+20=100%), but **missing 1-100 score range declaration and numeric calibration examples** — **Needs improvement**
- **REQ-052**: `_FINE_SYSTEM_PROMPT` character-identical between two Agents — **Pass**

### Hallucination Protection Assessment

| Agent | Protection Strength | Mechanism |
|-------|---------------------|-----------|
| company_agent | Strong | URL completely removed from LLM decision chain |
| resume_optimizer | Strong | Dual-layer constraints (hard prohibition + positive scoping) |
| job_agent | Moderate | Salary field explicitly states "do not fabricate"; other fields rely on extraction behavior |
| match_agent | N/A | Scoring task, no hallucination risk |

### Assessment Coverage

- **Functional layer coverage**: 9/9 (100%) — All Gemini call points have functional tests
- **Semantic quality layer coverage**: 0/9 (0%) — No AI output semantic correctness tests

Key gaps: No hallucination black-box tests, no scoring consistency tests, Fine score range unconstrained.

### Eval Engineer Action Items

| # | Description | Priority |
|---|-------------|----------|
| EA-01 | Append `1-100` range declaration to end of `_FINE_SYSTEM_PROMPT` (sync both files) | P1 |
| EA-02 | Add `_FINE_SYSTEM_PROMPT` full-text diff assertion in `TestPrompts` (precise REQ-052 verification) | P1 |
| EA-03 | Add hallucination protection black-box test framework | P2 |
| EA-04 | Change `batch_re_score` fallback value from 0 to 1 (unify minimum score constraint) | P3 |

---

## Section 5: Merged Action Items

### P1 (Recommend completing before Phase 5)

| # | Source | Description |
|---|--------|-------------|
| EA-01 | Eval Engineer | Append 1-100 score range declaration to `_FINE_SYSTEM_PROMPT` |
| EA-02 | Eval Engineer | Add `_FINE_SYSTEM_PROMPT` full-text diff test |

### P2 (Recommend completing in subsequent iterations)

| # | Source | Description |
|---|--------|-------------|
| DA-01 | TPM | Add API quota and model retirement risks to tech-design Section 4 risk table |
| DA-03 | TPM | Add cross-Agent data contract summary table to tech-design Section 5.2 |
| RED-01 | Agent Reviewer + Schema Validator | Define `_MATCH_COL` / `_TAILORED_COL` dynamic column mapping |
| YEL-01~03 | Agent Reviewer | Extract duplicate functions to shared/ |
| EA-03 | Eval Engineer | Add hallucination protection black-box test framework |

### P3 (Optional improvements)

| # | Source | Description |
|---|--------|-------------|
| DA-02 | TPM | Add L2 Agent data flow sequence description to Section 1.2 |
| DA-04 | TPM | Add remaining Bug test coverage statement to Section 2.4 |
| EA-04 | Eval Engineer | Unify `batch_re_score` fallback value to 1 |
| YEL-05 | Agent Reviewer | Add comment for job_agent RPM=10 |

---

## Section 6: Review Sign-off

- [x] **TPM Agent** — Conditional Pass (2026-03-17)
- [x] **Agent Reviewer** — Conditional Pass (2026-03-17)
- [x] **Schema Validator** — Conditional Pass (2026-03-17)
- [x] **Eval Engineer** — Conditional Pass (2026-03-17)

**Overall Recommendation**: Project may proceed to Phase 3. P1 items (EA-01/EA-02) should be completed before Phase 5 launch assessment; P2/P3 items can be addressed incrementally in subsequent iterations.
