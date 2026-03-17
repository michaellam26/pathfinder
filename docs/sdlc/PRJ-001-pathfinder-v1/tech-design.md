# Tech Design: PathFinder v1.0

**Project ID**: PRJ-001
**Author**: Engineer Lead (Claude Code)
**Status**: Completed (Backfill)
**Date**: 2026-03-17

---

## 0. Document Positioning

This document is the SDLC Phase 2 technical design and **does not repeat** content already in ARCHITECTURE.md.

- **System component diagram, Agent detailed descriptions, Excel Schema, external service dependencies** -> see [ARCHITECTURE.md](../../../ARCHITECTURE.md)
- **Complete functional requirements list (REQ-001 ~ REQ-063)** -> see [REQUIREMENTS.md](../../../REQUIREMENTS.md)
- **BRD business goals and acceptance criteria** -> see [brd.md](./brd.md)

This document supplements three topics from the SDLC perspective: **Implementation Task Breakdown**, **Testing Strategy**, and **Deployment & Runtime Plan**.

---

## 1. Implementation Task Breakdown

### 1.1 Module Dependency Graph

```
shared/config.py          <- No dependencies (constant definitions)
shared/rate_limiter.py     <- No dependencies (pure asyncio)
shared/gemini_pool.py      <- google-generativeai
shared/excel_store.py      <- openpyxl, shared/config.py

agents/company_agent.py    <- shared/excel_store, shared/gemini_pool, tavily, requests
agents/job_agent.py        <- shared/excel_store, shared/gemini_pool, shared/rate_limiter,
                              shared/config, tavily, firecrawl, crawl4ai, requests, pycountry
agents/match_agent.py      <- shared/excel_store, shared/gemini_pool, shared/rate_limiter
agents/resume_optimizer.py <- shared/excel_store, shared/gemini_pool, shared/rate_limiter
```

### 1.2 Implementation Order (Bottom-Up)

Implementation is ordered by 4-layer dependency relationships; modules within each layer can be developed in parallel:

| Layer | Module | Key REQ | Notes |
|------|------|----------|------|
| L0 Shared Foundation | `shared/config.py` | — | Constant definitions (MODEL, AUTO_ARCHIVE_THRESHOLD) |
| L0 Shared Foundation | `shared/rate_limiter.py` | REQ-042 | Token-bucket rate limiter |
| L0 Shared Foundation | `shared/gemini_pool.py` | REQ-017, 041, 057 | Key rotation base class |
| L1 Persistence | `shared/excel_store.py` | REQ-044~048 | 5-table Schema + CRUD + migration + corruption recovery |
| L2 Agent | `agents/company_agent.py` | REQ-005~016 | Depends on L0+L1 |
| L2 Agent | `agents/job_agent.py` | REQ-018~029, 058~063 | Depends on L0+L1, most complex Agent |
| L2 Agent | `agents/match_agent.py` | REQ-030~043 | Depends on L0+L1, requires JD_Tracker data |
| L2 Agent | `agents/resume_optimizer.py` | REQ-049~057 | Depends on L0+L1, requires Match_Results data |
| L3 Tooling | `.claude/agents/` (11) | — | Development assistance, no runtime code dependency |
| L3 Tooling | `.claude/skills/` (8) | — | Operations automation, invokes Agents and tests |

### 1.3 Task Checklist (Grouped by Agent)

#### shared/ — Shared Modules (8 tasks)

| # | Task | Corresponding REQ | File |
|---|------|----------|------|
| S-01 | Implement Token-bucket async rate limiter (13 RPM) | REQ-042 | `rate_limiter.py` |
| S-02 | Implement Gemini Key rotation base class (Client caching, round-robin, thread-safe) | REQ-017/041/057 | `gemini_pool.py` |
| S-03 | Implement Excel persistence layer: 5-table creation + Schema initialization | REQ-044/045 | `excel_store.py` |
| S-04 | Implement Schema migration (auto-backfill missing columns) | REQ-046 | `excel_store.py` |
| S-05 | Implement file corruption recovery (.bak backup + rebuild) | REQ-047 | `excel_store.py` |
| S-06 | Implement CRUD function set (upsert/batch/read) | REQ-048 | `excel_store.py` |
| S-07 | Implement archive management functions (5 functions) | REQ-063 | `excel_store.py` |
| S-08 | Define MODEL / AUTO_ARCHIVE_THRESHOLD constants | REQ-063 | `config.py` |

