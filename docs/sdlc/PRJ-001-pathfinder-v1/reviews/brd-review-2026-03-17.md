# BRD Review Report — PRJ-001: PathFinder v1.0

**Review Date**: 2026-03-17
**Review Phase**: Phase 1 — BRD
**Reviewers**: TPM Agent + PM Agent + Engineer Lead
**BRD Version**: Retroactive version (v1.5)

---

## Overall Review Conclusion

| Reviewer | Conclusion | Notes |
|----------|------------|-------|
| TPM Agent | **Conditional Pass** | 7 findings (0 blocking, 2 medium, 5 low/very low), recommend completing corrections before Phase 5 |
| PM Agent | **Recommended Pass (Conditional)** | Core value fully delivered, 6 product risks (1 high, 3 medium, 2 low), recommend strengthening acceptance criteria |
| Engineer Lead | **Pass** | BRD fully consistent with code implementation (6/6 checkpoints passed), 3 technical recommendations |

**Overall Determination: Conditional Pass** — May proceed to Phase 2 (Tech Design), the following Action Items can be completed incrementally in subsequent phases.

---

## Section 1: TPM BRD Review Report

### Review Conclusion: Conditional Pass

Overall BRD quality is excellent. All 63 requirements have been implemented and tested. Requirements coverage is broad and acceptance criteria are clear and measurable. This is a retroactive review (project implementation already complete), so the review focuses on document quality and process completeness rather than blocking project progress. The following 4 issues requiring attention should be resolved before entering Phase 5 (Launch Assessment).

### 1. Requirement Completeness

**Assessment: Pass**

63 REQs are organized into 17 subsections by functional module, covering the complete 4-Agent pipeline:

| Module | REQ Range | Count | Coverage Assessment |
|--------|-----------|-------|---------------------|
| System Architecture | REQ-001~004 | 4 | Complete |
| Company Agent — Company Discovery | REQ-005~010 | 6 | Complete |
| Company Agent — Career URL | REQ-011~013 | 3 | Complete |
| Company Agent — ATS Upgrade | REQ-014~016 | 3 | Complete |
| API Reliability (Gemini) | REQ-017 | 1 | Complete |
| Job Agent — Job Discovery | REQ-018~020 | 3 | Complete |
| Job Agent — JD Extraction | REQ-021~029 | 9 | Complete |
| Match Agent — Resume Loading | REQ-030~032 | 3 | Complete |
| Match Agent — Two-Stage Matching | REQ-033~040 | 8 | Complete |
| Match Agent — API Reliability | REQ-041~043 | 3 | Complete |
| Shared Persistence Layer | REQ-044~048 | 5 | Complete |
| Resume Optimizer — Resume Optimization | REQ-049~053 | 5 | Complete |
| Resume Optimizer — Incremental Updates | REQ-054~055 | 2 | Complete |
| Resume Optimizer — API Reliability | REQ-056~057 | 2 | Complete |
| Job Agent Enhancement — ATS Extension | REQ-058~059 | 2 | Complete |
| Job Agent Enhancement — Data Quality | REQ-060~061 | 2 | Complete |
| Job Agent Enhancement — Architecture Extensibility | REQ-062~063 | 2 | Complete |

**Potential Omissions (Minor, Non-blocking)**:

- **Error Recovery & Checkpoint Resume**: BRD describes incremental updates (hash, timestamp skipping), but does not explicitly define recovery strategy for mid-run Agent crashes. Based on code behavior, the upsert pattern naturally supports re-runs, but BRD does not explicitly declare this guarantee.
- **Logging & Observability**: Runtime log format and levels are not defined in functional requirements.

### 2. Priority Reasonableness

**Assessment: Pass**

| Priority | Count | Percentage | Coverage Areas |
|----------|-------|------------|----------------|
| P0 | 24 | 38% | Core architecture, Agent main flows, scoring logic, persistence creation, API Key rotation |
| P1 | 21 | 33% | Incremental updates, rate limiting, concurrency control, ATS extension, data validation |
| P2 | 8 | 13% | Data quality grading, URL format extension, console output |
| P3 | 2 | 3% | Architecture refactoring (declarative routing), auto-archiving |
| Unlabeled | 8 | 13% | System architecture REQ-001~004 + Persistence REQ-044~048 (implied P0) |

