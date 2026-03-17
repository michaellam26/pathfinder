# Testing Review — PRJ-001 PathFinder v1.0

**Date**: 2026-03-17
**Phase**: Phase 4 — Testing & QA
**Review Team**: Test Analyzer + Bug Tracker + Doc Sync + API Debugger + Eval Engineer (5 agents in parallel)
**Overall Rating**: Conditional Pass (5/5 agents gave Conditional Pass)

---

## Review Summary

| Agent | Rating | Key Findings |
|-------|--------|--------------|
| Test Analyzer | Conditional Pass | 485 test cases 100% passing; main() orchestration logic untested; 4 REQs without direct coverage; BUG-28 has no regression test |
| Bug Tracker | Conditional Pass | 55/55 Bug fix code all in place; 5 new P3 potential issues discovered (exception swallowing/missing logs) |
| Doc Sync | Conditional Pass | REQ-056 Semaphore documentation severely inconsistent with code; job_agent rpm=10 vs documented 13; BRD variable name error |
| API Debugger | Conditional Pass | company_agent Gemini calls have no rate limiting; ATS API non-200 status codes not logged; rate_limiter comments inaccurate |
| Eval Engineer | Conditional Pass | Fine Prompt missing score range declaration; fallback value inconsistency (0 vs 1); AI semantic quality test coverage 0/9; hallucination tests 0/2 |

---

## 1. Test Analyzer Review

### 1.1 Test Execution Results

- **Total test cases**: 485
- **Passed / Failed / Skipped**: 485 / 0 / 0
- **Execution time**: 7.74 seconds
- **Test files**: 6

### 1.2 Coverage Analysis

| Test File | Case Count | Covered Module | Coverage Assessment |
|-----------|------------|----------------|---------------------|
| `test_excel_store.py` | 118 | `shared/excel_store.py` | Most comprehensive: all 24 public functions covered |
| `test_job_agent.py` | 175 | `agents/job_agent.py` | Strongest: ATS routing, location filtering, soft 404, JD quality, archiving all covered |
| `test_company_agent.py` | 66 | `agents/company_agent.py` | Moderate: core paths covered, `run_phase_1_5()`/`main()` untested |
| `test_match_agent.py` | 63 | `agents/match_agent.py` | Good: scoring/filtering fully covered, `_format_jd_for_coarse()` untested |
| `test_resume_optimizer.py` | 39 | `agents/resume_optimizer.py` | Good: customization/re-scoring covered, `main()` untested |
| `test_workday_url.py` | 24 | `agents/job_agent.py` (Workday subset) | Complete: REQ-061 all format variants covered |

### 1.3 REQ Coverage Gaps

| REQ ID | Requirement | Gap Description |
|--------|-------------|-----------------|
| REQ-009 | Max 50 per batch / total limit 200 | `need` parameter upper limit logic untested |
| REQ-025 | FRESH_DAYS incremental skip | age field tested, skip control flow untested |
| REQ-032 | Resume change triggers re-evaluation | No direct test |
| REQ-054 | resume_hash incremental skip | Read path tested, skip decision in main() untested |

### 1.4 Bug Regression Tests

51 of 55 Bugs have dedicated regression tests. **BUG-28 (P1, retry block position) has no regression test protection**.

### 1.5 Structural Blind Spots

- All 4 Agents' `main()` orchestration logic has no direct tests
- Multiple uses of `inspect.getsource` code text analysis instead of behavioral verification (high maintenance cost)
- TD-01 hardcoded column numbers have no regression protection tests

---

## 2. Bug Tracker Review

### 2.1 Bug Status Statistics

| Priority | Total | Fixed | Unfixed |
|----------|-------|-------|---------|
| P0 Critical | 5 | 5 | 0 |
| P1 High | 15 | 15 | 0 |
| P2 Medium | 23 | 23 | 0 |
| P3 Low | 12 | 12 | 0 |
| **Total** | **55** | **55** | **0** |

### 2.2 P0 Bug Fix Verification

| Bug ID | Description | Code Still In Place |
|--------|-------------|---------------------|
| BUG-01 | `.env` plaintext Keys -> `.gitignore` protection | Confirmed |
| BUG-02 | `requirements.txt` missing core dependencies | Confirmed |
| BUG-03 | `_is_us_segment()` ambiguous state code misjudgment | Confirmed |
| BUG-32 | Tesla JD `FirecrawlApp` class name error | Confirmed |
| BUG-33 | Gemini returns null -> `(d.get(...) or [])` protection | Confirmed |