#### company_agent — Company Discovery (6 tasks)

| # | Task | Corresponding REQ |
|---|------|----------|
| C-01 | Tavily 7-query batch search + 4-category distribution | REQ-006/007 |
| C-02 | Gemini company info extraction (name/domain/description), no URL generation | REQ-008/010 |
| C-03 | Multi-strategy Career URL finding (5-level fallback) | REQ-011/012/013 |
| C-04 | Company name deduplication (normalized + bidirectional startswith check) | REQ-005/009 |
| C-05 | Phase 1.5: ATS URL upgrade (Greenhouse/Lever slug probing + Workday hardcoded) | REQ-014/015/016 |
| C-06 | Excel upsert (Company_List write) | REQ-002 |

#### job_agent — Job Discovery (10 tasks)

| # | Task | Corresponding REQ |
|---|------|----------|
| J-01 | ATS declarative routing table (ATS_PLATFORMS dict + _match_ats) | REQ-062 |
| J-02 | Path A: Greenhouse/Lever/Ashby API job listing retrieval | REQ-018/058 |
| J-03 | Path B: Firecrawl + Crawl4AI crawler path | REQ-019 |
| J-04 | TPM keyword filtering + North America location filtering | REQ-020 |
| J-05 | JD scraping + Markdown caching + MD5 hashing | REQ-021/024 |
| J-06 | Soft 404 detection + JD positive signal validation | REQ-022/059 |
| J-07 | Gemini JD structured extraction + field completeness grading | REQ-023/060 |
| J-08 | Incremental skip (unchanged hash + FRESH_DAYS) + retry mechanism | REQ-025/026 |
| J-09 | Batch upsert JD_Tracker + Company_List count update | REQ-027/028 |
| J-10 | Auto-archive companies without TPM jobs | REQ-063 |

#### match_agent — Resume Matching (5 tasks)

| # | Task | Corresponding REQ |
|---|------|----------|
| M-01 | Resume loading + MD5 hashing + expiration detection | REQ-030/031/032 |
| M-02 | Stage 1: Keyword pre-filter (AI tech term overlap < 4 -> score=0) | REQ-033 |
| M-03 | Stage 1: Gemini batch coarse screen (batch 10, 1-100 score) | REQ-034 |
| M-04 | Stage 2: Gemini fine evaluation Top 20% (4-dimension weighted) | REQ-035/036/037/038 |
| M-05 | Batch upsert Match_Results + console Top 5 output | REQ-039/040 |

#### resume_optimizer — Resume Optimization (4 tasks)

| # | Task | Corresponding REQ |
|---|------|----------|
| R-01 | Load match records (score >= 0) + incremental skip (resume_hash) | REQ-049/054/055 |
| R-02 | Gemini tailored resume rewrite (no fabricated experience) | REQ-050 |
| R-03 | Save tailored resumes to tailored_resumes/ + Gemini re-scoring | REQ-051/052 |
| R-04 | Batch upsert Tailored_Match_Results + console summary | REQ-053 |

---

## 2. Testing Strategy

### 2.1 Test Layers

```
┌──────────────────────────────────────────────┐
│       Manual End-to-End Verification          │  4 Agents sequential run, verify Excel data flow
│              (No automation)                  │
├──────────────────────────────────────────────┤
│     Integration Tests (INTEGRATION_TEST=1)    │  Real HTTP/API calls (manual trigger on demand)
├──────────────────────────────────────────────┤
│      Unit Tests (485+ cases, all mocked)      │  Core test layer, CI level
└──────────────────────────────────────────────┘
```

### 2.2 Unit Test Coverage

| Test File | Covered Module | Case Count | Key Test Scope |
|----------|----------|--------|-------------|
| `tests/test_excel_store.py` | `shared/excel_store.py` | ~160 | 5-table CRUD, Schema migration, corruption recovery, handle leak (BUG-12), archive management |
| `tests/test_company_agent.py` | `agents/company_agent.py` | ~50 | Company name dedup, Career URL verification, ATS slug probing, Phase 1.5 row alignment (BUG-05) |
| `tests/test_job_agent.py` | `agents/job_agent.py` | ~180 | ATS routing, location filtering (BUG-03), soft 404, JD quality grading, Workday URL, auto-archiving, pycountry full mock (BUG-26) |
| `tests/test_match_agent.py` | `agents/match_agent.py` | ~50 | Pre-filter, coarse screen batch, fine evaluation dimensions, Score clamp, Prompt content |
| `tests/test_resume_optimizer.py` | `agents/resume_optimizer.py` | ~45 | Tailored rewrite, re-scoring, incremental skip, concurrency control |