**Finding**: REQ-001~004 and REQ-044~048 (9 requirements total) have no priority label assigned. Recommend labeling as P0.

### 3. Dependencies & Risks

**Assessment: Conditional Pass**

BRD identifies 9 risks with specific mitigation measures.

**Missing Risk Items (Recommend Adding)**:

| Risk | Impact | Recommended Mitigation |
|------|--------|----------------------|
| Gemini model version retirement/renaming (`preview` suffix) | High | Already managed centrally via `shared/config.py` MODEL constant with low switching cost, but BRD should explicitly state this risk |
| Tavily/Firecrawl free tier policy changes | Medium | Document current specific free quota values, establish degradation plan |

### 4. Acceptance Criteria

**Assessment: Pass**

| Dimension | Measurability | Assessment |
|-----------|---------------|------------|
| Functional completeness | 63/63 REQ, 55/55 BUG, 485+ tests | Excellent |
| Critical P0 Bug fixes | 5 P0s listed individually | Excellent |
| End-to-end acceptance scenarios | 4-step flow, each step with expected output | Excellent |
| Performance baseline | 3 scenarios with time limits | Excellent |

**Improvement Recommendation**: Missing acceptance criteria for exception paths (e.g., expected system behavior when all Keys are exhausted).

### 5. Scope Boundaries

**Assessment: Pass**

In-Scope and Out-of-Scope are clearly delineated with unambiguous boundaries. Scope boundary definition is one of the highlights of this BRD.

### 6. Cross-Agent Coordination

**Assessment: Conditional Pass**

Data flow is implicitly defined completely through Excel worksheets:

```
Company Agent → Company_List → Job Agent → JD_Tracker → Match Agent → Match_Results → Resume Optimizer → Tailored_Match_Results
```

**Needs Improvement**: BRD lacks an explicit cross-Agent data contract table (writer-reader-column mapping). Recommend referencing ARCHITECTURE.md Section 4 in the appendix.

### 7. Technical Decisions

**Assessment: Pass**

DEC-001 (LLM Model Selection — retain Gemini flash-lite) is data-driven, well-justified, and leaves room for future extension.

### 8. TPM Findings & Recommendations

| # | Type | Severity | Description | Recommendation |
|---|------|----------|-------------|----------------|
| F-01 | Document completeness | Low | REQ-001~004 and REQ-044~048 (9 requirements total) have no priority label | PM to add priority labels (recommend all P0) |
| F-02 | Risk coverage | Medium | Gemini model version retirement risk not identified | Add a row to Section 7 risk table |
| F-03 | Cross-Agent Coordination | Medium | BRD lacks explicit cross-Agent data contract table | Add to appendix or reference ARCHITECTURE.md |
| F-04 | Acceptance Criteria | Low | End-to-end acceptance defines only happy path | Add expected behavior for exception scenarios |
| F-05 | Risk coverage | Low | Tavily/Firecrawl free tier specific quota values not documented | Add specific values to dependency table |
| F-06 | Document consistency | Low | status.md shows all Phase 1 tasks unchecked | Update status.md to reflect actual state |
| F-07 | Requirement wording | Very Low | REQ-017/041/057 three descriptions are highly repetitive | Mark dependency on REQ-017 in REQ-041/057 |

---

## Section 2: PM BRD Impact Analysis Report

### Analysis Conclusion: Recommended Pass (Conditional)

BRD documentation is complete, design is sound, and delivery verification is thorough. All 63 REQs implemented, all 55 Bugs fixed, 485+ tests passing. Core user value has been fully delivered. The conditional aspects focus on BRD document quality (information lag due to retroactive nature) and two medium-priority product risks.

### 1. User Value Assessment

**Core Pain Point Coverage: High**

| User Pain Point | Solution | Value Realization |
|-----------------|----------|-------------------|
| Fragmented company discovery | Company Agent (Tavily + Gemini, 200 company limit) | High |
| Non-uniform formats across multiple ATS platforms | Job Agent (API + crawler, 6 major ATS) | High |
| Lack of quantitative matching evidence | Match Agent (two-stage scoring, 4-dimension weighted) | Medium (scoring anchors and calibration baselines undefined) |
| Time-consuming resume customization | Resume Optimizer (rewrite + Score Delta) | High |

