# BRD: PathFinder v1.0

**Project ID**: PRJ-001
**Author**: PM Agent
**Status**: Completed (Backfill)
**Date**: 2026-03-17

---

## 1. Background & Problem Statement

### Problem

The TPM (Technical Program Manager) job search process is highly fragmented. Candidates must manually perform the following repetitive tasks:

1. **Company Discovery**: Searching AI companies one by one, manually maintaining candidate lists, with difficulty systematically covering emerging AI startups and large model labs.
2. **Job Tracking**: Visiting each company's career page separately to identify TPM-related positions. Formats vary across platforms (Greenhouse / Lever / Ashby / Workday / custom pages), making batch processing impossible.
3. **Resume Matching**: Subjectively judging resume-to-JD match quality without quantitative metrics, making prioritization difficult.
4. **Resume Customization**: Manually rewriting resumes for each position, which is time-consuming and lacks quality verification — no way to know if the rewrite actually "matches better."

All of the above steps are executed manually. A single full-cycle operation takes several days and cannot be maintained at a reasonable frequency for continuous tracking.

### Solution

PathFinder is a multi-Agent AI automation system for TPM job seekers. The system encapsulates the four steps above into independent Agents that execute sequentially and automatically. Results are persisted to a local Excel dashboard, and candidates only need to focus on the final ranked results and tailored resumes.

### Key Constraints

- **Zero Cloud Dependency**: All data stored in local Excel files, no dependency on Google Sheets, Notion, or any cloud service.
- **Low-Cost Operation**: Based on Gemini free tier (15 RPM / 500 RPD), full run takes ~33 minutes with zero API cost.
- **Local Command Line**: Run directly via `python agents/<agent>.py`, no Colab or Docker needed.

---

## 2. Goals & Success Criteria

### Goals

| ID | Goal | Success Criteria |
|------|------|----------|
| G-01 | Automatically discover North American AI companies and maintain a candidate list | `Company_List` can accumulate up to 200 companies; single run adds at most 50 new ones; only US-headquartered companies included |
| G-02 | Automatically scrape TPM positions from major ATS platforms and structure them | Cover Greenhouse / Lever / Ashby (API) + Workday / Google / custom pages (crawler); JD structured fields include job title, company, location, salary, AI tech stack, responsibilities, whether AI TPM |
| G-03 | Quantify resume-to-JD match quality with priority ranking | Two-stage scoring (coarse batch of 10 + fine evaluation of Top 20%); 4-dimension weighted scoring (AI Technical Depth 30% / TPM Match 30% / Domain Relevance 20% / Growth Trajectory 20%); results written to `Match_Results` |
| G-04 | Automatically tailor resumes and quantitatively verify improvement | Generate tailored resume for each high-match JD; re-score after tailoring; Score Delta observable; results written to `Tailored_Match_Results` |
| G-05 | Data persistence and incremental updates | Single Excel file with 5 worksheets; support schema migration; JD content hash deduplication; resume hash change auto-triggers re-scoring; incremental runs only process new/changed records, skipping already-processed and non-expired data |

### Actual Delivery Results (Backfill Verification)

- 63 functional requirements (REQ-001 ~ REQ-063) all implemented, status `[x]`
- 55 Bugs (BUG-01 ~ BUG-55) all fixed, covering P0~P3 all priority levels
- 485+ unit tests passing (including regression tests)
- 4 Runtime Agents + 4 Shared Modules delivered
- 11 Custom Agents + 8 Skills development tooling layer fully built

---

## 3. Scope

### In-Scope

**Runtime System (the product itself):**

- `company_agent.py` — AI company discovery (Tavily search + Gemini extraction + multi-strategy Career URL finding + ATS URL upgrade)
- `job_agent.py` — TPM job discovery (ATS API path + crawler path) + JD structured extraction + JD field completeness grading + ATS declarative routing + auto-archiving
- `match_agent.py` — Two-stage resume matching scoring (keyword pre-filter + Gemini coarse screen + Gemini fine evaluation)
- `resume_optimizer.py` — Resume tailoring rewrite (Gemini generates tailored version + re-scoring verification)
- `shared/excel_store.py` — Unified persistence layer for 5 worksheets, with schema migration and corruption recovery
- `shared/gemini_pool.py` — Gemini API Key rotation (round-robin, Client caching, thread-safe)
- `shared/rate_limiter.py` — Token-bucket async rate limiter (13 RPM)
- `shared/config.py` — Shared constants (MODEL, AUTO_ARCHIVE_THRESHOLD)