### 2.3 Mock Strategy

All external dependencies are fully mocked in unit tests, ensuring offline/CI runnability:

| External Dependency | Mock Approach |
|----------|----------|
| Gemini API | `patch` `google.generativeai`'s `GenerativeModel.generate_content` |
| Tavily API | `patch` `tavily.TavilyClient.search` |
| Firecrawl | `patch` `firecrawl.FirecrawlApp` |
| Crawl4AI | `patch` `crawl4ai.AsyncWebCrawler` |
| HTTP requests | `patch` `requests.get` / `httpx` |
| pycountry | Full 50 states + DC mock (after BUG-26 fix) |
| File system | `tmp_path` fixture / `tempfile.NamedTemporaryFile` |

### 2.4 Regression Tests

Among the 55 Bug fixes, key fixes have dedicated regression tests:

| Bug | Regression Test | Protection Target |
|-----|----------|----------|
| BUG-03 | `TestIsUsSegment` (13 cases) | Location filtering IN/OR/DE/ME ambiguity false positives |
| BUG-05 | `TestBug05CareerUrlRowAlignment` (2 cases) | Phase 1.5 row number misalignment |
| BUG-12 | `TestBug12WorkbookClose` (18 cases) | Excel file handle leak |
| BUG-27 | `TestRetryIncompleteRecords` | JD infinite retry loop |
| BUG-33 | null list TypeError test | Gemini returning null crash |

### 2.5 AI Output Quality Evaluation

The system contains 8 Gemini Prompts. Current tests cover the functional layer (9/9 = 100%), but the semantic quality layer has structural gaps (0/9 = 0%).

**Existing Coverage**:
- Prompt content existence tests (calibration anchors, hallucination guard rules, dimension weights)
- Abnormal fallback value tests (score clamp, empty dict protection)
- REQ-052 partial verification (`_FINE_SYSTEM_PROMPT` 4 substring matches)

**Identified Gaps & Improvement Plan**:

| Gap | Risk | Improvement Measure | Priority |
|------|------|----------|--------|
| `_FINE_SYSTEM_PROMPT` lacks explicit 1-100 score range declaration | Score inflation/deflation, asymmetric with Coarse Prompt | Append `Output compatibility_score as an integer between 1 and 100` to Prompt end (sync modification in match_agent + resume_optimizer) | P1 |
| REQ-052 verification imprecise | Two Agents' `_FINE_SYSTEM_PROMPT` could silently diverge from single-file modification | Add full-text `assertEqual` assertion to replace substring matching | P1 |
| `batch_re_score` fallback value is 0, inconsistent with `evaluate_match`'s fallback value of 1 | Score of 0 records may interfere with downstream filtering | Unify to 1 | P3 |
| No hallucination black-box tests | Tailored resumes may contain content not in original resume | Establish detection framework: fixed input -> mock output -> verify no new skills/numbers | P2 |
| No scoring consistency tests | Score stability for same input not verified | Repeated calls at T=0.0 for consistency check (integration test layer) | P3 |

**Remaining Bug Coverage Notes**: Among the 55 Bug fixes, section 2.4 above lists 5 key Bugs with dedicated regression tests. The remaining 50 fixes are indirectly covered through their module's unit tests (fix code paths are hit by existing test cases).

### 2.6 Test Execution

```bash
# Full test suite (recommended: run after every change)
source venv/bin/activate
python -m pytest tests/ -v

# Single module test
python -m pytest tests/test_job_agent.py -v

# Integration test (requires real API Keys, manual trigger)
INTEGRATION_TEST=1 python -m pytest tests/ -v -k integration

# Via Skill
/test-all          # Full suite
/test-one job      # Single module
```

---

## 3. Deployment & Runtime Plan

### 3.1 Runtime Environment

| Item | Requirement |
|------|------|
| Python | 3.11 (uses `str \| None`, `list[str]` and other 3.10+ syntax) |
| OS | macOS / Linux (Crawl4AI requires Playwright + Chromium) |
| Execution | Local command line, no containers/cloud platforms |
| Virtual Environment | `./venv` (pre-configured) |

### 3.2 Environment Initialization

