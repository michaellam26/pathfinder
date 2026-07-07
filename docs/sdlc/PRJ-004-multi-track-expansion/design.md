# Tech Design: Multi-Track Expansion

**Project ID**: PRJ-004
**Author**: Engineer Lead
**Status**: Approved (User, 2026-07-07 — TPM review applied; §8 questions resolved, see resolutions)
**Date**: 2026-07-07
**Inputs**: BRD (`docs/sdlc/PRJ-004-multi-track-expansion/brd.md`, approved with §7 resolutions), intake doc (`docs/sdlc/multi-track-expansion-requirements.md`), TPM review (Sequencing Notes honored), Engineer Lead review (feasibility notes honored). All code anchors below were verified against the working tree on branch `prj-004-multi-track-expansion`.

---

## 1. Overview & Design Principles

PathFinder's 4-agent pipeline (company → job → match → optimizer) is extended from AI-only/200-company scope to a 6-track/500-company scope with freshness, YoE-seniority, and work-authorization filtering. This design makes **no framework or architectural changes**. Every REQ lands as an extension of an existing mechanism:

| Existing mechanism | How it is extended |
|---|---|
| `AI_DOMAIN_VALUES` tuple + `MAX_TOTAL` constants (`agents/company_agent.py:59-72`) | Replaced by `TRACK_VALUES` + `TRACK_QUOTAS` (per-bucket, not global-only) |
| Gemini structured extraction with a single Pydantic schema (`JobDetails`, `agents/job_agent.py:192-204`) | New fields folded into the **same** schema/prompt — **zero additional Gemini round-trips per JD** (per Engineer review note 1, BRD §5 cost table) |
| Adapter registry `ATS_PLATFORMS` + `_resolve_list_fn`/`_JD_FN_REGISTRY` dispatch (`agents/job_agent.py:214-316, 812-819, 1618-1625`) | Amazon (P1) and Google (P2) adapters are new registry entries; no new dispatch mechanism |
| Prefetched-metadata pattern (`workday_meta`, `agents/job_agent.py:1784, 1628-1632`) | Generalized to carry posting dates (all ATS platforms) and prefetched Amazon JD text |
| `_JD_COL` dynamic column lookup (BUG-52, `shared/excel_store.py:51`) | Header changes propagate automatically; read paths untouched individually |
| Header-migration blocks in `get_or_create_excel` (`shared/excel_store.py:70-246`) | `AI Domain`→`Track` rename and JD_Tracker header replacement are new migration blocks in the same style |
| Byte-identical prompt-pair constants in `shared/prompts.py` (REQ-052) | 5 pairs in one module-level dict; match_agent and resume_optimizer reference the **same constant object** per track, so byte-identity is structurally enforced exactly as today |
| Key-pool / rate-limiter / RunSummary | Unchanged; RunSummary gains one note (token usage) for the REQ-004-26 trial run; launchd wrapper gains a failure marker file |

**Settled decisions honored (BRD §7 Resolutions):** header renamed `AI Domain`→`Track`; explicit classifier anchors added for Robotics/Space/Defense sub-orgs; 15-day skip is write-time-only on new rows; migrated over-quota survivors are grandfathered (quotas constrain new discovery only).

**Out of scope (untouched):** `shared/ats_matcher.py`, `shared/ats_synonyms.py`, any direct LinkedIn scraping, regional percentage quotas.

---

## 2. Module-by-Module Design

### 2.1 `agents/company_agent.py` — taxonomy, quotas, rules, migration

**Current state**
- `MAX_TOTAL = 200`, `BATCH_SIZE = 50` (`company_agent.py:59-60`); global cap only, no per-bucket accounting (`main()` slot math at `company_agent.py:860-867`).
- `AI_DOMAIN_VALUES` — 6 AI-only buckets (`company_agent.py:65-72`); mirrored as a `Literal` on `AICompanyInfo.ai_domain` (`company_agent.py:75-98`).
- Discovery: 7 AI-themed `TAVILY_QUERIES` (`company_agent.py:184-218`); Gemini system prompt hardcodes the AI distribution and "headquartered in the United States" geography (`company_agent.py:593-631`).
- `upsert_companies` writes `c.get("ai_domain")` to column 2 (`shared/excel_store.py:322`).

**Target state**

New constants (replacing `company_agent.py:59-72`):

```python
MAX_TOTAL = 500
TRACK_VALUES = ("AI-native", "Mid-large Tech", "Robotics", "Fintech", "Space", "Defense")
TRACK_QUOTAS = {"AI-native": 150, "Mid-large Tech": 150, "Robotics": 50,
                "Fintech": 50, "Space": 50, "Defense": 50}
DEFENSE_EXCLUDED_PRIMES = frozenset({"boeing", "lockheed martin", "raytheon", "rtx",
    "northrop grumman", "general dynamics", "bae", "bae systems", "l3harris"})
DEFENSE_ALLOWLIST = frozenset({"palantir"})            # early-company-rule exception
VERTICAL_TRACKS = frozenset({"AI-native", "Robotics", "Fintech", "Space", "Defense"})
```

- `AICompanyInfo` → renamed `CompanyInfo`; field `ai_domain` → `track: Literal[<6 new values>]`. `CompanyInfoList` unchanged shape.
- **Per-bucket slot accounting (REQ-004-01 + Q4 grandfathering)**: `main()` Step 2 replaced by a per-bucket computation: read existing rows, count per `Track` value, `need[bucket] = max(0, TRACK_QUOTAS[bucket] - count[bucket])` — a bucket at/over quota (grandfathered survivors) gets `need = 0`, is never trimmed. Total request per run remains capped by `BATCH_SIZE = 50`, allocated proportionally to open slots. The Gemini prompt's category distribution string is generated from `need`, replacing the hardcoded percentages at `company_agent.py:600-619`.
- **Early-company rule (REQ-004-02/03/04)**: encoded twice —
  1. In the discovery system prompt: vertical buckets require founding ~2000+; legacy incumbents (Boeing, Visa, PayPal, Intuit, Boston Dynamics, ABB…) only via Mid-large Tech; defense targets venture-backed post-2010 (Anduril, Shield AI, Saronic, Castelion); Palantir explicitly in scope; Space early-rule noted as "prefer SpaceX/Relativity/Stoke over incumbent space divisions".
  2. Deterministic post-filter `_apply_bucket_rules(companies) -> list` after the dedup filter (`company_agent.py:648-662`): drop any `track == "Defense"` candidate whose normalized name matches `DEFENSE_EXCLUDED_PRIMES` (unless in `DEFENSE_ALLOWLIST`) — the hard-exclusion must not depend on LLM compliance. The Space rule stays prompt-only (experimental, REQ-004-04 P1, flagged for post-launch review — no code hard rule yet).
