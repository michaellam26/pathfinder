# CHANGELOG

## 2026-03-17

### Rename: Simplified Excel Tab Names (Removed Redundant "AI_" Prefix)

- `AI_Company_List` → `Company_List`, `AI_Company_Without_TPM` → `Company_Without_TPM`
- **Migration compatibility**: `get_or_create_excel()` added sheet rename migration logic; existing Excel files automatically rename old tabs
- **Code updates**: Global replacement across `shared/excel_store.py`, `agents/company_agent.py`, `tests/test_excel_store.py`
- **Documentation updates**: REQUIREMENTS.md, ARCHITECTURE.md, brd.md, observability.md, schema-validator.md

### New: Observability Agent + Cost Agent

- **`.claude/agents/observability.md`** — Added Observability Agent (sonnet, Quality layer)
  - Mode A: Run Report — Global overview of metrics across 4 Agents (company count, JD count, score distribution, optimization effectiveness)
  - Mode B: Quality Drift Detection — Score distribution shift, JD extraction degradation, AI TPM classification drift, Score Delta trends
  - Mode C: Anomaly Detection — All-zero scores, score clustering, orphan records, Excel corruption, Schema mismatches
- **`.claude/agents/cost.md`** — Added Cost Agent (sonnet, Quality layer)
  - Mode A: Token Usage Estimation — Gemini/Tavily/Firecrawl call counts and token consumption estimates per Agent
  - Mode B: API Quota Check — Gemini RPD/RPM/TPM, Tavily monthly search count, Firecrawl credits quota status
  - Mode C: Optimization Recommendations — Prompt length optimization, batch size tuning, pre-filter threshold analysis, cache hit rate evaluation
- **Documentation updates** — CLAUDE.md (9 → 11 agents), ARCHITECTURE.md (layered diagram + agents table + file structure)

## 2026-03-16

### Bug Fixes: Full Code Audit (BUG-28~55)

- **BUG-28 (P1)**: Fixed retry phase executing outside `AsyncWebCrawler` context, causing crawler to become inactive
- **BUG-29 (P2)**: `_GeminiKeyPool` empty key list protection (via inheriting `_GeminiKeyPoolBase`)
- **BUG-30 (P2)**: Added missing `wb.close()` to `_print_top_results()`
- **BUG-31 (P3)**: Unified duplicate `_GeminiKeyPool` subclasses across 4 agents to `_GeminiKeyPoolBase` alias
- **BUG-32 (P0)**: `_scrape_tesla_jd` imported incorrect `Firecrawl` class name; corrected to `FirecrawlApp`
- **BUG-33 (P0)**: `d.get("requirements", [])` still returns `None` when Gemini returns `null`; changed to `(d.get(...) or [])`
- **BUG-34 (P1)**: `gemini_pool` created a new Client on each call; changed to per-key cached `_clients` dictionary
- **BUG-35 (P1)**: `rotate()` incremented one-way without wrapping; changed to `% len` round-robin
- **BUG-36 (P1)**: `_idx`/`rotate()` had no lock protection; added `threading.Lock`
- **BUG-37 (P1)**: `_firecrawl_map` synchronously blocked the event loop; call site changed to `asyncio.to_thread`
- **BUG-38 (P1)**: Semaphore+RateLimiter stacking caused actual RPM to exceed limits; moved Gemini calls outside Semaphore block
- **BUG-39 (P2)**: `_load_jd_markdown` did not read `_structured.md`; changed to prioritize structured version
- **BUG-40 (P2)**: Python operator precedence error (`or "" if cond else ""`); added parentheses at 4 locations
- **BUG-41 (P2)**: Stage 1/2 had independent `_RateLimiter` instances; changed to module-level shared `_GEMINI_LIMITER`
- **BUG-42 (P2)**: `asyncio.gather(return_exceptions=True)` silently swallowed 429 errors; added quota warning
- **BUG-43 (P2)**: `_scrape_google_jd` was missing `formats=["markdown"]`
- **BUG-44 (P2)**: Tavily quota exhaustion was not handled separately; added 402/429/quota detection and warning
- **BUG-45 (P2)**: `upsert_companies` only wrote 5 columns; expanded to 9 columns covering all COMPANY_HEADERS
- **BUG-46 (P2)**: `batch_update_jd_timestamps` docstring had inconsistent column number
- **BUG-47 (P2)**: `data_quality` field was not included in the `JobDetails` Pydantic model
- **BUG-48 (P2)**: `[{}] * N` created shared references; changed to list comprehension
- **BUG-49 (P2)**: `discover_ai_companies` directly modified the caller's set; changed to local copy
- **BUG-50 (P3)**: `_print_summary` hardcoded column numbers changed to `TAILORED_HEADERS.index()` dynamic lookup
- **BUG-51 (P3)**: `_print_top_results` hardcoded column numbers changed to `MATCH_HEADERS.index()` dynamic lookup
- **BUG-52 (P3)**: 7 JD_Tracker functions with hardcoded column numbers changed to `_JD_COL` mapping
- **BUG-53 (P3)**: `_fmt_addr` was repeatedly defined inside the loop; moved before the loop
- **BUG-54 (P3)**: Added `_KEY_POOL` None guards across 4 agents (9 functions)
- **BUG-55 (P2)**: `WITHOUT_TPM_HEADERS` expanded from 5 columns to 7 columns + migration logic