```bash
# 1. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Playwright browser (Crawl4AI dependency)
playwright install chromium

# 4. Configure API Keys
cp .env.example .env
# Edit .env and fill in: GEMINI_API_KEY, GEMINI_API_KEY_2, TAVILY_API_KEY, FIRECRAWL_API_KEY

# 5. Verify environment
/check-env   # or python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('OK' if os.getenv('GEMINI_API_KEY') else 'MISSING')"
```

### 3.3 Execution Modes

#### Full Pipeline (Recommended for First Run)

```bash
source venv/bin/activate
python agents/company_agent.py    # -> Company_List
python agents/job_agent.py        # -> JD_Tracker + jd_cache/
python agents/match_agent.py      # -> Match_Results
python agents/resume_optimizer.py # -> Tailored_Match_Results + tailored_resumes/
```

Or via Skill: `/pipeline`

#### Incremental Run (Daily Use)

| Scenario | Command | Notes |
|------|----------|------|
| Discover new companies | `python agents/company_agent.py` | Excludes existing companies, only adds new ones |
| Refresh jobs | `python agents/job_agent.py` | MD5 hash + FRESH_DAYS skips unchanged JDs |
| After resume update | `python agents/match_agent.py` -> `python agents/resume_optimizer.py` | Resume MD5 change triggers full re-evaluation |
| Re-optimize only | `python agents/resume_optimizer.py` | Skips pairs with unchanged resume_hash |

### 3.4 Data File Layout

```
pathfinder/
├── pathfinder_dashboard.xlsx    # Main data file (5 tables, auto-created)
├── jd_cache/                    # JD Markdown cache (named by URL MD5)
│   ├── {md5}.md                 # Raw scraped content
│   └── {md5}_structured.md      # Gemini structured version
├── tailored_resumes/            # Tailored resume output
│   └── {resume_id}/
│       └── {url_md5}.md         # Tailored resume for specific JD
└── profile/                     # Candidate original resume (manually placed)
    └── *.md / *.txt
```

### 3.5 API Quota Budget

Based on Gemini free tier (15 RPM / 500 RPD / 250k TPM):

| Agent | Gemini Calls (estimated) | Time (estimated) |
|-------|----------------------|-------------|
| company_agent | ~50 (company extraction) | ~4 minutes |
| job_agent | ~100-200 (JD structured extraction) | ~10-15 minutes |
| match_agent | ~30 (coarse screen batch) + ~20-40 (fine evaluation) | ~5-8 minutes |
| resume_optimizer | ~40-80 (tailor + re-score, 2 calls per JD) | ~6-12 minutes |
| **Total** | **~240-370 RPD** | **~25-40 minutes** |

Within the 500 RPD limit, a single full run is safely manageable. Incremental runs typically consume only 10-50 RPD.

### 3.6 Failure Recovery

| Failure | Auto-Recovery Mechanism | Manual Action |
|------|-------------|---------|
| Gemini 429 quota exhaustion | Auto-rotate to GEMINI_API_KEY_2 | Wait for daily quota reset |
| Tavily 402 quota exhaustion | Detect and early-terminate subsequent queries, output warning | Wait for monthly quota reset |
| Firecrawl 429 | 3 retries + exponential backoff (30s x attempt) | Check credits balance |
| Excel file corruption | Auto .bak backup + recreate empty file | Recover data from .bak |
| JD extraction failure | data_quality=failed, auto-retry on next run | No intervention needed |
| Website anti-crawling 403 | Crawl4AI Playwright rendering / hardcoded ATS overrides | Manually update KNOWN_CAREER_URLS |

---

## 4. Technical Risks & Mitigation (Implementation Perspective)