**Development Tooling Layer (development assistance, read-only):**

- 11 Custom Agents (product-manager, tpm, agent-reviewer, schema-validator, test-analyzer, api-debugger, doc-sync, bug-tracker, eval-engineer, observability, cost)
- 8 Skills (sdlc-init, sdlc-status, sdlc-review, pipeline, run-agent, test-all, test-one, check-env)
- SDLC 5-phase workflow framework (`docs/sdlc/`)

**Test Suite:**

- `tests/` — 485+ unit tests covering all Agents and Shared Modules

### Out-of-Scope

- Web UI or visual dashboard (data stored in Excel, no frontend interface)
- Auto-submitting resumes or interacting with ATS systems (only reads public data, no writes)
- Multi-candidate support (current design is single-user with single `profile/` directory)
- Real-time stream processing (each Agent runs independently in batch, not a real-time pipeline)
- Cloud deployment or Colab environment (local command line only)
- Non-AI companies or non-TPM positions (product positioning clearly focused on AI company TPM job search)
- PathFinder 2.0 multi-model hybrid scoring architecture (excluded after DEC-001 evaluation)

---

## 4. Functional Requirements

### 4.1 System Architecture

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-001 | System consists of four independently runnable Agents: `company_agent`, `job_agent`, `match_agent`, `resume_optimizer` | P0 | Implemented |
| REQ-002 | Four Agents share a unified Excel persistence layer (`shared/excel_store.py`) | P0 | Implemented |
| REQ-003 | Persistence uses a local Excel file (`pathfinder_dashboard.xlsx`), no cloud service dependency | P0 | Implemented |
| REQ-004 | Each Agent can run independently (`python agents/<agent>.py`), no need to start other Agents | P0 | Implemented |

### 4.2 Company Agent — Company Discovery

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-005 | Read existing company list from Excel (both `Company_List` and `Company_Without_TPM` sheets) for deduplication exclusion | P0 | Implemented |
| REQ-006 | Search 7 preset queries via Tavily API, covering 4 company categories (Big Tech / AI Startups / AI Infrastructure / Large Model Labs) | P0 | Implemented |
| REQ-007 | Search distribution: Big Tech (AI) 50%, AI Startups 25%, AI Infrastructure/Compute 15%, Large Model Labs 10% | P1 | Implemented |
| REQ-008 | Use Gemini LLM to extract N new companies from search results (company name, AI domain classification, business description), URLs not generated by LLM | P0 | Implemented |
| REQ-009 | Single run discovers at most 50 new companies, `Company_List` total cap of 200 | P1 | Implemented |
| REQ-010 | Only include US-headquartered companies, strictly exclude non-US companies | P0 | Implemented |

### 4.3 Company Agent — Career URL Discovery

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-011 | Career URL found through the following strategies in order (not guessed by LLM): 1. Hardcoded known URLs -> 2. Tavily ATS-targeted search -> 3. Tavily general search -> 4. ATS slug probing -> 5. Company homepage crawling | P0 | Implemented |
| REQ-012 | Companies without a valid Career URL are skipped and not written to Excel | P1 | Implemented |
| REQ-013 | All Career URLs must pass HTTP verification (HTTP status < 400) to be accepted | P1 | Implemented |

### 4.4 Company Agent — ATS URL Upgrade (Phase 1.5)

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-014 | For companies in `Company_List` with non-ATS URLs, attempt to detect Greenhouse / Lever slugs and upgrade to ATS job board URLs | P1 | Implemented |
| REQ-015 | Maintain a hardcoded ATS override list for special companies (NVIDIA, Tesla, etc. using Workday), with highest priority | P1 | Implemented |
| REQ-016 | Upgraded URLs are written back to `Company_List` | P1 | Implemented |

### 4.5 API Reliability (Gemini Key Rotation)

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-017 | Support multiple Gemini API Keys (`GEMINI_API_KEY`, `GEMINI_API_KEY_2`), auto-rotate on 429 quota exhaustion | P0 | Implemented |

### 4.6 Job Agent — Job Discovery

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-018 | **Path A (ATS API)**: For Greenhouse / Lever URLs, directly call public JSON APIs to get job listings, no authentication required | P0 | Implemented |
| REQ-019 | **Path B (Crawler)**: For non-standard URLs, use Firecrawl and/or Crawl4AI (with Playwright JS rendering) to scrape career pages | P0 | Implemented |
| REQ-020 | Job titles must contain TPM keywords, locations must be in North America (including Remote), non-matching jobs filtered out | P0 | Implemented |