### New: Job Agent Enhancements (REQ-058~063)

- **REQ-058 (P1)**: Ashby upgraded to API_ATS — Uses public Job Posting API for structured JSON retrieval
- **REQ-059 (P1)**: Soft 404 hardening + JD positive signal validation — Expanded keyword set + positive feature word threshold detection
- **REQ-060 (P2)**: JD field completeness grading — `_assess_jd_quality()` + `Data Quality` column
- **REQ-061 (P2)**: Workday URL format expansion — Support for formats without `wd` prefix
- **REQ-062 (P3)**: ATS declarative routing table refactor — `ATS_PLATFORMS` dict + `_match_ats()` router
- **REQ-063 (P3)**: Auto-archive companies with no TPM positions — `No TPM Count`/`Auto Archived` columns + 5 management functions

### Improvements: Gemini Pool Refactor

- **`shared/gemini_pool.py`** — Unified to `_GeminiKeyPoolBase` base class
  - `genai_mod` parameter enables unified `generate_content` method
  - `_clients` dictionary caches Client instances per key
  - `rotate()` changed to round-robin (`% len`)
  - `threading.Lock` protects `_idx`/`rotate()`/`_get_client()`
  - Subclass definitions in 4 agents changed to `_GeminiKeyPool = _GeminiKeyPoolBase` alias

### New: SDLC Workflow Framework (TPM Agent + Coordination Layer)

- **`.claude/agents/tpm.md`** — Added TPM Agent (opus): Coordinates full SDLC workflow
  - 7 operation modes: kickoff / review-brd / review-design / coordinate / status / launch / fast-track
  - Document-driven communication, `status.md` as single source of truth
  - Escalation mechanism: L1 Info → L2 Decision → L3 Business [ESCALATE] → L4 Blocker [BLOCKED]
- **`.claude/agents/product-manager.md`** — PM Agent added 2 new modes
  - Mode F: BRD Writing (research feasibility, generate structured BRD draft)
  - Mode G: Testing Sign-off (evaluate test results against BRD success criteria, output sign-off)
  - description updated to "Research, feasibility analysis, BRD writing, testing sign-off"
- **`docs/sdlc/`** — SDLC project documentation directory
  - `index.md` project index table
  - Each project in its own directory `PRJ-xxx-<name>/` (status.md, brd.md, tech-design.md, reviews/)
- **`.claude/skills/`** — 3 new SDLC Skills
  - `/sdlc-init` — Initialize project (assign ID, create directory and templates)
  - `/sdlc-status` — View project status (single project details or global overview)
  - `/sdlc-review` — Trigger stage-specific reviews (brd/design/testing/launch)
- **SDLC 5-phase workflow** — BRD → Tech Design → Implementation → Testing → Launch
  - Roles: User(Business Owner) + PM + TPM + Engineer Lead(Claude Code) + QA Team(6 agents)
- **Architecture layer updates** — Planning layer + Coordination layer(new) + Quality layer + Operations layer
- **Documentation updates** — ARCHITECTURE.md v1.3, CLAUDE.md (8 agents + 8 skills), CHANGELOG.md

### New: Development Tooling Layer (Custom Agents + Skills)