| Risk | Impact | Mitigation | Status |
|------|------|----------|------|
| Gemini API 429 quota exhaustion | High: full run interrupted | Multi-Key rotation (round-robin + 429 auto-fallback); Token-bucket 13 RPM rate limiting; Semaphore(3) concurrency control; quota budget 240-370 / 500 RPD | Mitigated |
| Tavily API 402 quota exhaustion | Medium: company discovery interrupted | Detect 402/429/quota error codes and early-terminate subsequent queries, output user warning (BUG-44) | Mitigated |
| Firecrawl 429 quota exhaustion | Medium: crawler path disabled | 3 retries + exponential backoff (429: 30s x attempt, others: 5s x attempt) (BUG-17) | Mitigated |
| Career site anti-crawling 403 / dynamic rendering | Medium: JD scraping failure | Crawl4AI + Playwright JS rendering; hardcoded ATS overrides for special companies; Firecrawl as fallback | Mitigated |
| Gemini model version retirement | High: entire system unavailable | MODEL constant centrally managed in `shared/config.py`, change one place to switch globally; currently using `gemini-3.1-flash-lite-preview`, need to monitor Google model lifecycle announcements | Monitoring Required |
| Gemini batch coarse screen JSON parsing failure | Low: lost scoring | Each JD defaults to score=1 fallback, does not return empty dict (BUG-33 fix) | Mitigated |
| Excel concurrent write conflict | High: data corruption | Single-process load-modify-save + job_agent asyncio.Lock | Mitigated |
| New/changed ATS platform | Medium: jobs missed | Declarative routing table ATS_PLATFORMS + generic fallback (REQ-062) | Mitigated |
| Long-running file handle leak | Medium: system resource exhaustion | All 19 functions have try/finally wb.close() (BUG-12 fix) | Mitigated |
| Rate limiter and concurrency control stacking | Medium: actual RPM exceeds limit | Gemini calls moved out of Semaphore block (BUG-38 fix) | Mitigated |

### 4.1 Known Technical Debt

| ID | Issue | Impact | Current State | Improvement Plan |
|------|------|------|----------|----------|
| TD-01 | `excel_store.py`'s `get_match_pairs()`, `get_scored_matches()`, `get_tailored_match_pairs()` use hardcoded column numbers (3/8/9/6/11) instead of dynamic column mapping | Match_Results / Tailored_Match_Results Schema changes require manual column number sync | Functionally correct (column numbers match HEADERS), but inconsistent with JD_Tracker's `_JD_COL` dynamic mapping pattern | Define `_MATCH_COL = {h: i+1 for i, h in enumerate(MATCH_HEADERS)}` and `_TAILORED_COL` dynamic mappings to replace hardcoded indices |
| TD-02 | `load_resume()`, `_load_jd_markdown()`, `JD_CACHE_DIR` are duplicated in match_agent and resume_optimizer | Modifications require syncing two locations, increasing maintenance risk | Functionally correct, both definitions are consistent | Extract to `shared/` module for unified management |

---

## 5. Development Tooling Layer Design

### 5.1 Layered Architecture

```
Planning Layer ─── product-manager (sonnet)    Requirements analysis, BRD writing, testing sign-off
Coordination Layer ─── tpm (opus)              SDLC coordination, task decomposition, launch assessment
              /sdlc-init, /sdlc-status, /sdlc-review
Quality Layer ─── agent-reviewer (opus)        Code quality, Prompt design
              schema-validator (sonnet)    Excel Schema contracts
              test-analyzer (sonnet)       Test coverage, failure analysis
              api-debugger (sonnet)        API diagnostics
              doc-sync (sonnet)            Documentation drift detection
              bug-tracker (sonnet)         Bug management
              eval-engineer (sonnet)       AI output quality evaluation
              observability (sonnet)       Run reporting, drift detection
              cost (sonnet)               Token estimation, cost optimization
Operations Layer ─── /pipeline, /run-agent, /test-all, /test-one, /check-env
```

### 5.2 Inter-Agent Communication

- **Communication Mechanism**: Document-driven (not API calls), exchanging information through `docs/sdlc/PRJ-xxx/status.md` and `reviews/` directories
- **Data Contract**: All Agents share `pathfinder_dashboard.xlsx`'s 5-table Schema, uniformly managed by `shared/excel_store.py`
- **Read-Only Constraint**: All 11 Custom Agents are for analysis/reporting purposes, no code or data modifications

---

## Appendix: REQ to Task Mapping Matrix

| REQ Range | Task ID | Module |
|----------|----------|------|
| REQ-001~004 | Architecture-level (implicit) | Global |
| REQ-005~016 | C-01 ~ C-06 | company_agent |
| REQ-017 | S-02 | gemini_pool |
| REQ-018~029 | J-01 ~ J-09 | job_agent |
| REQ-030~043 | M-01 ~ M-05 | match_agent |
| REQ-044~048 | S-03 ~ S-06 | excel_store |
| REQ-049~057 | R-01 ~ R-04 | resume_optimizer |
| REQ-058~061 | J-02, J-06, J-07, J-01 | job_agent |
| REQ-062 | J-01 | job_agent |
| REQ-063 | S-07, S-08, J-10 | excel_store + config + job_agent |