### 4.7 Job Agent — JD Extraction

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-021 | Use Crawl4AI to scrape JD pages into Markdown and cache locally in `jd_cache/` directory (named by URL MD5) | P0 | Implemented |
| REQ-022 | Detect soft 404s (job closed / page not found), skip such JDs | P1 | Implemented |
| REQ-023 | Use Gemini to extract structured data from JD Markdown: job title, company, location, salary, AI tech stack, responsibilities, whether AI TPM | P0 | Implemented |
| REQ-024 | Generate MD5 hash based on JD Markdown content for change detection and deduplication | P1 | Implemented |
| REQ-025 | Tracked JDs with unchanged content hash and not exceeding `FRESH_DAYS` (5 days) skip re-scraping | P1 | Implemented |
| REQ-026 | JDs with extraction failures (missing fields) are retried on next run | P1 | Implemented |
| REQ-027 | JD results written to `JD_Tracker` worksheet, supporting batch upsert (deduplicated by JD URL) | P0 | Implemented |
| REQ-028 | After each run, update TPM Jobs / AI TPM Jobs counts for each company in `Company_List` | P1 | Implemented |
| REQ-029 | Companies with no TPM jobs written to `Company_Without_TPM` sheet to avoid re-discovery next run (superseded by REQ-063 automation) | P2 | Implemented |

### 4.8 Match Agent — Resume Loading

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-030 | Load candidate resume (.md or .txt) from `profile/` directory (overridable via `PROFILE_DIR` environment variable) | P0 | Implemented |
| REQ-031 | Compute resume content MD5 hash for change detection | P1 | Implemented |
| REQ-032 | After resume change, mark existing scores for that candidate as expired, triggering re-scoring | P1 | Implemented |

### 4.9 Match Agent — Two-Stage Matching

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-033 | **Stage 1 Pre-filter**: Quick filter using keyword overlap count (AI tech terms), JDs below threshold (4 terms) directly marked score=0 without calling LLM | P1 | Implemented |
| REQ-034 | **Stage 1 Coarse Screen**: Each Gemini call batch-processes 10 JDs, returns 1-100 coarse scores (minimum score 1, 0 only used for pre-filter elimination), reducing API consumption | P0 | Implemented |
| REQ-035 | **Stage 2 Fine Evaluation**: For top 20% coarse-scored JDs, call Gemini individually for detailed evaluation (4 weighted dimensions) | P0 | Implemented |
| REQ-036 | Fine evaluation dimensions: AI/ML Technical Depth (30%), TPM Role Match (30%), Industry Domain Relevance (20%), Growth Trajectory (20%) | P0 | Implemented |
| REQ-037 | Fine evaluation results include: compatibility score, key strengths list, key gaps list, recommendation rationale (honest assessment, no inflated scores) | P0 | Implemented |
| REQ-038 | Prioritize reading JD Markdown from `jd_cache/` for fine evaluation; fall back to JD JSON fields if no cache | P1 | Implemented |
| REQ-039 | Scoring results written to `Match_Results` worksheet, supporting batch upsert (deduplicated by Resume ID + JD URL) | P0 | Implemented |
| REQ-040 | After run, print Top 5 match results to console, annotating fine evaluation (star) vs coarse screen (~) | P2 | Implemented |

### 4.10 Match Agent — API Reliability

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-041 | Support multiple Gemini API Keys, auto-rotate on quota exhaustion | P0 | Implemented |
| REQ-042 | Gemini calls implement rate limiting (token bucket, max 13 RPM) to avoid triggering API throttling | P1 | Implemented |
| REQ-043 | Fine evaluation stage max concurrency of 3 to prevent API overload | P1 | Implemented |

### 4.11 Shared Persistence Layer

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-044 | Excel file contains 5 worksheets: `Company_List`, `Company_Without_TPM`, `JD_Tracker`, `Match_Results`, `Tailored_Match_Results` | P0 | Implemented |
| REQ-045 | Excel file is auto-created with headers initialized when it does not exist | P0 | Implemented |
| REQ-046 | Support schema migration: old Excel files missing new columns are auto-backfilled (e.g., Job Title, TPM Jobs, Resume Hash, Stage) | P1 | Implemented |
| REQ-047 | Corrupted Excel files are auto-backed up (`.bak`) and recreated | P1 | Implemented |
| REQ-048 | All write operations use "load -> modify -> save" pattern to ensure single-process safety | P1 | Implemented |

