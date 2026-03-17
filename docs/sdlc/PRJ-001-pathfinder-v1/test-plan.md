# QA Test Plan — PRJ-001 PathFinder v1.0

**Version**: 1.0
**Date**: 2026-03-17
**Author**: QA Lead
**Phase**: Phase 4 — Testing & QA (Redo)

---

## 1. Test Scope

### In-Scope

| Category | Coverage Target | Test File |
|------|---------|---------|
| BRD §8 end-to-end acceptance | Complete data flow of 4 Agent `main()` orchestration processes | `test_acceptance.py` |
| REQ coverage gaps | REQ-009/025/032/054 — Requirements flagged as having no direct tests in first review | `test_acceptance.py` |
| BUG regression | BUG-28 (retry block inside crawler context) — Flagged as having no regression test in first review | `test_acceptance.py` |
| Cross-Agent data flow | Company->Job->Match->Optimizer Excel data contract validation | `test_acceptance.py` |
| Function coverage gaps | `_format_jd_for_coarse()` — Flagged as having no independent test in first review | `test_acceptance.py` |
| AI output quality | Prompt consistency (REQ-052), fallback value consistency, Pydantic schema, hallucination guard structure, scoring floor | `test_ai_quality.py` |

### Out-of-Scope

- Real API call tests (all mocked)
- Performance/load testing
- UI/visualization testing (project has no frontend)
- Product code modifications (only writing test code and documentation)

---

## 2. Testing Strategy

### 2.1 Framework

- **Test Framework**: `unittest` (consistent with existing 485 cases)
- **Mock Framework**: `unittest.mock` (`patch`, `MagicMock`, `AsyncMock`)
- **Temporary Files**: `tempfile.NamedTemporaryFile` / `tempfile.mkdtemp`

### 2.2 Mock Pattern

Continuing existing test conventions:

1. **Heavy dependency pre-injection**: `sys.modules` pre-injection of `google`/`google.genai`/`dotenv`/`firecrawl`/`crawl4ai`/`pycountry`/`tavily`
2. **API call mock**: `@patch` decorators mock Gemini/Tavily/Firecrawl/HTTP calls
3. **Excel isolation**: Use `tempfile` to provide isolated Excel files, operated through real `excel_store.py` API

### 2.3 End-to-End Test Strategy

- Directly call each Agent's `main()` function
- All external dependencies mocked (Gemini/Tavily/Firecrawl/Crawl4AI/HTTP/pycountry)
- Use real `shared/excel_store.py` to operate temporary Excel files
- Verification focus: data flow (Agent A writes -> Agent B reads), not AI output content

---

## 3. Scenario Classification & Priority

### P0 — BRD End-to-End + REQ Gaps (all must pass)

| Scenario ID | Test Class | Description | Coverage |
|---------|--------|------|------|
| A-01 | `TestCompanyAgentMain` | Company Agent main() writes to Company_List | BRD §8 Scenario 1 |
| A-02 | `TestCompanyAgentMain` | Verify MAX_TOTAL=200 cap | REQ-009 |
| A-03 | `TestJobAgentMain` | Job Agent main() writes to JD_Tracker | BRD §8 Scenario 2 |
| A-04 | `TestJobAgentMain` | FRESH_DAYS incremental skip | REQ-025 |
| A-05 | `TestMatchAgentMain` | Match Agent main() writes to Match_Results (coarse+fine) | BRD §8 Scenario 3 |
| A-06 | `TestMatchAgentMain` | Resume change triggers re-scoring | REQ-032 |
| A-07 | `TestResumeOptimizerMain` | Resume Optimizer main() writes to Tailored_Match_Results | BRD §8 Scenario 4 |
| A-08 | `TestResumeOptimizerMain` | resume_hash incremental skip | REQ-054 |
| A-09 | `TestEndToEndDataFlow` | Company->Job->Match cross-Agent data contract | BRD §8 End-to-End |

### P1 — BUG Regression + AI Quality (all must pass)

| Scenario ID | Test Class | Description | Coverage |
|---------|--------|------|------|
| B-01 | `TestJobAgentMain` | retry block executes inside crawler context | BUG-28 |
| Q-01 | `TestFinePromptConsistency` | match_agent vs resume_optimizer `_FINE_SYSTEM_PROMPT` full-text equality | REQ-052 |
| Q-02 | `TestFallbackValueConsistency` | Fallback value documentation | Eval Engineer finding |
| Q-03 | `TestHallucinationGuards` | Tailor prompt hallucination guard rule structural verification | Eval Engineer finding |
| Q-04 | `TestScoreClampBehavior` | Scoring floor behavior | Eval Engineer finding |

### P2 — Function Coverage Gaps

| Scenario ID | Test Class | Description | Coverage |
|---------|--------|------|------|
| F-01 | `TestFormatJdForCoarse` | `_format_jd_for_coarse()` normal/abnormal paths | Test Analyzer finding |

---

## 4. Pass Criteria

| Criterion | Target |
|------|------|
| Existing tests | 485 cases all pass (zero regression) |
| New acceptance tests | `test_acceptance.py` all pass |
| New AI quality tests | `test_ai_quality.py` all pass |
| No real API dependency | All mocked, runnable offline |
| No product code modification | Only new test files and documentation |

---

## 5. Test Deliverables

| Deliverable | Path |
|------|------|
| QA Test Plan | `docs/sdlc/PRJ-001-pathfinder-v1/test-plan.md` (this document) |
| Acceptance test cases | `tests/test_acceptance.py` |
| AI quality test cases | `tests/test_ai_quality.py` |
| Test Execution Report | `docs/sdlc/PRJ-001-pathfinder-v1/test-execution-report.md` |
| 5 Agent review report v2 | `docs/sdlc/PRJ-001-pathfinder-v1/reviews/testing-review-v2-2026-03-17.md` |