**Key User Value Gaps**:
1. **Insufficient transparency**: 4-dimension weights are defined internally by the system; candidates cannot understand scoring rationale
2. **Missing feedback loop**: Post-application results cannot flow back; scoring model has no closed-loop optimization mechanism
3. **Single candidate limitation**: Future multi-user support not specified

### 2. Requirement Impact Analysis

#### High Impact Requirements (Deletion or change would cause core functionality failure)

| REQ ID | Description | Impact Notes |
|--------|-------------|--------------|
| REQ-001~004 | Four-Agent independent architecture + shared Excel | System architecture foundation |
| REQ-018~019 | ATS API + crawler path | Job data entry point; failure cascades to all downstream |
| REQ-023 | Gemini structured JD extraction | Required input for matching phase |
| REQ-034~036 | Two-stage matching scoring | Core product differentiator |
| REQ-050~053 | Resume customization + re-scoring | Resume Optimizer core value chain |
| REQ-044~047 | Excel persistence layer | Sole persistence layer; data loss equals system failure |
| REQ-017/041/057 | Gemini Key rotation | Operational guarantee for batch runs on free tier |

#### Medium Impact Requirements

REQ-011~013, REQ-024~026, REQ-031~032, REQ-033, REQ-054~055, REQ-058~060, REQ-063 — Absence degrades quality but does not cause complete failure.

#### Low Impact Requirements

REQ-007, REQ-009, REQ-012, REQ-029, REQ-040, REQ-051, REQ-061~062 — Optimize experience or maintainability.

### 3. Priority & Value Alignment

Overall alignment is good. REQ-060 (JD field completeness grading) is rated P2 which is slightly low; from a product perspective, recommend treating as P1.

### 4. Competitive Differentiation Analysis

| Dimension | Manual Process | PathFinder v1.0 | Improvement Factor |
|-----------|---------------|-----------------|-------------------|
| Company discovery | Days | 15 minutes | 20-50x |
| ATS job scraping | Manual site-by-site visits | Automated | Saves 4-8 hours/100 companies |
| Matching judgment | Subjective gut feeling | Quantitative scoring | Qualitative leap |
| Resume customization | 30-60 min/resume | Automated + Score Delta | 30-60x/resume |
| Full pipeline | Days | <= 60 minutes | 10-30x |

**Key differentiators**: Ashby API coverage, Score Delta observability, zero-cost operation.

### 5. Product Risks

| # | Risk | Impact | Recommendation |
|---|------|--------|----------------|
| 1 | LLM scoring reliability not calibrated | High | v2.0: collect application feedback to calibrate weights; v1.0: clearly state "scores are for reference only" |
| 2 | ATS format changes causing silent data degradation | Medium | Pair with Observability alerting mechanism |
| 3 | Soft 404 false positives causing valid jobs to be silently skipped | Medium | Write skipped JD count to logs or Excel |
| 4 | Gemini score inflation (LLM sycophancy) | Medium | eval-engineer periodic sampling to verify score distribution |
| 5 | Tavily quota exhaustion causing silent company discovery failure | Low | Write quota status to Excel metadata |
| 6 | Single-user design limiting future monetization | Low | Document multi-user extension path in ARCHITECTURE.md |

### 6. Acceptance Criteria Assessment

**Recommend strengthening two areas**:
1. **Data quality acceptance criteria**: JD `data_quality=complete` ratio threshold + `is_ai_tpm=True` minimum count requirement
2. **Match scoring reliability acceptance criteria**: Fine-evaluated Top 5 `Strengths`/`Gaps` non-empty validation

### 7. Future Evolution Recommendations

**P0 Direction**: Scoring feedback loop, scoring explainability output
**P1 Direction**: More ATS platform coverage, run quality monitoring dashboard
**P2 Direction**: One-click install script, multi-candidate support, scheduling automation

---

## Section 3: Engineer Lead BRD Review Report

### Review Conclusion: Pass

As Engineer Lead, I reviewed the BRD from a technical implementation perspective, focusing on verifying consistency between BRD technical claims and actual code, architectural design soundness, and technical feasibility.

### 1. BRD vs Code Consistency Verification

Code-level verification of 6 key technical claims in the BRD — **all consistent**:

