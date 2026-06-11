# CHANGELOG

## 2026-05-20

### Manual-entry override: backfill Career URL for hand-inserted Company_List rows

`company_agent.run_phase_1_5` now detects `Company_List` rows that were inserted
manually (`Company Name` + `AI Domain` present, `Career URL` blank) and runs the
full `find_career_url` discovery pipeline on them — Tavily ATS-targeted search →
Tavily general search → Greenhouse / Lever / Ashby / Workable slug probes →
Workday-via-Tavily fallback → homepage crawl — then writes the result back.
Tavily is a hard requirement for this path; rows that resist discovery are
reported and left blank for the next run to retry. `AI Domain` accepts any of
the 6 whitelisted buckets *or* a custom string (job_agent treats unknown
buckets as `ai_native`). Lets the user drop in a target company list without
also hunting down their ATS URLs by hand.

### Gemini model name → GA (`gemini-3.1-flash-lite`)

`shared/config.py:MODEL` updated from `gemini-3.1-flash-lite-preview` to
`gemini-3.1-flash-lite` (the GA name). Google deprecates the `-preview` alias
on 2026-05-25; this is a pure rename — same model, same weights, same prompts,
same costs, scores comparable across the rename. No call-site changes.

## 2026-05-05

### Discovery coverage: Workday-via-Tavily fallback (with strict subdomain guard)

Follow-up to the Workable + URL-unwrap work below. Many big-tech and infra companies (Adobe, Cisco, Qualcomm, Salesforce, Dell, Broadcom, Cadence, DataRobot, Zendesk, PayPal, Equinix, etc.) use Workday with **unguessable subdomains** (`adobe.wd5`, `cisco.wd5`, `qualcomm.wd12`, `paypal.wd1`, …), so slug-probing can never find them. They were stuck at custom career pages or LinkedIn URLs.

- **`_find_workday_url(company_name, tavily_client)`** in `agents/company_agent.py`: queries Tavily with `"<company>" careers site:myworkdayjobs.com` and returns the first hit on `myworkdayjobs.com` whose subdomain matches the company name.
- **`_workday_subdomain_matches_company(url, company_name)`** — critical false-positive guard. Tavily's site filter happily returns URLs from *other* companies that happen to mention the search term in their JD pages: AMD → `argonne.wd1` (Argonne Lab JDs reference AMD silicon), Oracle → `pwc.wd3` (PwC Oracle-consulting roles), Apple → `applebank.wd5`, Western Digital → `westernunion.wd5`, Clay → `claycountybcc.wd1`. Initial fuzzy `c_compact in sub_compact` matching let the substring cases through; tightened to **exact compact-form equality** (each slug candidate must equal the subdomain after stripping non-alphanumerics — no prefix or substring rules).
- Wired as **step 4** in `validate_and_upgrade_ats_url` (after slug-probe misses); only fires when a `tavily_client` is supplied. `run_phase_1_5` now auto-instantiates a Tavily client from `TAVILY_API_KEY` if none is passed.

**Phase-1.5 re-run results** (against `pathfinder_dashboard.xlsx`, 75 non-ATS candidate rows): **26 upgrades, 0 false positives**.
- Workday recoveries (11): Adobe, Cisco, Qualcomm, Salesforce, Dell Technologies, Broadcom, Cadence Design Systems, DataRobot, Zendesk, PayPal, Equinix — all → their real `*.wdN.myworkdayjobs.com` boards.
- Plus 15 Ashby + unwrap wins from the prior iteration (Sierra, Cursor, Weaviate, Modal Labs, Baseten, Replit, Runway, Suno, Gamma, Applied Materials, ElevenLabs, Mercor, Nutanix, EliseAI, Physical Intelligence).

**Tests**: +18 added (`TestWorkdaySubdomainMatch` 9 cases including the 3 real false-positive guards; `TestFindWorkdayUrl` 8 cases; `TestValidateAndUpgradeWorkdayFallback` 4 cases). Full suite 854/854 green.

---

### Discovery coverage: Workable ATS + LinkedIn / VC-portfolio URL unwrapping