### 4.12 Resume Optimizer Agent — Resume Optimization

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-049 | Load all match records from Match_Results with score >= 0 as optimization candidates | P0 | Implemented |
| REQ-050 | For each matched JD, use Gemini to tailor-rewrite the resume (only using information from the original resume, no fabricated experience) | P0 | Implemented |
| REQ-051 | Tailored resumes saved to `tailored_resumes/{resume_id}/{url_md5}.md`, organized by resume ID subdirectories | P1 | Implemented |
| REQ-052 | Use the same `_FINE_SYSTEM_PROMPT` (4-dimension weighted scoring) as Match Agent to re-score tailored resumes, supporting batch processing (`batch_re_score`) | P0 | Implemented |
| REQ-053 | Results written to new Excel worksheet `Tailored_Match_Results`, including original score, tailored score, delta, optimization summary, etc. | P0 | Implemented |

### 4.13 Resume Optimizer Agent — Incremental Updates

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-054 | Skip already-optimized (resume_id, jd_url) pairs with unchanged resume_hash to avoid reprocessing | P1 | Implemented |
| REQ-055 | After resume update (MD5 change), automatically re-optimize all existing pairs | P1 | Implemented |

### 4.14 Resume Optimizer Agent — API Reliability

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-056 | Each JD requires 2 Gemini calls (tailor + re-score), using `asyncio.Semaphore(3)` + `_RateLimiter(rpm=13)` for concurrency control | P1 | Implemented |
| REQ-057 | Support multiple Gemini API Keys, auto-rotate on quota exhaustion | P0 | Implemented |

### 4.15 Job Agent Enhancement — ATS Coverage Expansion (P1)

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-058 | **Ashby Upgrade to JSON API (API_ATS)**: Upgrade Ashby from crawler path (CRAWLER_ATS) to API path, using public Job Posting API (`GET https://api.ashbyhq.com/posting-api/job-board/{slug}`) to get structured JSON data, processed at the same level as Greenhouse / Lever | P1 | Implemented |
| REQ-059 | **Soft 404 Hardening + JD Positive Signal Validation**: Expand soft 404 keyword set to cover major ATS platforms; add JD positive feature word detection, marking content as invalid and skipping if positive feature word count falls below threshold | P1 | Implemented |

### 4.16 Job Agent Enhancement — Data Quality & Robustness (P2)

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-060 | **JD Field Completeness Grading**: Perform field completeness validation on each JD extraction result, output quality grade: `complete` / `partial` / `failed`, written to `JD_Tracker`'s `data_quality` column; `failed` records marked for retry | P2 | Implemented |
| REQ-061 | **Workday URL Format Coverage Expansion**: Fix Workday URL regex to support format without `wd` prefix (`company.myworkdayjobs.com/site` and `company.myworkdayjobs.com/en-US/site`) | P2 | Implemented |

### 4.17 Job Agent Enhancement — Architecture Extensibility (P3)

| REQ ID | Description | Priority | Status |
|--------|------|--------|------|
| REQ-062 | **ATS Declarative Routing Table Refactor**: Refactor if-elif ATS determination chain into a declarative routing configuration table (`ATS_ROUTING` dict), one config entry per ATS platform; adding a new ATS only requires adding a dict entry without changing existing behavior | P3 | Implemented |
| REQ-063 | **Auto-Archive Companies Without TPM Jobs**: Companies with no TPM jobs for N consecutive runs (default 3) are automatically marked as `auto_archived` and skipped in subsequent runs; supports manual recovery (`unarchive`) operation; this is the automated implementation of REQ-029 | P3 | Implemented |

---

## 5. Technical Decisions

### DEC-001: LLM Model Selection — Keep Gemini flash-lite (2026-03-16)

**Background**: Evaluated whether to switch to a stronger model (GPT-5.1, GPT-5.1-mini, Claude Sonnet/Opus) to improve match scoring quality.

**Workload**: ~50-100 companies, 100-200 JDs, full run ~500-1000 API calls.

**Free Tier Comparison**:

| Model | RPM | TPM | RPD | Can Complete Full Run |
|------|-----|-----|-----|-------------|
| Gemini 3.1 flash-lite (selected) | 15 | 250k | 500 | Yes (~33 minutes) |
| GPT-5.1 | 3 | 10k | 200 | No (RPD insufficient, TPM too low) |
| GPT-5.1-mini | 3 | 60k | 200 | No (RPD insufficient) |
| Claude Sonnet/Opus | 5 | 10k | 200 | No (RPD insufficient, TPM too low) |