### 2.3 P1 Bug Fix Verification (Full)

All 15 P1 Bug fix code verified in place via code inspection, including:
- BUG-27 JD infinite retry -> `_JD_MISSING` filtering
- BUG-28 retry block position -> now inside `async with`
- BUG-34~36 Gemini Pool refactoring -> Client cache + round-robin + thread lock
- BUG-37~38 concurrency control -> `asyncio.to_thread` + Semaphore/Gemini separation

### 2.4 Newly Discovered Potential Issues

| # | File | Line | Type | Description | Priority |
|---|------|------|------|-------------|----------|
| 1 | `resume_optimizer.py` | 447 | Exception swallowing | fallback tailor exception does not print exception object `e` | P3 |
| 2 | `resume_optimizer.py` | 496 | Exception swallowing | fallback re-score silently returns 0 score, no warning | P3 |
| 3 | `job_agent.py` | 1086 | Exception swallowing | Workday JD parsing `except Exception: continue` with no logging | P3 |
| 4 | `job_agent.py` | 1093 | Exception swallowing | Workday salary extraction `except Exception: pass` completely silent | P3 |
| 5 | `company_agent.py` | 521 | Architecture risk | Synchronous `time.sleep(0.5)` will block event loop if async-ified in the future | P3 |

Zero TODO/FIXME/HACK comments in code; high cleanliness.

---

## 3. Doc Sync Review

### 3.1 Key Deviations

| Severity | Deviation | Affected Documents |
|----------|-----------|-------------------|
| **Critical** | REQ-056: Documentation claims `asyncio.Semaphore(3)`, code actually uses sequential batch processing (`BATCH_TAILOR_SIZE=2` / `BATCH_RESCORE_SIZE=5`) + `_RateLimiter`, no Semaphore | REQUIREMENTS.md, ARCHITECTURE.md, BRD |
| **Critical** | job_agent `_GEMINI_LIMITER = _RateLimiter(rpm=10)`, documentation claims 13 RPM | ARCHITECTURE.md |
| Needs Update | ARCHITECTURE.md file tree `config.py` comment missing `AUTO_ARCHIVE_THRESHOLD` | ARCHITECTURE.md |
| Needs Update | BRD Section 4.17 REQ-062 variable name `ATS_ROUTING` should be `ATS_PLATFORMS` | brd.md |

### 3.2 Verified Consistent Items

- All 5 Excel Schemas (column names/column counts) fully consistent with code HEADERS
- REQ-058 (Ashby API), REQ-060 (JD quality grading), REQ-062 (ATS routing table), REQ-063 (auto-archiving) code implementation consistent with documentation
- CLAUDE.md overall accurate, no major deviations
- CHANGELOG.md records of 55 Bug fixes and 6 REQ enhancements are complete

---

## 4. API Debugger Review

### 4.1 Per-API Integration Assessment

| API | Error Handling | Retry Strategy | Rate Limiting | Assessment |
|-----|---------------|----------------|---------------|------------|
| Gemini | 429 auto-rotation + Client cache + thread safety | Re-raise after all keys exhausted | 13 RPM (match/resume), 10 RPM (job) | Good |
| Tavily | 402/429/quota detection + fast fail | No retry (degrade to other strategies) | None | Acceptable |
| Firecrawl | 3 retries + linear backoff (30s/60s for 429) | `_FC_MAP_LIMITER` rpm=1 | Only map calls rate-limited | Good |
| Crawl4AI | JS rendering + timeout 35-60s + `return_exceptions=True` | No retry | None | Acceptable |
| ATS API | Ashby logs status code, Greenhouse/Lever do not | No retry, degrade to crawler | None | Acceptable |

### 4.2 Key Findings