Audit of the 146-company `Company_List` sheet showed two coverage gaps that were *not* unsupported scrapers but unsupported *URL shapes*: 8 companies stuck at `linkedin.com/jobs/<slug>-jobs` and 4 stuck behind VC-portfolio job-listing wrappers (a16z / battery / gaingels / 01a). Plus Hugging Face routed through the Firecrawl crawl path despite Workable having a clean public API.

- **A′ — Workable as first-class ATS**: added `workable` entry to `ATS_PLATFORMS` (`agents/job_agent.py`) and a dedicated `_fetch_workable_jobs` (mirrors `_fetch_ashby_jobs` — Workable's widget API uses multi-field `city/state/country/locations[]/telecommuting` rather than a single `location` dict). Endpoint: `https://apply.workable.com/api/v1/widget/accounts/{slug}` (the older `/api/v3/accounts/...` path 404s). Added Workable to `ATS_VALIDATORS` in `agents/company_agent.py` so slug-probing also covers it during phase 1.5.
- **A″ — wrapper URL unwrapper**: new `_unwrap_career_url(url)` helper in `agents/company_agent.py` extracts the underlying company slug from `linkedin.com/jobs/<slug>-jobs`, `linkedin.com/company/<slug>/jobs`, and `jobs.<vc>.com/jobs/<slug>` for the four known VC-portfolio hosts. Wired into `validate_and_upgrade_ats_url` between the hard-coded-override step and the already-ATS short-circuit; on a wrapper match, the extracted slug feeds `_check_ats_slug` against all validators. If the underlying company is on a public ATS, `current_url` is rewritten to the real board URL.
- **Ashby in `ATS_VALIDATORS`** (pre-existing gap, surfaced during A″ verification): `company_agent.py`'s slug-probe validators previously only covered Greenhouse + Lever, so any company on Ashby (a heavily-used AI-startup ATS) silently fell through to homepage scraping. Added Ashby to `ATS_VALIDATORS` — fixes both the new A″ unwrap path AND the existing `find_career_url` / `validate_and_upgrade_ats_url` step-3 slug-probe. Added regression test `test_validators_cover_all_json_api_platforms`.

**Phase-1.5 re-run results** (against `pathfinder_dashboard.xlsx`, 75 non-ATS candidate rows): **16 upgrades**.
- A″ unwrap wins (4): Modal Labs, Baseten, Replit, EliseAI — all → Ashby.
- Ashby-validator wins (12): Snowflake, Sierra, Cursor, Weaviate, Runway, Suno, Gamma, Applied Materials, ElevenLabs, Mercor, Nutanix, Physical Intelligence — all were stuck on custom career URLs, now routed to their Ashby boards.

**Tests**: +36 added by this work (17 Workable in `tests/test_job_agent.py`: `TestWorkableAtsConfig` / `TestFormatWorkableLocation` / `TestFetchWorkableSlugExtraction` / `TestFetchWorkableApiParsing` / `TestDiscoverJobsWorkableRouting`; 19 in `tests/test_company_agent.py`: `TestUnwrapCareerUrl` / `TestValidateAndUpgradeUnwraps` + `test_validators_cover_all_json_api_platforms`). Full suite 833/833 green. All mocked — no live network calls.

### Self-audit fixes: TPM scraping coverage + classifier strictness

Self-audit (two parallel `Explore` subagents) of the AI-TPM job pipeline surfaced three concrete defects, all fixed in `agents/job_agent.py`:

- **Workable + Workday fallback search params** (`ATS_SEARCH_PARAM`): primary JSON-API path was already TPM-filtered, but the fallback `_crawl_ats_board` crawler had no search keyword for these two platforms, so when the API returned empty the crawler would scrape the entire job board un-filtered. Added `workable: query=…` and `workday: q=…` (the standard public search-URL syntax for each platform). Defense-in-depth — affects ~20 companies (Hugging Face, Intel, HPE, NVIDIA, Pinecone, etc.) when their JSON API hiccups.
- **Compliance/SOX/audit/governance/GRC title block** (`_TITLE_BLOCK_KW`): Big-Tech title prefilter was admitting roles like "TPM, SOX Compliance" and "TPM, GRC Audit" as candidates. The downstream LLM classifier also accepted some as `is_ai_tpm=True` because the prompt's domain-exclusion list omitted compliance/audit. Added 5 keywords to the title prefilter so these never reach Gemini.
- **Big Tech `is_ai_tpm` prompt**: appended explicit ACCEPT/REJECT few-shot examples (ML Infrastructure / GPU Cluster / Foundation Models vs. SOX / Marketing-Tech / Trust & Safety / Federal-clearance) and added the same compliance keywords to the natural-language exclusion list. Reduces false positives on JDs whose titles slipped past the title prefilter.

**Tests**: 802 → 805 (+3). New `TestAiTitlePrefilter` class regression-tests the compliance keyword block; `test_search_params_exist_for_main_ats` extended to require Workable + Workday entries.

### Self-audit P1 follow-up: silent-failure observability + retries + Microsoft JD

Round-2 fixes for the P1 items the self-audit flagged but the first batch deferred. All in `agents/job_agent.py`.

- **HTTP retry helper** (`_http_request_with_retry`): new module-level function with exponential backoff (0.5/1.0/2.0s) on 429 + 5xx + transient network exceptions. All 4 ATS API fetchers (`_fetch_ats_jobs` for Greenhouse/Lever, `_fetch_ashby_jobs`, `_fetch_workable_jobs`, `_fetch_workday_jobs`) routed through the helper — used to be `requests.get` once, return `[]` on any non-200, no retry, no URL in the error log. Now: 3 attempts, sleep between attempts, every retry/failure logs URL + status + attempt number. The helper dispatches to `requests.get` / `requests.post` (rather than `requests.request`) so the 50+ existing test patches that mock those names continue to work unchanged. Backoff base is the module-level constant `_RETRY_BASE_SLEEP_SECS` (default 0.5s, set to 0 in tests).
- **Error-context logging** at the 4 remaining swallow sites: `_crawl_page` / `scrape_jd` / `llm_filter_jobs` / `extract_jd` previously logged just the exception message. Now log the URL (or company + JD char count + classification class for the LLM calls) and the exception type. "API down" no longer looks like "zero jobs" in the run log.
- **Microsoft careers JD scraper** (`_scrape_microsoft_jd`): mirrors `_scrape_google_jd`. Routes URLs at `jobs.careers.microsoft.com` and `careers.microsoft.com` through Firecrawl with `only_main_content=True`, falls back to plain HTTP + JSON-LD if Firecrawl is unavailable, falls back further to the generic browser scraper if both miss. Closes the audit's "40-50% of cached MS JDs were nav-chrome" finding. Wired via the existing `ATS_PLATFORMS` table + `_JD_FN_REGISTRY` so no router code changed.

**Confidence/reasoning fields on `JobDetails`** (audit P2): deliberately deferred. Adding it would touch `excel_store.py` (column migration) + `match_agent.py` + `resume_optimizer.py` (downstream consumers must read it); >3 files violates the project's task-size rule. Will land as its own PR.

**Tests**: 805 → 832 (+27, includes prior parallel session's 805→820 baseline shift). New `TestHttpRetryHelper` (7) + `TestMicrosoftJdScraper` (5) classes in `tests/test_job_agent.py`. The retry helper is exercised against 200/4xx/429/5xx/exception scenarios; the Microsoft scraper is asserted to route via `_match_ats` and to call Firecrawl with `only_main_content=True`. Existing ATS fetcher tests still patch `requests.get`/`requests.post` directly; module-level `_RETRY_BASE_SLEEP_SECS = 0` keeps the suite snappy despite the new retries.

### PRJ-003: PDF Resume I/O + Claude Opus Tailor Evaluation

Three additions, all opt-in / passive:

- **PDF → MD resume input** (no LLM): drop a `.pdf` into `profile/` and the agents auto-convert via `pdfplumber`. Conversion is deterministic, layout-aware (detects section headers by font size + all-caps, preserves bullet structure), and cached at `profile/.cache/{stem}.{md5}.md` — re-runs are zero-cost. Picker priority is `.md > .txt > .pdf` so a hand-edited `.md` always wins. `resume_id` is preserved across formats so existing Excel keys remain stable. Implemented in `shared/resume_io.py`; `agents/match_agent.py` and `agents/resume_optimizer.py` now import the shared loader (local copies removed).
- **MD → PDF tailored output (ATS-safe)**: every tailored resume written to `tailored_resumes/{resume_id}/{md5}.md` now also gets a sibling `{md5}.pdf` rendered via WeasyPrint. The CSS template (`templates/resume.css`) enforces ATS-safe rules: single column, standard fonts (Helvetica / Arial / Times / Calibri / Georgia stack), no images / headers / footers / multi-column, real Unicode bullets, selectable text. Font family + body size are captured from the input PDF (when present) and injected as CSS variables so output mimics source typography while staying ATS-safe; body size clamps to [9pt, 12pt]. PDF generation failures log a warning but never block the pipeline — the `.md` remains source of truth for Excel records.
- **Claude Opus 4.7 tailor evaluation memo** (`docs/sdlc/PRJ-003-pdf-io-opus-eval/eval.md`): cost / latency / quality analysis vs current Gemini 3.1 Flash Lite for the `tailor_resume` step. **Verdict**: not as a full swap — Opus is ~170× more expensive per call and ~2–3× slower; recommend opt-in fallback that fires only on regressions and user-flagged priority JDs.

**System dependency**: WeasyPrint needs Pango/Cairo. On macOS: `brew install pango` (one-time).

**Tests**: 736 → 749 (+13 in `tests/test_resume_io.py`), all passing.

**Reference docs**: `docs/sdlc/PRJ-003-pdf-io-opus-eval/` (status + eval memo).

### Tailored-resume user-edit protection

`resume_optimizer._save_tailored_resume` now refuses to overwrite a tailored
resume that the user hand-edited between runs. Mechanism: each successful
write records a `sha256` of the `.md` content in a new
`Tailored_Match_Results.Last Written Hash` column; before any subsequent
write, the on-disk hash is compared against that record — mismatch ⇒ skip
both the `.md` write and the sibling `.pdf` render, and exclude the pair from
that run's Excel update so the row stays aligned with the on-disk
(user-edited) file. Legacy rows (empty `Last Written Hash`) are treated as
"no prior write on file" and write normally on first run (no false-positive
tamper detection). New `--force-rewrite` CLI flag bypasses the check.
Motivation: daily scheduled re-runs (see launchd entry below) would
otherwise silently clobber polish the user applied by hand.

**Tests**: +13 in `tests/test_resume_optimizer.py` (`TestUserEditProtection`)
and `tests/test_excel_store.py` (`TestLastWrittenHash`).

### JD_Tracker auto-sort by location tier

After each `job_agent` run, `JD_Tracker` is now sorted into three location
tiers — **Greater Seattle** → **Remote (US)** → **Other** — with a new
`Location Tier` column and row highlighting per tier. Tier classifier
recognises Seattle / Bellevue / Redmond / Kirkland / Greater Seattle
metro variants; Remote includes "Remote (US)", "United States — Remote",
etc. The sort is stable within-tier (preserves prior recency order). Lets
the user scan the highest-priority openings first without spreadsheet
filters.

### launchd-based daily pipeline runner

Added `scripts/run_daily_pipeline.sh` + sample `com.pathfinder.daily.plist`
that schedules the full 4-agent pipeline (company → job → match →
optimizer) via macOS `launchd`. Logs land in `logs/` (gitignored).
`.gitignore` updated to also exclude `worktrees/` (Claude Code agent
isolation artifacts). Replaces ad-hoc terminal runs for users who want a
fire-and-forget daily refresh.

## 2026-04-28

### Major: 3-Dimension Scoring (PRJ-002)

The resume-fit scoring pipeline is restructured from a single LLM-derived "fit score" into three parallel dimensions that each map to one real-world hiring filter:

- **ATS Coverage** (deterministic keyword match, no LLM) — proxy for Applicant Tracking System / recruiter-keyword-search pass-through. Implemented in `shared/ats_matcher.py` (~120 lines, no new pip deps) with case-insensitive matching, lightweight plural stem (`-ies` / `-sses` / `-xes` / `-ches` / `-shes` / `-s`), and a hand-curated synonym table (~18 entries: GenAI≈Generative AI, K8s≈Kubernetes, LLM≈Large Language Model, etc.) in `shared/ats_synonyms.py`.
- **Recruiter Score** (Gemini, was COARSE) — quick recruiter-style 1-100 scan; renamed for clarity.
- **HM Score** (Gemini, was FINE) — hiring-manager 4-criteria deep evaluation (AI/ML Tech Depth 30% / TPM Function 30% / Domain 20% / Growth 20%); renamed for clarity.

**New behavior**:
- `agents/job_agent.py`: `JobDetails` extracts `ats_keywords: list[str]` (8-15 noun phrases) at JD ingest time.
- `agents/match_agent.py`: ATS coverage runs deterministically before Stage 1 for every pending JD; Recruiter and HM dimensions retain existing call shapes. Coarse / fine records switch to dict format with optional per-dim fields.
- `agents/resume_optimizer.py`: rescores all 3 dimensions after tailoring (1 deterministic ATS + 1 Recruiter Gemini + 1 HM Gemini per JD). Surfaces per-dimension delta so users can see ATS keyword gains separately from semantic strength changes.
- **Regression flag now means `HM Delta < 0` only** (was: legacy single-score delta < 0). ATS / Recruiter drops are informational — a tailor that shifts emphasis away from a recruiter keyword while preserving HM fit is fine and should NOT push the user to keep the base resume.

**Excel schema changes** (auto-migrated, backward compatible):
- `Match_Results`: +4 columns (ATS Coverage %, Recruiter Score, HM Score, ATS Missing). All legacy column indices preserved.
- `Tailored_Match_Results`: +9 columns (per-dim Original / Tailored / Delta × {ATS, Recruiter, HM}). Legacy `Original Score` / `Tailored Score` / `Score Delta` mirror the HM dimension for back-compat.
- Old rows: blank values for new cols. Re-run match_agent / optimizer to populate.
- `batch_upsert_match_records` and `batch_upsert_tailored_records` accept dict records with optional per-dim keys; key absent → preserve cell. Tuple-format records still supported for back-compat.

**Prompt rename pivot** (pure rename, content byte-identical):
- `COARSE_SYSTEM_PROMPT` → `RECRUITER_SYSTEM_PROMPT` (back-compat alias retained)
- `FINE_SYSTEM_PROMPT` → `HM_SYSTEM_PROMPT` (back-compat alias retained)

**Cost impact**: Resume Optimizer adds 1 Recruiter Gemini call per tailored JD (was: 1 tailor + 1 HM rescore; now: 1 tailor + 1 Recruiter + 1 HM). At 13 RPM shared rate limit, 10 tailored JDs takes ~45s extra. ATS dimension is deterministic — zero API cost.

**Reference docs**: `docs/sdlc/PRJ-002-3d-scoring/` (BRD + tech design + status).

**Tests**: 619 → 718 (+99 across 5 sequential PRs), all passing.

### P0 Code Review Follow-ups

- **P0-9** (`6e9267f`): Stage 2 fine candidate selection switched from "top 20%" to UNION of (score >= `MATCH_FINE_SCORE_THRESHOLD`, top `MATCH_FINE_TOP_PERCENT%`). Protects against both flat-high distributions (where top-N% would discard genuine fits) and flat-low ones (where the absolute threshold would select nothing).
- **P0-10** (`43bb666`): Optimizer rescore call shape unified with match_agent's fine eval. Dropped batch re-score (5 pairs/call) in favor of per-JD calls with `RESCORE_CONCURRENCY=3`. Eliminates ~3-5pt batch-context anchoring inflation in Score Delta. Removed unused `BATCH_FINE_SYSTEM_PROMPT` / `BatchMatchItem` / `BatchMatchResult`.
- **P0-11** (`b88ab9a`): Gemini transient errors (5xx / UNAVAILABLE / timeout) now retry on the same key with bounded exponential backoff (2s / 4s / 8s + jitter) before raising. Quota / 429 still rotates keys (key-specific). Aligns with Gemini API guidance for retryable server-side errors.
- **P0-12** (`712cd0e`): `Tailored_Match_Results` gains a persisted `Regression` boolean column. Previously this signal was only printed at run time and lost between runs; users had to re-derive from Score Delta < 0.

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