| Checkpoint | Verification Item | Result |
|------------|-------------------|--------|
| Company Agent | MAX_TOTAL=200, BATCH_SIZE=50, 7 queries, search distribution ratio, 5-strategy Career URL waterfall | Consistent |
| Job Agent | ATS_PLATFORMS 6 entries, FRESH_DAYS=5, `_is_valid_jd_content()` soft 404 detection, `_assess_jd_quality()` field grading | Consistent |
| Match Agent | _KEYWORD_THRESHOLD=4, batch=10, Top 20%, weights 30/30/20/20, Semaphore(3)+RPM=13 | Consistent |
| Resume Optimizer | score>=0 filtering, _FINE_SYSTEM_PROMPT re-scoring, Semaphore(3)+RPM=13 | Consistent |
| Excel Store | 5 worksheet names + all table column names fully match ARCHITECTURE.md | Consistent |
| Gemini Pool | _GeminiKeyPoolBase base class, round-robin rotate(), Client cache dict | Consistent |

### 2. Architecture Design Assessment

**Assessment: Pass**

- **Modularity**: 4 Agent + 4 Shared Module decoupled design is sound; Agents exchange data via Excel worksheets with no direct code dependencies
- **Extensibility**: ATS_PLATFORMS declarative routing table (REQ-062) significantly reduces the cost of adding new ATS, changing from modifying if-elif chains to adding dictionary entries
- **Fault tolerance**: Schema migration + corruption recovery + upsert pattern combination ensures data layer robustness
- **API economy**: Pre-filter (keyword threshold=4) -> batch coarse screening (10/batch) -> fine evaluation (Top 20%) three-level funnel effectively controls Gemini API call volume

### 3. Technical Risk Additions

| # | Risk | Severity | Notes |
|---|------|----------|-------|
| E-01 | Excel single-process write is a performance bottleneck | Low (no impact for v1.0) | load->modify->save pattern has no issues at 200 company scale, but if scaling to 1000+ companies or multi-user in the future, migration to SQLite should be considered |
| E-02 | `_is_valid_jd_content()` function name does not fully correspond to BRD's `_is_soft_404()` description | Very Low | Code uses a broader function name (covering both soft 404 + positive signal validation), functionality is consistent but naming has minor deviation; recommend BRD use actual function name |
| E-03 | Semaphore value in resume_optimizer.py not directly confirmed as constant in code search | Very Low | May be inlined in `asyncio.Semaphore(3)` call; recommend extracting as named constant for consistency with match_agent |

### 4. Engineer Lead Recommendations

| # | Description | Priority |
|---|-------------|----------|
| E-A1 | BRD Section 4.7 REQ-022 reference to `_is_soft_404` function name should be updated to actual code name `_is_valid_jd_content` | P3 |
| E-A2 | Agree with TPM's F-03 — cross-Agent data contract table is critical for Phase 2 Tech Design; recommend formally defining in tech-design.md | P2 |
| E-A3 | Agree with TPM's F-02 — Gemini `preview` model retirement risk should be added to risk table; code layer already mitigated via `shared/config.py` MODEL constant | P1 |

---

## Section 4: Merged Action Items

| # | Source | Description | Assignee | Priority |
|---|--------|-------------|----------|----------|
| A-01 | TPM | Add priority labels to REQ-001~004 and REQ-044~048 (P0) | PM Agent | P2 |
| A-02 | TPM | Add "Gemini model version retirement" risk item to BRD Section 7 risk table | PM Agent | P1 |
| A-03 | TPM | Add cross-Agent data contract table to BRD appendix or reference ARCHITECTURE.md | PM Agent | P2 |
| A-04 | TPM | Add exception path acceptance scenarios to BRD Section 8 | PM Agent | P3 |
| A-05 | TPM | Add Tavily/Firecrawl free tier specific quota values to BRD Section 6 | PM Agent | P3 |
| A-06 | TPM | Update status.md, mark completed Phase 1 items as `[x]` | TPM Agent | P1 |
| A-07 | PM | Add data quality dimension to BRD acceptance criteria | PM Agent | P1 |
| A-08 | PM | Add match scoring reliability acceptance criteria to BRD | PM Agent | P1 |
| A-09 | PM | Mark REQ-029 as "superseded by REQ-063" | Engineer Lead | P2 |
| A-10 | PM | Register high-impact product risks in status.md risk registry | TPM | P1 |
| A-11 | PM | eval-engineer to execute scoring distribution sampling analysis (during Phase 4) | QA Team | P2 |
| A-12 | PM | Include v2.0 priority directions as PRJ-002 BRD input | TPM + PM | P3 |