- **`.claude/agents/`** — Added 7 Custom Agents (development assistance, read-only analysis)
  - `product-manager` (sonnet) — Requirements analysis, progress tracking, impact assessment, decision support
  - `agent-reviewer` (opus) — Code quality review, Prompt design, cross-Agent consistency
  - `schema-validator` (sonnet) — Excel schema and data contract validation
  - `test-analyzer` (sonnet) — Test failure analysis, coverage gap identification
  - `api-debugger` (sonnet) — Gemini/Tavily/Firecrawl/ATS API diagnostics
  - `doc-sync` (sonnet) — Code-to-documentation drift detection
  - `bug-tracker` (sonnet) — BUGS.md status verification, new bug scanning, regression test recommendations
- **`.claude/skills/`** — 5 operational execution Skills (pipeline, run-agent, test-all, test-one, check-env)
- **Architecture layers**: Planning layer(PM agent) → Quality layer(6 analysis agents) → Operations layer(5 skills)
- **Documentation updates** — ARCHITECTURE.md v1.2, CLAUDE.md, CHANGELOG.md

### Improvements: Score Floor + Coarse Prompt + Company Dedup

- **agents/match_agent.py** — Changed Gemini scoring minimum to 1
  - JDs scored by Gemini get a minimum score of 1; pre-filter rejected JDs remain at 0
  - `batch_coarse_score` default and fallback both changed to 1, return value `max(1, score)`
  - `evaluate_match` returns complete JSON (score=1) on exception, no longer returns empty `{}`
  - `main()` coarse_scores default changed to 1, fine eval parsed score clamped to 1
  - `resume_optimizer.get_scored_matches()` filters `score >= 0` to retrieve all match records for optimization

- **agents/match_agent.py** — Improved Coarse Scoring Prompt
  - Extracted inline prompt to `_COARSE_SYSTEM_PROMPT` module-level constant
  - Added 3 calibration anchor sections (1-30 weak match / 31-60 moderate / 61-100 strong match)
  - Listed 3 key scoring factors (AI/ML relevance, TPM function match, seniority match)

- **agents/company_agent.py** — Improved company name deduplication
  - Added `_normalize_company_name()`: lowercase + strip + remove common suffixes (Inc/Corp/LLC/Ltd/Technologies/Labs/AI/Platform/Systems/Computing)
  - Added `_is_duplicate_company()`: normalized matching + bidirectional startswith check (minimum >= 4 characters)
  - Replaced original exact-match dedup filter