**Decision**: Keep Gemini 3.1 flash-lite as the sole model.

**Rationale**: Other free models' RPD (200) cannot cover the 500-1000 calls needed for a full run; GPT-5.1 and Claude's TPM (10k) is too tight for long-text tasks like JD extraction/matching; current matching quality meets requirements, no need to introduce multi-model complexity for quality improvement. If stronger models are needed in the future, a hybrid strategy can be adopted: Gemini coarse screen for all + strong model fine evaluation for top 20-30 (within RPD limits).

---

## 6. Dependencies & Constraints

### External Service Dependencies

| Service | Purpose | Authentication | Key Limitations |
|------|------|----------|----------|
| Google Gemini (`gemini-3.1-flash-lite-preview`) | Company info extraction, JD structuring, coarse scoring, fine evaluation, resume tailoring and re-scoring | `GEMINI_API_KEY` / `GEMINI_API_KEY_2` | Free tier: 15 RPM / 500 RPD / 250k TPM; supports multi-Key rotation |
| Tavily API | AI company web search, Career URL search | `TAVILY_API_KEY` | Limited free quota; quota exhaustion returns 402/429 |
| Firecrawl | Career page crawling/Map | `FIRECRAWL_API_KEY` | Has credits quota; 429 requires retry |
| Crawl4AI + Playwright | JS rendering crawler (JD page scraping) | No authentication needed | Local run requires Chromium installation (`playwright install chromium`) |
| Greenhouse Public API | ATS job listings | No authentication needed | Public endpoint, no limits |
| Lever Public API | ATS job listings | No authentication needed | Public endpoint, no limits |
| Ashby Public API | ATS job listings (added in REQ-058) | No authentication needed | Public endpoint: `https://api.ashbyhq.com/posting-api/job-board/{slug}` |

### Technical Constraints

- Python 3.11 (uses `str | None`, `list[str]` and other 3.10+ syntax)
- Single-process execution, `shared/excel_store.py` uses load-modify-save pattern for single-process safety (does not support multi-process concurrent writes to the same Excel file)
- `jd_cache/` and `tailored_resumes/` directories are local filesystem, not version-controlled (`.gitignore`)
- `.env` file stores API Keys, not version-controlled

---

## 7. Risks & Mitigation

| Risk | Impact Level | Mitigation |
|------|----------|----------|
| Gemini API quota exhaustion (429) | High | Multi-Key rotation (`shared/gemini_pool.py`, round-robin); rate limiting (13 RPM token bucket); Semaphore(3) concurrency control; `asyncio.gather` post-check for quota_errors with warning output |
| Tavily API quota exhaustion (402) | Medium | Detect 402/429/quota error codes and early-terminate subsequent queries, output user-visible warning (BUG-44) |
| Firecrawl quota exhaustion (429) | Medium | 3 retries + exponential backoff (429 uses 30s x attempt, other errors 5s x attempt) (BUG-17) |
| Career site anti-crawling (403/dynamic rendering) | Medium | Crawl4AI + Playwright handles JS-rendered pages; hardcoded ATS overrides for special companies like Tesla/Google; Firecrawl as fallback crawler |
| ATS format changes causing parsing failures | Medium | Declarative routing table (REQ-062) facilitates adding new ATS; JD field completeness grading (REQ-060) identifies extraction failures; auto-retry mechanism (REQ-026) |
| Soft 404 false positives causing valid JDs to be skipped | Medium | Positive signal validation (REQ-059) dual verification: soft 404 detection + positive feature word confirmation, reducing false positive rate |
| Excel file corruption causing data loss | Low | Auto-backup (`.bak`) then recreate (REQ-047); schema migration ensures backward compatibility for old files (REQ-046) |
| Company name deduplication false matches | Low | Normalized matching + bidirectional startswith check, avoiding exact-match misses of variants (e.g., "Anthropic" vs "Anthropic AI") |
| Workday URL format diversity | Low | URL regex extended to support both with/without `wd` prefix formats (REQ-061) |
| Companies without TPM jobs continuously consuming API quota | Low | Auto-archive mechanism (REQ-063): automatically skipped after 3 consecutive runs without TPM jobs, supports manual recovery |

---

## 8. Acceptance Criteria

### Functional Completeness