- **Geography semantics (REQ-004-05)**: prompt text change only — replace "headquartered in the United States" / "STRICTLY exclude non-US companies" (`company_agent.py:596, 620`) with "companies that hire TPMs in Greater Seattle, California (Bay Area + Southern California), or Texas — qualification is by hiring footprint in these regions, NOT HQ location". No code-level region validation at discovery time (the tightened job-geo filter, §2.2.4, is the enforcement backstop).
- **`TAVILY_QUERIES`**: rewritten as ~10 queries covering the 6 buckets (2 AI-native, 2 mid-large, 1–2 each for robotics/fintech/space/defense), each biased with Seattle/CA/TX hiring terms. LinkedIn appears only as `site:linkedin.com` scoping inside Tavily queries (REQ-004-19), never fetched directly.
- **Re-bucket migration (REQ-004-06)**: new one-time entry point — see §4.

### 2.2 `agents/job_agent.py` — extraction fields, classifier, dates, work-auth, geo, scrapers

#### 2.2.1 Extraction schema — YoE, domain, work-auth, all in the existing call (REQ-004-08/09/11)

**Current state**: `JobDetails` (`job_agent.py:192-204`) has `is_ai_tpm: bool`; `extract_jd` (`job_agent.py:1543-1616`) branches on `_classify_by_domain` (`job_agent.py:338-351`) to pick an "unconditional true" vs "strict AI" system instruction; one Gemini call per JD.

**Target state** — `JobDetails` gains four fields, `is_ai_tpm` removed:

```python
job_domain: Literal["AI", "Robotics", "Fintech", "Space", "Defense", "None"]
min_yoe: int | None = None          # minimum stated years; None if not stated
work_auth: Literal["citizenship_required", "clearance_required",
                   "us_person_ok", "none_stated"] = "none_stated"
posted_date: str = ""               # NOT LLM-extracted; injected by code (see 2.2.3);
                                    # declared here so cached JDs round-trip
```

`extract_jd(markdown, company, track)` replaces the `ai_domain` param name and the two-branch prompt:
- **Vertical-track company** (`track ∈ VERTICAL_TRACKS`, replaces `_classify_by_domain`): prompt states "every TPM role at this company qualifies; set `job_domain` to `<track>`". Code additionally **overrides** `parsed["job_domain"] = track_to_domain(track)` after parse (deterministic; `AI-native`→`AI`, others map 1:1) — the classifier is not trusted for the trivial case.
- **Mid-large-tech company**: prompt instructs the 5-track judgment with the **explicit mapping anchors** (Q2 resolution):
  - Cloud/compute infra (AWS/GCP/Azure infrastructure, datacenter, silicon, GPU fleet) → `AI`
  - Payments orgs (Google Pay, Apple Pay, Amazon Payments, checkout/risk/ledger platforms) → `Fintech`
  - Robotics sub-orgs (Amazon Robotics, fulfillment/warehouse robotics, autonomous-mobility hardware, humanoid programs) → `Robotics`
  - Space sub-orgs (Project Kuiper, Amazon Leo, Azure Space, satellite/ground-segment programs) → `Space`
  - Defense/gov sub-orgs (Azure Government, AWS GovCloud/DoD programs, mission-systems teams) → `Defense`
  - Anything else (Office 365, general finance/HR/retail TPM, generic web products) → `"None"`
- **Unknown/unmigrated track value**: treated as mid-large-tech (strictest path — per-JD judgment) + a logged warning naming the company (mirrors BRD §6 unmigrated-value risk mitigation). Never silently coerced.
- YoE prompt clause: "extract the minimum required years of experience as an integer if the JD states one (e.g. '7+ years' → 7); use the requirements section's stated minimum; null if no numeric minimum is stated". Work-auth clause: "classify authorization requirements: `citizenship_required` (US citizenship required), `clearance_required` (active clearance OR 'must be able to obtain' a clearance), `us_person_ok` (US person / permanent resident / green card acceptable — ITAR standard), `none_stated`."
- `SECURITY_CLAUSE` still appended (`job_agent.py:1596`); temperature/schema config unchanged.

**Write-time gates** in `_process_scraped_jd` (`job_agent.py:1706-1741`), applied after parse, before staging — skipped rows are **never written** (no auto-delete of existing rows is implicated; these gates only run on the staging path):