- **tests/** — Added 21 test cases
  - `test_match_agent.py`: +2 score clamp tests, +3 prompt content tests, modified 3 existing assertions
  - `test_company_agent.py`: +8 normalization tests, +8 duplicate detection tests

### New Feature: Resume Optimizer Agent
- **agents/resume_optimizer.py** — 4th Agent, tailors and rewrites resume for each matched JD
  - Loads all match records with score >= 0, calls Gemini to generate tailored resume for each JD
  - Tailored resume only reorganizes/rewrites existing content, never fabricates experience (strict ATS optimization rules)
  - Re-scores using the same `_FINE_SYSTEM_PROMPT` as Match Agent, ensuring fair before/after comparison
  - Tailored resumes saved to `tailored_resumes/{resume_id}/{url_md5}.md`
  - Supports incremental updates: skips already-optimized pairs with unchanged resume_hash
  - Concurrency control: `asyncio.Semaphore(3)` + `_RateLimiter(rpm=13)`
- **shared/excel_store.py** — Added `Tailored_Match_Results` worksheet support
  - Added `TAILORED_HEADERS` constant (11 columns)
  - Added `get_scored_matches()` — Reads all match records with score >= 0
  - Added `get_tailored_match_pairs()` — Reads already-optimized records (for incremental skip)
  - Added `batch_upsert_tailored_records()` — Batch writes tailored match results
  - `get_or_create_excel()` auto-creates/migrates `Tailored_Match_Results` sheet
- **tests/** — Added `test_resume_optimizer.py` + extended `test_excel_store.py`
- **Documentation updates** — REQUIREMENTS.md (REQ-049~057), ARCHITECTURE.md (v1.1), CLAUDE.md

## 2026-03-14

### Bug Fixes
- **BUG-27 (P1)**: Fixed incomplete JD records not being reprocessed by the main loop
  - `get_jd_url_meta` originally only excluded rows where company was empty/"N/A"/"JSON ERROR"; incomplete records with valid company but missing location/tech/resp still entered `fresh_set`, main loop skipped them, relying only on retry phase
  - Fix: `get_jd_url_meta` now also reads location/tech/resp; if values are in `_JD_MISSING`, they are skipped and not placed into `fresh_set`, ensuring the main loop rediscovers and processes these URLs
  - Also fixed `retry_one` validation: if extracted location/tech/resp are all empty, old records are not overwritten (prevents infinite retry loop writing "None")
  - 122 tests all passed

## 2026-03-12

### Bug Fixes
- **BUG-05 (P1)**: Fixed Career URL write row misalignment in `run_phase_1_5`
  - Added `get_company_rows_with_row_num()` returning `(excel_row, row_data)` tuples with actual Excel row numbers
  - `update_company_career_url` parameter changed from 0-based list index to actual Excel row number (`excel_row`), eliminating implicit `+2` offset convention
  - `run_phase_1_5` now uses `get_company_rows_with_row_num()`, ensuring Career URL is not written to wrong company row when empty rows exist
  - Added 2 regression tests (`TestBug05CareerUrlRowAlignment`), 162 tests all passed

- **BUG-09 (P1)**: Converted network-dependent tests in `tests/test_company_agent.py` to use mocks
  - `TestValidateCareerUrl`, `TestCheckAtsSlug`, `TestFindAtsUrl` test classes originally made real HTTP requests
  - Fix: Replaced with `unittest.mock.patch` for `requests.get` and `_check_ats_slug`, eliminating network dependency and real API quota consumption
  - Also fixed `test_openai_careers` (OpenAI returning 403 caused false failure); behavior is now deterministic with mocks
  - Also mocked `time.sleep` to eliminate artificial delay in `_find_ats_url`; test execution time reduced from ~6.8s to ~0.34s
  - 164 tests all passed

- **BUG-12 (P2)**: Fixed workbook handle leaks across entire `shared/excel_store.py`
  - Added `try/finally: wb.close()` to all 19 functions, including both paths in `get_or_create_excel`
  - Added `TestBug12WorkbookClose` (18 test cases), 61 related tests all passed

- **BUG-18 (P2)**: Missing `jd_cache/` directory in `.gitignore`
  - Added `jd_cache/` to `.gitignore` to prevent JD cache files from being committed to VCS

- **BUG-19 (P2)**: Missing core dependencies in `CLAUDE.md` Key Libraries table
  - Added `pycountry`, `openpyxl`, `tavily-python` with usage descriptions

- **BUG-21 (P3)**: Duplicate `hashlib` import in `match_agent.py` (cleaned up alongside BUG-07)
- **BUG-25 (P3)**: Dead code variable `already_ats` in `company_agent.py:528-531` cleaned up

- **BUG-04 (P1)**: `process_company()` URL concurrent deduplication (documented)
- **BUG-07**: `match_agent.py` duplicate `hashlib` import (documented)
- **BUG-08**: Cache round-trip test validity fix (documented)
- **BUG-10**: `_GeminiKeyPool` empty key list IndexError (documented)
- **BUG-11**: CLAUDE.md Python version documentation correction (documented)

## 2026-03-12 (this session)

### Bug Fixes
- **BUG-24 (P3)**: Misleading module docstring in `tests/test_company_agent.py`
  - Original docstring stated "real HTTP check", "live ATS API probe", but BUG-09 had already mocked all HTTP calls
  - Updated module docstring to accurately describe that all HTTP calls are mocked, and added integration test instructions (`INTEGRATION_TEST=1`) and `@unittest.skipUnless` usage guidance

- **BUG-26 (P3)**: `tests/test_job_agent.py` pycountry mock contained only 1 state
  - Original mock only had California, causing IN/OR/DE/ME/OK tests to "falsely pass" (these state codes were not in the mock at all)
  - Replaced with complete mock of all 50 states + DC; BUG-03 regression tests in `TestIsUsSegment` now genuinely validate the fix logic

- **BUG-20 (P2)**: Added missing CHANGELOG historical records
  - Added CHANGELOG entries for BUG-12/18/19/21/25; documentation now accurately reflects historical fix status