| Criterion | Target | Actual Delivery |
|------|------|----------|
| Functional requirements implementation rate | 100% | 63/63 REQs all implemented (`[x]`) |
| Bug fix rate | All P0/P1 fixed | 55/55 Bugs all fixed (P0:5, P1:15, P2:23, P3:12) |
| Test pass rate | All pass | 485+ unit tests all passed |
| ATS platform coverage | Major ATS | Greenhouse, Lever, Ashby (API) + Workday, Google, Tesla (crawler) — 6 platforms total |

### Key P0 Bug Fix Confirmation

| Bug | Impact | Fix Status |
|-----|------|----------|
| BUG-01 | API Keys security | Fixed (.gitignore protection, .env.example placeholder) |
| BUG-02 | Core dependency missing prevents running | Fixed (requirements.txt completed) |
| BUG-03 | Location filter false positives causing North American jobs to be missed | Fixed (state code matching rules strengthened) |
| BUG-32 | Tesla JD extraction completely broken (Firecrawl class name error) | Fixed (FirecrawlApp) |
| BUG-33 | Gemini returning null list causing TypeError crash | Fixed (`or []` pattern) |

### P0+P1 Bug Fix Confirmation

All 20 P0+P1 Bugs fixed (P0: 5, P1: 15), covering API security, data integrity, concurrency safety, ATS compatibility, and other critical areas:

| Priority | Bug Scope | Count | Representative Issues |
|--------|----------|------|-----------|
| P0 | API security, runtime crashes | 5 | BUG-01 (Key plaintext), BUG-32 (Tesla Firecrawl class name), BUG-33 (null list TypeError) |
| P1 | Data correctness, concurrency safety, performance | 15 | BUG-27 (JD infinite retry), BUG-28 (crawler failure), BUG-34 (Client caching), BUG-35 (round-robin), BUG-36 (thread safety), BUG-38 (RPM exceeded) |

### End-to-End Acceptance Scenarios

Starting from a blank state, run all 4 Agents sequentially to verify complete data flow:

1. **Company Agent** -> `Company_List` has company data written, each record contains Company Name / AI Domain / Career URL
2. **Job Agent** -> `JD_Tracker` has structured JDs written, key fields (Job Title / Company / Location / Is AI TPM) non-empty; `jd_cache/` directory has Markdown cache files
3. **Match Agent** -> `Match_Results` has scoring records written, containing both coarse and fine Stage types; Top 5 results output to console
4. **Resume Optimizer** -> `Tailored_Match_Results` has tailored results written, Score Delta observable; `tailored_resumes/` directory has tailored resume files

### Performance Baseline

| Metric | Baseline Value | Notes |
|------|--------|------|
| Full run time (~100 companies) | <= 60 minutes | Constrained by Gemini free tier 15 RPM / 500 RPD limits |
| Incremental run time (no new/changes) | <= 5 minutes | Only performs hash comparison and timestamp checks, skips processed records |
| Single Company Agent run | <= 15 minutes | Includes Tavily search + Gemini extraction + Career URL verification |

### Key Architecture Quality

- Gemini Client caching (BUG-34): Eliminates TCP/TLS handshake latency during batch runs
- Round-robin Key rotation (BUG-35): Auto-fallback to other Keys after 429, reuse after recovery
- Thread safety (BUG-36): `threading.Lock` protects `_idx` and `rotate()`, preventing concurrent Key skipping
- Semaphore/RateLimiter separation (BUG-38): Gemini calls moved out of Semaphore block, preventing actual RPM from exceeding limits
- Workbook handle management (BUG-12): All 19 functions have `try/finally: wb.close()`, eliminating file handle leaks

---

## Appendix: Version Evolution Summary

| Version | Date | Key Changes |
|------|------|----------|
| v5 (draft) | Before 2026-03 | Monolithic Colab Notebook, dependent on Google Sheets / Drive |
| v1.0 | 2026-03-12 | Refactored to 3 independent Agents + local Excel; two-stage matching; JD local caching; Gemini Key rotation |
| v1.1 | 2026-03-16 | Added 4th Agent (resume_optimizer); Tailored_Match_Results worksheet |
| v1.2 | 2026-03-16 | Added development tooling layer: 7 Custom Agents + 5 Skills |
| v1.3 | 2026-03-16 | Added coordination layer: TPM Agent + 3 SDLC Skills + SDLC 5-phase workflow framework |
| v1.4 | 2026-03-16 | Comprehensive code audit fixed 55 Bugs; Job Agent enhancements (REQ-058~063); Gemini Pool refactor; tests grew from 120 to 485+ |
| v1.5 (current) | 2026-03-17 | Added Observability Agent + Cost Agent; Custom Agents grew from 9 to 11 |