1. **Domain gate (REQ-004-09)**: `job_domain == "None"` → skip + log. (Vertical companies can't hit this due to the override.)
2. **YoE gate (REQ-004-08)**: `min_yoe ≤ 3` or `min_yoe ≥ 12` → skip + log ("10+ years" → `min_yoe=10` → keep; "12+ years" → skip). `min_yoe is None` → keep; if title matches `r"\b(senior|sr\.?|staff|principal|director)\b"` set `yoe_flag = "auto-qualified (title)"`, else `yoe_flag = "manual review — YoE unstated"`. Never silently dropped.
3. **Work-auth gate (REQ-004-11)**: `citizenship_required` / `clearance_required` → skip + log. Kept rows persist `work_auth` verbatim to the `Work-Auth Status` column (G5 audit).
4. **Freshness gate (REQ-004-10, write-time only per Q3)**: see 2.2.3.

**Title filter (REQ-004-07)**: `TPM_KW` (`job_agent.py:449-450`) confirmed unchanged — permissive, no seniority exclusion. `_TITLE_BLOCK_KW`/`_ai_title_prefilter` (`job_agent.py:631-653`) are **kept but renarrowed**: rename to `_nontech_title_prefilter`, apply when `track == "Mid-large Tech"` (currently gated on `"big tech" in ai_domain.lower()` at `job_agent.py:643`), and remove `"operations"` from the blocklist (space/defense "Mission Operations TPM" is a legitimate track role); finance/HR/legal/etc. remain valid pre-Gemini cost savers. `llm_filter_jobs` (`job_agent.py:910-944`, Path B) has its system prompt rewritten from "strict Technical Recruiter specializing in AI … reject non-AI" to the 5-track rule with the same mapping anchors; company track is passed in so vertical companies keep all TPM titles.

#### 2.2.2 `is_ai_tpm` gating removal / counts

`count_tpm_jobs_by_company` (`shared/excel_store.py:687-711`) currently keys `ai_tpm` off `Is AI TPM == "True"`. New: `"qualified"` count = rows whose `Job Domain` ∈ 5 valid values (under REQ-004-09 that is every valid row). The `Company_List` `AI TPM Jobs` header is renamed `Qualified Jobs` in the same header migration that renames `AI Domain` (§4.3); `update_company_job_counts` (`shared/excel_store.py:742-762`) looks up the new header. The console tallies at `job_agent.py:2023-2029` update accordingly.

#### 2.2.3 Posting-date extraction, 15-day write-time gate, tiers (REQ-004-10)

**Current state**: no posting-date anywhere. `FRESH_DAYS = 5` (`job_agent.py:53`) drives a **re-scrape-effort** skip keyed on the Excel `Updated At` timestamp (`job_agent.py:1786-1796`) — that mechanism is orthogonal (scrape-cost optimization) and **stays as-is**.

**Target state**:
- Each ATS `list_fn` adds `"posted_date": <ISO date str or "">` to its candidate dicts:
  - `_fetch_ats_jobs` (`job_agent.py:474-511`): Greenhouse `updated_at`, Lever `createdAt` (epoch-ms) — add `date_field`/`date_parser` entries to `_ATS_FETCH` (`job_agent.py:453-472`).
  - `_fetch_ashby_jobs` (`job_agent.py:513-554`): `publishedDate` (tolerate `publishedAt` variant).
  - `_fetch_workday_jobs` (`job_agent.py:656-710`): `postedOn` relative text ("Posted Today", "Posted 2 Days Ago", "Posted 30+ Days Ago") via a new deterministic parser `_parse_workday_posted_on(text, today) -> date | None` ("30+ Days Ago" → date 31 days back, which correctly fails the 15-day gate).
  - Workable: `published_on` if present, else `""`.
  - Amazon adapter: `posted_date` field (see 2.2.5).
- **Metadata threading**: `process_company` (`job_agent.py:1745+`) generalizes the existing `workday_meta` pattern (`job_agent.py:1784`) into `list_meta = {l["url"]: l for l in raw}`; `_process_scraped_jd` receives it and injects `parsed["posted_date"]` before staging.
- **Write-time gate (Q3 resolution)**: applied **only to URLs not already in `known_url_meta`** — pre-scrape when the list API supplied a date (skip before spending Firecrawl/Gemini), post-parse otherwise. **Boundary convention (pinned per TPM design-review Finding 1)**: keep iff age ≤ 14 days; age ≥ 15 days → skip + log. This makes the gate boundary and the tier ceiling identical (every kept dated posting is tierable — no day-15 dead zone), and reads BRD "older than 15 days" as "15 or more days old". Existing rows are never retroactively touched (G7/REQ-004-16).
- **Unknown date**: keep + `Date Flag = "manual review — unknown posted date"`.
  *Clarification (Phase 4 code review F3)*: the freshness gate applies only to
  list-API-supplied dates pre-scrape; a date recovered later by backfill is
  NEVER a drop condition even if aged — the row keeps and sinks to Sort Tier 9.
  This resolves the "post-parse otherwise" ambiguity in favor of never-drop. Best-effort backfill: new `_backfill_posted_date(company, title, tavily_client) -> str` running one Tavily query scoped `site:linkedin.com/jobs "<title>" "<company>"` and regex-parsing a posted-date string from result snippets (REQ-004-19: search-signal only, never fetch LinkedIn pages). Runs only when `TAVILY_API_KEY` is set (new optional env read in job_agent `_main_inner`); failure leaves the flag for manual lookup. Never a drop condition.
- **Tier computation**: shared pure function in `shared/excel_store.py` (next to `classify_location`):
  ```python
  def compute_freshness_tier(posted_date: str, today: date | None = None) -> int | None:
      # age 0–2d → 1; 3–7d → 2; 8–14d → 3; >14d or unparsable/blank → None
  ```
  job_agent writes the tier at staging; the **sort path recomputes it every run** from `Posted Date` (Engineer review note 4) — see 2.3.3.

#### 2.2.4 Tightened geo filter (REQ-004-12)

**Current state**: `_is_us`/`_is_us_segment` (`job_agent.py:401-447`) keep any US location; applied in `_tpm_filter` (`job_agent.py:618-629`) and in `_process_scraped_jd` for generic-crawled JDs (`job_agent.py:1729-1733`).

**Target state**: new shared classifier in `shared/excel_store.py`:

```python
def classify_region(location: str) -> str:
    # → "Seattle" | "CA" | "TX" | "Remote" | "Other" | "Unknown"
```
built from the existing `classify_location` Seattle logic (`shared/excel_store.py:801-846`) plus CA/TX detection (state code `, CA`/`, TX`, full names, and the existing `_US_METRO` city lists partitioned by state). Remote reuses the `_US_REMOTE_QUALIFIERS` rule (US-remote only, existing `_is_us` semantics preserved). Multi-location strings ("; "-separated) qualify if **any** segment qualifies; the best region wins for sorting (precedence Seattle > Remote > CA > TX).

job_agent replaces its `_is_us(...)` keep checks with `classify_region(loc) != "Other"`; `"Unknown"`/placeholder locations keep (existing conservative behavior at `job_agent.py:429-444`) and rely on the post-extraction check. NYC-only postings now drop. TPM-review Finding 4(b) mitigation: dropped-row locations are logged at INFO with a `[GeoFilter]` prefix for early post-launch spot-checks.

#### 2.2.5 Scraper reliability (REQ-004-13/17/18/20)

- **Workday pagination (REQ-004-13, P0, G6a)**: `_fetch_workday_jobs` (`job_agent.py:656-710`) — replace the single `payload = {"limit": 20, "offset": 0, ...}` (`job_agent.py:678`) with a loop: `limit: 50`, `offset += 50`, terminate when a page returns fewer than `limit` postings or the response `total` field is reached; defensive runaway guard at 100 pages (5,000 postings) that logs an error if hit — a corruption guard, not a result cap.
- **Firecrawl map cap (REQ-004-13)**: `_firecrawl_map` (`job_agent.py:768-794`) — drop `limit=100` from `app.map(...)` (`job_agent.py:774`); no artificial cap.
- **Amazon.jobs adapter (REQ-004-17, P1, G6b)**: new `ATS_PLATFORMS["amazon"]` entry — `domains: ["amazon.jobs"]`, `strategy: "json_api"`, `list_fn: "_fetch_amazon_jobs"`, `jd_fn: None`. New `_fetch_amazon_jobs(career_url)` paginates `https://www.amazon.jobs/en/search.json?base_query=technical+program+manager&country=USA&result_limit=100&offset=N` via `_http_request_with_retry`; maps `jobs[].title`, `https://www.amazon.jobs` + `job_path`, `normalized_location` (join list with "; "), `posted_date`. Because `search.json` also returns `description` / `basic_qualifications` / `preferred_qualifications`, each candidate carries `"_prefetched_md": <assembled markdown>`; `_route_scraper` (`job_agent.py:1628-1658`) gains a Priority-0 check against `list_meta` prefetched markdown (generalizing the current `workday_meta` special case) — Amazon JDs need **zero** browser/Firecrawl calls and never fall to the generic crawler (G6b). Registered in `_resolve_list_fn` (`job_agent.py:812-819`). `KNOWN_CAREER_URLS["Amazon"]` already points at `https://www.amazon.jobs/` (`company_agent.py:145`) so routing engages with no data change. Adapter failure falls back to the existing crawler path exactly like other `json_api` platforms (TPM Finding 4(a)).
- **Google Careers adapter (REQ-004-18, P2, decoupled)**: fills the existing stub — `ATS_PLATFORMS["google"]["list_fn"]` flips from `None` (`job_agent.py:261`) to `"_fetch_google_jobs"` hitting the unofficial `careers.google.com/api/v3/search/?q=technical%20program%20manager&page=N` JSON API; JD scraping already exists (`_scrape_google_jd`, `job_agent.py:947-1037`). Shipped as an isolated follow-on PR; nothing else depends on it.
- **Tesla (REQ-004-20, P2)**: verification only — one regression test asserting `_scrape_tesla_jd` output passes the new gates (schema fields default sanely for unknown date/work-auth); no code change to `job_agent.py:1207-1393`.

#### 2.2.6 Console/count cleanups

`process_company` variable `ai_domain` (row[1] read at `job_agent.py:1750`) renames to `track`; retry-phase lookup map at `job_agent.py:1949-1963` likewise. Purely mechanical; positional column read is unchanged (col 2 keeps its position under the header rename).

### 2.3 `shared/excel_store.py` — schema, sort, selector

#### 2.3.1 `JD_HEADERS` (REQ-004-14)

**Current**: `shared/excel_store.py:20-30`, with `Is AI TPM` at position 9. **Target**:

```python
JD_HEADERS = ["JD URL", "Job Title", "Company", "Location", "Salary", "Requirements",
              "Additional Qualifications", "Responsibilities",
              "Job Domain",                 # replaces "Is AI TPM", same position
              "Updated At", "MD Hash", "Data Quality", "ATS Keywords",
              "Sort Tier",                  # replaces "Location Tier", same position
              "Posted Date", "Freshness Tier", "Min YoE", "YoE Flag",
              "Work-Auth Status", "Date Flag"]
```

`_JD_COL` (`shared/excel_store.py:51`) recomputes automatically — BUG-52's design goal. Writers `upsert_jd_record` / `batch_upsert_jd_records` (`shared/excel_store.py:578-647`) extend `row_data` with `d.get("job_domain","")`, `d.get("posted_date","")`, computed freshness tier, `d.get("min_yoe")`, `d.get("yoe_flag","")`, `d.get("work_auth","")`, `d.get("date_flag","")`; the JSON-error row template extends to match. Readers using `_JD_COL` (`get_jd_urls`, `get_jd_url_meta`, `get_incomplete_jd_rows`) need no changes.

**Migration mechanics**: because the user wipes JD_Tracker pre-launch (intake C3), no data migration — a new block in `get_or_create_excel` detects `Is AI TPM` in the header row, asserts the sheet has no data rows, and rewrites row 1 to the new `JD_HEADERS`. If data rows exist, it raises `RuntimeError("JD_Tracker still contains legacy rows — wipe required before PRJ-004 schema migration")` — a loud guard on the TPM-review precondition ("Confirm the wipe happened before shipping the schema change").

#### 2.3.2 `Company_List` `AI Domain` → `Track` rename (Q1 resolution)

- `COMPANY_HEADERS` / `WITHOUT_TPM_HEADERS` (`shared/excel_store.py:18-19`): `"AI Domain"` → `"Track"`; `"AI TPM Jobs"` → `"Qualified Jobs"`.
- New migration block in `get_or_create_excel` (same style as `shared/excel_store.py:141-171`): for both sheets, if header cell reads `AI Domain`, rename in place to `Track`; likewise `AI TPM Jobs` → `Qualified Jobs`. Data untouched (values migrate via the REQ-004-06 LLM pass, §4).
- Read/write sites are positional (col 2) — `get_company_rows` consumers (`job_agent.py:1750`, `company_agent` phase 1.5) are unaffected; the only name-keyed writes are `upsert_companies` (`shared/excel_store.py:322`, key change `ai_domain`→`track`) and `update_company_job_counts` (`shared/excel_store.py:752`, header lookup string change).

#### 2.3.3 Combined 1–6 sort tier (REQ-004-15)

**Current**: `sort_jd_tracker_by_tier` (`shared/excel_store.py:849-908`) sorts Greater Seattle → Remote → Other via `classify_location` + `_TIER_PRIORITY` (`shared/excel_store.py:793`), Updated-At-desc within tier.

**Target**: new pure function + rewritten sorter, same load→sort→rewrite skeleton:

```python
def compute_sort_tier(freshness_tier: int | None, region: str) -> int:
    # region ∈ {"Seattle","Remote"} → group A; {"CA","TX"} → group B
    # (T1,A)=1 (T1,B)=2 (T2,A)=3 (T2,B)=4 (T3,A)=5 (T3,B)=6
    # freshness None (unknown date / aged grandfathered rows) or region Other → 9
```

`sort_jd_tracker_by_tier` per row: read `Posted Date`, **recompute** `Freshness Tier` via `compute_freshness_tier` and write it back (Engineer review note 4 — tier drifts daily; scrape-time value alone goes stale), read `Location`, `classify_region`, compute `Sort Tier`, write it, then sort by (`Sort Tier` asc, `Posted Date` desc, `Updated At` desc). Row fills reuse the existing `PatternFill` constants: tiers 1–2 green, 3–4 yellow, 5+ none. Tier-9 rows (unknown-date/manual-review + grandfathered aged rows) sink to the bottom — visible, never deleted (REQ-004-16/G7: the sorter rewrites rows in place, count-preserving, exactly like today; no deletion path is added anywhere in this design).

#### 2.3.4 Row selector fix (REQ-004-21)

**Current**: `get_jd_rows_for_match` (`shared/excel_store.py:526-575`) filters `is_tpm != "True"` (`shared/excel_store.py:557-558`) against `_JD_COL["Is AI TPM"]` and hardcodes `"is_ai_tpm": True` into the reconstructed JSON (`shared/excel_store.py:569`). (Note: the intake's `get_ai_tpm_rows` name refers to this function's docstring behavior — no separately named function exists in the tree; the name `get_jd_rows_for_match` is already appropriate and is **kept**, so match_agent/resume_optimizer imports don't churn.)

**Target**: select **all valid JD rows** — keep `url` present, `company ∉ {"", "N/A", "JSON ERROR"}`, and `Data Quality != "failed"`; drop the boolean check. Read `Job Domain` and return it both in the dict (`{"url", "jd_json", "job_domain"}`) and inside the reconstructed `jd_json` (`"job_domain": <value>` replacing `"is_ai_tpm": True`) — the match layer routes on it (§2.4). Blank/invalid `Job Domain` (should not occur post-G2) → include with `job_domain="AI"` fallback + a logged warning, never dropped.

### 2.4 Match layer — 5 prompt pairs, routing, caching (REQ-004-22/23)

#### 2.4.1 `shared/prompts.py`

**Current**: one AI-framed pair `RECRUITER_SYSTEM_PROMPT` (`prompts.py:32-48`) / `HM_SYSTEM_PROMPT` (`prompts.py:51-67`), aliased `COARSE_/FINE_SYSTEM_PROMPT` (`prompts.py:78-79`); `TAILOR_SYSTEM_PROMPT`/`BATCH_TAILOR_SYSTEM_PROMPT` (`prompts.py:82-106`).

**Target** (single source of truth, REQ-052 pattern preserved):

```python
TRACKS = ("AI", "Robotics", "Fintech", "Space", "Defense")
RECRUITER_PROMPTS: dict[str, str]   # 5 entries, each = shared scoring mechanics
                                    #   (calibration bands, BatchCoarseResult contract,
                                    #    min-score-1, SECURITY_CLAUSE) + track persona
HM_PROMPTS: dict[str, str]          # 5 entries, each = 4-criteria weighted rubric with
                                    #   criterion 1 re-domained (e.g. Space: hardware/mission
                                    #   program depth instead of GenAI production depth) +
                                    #   the approved §4a positioning angle + SECURITY_CLAUSE
TAILOR_EMPHASIS: dict[str, str]     # 5 short per-track tailoring-emphasis clauses from the
                                    #   approved §4a narratives (e.g. Space/Defense:
                                    #   "do not push GenAI experience; emphasize large-scale
                                    #    systems discipline, hardware-software integration")

def get_prompt_pair(job_domain: str) -> tuple[str, str]:
    # returns (RECRUITER_PROMPTS[d], HM_PROMPTS[d]); unknown/blank → AI pair + log warning

def get_tailor_prompts(job_domain: str) -> tuple[str, str]:
    # (TAILOR_SYSTEM_PROMPT + TAILOR_EMPHASIS[d],
    #  that + the existing BATCH MODE suffix)
```

The `HM_PROMPTS["AI"]` entry is the current `HM_SYSTEM_PROMPT` content updated per the approved AI narrative; the mechanics scaffolding (weights 30/30/20/20, "brutally specific", BatchCoarseResult instructions) is shared via composition so the 5× maintenance surface stays small. `COARSE_/FINE_SYSTEM_PROMPT` aliases are retargeted to the AI pair and kept only until the test suite is updated (see §7 regression notes); new code uses the dicts. The persona line in each recruiter/HM prompt is written from a recruiter/HM hiring in that track, per REQ-004-22.

**Byte-identity guarantee (REQ-004-23 / REQ-052)**: `match_agent` Stage 2 and `resume_optimizer.re_score` both call `get_prompt_pair(job_domain)[1]` — the same interned constant per track. Before/after scores for a JD always come from the identical track pair; cross-track comparison is structurally impossible because the track travels with the JD row (`Job Domain` column → `get_jd_rows_for_match` → both agents).

#### 2.4.2 `agents/match_agent.py`

**Current**: Stage 1 `batch_coarse_score` uses `COARSE_SYSTEM_PROMPT` (`match_agent.py:176`), batches any 10 JDs per call (`match_agent.py:406-429`); Stage 2 `evaluate_match` uses `FINE_SYSTEM_PROMPT` (`match_agent.py:236`); context cache `_FINE_CACHE_NAME` (`match_agent.py:93-96`) is created once with `system_instruction=FINE_SYSTEM_PROMPT` (`match_agent.py:503-509`) and used in the cached config path (`match_agent.py:222-233`).

**Target**:
- `batch_coarse_score(resume_text, jds_batch, job_domain)` — config uses `get_prompt_pair(job_domain)[0]`. **Stage 1 batching groups by track first**: `pending_jds` is partitioned by `jd["job_domain"]`, then chunked by 10 within each group (a batch must share one system prompt). Same call count overall (≤4 extra partial batches per run worst-case); no schema change (`BatchCoarseResult` unchanged).
- `evaluate_match(resume_text, jd_json, job_domain)` — uncached path uses `get_prompt_pair(job_domain)[1]`.
- **Context caching with 5 HM prompts (decision)**: the Gemini caches API binds `system_instruction` into the cache (`gemini_pool.create_cache`, `shared/gemini_pool.py:171-204`), and a request using `cached_content` cannot supply a different system instruction — so one cache cannot serve five prompts. Design: `_FINE_CACHE_NAME: str | None` becomes `_FINE_CACHE_NAMES: dict[str, str]` — one cache per track, created **lazily** only for tracks with ≥ 2 fine-eval candidates in this run (same ≥2 threshold as today, `match_agent.py:502`), each caching `resume + HM_PROMPTS[track]`, TTL 3600s, display name `match-{run_id}-{track}`. `evaluate_match` looks up `_FINE_CACHE_NAMES.get(job_domain)`; miss → uncached path (existing transparent fallback). All caches deleted in the existing `finally` teardown (`match_agent.py:561-565`). Cost: worst case 5 small caches per run instead of 1 — the cached content is dominated by the resume (identical across tracks); the token savings per fine call are unchanged, and single-track runs behave exactly as today.
- Console copy at `match_agent.py:353, 380` ("AI-TPM JDs") updates to "domain-qualified JDs".

#### 2.4.3 `agents/resume_optimizer.py`

**Current**: imports `FINE_SYSTEM_PROMPT` (`resume_optimizer.py:38`); `tailor_resume` uses `TAILOR_SYSTEM_PROMPT` (`resume_optimizer.py:174-179`); `batch_tailor_resume` uses `BATCH_TAILOR_SYSTEM_PROMPT` (`resume_optimizer.py:207-212`); `re_score` uses `FINE_SYSTEM_PROMPT` (`resume_optimizer.py:252-257`); Recruiter rescore reuses `match_agent.batch_coarse_score` (`resume_optimizer.py:52, 505-509`); JD metadata built from `get_jd_rows_for_match` (`resume_optimizer.py:341-352`).

**Target**:
- `jd_meta[url]` gains `"job_domain"` (now returned by the selector); every `job_items` entry carries the track.
- `tailor_resume(resume_text, jd_content, job_domain)` / `batch_tailor_resume(resume_text, jd_contents, job_domain)` use `get_tailor_prompts(job_domain)` — batch tailoring therefore also **groups job_items by track** before chunking by `BATCH_TAILOR_SIZE` (`resume_optimizer.py:404-405`), same pattern as match Stage 1.
- `re_score(tailored_resume, jd_content, job_domain)` uses `get_prompt_pair(job_domain)[1]` — identical constant to match_agent Stage 2 for that track (byte-identity preserved).
- Recruiter rescore call passes the track: `batch_coarse_score(tailored_md, [jd_dict], job_domain)` (`resume_optimizer.py:507-509`).
- No `TAILORED_HEADERS`/`MATCH_HEADERS` changes (BRD §5): scores land in the same columns regardless of which track's prompts produced them.

### 2.5 Operational — launchd failure surfacing (REQ-004-25)

**Current**: `scripts/run_pipeline_scheduled.sh` — `run_step` failure fires a macOS notification and `exit 1` (`run_pipeline_scheduled.sh:30-34`); a missed notification leaves no persistent trace beyond the log file. RunSummary JSONs land in `run_logs/` per agent (`shared/run_summary.py:72-86`).

**Target** (Engineer review C4 — no new infrastructure):
- `run_step` failure branch additionally writes a marker: `printf '%s\nstep=%s\nlog=%s\n' "$(date '+%F %T')" "$step_name" "$LOG_FILE" > "$PROJECT_DIR/logs/LAST_RUN_FAILED"`.
- Successful completion (end of script) removes it: `rm -f "$PROJECT_DIR/logs/LAST_RUN_FAILED"` and writes `logs/LAST_RUN_OK` with the timestamp — a stale `LAST_RUN_OK` (>36h) is itself a detectable "runs stopped firing" signal, covering the launchd-never-ran failure mode that an error marker alone misses.
- Python-side: each agent's `finally` block already writes RunSummary; add `summary.note(f"gemini usage: {get_usage_summary()}")` (from `shared/gemini_pool.py:54-58`) in job/match/optimizer mains — this is also the measurement carrier for the REQ-004-26 trial run.
- Explicit statement per TPM Finding 2: P0 freshness tiering (REQ-004-10) has **no functional dependency** on this P1 alerting task; tiers are recomputed from `Posted Date` at every sort regardless of run cadence.

---

## 3. Data Contracts

### 3.1 `JD_Tracker` columns (full list, post-change)

| # | Column | Type / Allowed values | Writer |
|---|--------|----------------------|--------|
| 1–8 | JD URL, Job Title, Company, Location, Salary, Requirements, Additional Qualifications, Responsibilities | unchanged | job_agent |
| 9 | **Job Domain** (replaces `Is AI TPM`) | exactly one of `AI` / `Robotics` / `Fintech` / `Space` / `Defense` (no "Core-company" value) | job_agent |
| 10–13 | Updated At, MD Hash, Data Quality, ATS Keywords | unchanged | job_agent |
| 14 | **Sort Tier** (replaces `Location Tier`) | int 1–6, or 9 (unknown-date / aged / review) | `sort_jd_tracker_by_tier` |
| 15 | **Posted Date** | `YYYY-MM-DD` string, or blank (unknown) | job_agent (+ Tavily backfill) |
| 16 | **Freshness Tier** | 1 (1–2d) / 2 (3–7d) / 3 (8–14d) / blank (unknown or >14d) — recomputed each run at sort time | job_agent + sorter |
| 17 | **Min YoE** | int, or blank (unstated) | job_agent |
| 18 | **YoE Flag** | `""` / `auto-qualified (title)` / `manual review — YoE unstated` | job_agent |
| 19 | **Work-Auth Status** | `us_person_ok` / `none_stated` (kept rows only; `citizenship_required`/`clearance_required` rows are never written) | job_agent |
| 20 | **Date Flag** | `""` / `manual review — unknown posted date` | job_agent |

### 3.2 `Company_List` / `Company_Without_TPM` changed columns

| Column | Change |
|---|---|
| `AI Domain` → **`Track`** | header rename (in-place migration); values become exactly one of `AI-native` / `Mid-large Tech` / `Robotics` / `Fintech` / `Space` / `Defense` after the REQ-004-06 migration; any other value = unmigrated, flagged (see §4) |
| `AI TPM Jobs` → **`Qualified Jobs`** | header rename; value = count of that company's JD rows with a valid `Job Domain` |

`Match_Results` / `Tailored_Match_Results`: **no changes** (BRD §5).

### 3.3 Pydantic schema changes

- `agents/job_agent.py::JobDetails` — remove `is_ai_tpm: bool`; add `job_domain: Literal["AI","Robotics","Fintech","Space","Defense","None"]`, `min_yoe: int | None = None`, `work_auth: Literal["citizenship_required","clearance_required","us_person_ok","none_stated"] = "none_stated"`, `posted_date: str = ""` (code-injected, defaulted for cached round-trips).
- `agents/company_agent.py::CompanyInfo` (renamed from `AICompanyInfo`) — `ai_domain` field → `track: Literal["AI-native","Mid-large Tech","Robotics","Fintech","Space","Defense"]`.
- New `agents/company_agent.py::TrackClassification` for the migration pass: `company_name: str`, `track: Literal[<6 values>]`, `rationale: str` (BRD §6 audit-note mitigation), `confident: bool`.
- `shared/schemas.py` (`CoarseItem`, `BatchCoarseResult`, `MatchResult`, tailored schemas): **unchanged** — prompt routing does not alter response shapes.

---

## 4. Migration Plan

### 4.1 `Company_List` re-bucket (REQ-004-06) — one-time LLM pass

**Precondition (user-owned, blocking)**: user has manually pruned `Company_List` (intake §9.1). Tracked as an external dependency, not an engineering task.

**Mechanism**: new CLI mode `python agents/company_agent.py --migrate-tracks` (argparse added to `main()`; same pattern as resume_optimizer's `--force-rewrite`, `resume_optimizer.py:709-717`). Flow:

1. `get_or_create_excel` runs first → header renames (`AI Domain`→`Track`, `AI TPM Jobs`→`Qualified Jobs`) are already applied (§4.3).
2. Read all rows via `get_company_rows_with_row_num` (`shared/excel_store.py:287-302`); skip rows whose `Track` is already one of the 6 new values (idempotent — safe to re-run after partial failure).
3. Batch remaining rows (25/batch) into Gemini calls: input = company name + `Business Focus` text; `response_schema=list[TrackClassification]`; system prompt carries the 6 bucket definitions, the early-company rule, and the defense prime-exclusion list.
4. Deterministic post-check per result: `DEFENSE_EXCLUDED_PRIMES` match forces `Mid-large Tech` (a prime can survive only there); `confident == False` → do not write a track, write `UNMIGRATED — manual review` instead.
5. Write `Track` in place (new `update_company_track(xlsx_path, excel_row, value)` helper next to `update_company_career_url`, `shared/excel_store.py:352-360`); print a per-bucket tally + full audit table (name, old value, new track, rationale) for the user spot-check.
6. **Grandfathering (Q4)**: no trimming, ever. Post-migration bucket counts feed the discovery `need` calculation; a bucket at/over quota simply gets 0 new-discovery slots.

**Unmigrated-value handling downstream**: `job_agent` treats any `Track` value ∉ 6 buckets (including `UNMIGRATED — manual review` and stale legacy strings) as mid-large-tech for classification purposes + logs a `[Track] unmigrated value` warning per company per run. Never coerced, never dropped (BRD §6 mitigation).

### 4.2 `JD_Tracker` fresh start

Precondition: user wipes all JD rows (intake C3). Enforced by the assert-empty guard in the header migration (§2.3.1) — the schema change **cannot** silently apply over legacy data. No data migration code is written for JD_Tracker.

### 4.3 Header rename mechanics

Both renames (Company sheets + JD_Tracker header rewrite) live in `get_or_create_excel`'s existing migration chain (`shared/excel_store.py:70-246`), so every entry point (any agent, tests, the migration CLI) self-heals the workbook exactly once. Order within the function: sheet-level renames → Company header renames → JD_Tracker guard+rewrite → existing column-append migrations.

### 4.4 Rollout order (launch checklist)

1. Ship schema + code (tasks T1–T13, §6) — inert against a wiped JD_Tracker.
2. User prunes Company_List → run `--migrate-tracks` → user spot-checks.
3. User wipes JD_Tracker (guard verifies).
4. Discovery runs top up buckets toward quotas (multiple runs at `BATCH_SIZE=50`).
5. **Trial run** (REQ-004-26 second gate): one full uncapped single run; read Gemini/Tavily/Firecrawl consumption from RunSummary notes + `run_logs/`; user confirms cost.
6. Enable daily launchd schedule (REQ-004-25 already deployed with it).

---

## 5. G1 Tolerance Band Proposal (mandatory Phase 2 deliverable)

**Measurement point**: after the migration pass plus discovery convergence, defined as the first run where discovery adds < 5 net-new companies (yield exhaustion), or 10 discovery-enabled runs, whichever comes first.

**Proposed pass/fail band**:

| Metric | Pass condition | Rationale |
|---|---|---|
| Per-bucket count (each of the 6) | ≥ **80% of quota** (AI-native ≥ 120, Mid-large ≥ 120, each vertical ≥ 40) and ≤ quota **+ grandfathered overage** for that bucket (overage recorded by the migration tally) | The verticals are supply-constrained: early-company (~2000+/2010+) × hires-TPMs-in-Seattle/CA/TX × non-prime is a genuinely small universe for Space and Defense. 80% keeps G1 meaningful without incentivizing padding with low-quality entries. The ceiling is structural: discovery stops at quota; only grandfathered survivors may exceed it (Q4). |
| Total rows | ≥ **450** (90% of 500) and ≤ 500 + total grandfathered overage | Follows from the per-bucket floors; the 90% aggregate tolerates one lagging bucket. |
| Value validity | **100%** of rows carry one of the 6 valid `Track` values — no band, hard requirement | BRD G1 states this outright; `UNMIGRATED — manual review` rows must be resolved by the user before G1 sign-off. |

**Fail handling**: a bucket below 80% at convergence is a discovery-query problem, not a launch blocker for the other buckets — G1 is assessed per-bucket with a named exception list rather than pass/fail on the total alone. This band should be ratified by the Architect at design review (it is the BRD's one explicitly delegated number).

---

## 6. Implementation Task Breakdown

Ordering honors the TPM Sequencing Notes: schema-first; sort after freshness+geo; migration blocked on user pruning; trial run late-stage. All work on branch `prj-004-multi-track-expansion`.

**Critical path (P0)**: **T1 → T5(L) → T6 → T9 → T17**. Parallel P0 chains: T1 → T2 → T11 → T12 (match layer — T11/T12 build against T2's `job_domain` selector contract and do NOT wait on T5) and T1 → T3 → T4 (company layer — T4 externally blocked on user pruning). Independent roots T8, T10, T13 can land any time. T5 is the single longest-pole task; everything scraper-side (T6, T14, T15) queues behind it.

| # | Task | Size | REQs | P0 launch-blocking | Depends on |
|---|------|------|------|--------------------|------------|
| T1 | `excel_store` schema: new `JD_HEADERS`, `Track`/`Qualified Jobs` renames + migrations + assert-empty guard, writer `row_data` extension, `compute_freshness_tier`, `classify_region`, `compute_sort_tier` (functions only) | M | 14, part 10/12/15 | **Yes** | — |
| T2 | Row selector: `get_jd_rows_for_match` all-valid-rows + `job_domain` passthrough; `count_tpm_jobs_by_company`/`update_company_job_counts` qualified-count rework | S | 21 | **Yes** | T1 |
| T3 | `company_agent` taxonomy: `TRACK_VALUES`/`TRACK_QUOTAS`/`MAX_TOTAL=500`, `CompanyInfo.track`, per-bucket `need` math, new `TAVILY_QUERIES`, discovery prompt (early-company, defense exclusions + Palantir, space-experimental, hires-in-region), `_apply_bucket_rules` | M | 01,02,03,04,05 | **Yes** | T1 |
| T4 | Migration CLI `--migrate-tracks`: `TrackClassification` pass, grandfathering, unmigrated flagging, audit output, `update_company_track` helper | M | 06 | **Yes** (blocked externally on user pruning) | T1, T3 |
| T5 | `job_agent` extraction core: `JobDetails` fields, `extract_jd` track-aware prompts + mapping anchors + deterministic vertical override, write-time gates (domain/YoE/work-auth), `_nontech_title_prefilter` renarrow, `llm_filter_jobs` rewrite, `track` renames | L | 07,08,09,11 | **Yes** | T1, T2 |
| T6 | Posting dates: ATS date fields (GH/Lever/Ashby/Workday/Workable), `list_meta` generalization, 15-day write-time gate (new URLs only), tier write, unknown-date flag, Tavily backfill (`site:linkedin.com/jobs` scoped) | M | 10, 19 | **Yes** | T1, T5 |
| T7 | Geo tighten: `classify_region` wiring into `_tpm_filter` + post-extraction check, dropped-row logging | S | 12 | **Yes** | T1 |
| T8 | Uncap: Workday pagination loop; Firecrawl `limit` removal | S | 13 | **Yes** (G6a) | — |
| T9 | Sort: rewrite `sort_jd_tracker_by_tier` (recompute freshness, 1–6 tier, tier-9 sink, fills) | M | 15, 16 | **Yes** | T1, T6, T7 |
| T10 | `prompts.py`: `RECRUITER_PROMPTS`/`HM_PROMPTS`/`TAILOR_EMPHASIS` dicts + accessors (narratives approved 2026-07-07 — REQ-004-24 gate cleared) | M | 22, 24 | **Yes** | — |
| T11 | `match_agent` routing: per-track Stage-1 grouping, `evaluate_match(job_domain)`, per-track cache dict | M | 22 | **Yes** | T2, T10 |
| T12 | `resume_optimizer` routing: track-grouped tailoring, per-track `re_score`/recruiter rescore, tailor emphasis | M | 23 | **Yes** | T2, T10, T11 |
| T13 | launchd failure surfacing: marker files + RunSummary usage note | S | 25 | No (P1; freshness does not depend on it) | — |
| T14 | Amazon.jobs adapter (`_fetch_amazon_jobs`, prefetched-JD routing) | M | 17 | No (P1 fast-follow, G6b) | T6 |
| T15 | Tesla scraper regression verification under new filters | S | 20 | No (P2) | T5–T7 |
| T16 | Google Careers adapter | M | 18 | No (P2 stretch, fully decoupled) | T6 |
| T17 | Launch checklist: user prune → T4 run → user wipe → discovery top-up → **uncapped trial run + cost confirmation** (REQ-004-26 second gate) → enable daily schedule | S (eng share) | 26, 25 | **Yes** (gates rollout, not code) | all P0 |

---

## 7. Test Plan Outline

**Regression strategy for the existing 859-case suite (G9)**: the suite must end at 100%, but the schema rename intentionally breaks fixtures. One dedicated pass updates: `tests/test_excel_store.py` (185 cases — `JD_HEADERS` fixtures, `Is AI TPM` assertions → `Job Domain`, sort-tier expectations), `tests/test_job_agent.py` (209 — `JobDetails`/`extract_jd`/prefilter fixtures), `tests/test_match_agent.py` / `tests/test_resume_optimizer.py` (78/54 — prompt-constant references), `tests/test_shared_prompts.py` (18 — single-source assertions move to the dicts), `tests/test_company_agent.py` (111 — taxonomy constants). Semantic assertions are preserved; only vocabulary/fixtures change. Everything else (`ats_matcher` 50, gemini_pool, resume_io, run_summary, prompt_injection, workday_url…) must pass **unmodified** — any needed change there is a design regression signal.

**New unit tests by REQ area** (mock-based, consistent with existing suite conventions):

| Group | Tests | Verifies |
|---|---|---|
| Taxonomy & quotas | per-bucket `need` math incl. grandfathered-overage → 0 slots; `_apply_bucket_rules` prime exclusion + Palantir allowlist; `CompanyInfo.track` Literal rejection of legacy values | G1 (with §5 band), REQ-01/02/03 |
| Migration | `--migrate-tracks` idempotency (valid rows skipped); unconfident → `UNMIGRATED — manual review`; prime forced to Mid-large; no row deletion; JD_Tracker guard raises on non-empty legacy sheet | G1, REQ-06/14 |
| Domain classifier | vertical company → deterministic override; mid-large `"None"` → skipped not written; unmigrated track → mid-large path + warning; anchor prompts contain all 5 mapping rules (string assertions) | G2, REQ-09 |
| YoE | boundary table: 3→skip, 4→keep, 10→keep, 12→skip; unstated+Senior title → auto-qualified; unstated+plain title → manual-review flag row written | G3, REQ-08 |
| Freshness | `compute_freshness_tier` band boundaries (2/3, 7/8, 14/15 days); write-time gate keeps a 14-day posting, skips a 15-day posting (pinned boundary), leaves existing rows untouched; unknown date → kept + Date Flag; Workday `postedOn` relative-string parser incl. "30+ Days Ago"; Lever epoch-ms parse | G4, G7, REQ-10/16 |
| Work-auth | 4-way classification fixtures incl. "must be able to obtain a clearance" → skip; kept rows always carry audit value | G5, REQ-11 |
| Geo | `classify_region` matrix (Seattle metro, SoCal cities, TX, `Remote, Canada` → Other, NYC → Other, multi-segment best-region) | REQ-12 |
| Scrapers | Workday pagination: mocked 3-page response → all postings returned, loop terminates; >20 synthetic postings survive (G6a unit proxy); Firecrawl `map` called without `limit`; Amazon: search.json fixture → URLs/dates/prefetched JD, zero crawler fallback (G6b) | G6a/G6b, REQ-13/17 |
| Sort | `compute_sort_tier` 6-cell matrix + tier-9 cases; sorter recomputes stale freshness tiers; row count preserved (no deletion) | G4, G7, REQ-15/16 |
| Selector | all-valid-rows selection ignores domain value; blank domain → AI fallback + warning; `job_domain` present in returned dict and jd_json | REQ-21 |
| Prompt pairs | all 5 pairs exist, distinct, SECURITY_CLAUSE-suffixed; `get_prompt_pair` fallback; **byte-identity test**: object identity of HM prompt used by `evaluate_match` and `re_score` per track; Stage-1 batches never mix tracks; per-track cache created only for tracks with ≥2 fine JDs and all deleted on teardown | G8, REQ-22/23 |
| Operational | wrapper script: failed step → `LAST_RUN_FAILED` exists with step name; success → removed + `LAST_RUN_OK` written (bash test or subprocess harness) | REQ-25 |

**Acceptance / launch verification (non-unit)**: G3's 20-JD spot-check, G5's space/defense JD sample audit, G6a live NVIDIA run, and the G10 trial-run cost readout are launch-checklist items (T17), not CI tests. `tests/test_acceptance.py` gains the intake §9.4 seeds as fixture-level assertions ("a '12+ years' JD never reaches the sheet", "every row has a tier or a flag", "no kept row requires citizenship/clearance").

---

## 8. Risks & Open Design Questions

**Risks (design-level, beyond BRD §6):**
- *Test-suite churn concentration*: T1's rename fans out into 5 test files at once; mitigated by landing T1+fixture updates as one atomic PR so the suite is never red across commits.
- *Workday relative-date granularity*: `postedOn` strings floor at day resolution and "30+" saturates; Tier-1 (1–2d) boundaries are safe, but a tenant returning only "Posted 30+ Days Ago" for everything would gate all its jobs — the unknown-date keep+flag path is the fallback if `postedOn` is absent, and the parser treats unparseable text as unknown, not as aged.
- *Per-track cache API limits*: 5 concurrent caches per run is well within Gemini caches quota, but if `create_cache` starts failing for later tracks the transparent uncached fallback (existing behavior) absorbs it — no new failure mode.

**Open questions for the Architect (genuinely undecidable here):**
1. **Unmigrated-track fallback**: this design routes companies with invalid `Track` values through the mid-large-tech (strictest) classifier path rather than skipping them entirely. Confirm skip-vs-strict preference.
2. **`AI TPM Jobs` → `Qualified Jobs` rename**: implied but not mandated by the BRD (only `AI Domain`→`Track` was resolved). Confirm, or keep the stale header to reduce churn.
3. **Pre-scrape freshness gating**: applying the 15-day gate before scraping (when the list API supplies the date) saves Firecrawl/Gemini spend but means a skipped job leaves no audit trace beyond a log line. Confirm the efficiency reading of "skip at scrape time" is acceptable.
4. **G1 tolerance band** (§5): the 80%-per-bucket / 90%-total numbers need explicit ratification — this is the BRD's delegated Phase-2 number.
5. **Tavily in job_agent**: the posting-date backfill introduces `TAVILY_API_KEY` as an optional job_agent dependency (currently company_agent-only). Confirm acceptable, or defer backfill to a follow-on task within REQ-004-10 (the keep+flag path satisfies the requirement without it).

### Resolutions (User, 2026-07-07 design review — all per TPM/Engineer recommendations)

1. **Q1 — RESOLVED (D-17)**: unmigrated/invalid `Track` values route through the strict mid-large-tech classifier path + logged warning; never skipped, never coerced.
2. **Q2 — RESOLVED (D-15)**: `AI TPM Jobs` → `Qualified Jobs` rename approved; rides the same header-migration block.
3. **Q3 — RESOLVED (D-18)**: pre-scrape freshness gating accepted; log-line trace is sufficient audit for never-written rows.
4. **Q4 — RESOLVED (D-16)**: G1 tolerance band ratified as proposed in §5 (≥80% per bucket, ≥450 total, 100% valid track values, measured at discovery convergence).
5. **Q5 — RESOLVED (D-19)**: Tavily accepted as an optional job_agent dependency for posting-date backfill.