| # | Type | Description | Severity |
|---|------|-------------|----------|
| F-01 | Design flaw | `company_agent.py` Gemini calls are synchronous, cannot use asyncio rate limiter; high-frequency calls may trigger 429 | Medium |
| F-02 | Silent failure | Greenhouse/Lever API non-200 does not log specific status code | Low |
| F-03 | Documentation inaccuracy | `rate_limiter.py` comments say token-bucket, actual implementation is minimum interval | Low |
| F-04 | Potential quota leak | Google/Tesla JD Firecrawl `scrape()` not governed by `_FC_MAP_LIMITER` | Low |

---

## 5. Eval Engineer Review

### 5.1 Prompt Inventory

System contains 9 Gemini Prompts (3 scoring + 2 customization + 2 batch + 1 filtering + 1 extraction).

### 5.2 Scoring Calibration

| Prompt | Score Range Declaration | Anchors | Issues |
|--------|------------------------|---------|--------|
| `_COARSE_SYSTEM_PROMPT` | "1-100" (Pydantic Field says "0-100") | Complete (three tiers) | Pydantic description inconsistent with Prompt |
| `_FINE_SYSTEM_PROMPT` | **No explicit declaration** | No anchors | Score drift risk, only constrained by code `max(1,...)` lower bound |

### 5.3 Hallucination Protection

- `_TAILOR_SYSTEM_PROMPT` has two explicit constraints ("ONLY use" + "NEVER fabricate"), rules are effective
- `extract_jd` only has no-fabrication constraint for salary field, none for other fields
- **No automated tests verify the actual effectiveness of hallucination protection rules**

### 5.4 Prompt Consistency (REQ-052)

`_FINE_SYSTEM_PROMPT` text is fully identical (match_agent vs resume_optimizer), REQ-052 satisfied.

However, behavioral divergence exists:

| Difference | match_agent | resume_optimizer |
|------------|-------------|------------------|
| Exception fallback score | `compatibility_score: 1` | `compatibility_score: 0` |

### 5.5 AI Test Coverage

| Test Category | Coverage |
|---------------|----------|
| Functional tests (API calls/degradation) | 7/9 (78%) |
| Semantic quality tests | 0/9 (0%) |
| Hallucination detection tests | 0/2 (0%) |

### 5.6 Tech Design 2.5 Gap Status

| Gap | Priority | Current Status |
|-----|----------|----------------|
| Fine Prompt missing score range declaration | P1 | Not fixed |
| REQ-052 verification should use full-text assertEqual | P1 | Not fixed |
| `batch_re_score` fallback value 0 vs 1 inconsistency | P3 | Not fixed |
| Hallucination black-box test framework | P2 | Not fixed |
| Scoring consistency test (T=0.0) | P3 | Not fixed |

All 5 gaps were documented in tech-design 2.5; none implemented as of this audit.

---

## Overall Action Items

### Must Fix (Blocking Phase 4 Pass)

| # | Source | Action | File |
|---|--------|--------|------|
| 1 | Doc Sync | Update REQ-056 documentation: Semaphore(3) -> sequential batch processing model (or add Semaphore implementation in code) | REQUIREMENTS.md, ARCHITECTURE.md, brd.md |
| 2 | Doc Sync | Update ARCHITECTURE.md rpm values: job_agent uses 10 RPM, match/resume use 13 RPM | ARCHITECTURE.md |
| 3 | API Debugger | Add synchronous rate limiting before company_agent Gemini calls (`time.sleep(6)` or synchronous limiter) | agents/company_agent.py |

### Recommended Fixes (Non-blocking, impacts quality)

| # | Source | Action | Priority |
|---|--------|--------|----------|
| 4 | Eval Engineer | Append explicit 1-100 score range declaration to `_FINE_SYSTEM_PROMPT` (sync both files) | P1 |
| 5 | Eval Engineer / Test Analyzer | Add `_FINE_SYSTEM_PROMPT` full-text assertEqual test (replace substring matching) | P1 |
| 6 | Test Analyzer | Add code-structural regression test for BUG-28 | P1 |
| 7 | Eval Engineer | Unify `re_score`/`batch_re_score` fallback value from 0 to 1 | P3 |
| 8 | Eval Engineer | Change `CoarseItem.score` Field description from "0-100" to "1-100" | P1 |
| 9 | Doc Sync | BRD REQ-062 variable name `ATS_ROUTING` -> `ATS_PLATFORMS` | P3 |
| 10 | Doc Sync | Add `AUTO_ARCHIVE_THRESHOLD` to ARCHITECTURE.md config.py comments | P3 |
| 11 | Bug Tracker | Register 5 newly discovered P3 exception swallowing/missing log issues as BUG-56~60 | P3 |
| 12 | API Debugger | Add warning log for Greenhouse/Lever API non-200 responses | P3 |
| 13 | Test Analyzer | Add independent unit test for `_format_jd_for_coarse()` | P2 |
| 14 | Test Analyzer | Add minimal integration tests for 4 Agent `main()` functions | P2 |

---

## Review Conclusion

**Overall Rating: Conditional Pass**

**Pass Conditions**:
1. Fix 3 must-fix items (documentation consistency + company_agent rate limiting)
2. PM functional acceptance sign-off

**Project Quality Assessment**:
- Test suite is robust (485 test cases 100% passing, 7.74s, fully mocked)
- Bug management is thorough (55/55 fixes in place, zero TODO comments)
- API integration is reliable (multi-layer protection: Key rotation + rate limiting + retry backoff)
- Documentation completeness is high (main deviations are documentation not updated after implementation evolution)
- AI output quality testing is a known structural gap (documented in tech-design), not an oversight

---

## 6. PM Functional Acceptance Report

**Assessor**: PM Agent (product-manager)
**Assessment Date**: 2026-03-17

### 6.1 BRD Acceptance Criteria Item-by-Item Check

| Check Item | BRD Section 8 Target | Actual Result | Determination |
|------------|---------------------|---------------|---------------|
| Functional requirement implementation rate | 63/63 REQ all `[x]` | 63/63 all `[x]` | Pass |
| Bug fix rate | 55/55 all fixed | P0/P1/P2/P3 pending fixes all 0, code verification all in place | Pass |
| Test pass rate | 485+ test cases 0 failures | 485 passed / 0 failed / 0 skipped, 7.67s | Pass |
| ATS platform coverage | Major ATS | 6 platforms fully covered (Greenhouse/Lever/Ashby + Workday/Google/Tesla) | Pass |
| End-to-end data flow | 4 Agent data flow clear | 5 Excel Schemas zero deviation from code HEADERS | Pass |

**Functional completeness: 5/5 acceptance criteria all met.**

### 6.2 PM Assessment of QA "Must Fix" Items

| # | Issue | PM Assessment | Blocks v1.0? |
|---|-------|---------------|--------------|
| 1 | REQ-056 Semaphore documentation inconsistent with code | Documentation correction work, functionality running correctly | Non-blocking |
| 2 | job_agent rpm=10 vs documented 13 | Code is more conservative, documentation is wrong | Non-blocking |
| 3 | company_agent no rate limiting | Current scale (~14 calls/run) below 15 RPM limit, low probability of triggering | Conditionally non-blocking (v1.1 P1 fix) |

### 6.3 Product Risk Assessment

- **Functional completeness risk**: Low (63 REQ + 55 Bug all completed)
- **Data quality risk**: Low to medium (Fine Prompt score range declaration missing is known tech debt)
- **User experience risk**: Low (5 P3 exception swallowing issues do not affect normal operation)

### 6.4 Acceptance Decision

**Sign-off Status: Conditional Pass (Conditional Sign-off)**

**Conditions to address before Phase 5**:

| # | Content | Assignee |
|---|---------|----------|
| C-01 | Correct REQ-056 implementation description (Semaphore -> sequential batch) | Engineer Lead |
| C-02 | Correct ARCHITECTURE.md job_agent RPM value (13 -> 10) | Engineer Lead |
| C-03 | Add synchronous rate limiting to company_agent | Engineer Lead (v1.1 P1) |

**Deferred to v2.0**: AI semantic quality test framework, scoring idempotency verification, main() integration tests, BUG-56~60
**v1.1 Handling**: Fine Prompt score range declaration, CoarseItem.score description correction, BUG-28 regression test

### 6.5 PM Sign-off Statement

Based on the facts that BRD Section 8 all 5 acceptance criteria passed in actual testing, 485 unit tests 100% passing, 55 Bug fixes in place, and 5 Excel Schemas with zero deviation, PM signs off with **Conditional Pass**. Conditions are to correct documentation consistency deviations before Phase 5, and fix company_agent rate limiting in v1.1. Final launch decision to be made by TPM and User.
