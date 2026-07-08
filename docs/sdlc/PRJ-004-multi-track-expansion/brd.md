# BRD: Multi-Track Expansion

**Project ID**: PRJ-004
**Author**: PM Agent
**Status**: Approved (User, 2026-07-07 — TPM & Engineer Lead reviews applied; §7 questions resolved, see resolutions)
**Date**: 2026-07-07

---

## 1. Background & Problem Statement

PathFinder is a 4-agent pipeline (company discovery → job discovery/JD extraction → resume-JD matching → resume tailoring) persisting to `pathfinder_dashboard.xlsx`. It currently targets **North American AI companies only** — 6 AI-domain buckets, hard-capped at 200 total companies (`agents/company_agent.py:59-90`) — and gates every downstream stage (job filtering, matching, tailoring) on an AI-relevance judgment (`Is AI TPM`, `_ai_title_prefilter`, `llm_filter_jobs`'s AI-only rejection).

The user (a big-tech TPM: 4 years SDE + 6 years TPM, green-card holder) has updated their job-search thesis: six tracks — **AI, mid-large tech, robotics, fintech, space, defense** — have strong 10-year runway, and the winning play is **"early companies, and early divisions inside established companies"** (e.g., Amazon Leo, Project Kuiper, Azure Government, Google Pay). The current AI-only scope structurally excludes five of these six tracks.

Two secondary problems compound the scope gap:
- **Freshness is not tracked.** The pipeline has no posting-date extraction (`FRESH_DAYS = 5` in `agents/job_agent.py:53` operates on the Excel write timestamp, not the actual posting date) even though postings older than ~15 days have materially lower response rates.
- **Seniority is judged by title, not content.** Title conventions vary too much across companies (e.g., an Oracle "Principal TPM" ≈ 8 years elsewhere) — there is no years-of-experience extraction or filter today, so both under- and over-senior roles pass through undifferentiated.

Additionally, two known scraper gaps (Amazon has no ATS adapter and falls to a chronically-failing generic crawl path; Workday and Firecrawl both have hidden per-company result caps) understate job volume even within the current single-track scope, and would understate it more severely at 500 companies.

Company_List currently sits at **203 companies** (near the existing 200 cap). JD_Tracker is currently empty (0 rows) — pipeline is between runs / awaiting the pre-launch wipe described in the intake doc.

This BRD formalizes the six-track expansion, freshness/seniority/work-authorization filtering, sort/schema changes, and scraper reliability fixes specified in the signed-off intake document (`docs/sdlc/multi-track-expansion-requirements.md`, 2026-07-07), which is the authoritative source for every requirement below.

---

## 2. Goals & Success Criteria

| # | Goal | Success Criteria (measurable) |
|---|------|-------------------------------|
| G1 | Expand company universe to 6 tracks at 500-company scale | `Company_List` converges toward 500 rows distributed across the 6 buckets at their target quotas (AI 150 / Mid-large tech 150 / Robotics 50 / Fintech 50 / Space 50 / Defense 50), within a tolerance band agreed in Tech Design (bucket caps are quotas, not hard limits on survivors — see §7 open question). **Pinning the numeric tolerance band is a mandatory Phase 2 (Tech Design) deliverable** — G1 is not verifiable until it exists. 100% of rows carry one of the 6 valid bucket values (no blank/legacy values post-migration). |
| G2 | Every kept job row is domain-qualified under the new 5-track classifier | 100% of `JD_Tracker` rows have a non-blank `Job Domain` value ∈ {AI, Robotics, Fintech, Space, Defense} — zero rows with the old `Is AI TPM` semantics. |
| G3 | Seniority filtered by extracted YoE, not title | Spot-check sample of 20+ scraped JDs: 0 rows with an explicitly-stated minimum ≥12 years appear in the sheet; 0 rows with an explicitly-stated minimum ≤3 years appear in the sheet. Rows with no stated YoE are 100% either auto-qualified (Senior/Staff/Principal/Director title) or flagged for manual review — never silently dropped. |
| G4 | Freshness tracked and tiered | 100% of `JD_Tracker` rows have either a `Freshness Tier` value (1/2/3) or an explicit unknown-date manual-review flag — 0 rows with neither. 0 rows older than 15 days at scrape time are newly written (pre-existing rows are exempt per the no-auto-delete rule, G7). |
| G5 | Work-authorization screen applied globally | 0 kept rows require US citizenship or a security clearance (including "must be able to obtain a clearance" phrasing), verified against a sample of space/defense/gov-cloud JDs. 100% of rows carry a `Work-Auth Status` audit value. |
| G6a | Workday pagination verified (launch-blocking, REQ-004-13 P0) | NVIDIA (Workday) returns >20 TPM jobs in a run where >20 exist (pagination works). |
| G6b | Amazon adapter live (non-blocking fast-follow, REQ-004-17 P1) | Amazon jobs are discovered via the new `amazon.jobs` adapter with 0 fallback to the generic crawler for Amazon. Not a launch Go/No-Go criterion. |
| G7 | Row lifecycle unchanged (no silent data loss) | 0 automated deletions of aged `JD_Tracker` rows across the test period — row removal remains a user-initiated manual action. |
| G8 | Per-track match scoring is live and self-consistent | All 5 Recruiter/HM prompt pairs exist and are exercised by at least one test each; for a given JD, the original score and the tailored re-score in `resume_optimizer` are computed from the identical track's prompt pair (0 cross-track comparisons in test coverage). |
| G9 | No regression | Full existing test suite (859 cases, currently 100% passing) continues to pass at 100%, plus new tests covering B2/B4/B5/B6/B7 filters, the C1 schema change, and E2 per-track routing. |
| G10 | Cost/runtime sized and confirmed before rollout | §5 sizing estimate delivered in this BRD; user gives explicit go/no-go on the projected Gemini/Tavily/Firecrawl consumption before the first full 500-company daily run is enabled (per the project's standing "confirm before batch paid-API commitments" rule). |

---

## 3. Scope

### In-Scope
- New 6-bucket company taxonomy (AI-native / Mid-large tech / Robotics / Fintech / Space / Defense) at a 500-company total cap, replacing the current 6 AI-domain buckets and 200 cap.
- Early-company founding filter (~2000+) for the 5 vertical buckets, with defense's additional legacy-primes hard-exclusion list and a Palantir allowlist exception.
- "Hires TPMs in region" geography semantics (Greater Seattle / California incl. SoCal / Texas), replacing HQ-based geography, with no cross-region percentage quotas.
- One-time re-bucketing (LLM classification pass) of existing `Company_List` survivor rows into the new taxonomy.
- Permissive title filter confirmation (no title-based seniority exclusion).
- New years-of-experience extraction and [4,10]-year keep window, with defined unstated-YoE fallback behavior.
- New 5-track domain classifier replacing the AI-purity filter layer, including the cloud/compute→AI and payments→Fintech sub-rules.
- New posting-date extraction, 15-day freshness cutoff, and 3-tier freshness classification.
- New global work-authorization screen (citizenship/clearance skip; US-person/green-card/unstated keep) with an audit column.
- Tightened job geo filter (Seattle / CA / TX / US-Remote only).
- Removal of the Workday `limit: 20` and Firecrawl `map limit=100` hidden truncations.
- `JD_Tracker` schema changes: `Is AI TPM` → `Job Domain`; new `Posted Date`, `Freshness Tier`, `Min YoE`, `Work-Auth Status`, unknown-date flag, unparsed-YoE flag columns. `Company_List` `AI Domain` column semantics updated to the new 6-bucket taxonomy.
- New single combined 1–6 sort tier (freshness primary, Seattle+Remote > CA/TX secondary), replacing the current Seattle→Remote→Other tier sort.
- Confirmation that the no-auto-delete row lifecycle continues to hold.
- Amazon.jobs JSON adapter.
- Workday pagination fix.
- Google Careers adapter (explicitly a stretch goal, not a launch blocker).
- LinkedIn used only as a Tavily-scoped search signal (company hints, posting-date backfill) — never scraped directly.
- Verification (not rebuild) that the existing Tesla custom scraper still works.
- `get_ai_tpm_rows`/`get_jd_rows_for_match` row-selector fix to "all valid JD rows" instead of `Is AI TPM == True`.
- 5 new Recruiter/HM prompt pairs (one per vertical track) in `shared/prompts.py`, with `match_agent` routing by `Job Domain`.
- `resume_optimizer` routing so tailoring and re-scoring use the same track's prompts as the original score.
- 5 candidate-positioning narratives, drafted in this BRD phase (see §4a) for explicit user review/approval before implementation.
- Daily-run failure surfacing (the existing `launchd` runner, REQ-133, must not fail silently).
- Cost/runtime sizing estimate (this document, §5) with explicit user confirmation gate before full-scale rollout.

### Out-of-Scope
- Scraping LinkedIn job pages directly (policy decision — ToS and blocking risk; LinkedIn is search-signal-only).
- Any change to the ATS keyword-matching dimension (`shared/ats_matcher.py` / `shared/ats_synonyms.py`) — it stays shared and unchanged across all 5 tracks.
- Regional percentage quotas across Seattle/California/Texas (explicitly dropped in favor of bucket caps).
- User's own pre-launch data hygiene: manually pruning `Company_List` and wiping current `JD_Tracker` rows are user-owned actions, not agent/code work.

---

## 4. Functional Requirements

### 4.1 Company Discovery (`agents/company_agent.py`)

| REQ ID | Description | Priority |
|--------|-------------|----------|
| REQ-004-01 | Replace the 6 AI-domain buckets and `MAX_TOTAL = 200` cap (`agents/company_agent.py:59-90`) with a 6-bucket taxonomy — AI-native (150) / Mid-large tech (150) / Robotics (50) / Fintech (50) / Space (50) / Defense (50) — totaling 500. | P0 |
| REQ-004-02 | Apply an early-company founding filter (~2000+) to the 5 vertical buckets (AI, robotics, fintech, space, defense). Legacy incumbents (e.g., Boeing, Visa, PayPal, Intuit, Boston Dynamics, ABB) are excluded from vertical buckets; they may qualify via the mid-large-tech bucket where their track-relevant TPM roles pass the domain filter (REQ-004-09). | P0 |
| REQ-004-03 | Defense bucket additionally hard-excludes legacy primes (Boeing, Lockheed Martin, Raytheon/RTX, Northrop Grumman, General Dynamics, BAE, L3Harris); discovery targets venture-backed / roughly-post-2010-founded defense tech (e.g., Anduril, Shield AI, Saronic, Castelion). Palantir is an explicit allowlist exception to the early-company rule. | P0 |
| REQ-004-04 | Space bucket applies the early-company rule experimentally (prefer SpaceX/Relativity/Stoke over incumbent space divisions); flagged for post-launch review of results before being made a hard rule. | P1 |
| REQ-004-05 | Geography qualification changes to "hires TPMs in region" (Greater Seattle, California incl. Bay Area + Southern California, Texas) rather than HQ location. No cross-region percentage quotas — bucket caps alone balance distribution. | P0 |
| REQ-004-06 | One-time migration: re-bucket existing `Company_List` survivor rows (post user manual pruning) into the new 6-bucket taxonomy via an LLM classification pass; survivors count against their new bucket's quota; discovery only tops up remaining slots. User spot-checks output. | P0 |

### 4.2 Job Discovery & Filtering (`agents/job_agent.py`)

| REQ ID | Description | Priority |
|--------|-------------|----------|
| REQ-004-07 | Confirm the title filter stays permissive: any TPM-keyword title passes (existing `TPM_KW` substring match, `agents/job_agent.py:449-450`, already covers Senior/Staff/Principal/Director prefixes). No title-based seniority exclusion is introduced. | P0 |
| REQ-004-08 | Extract the JD's minimum required years of experience (new field). Keep if min ∈ [4, 10]; skip if min ≤ 3 or min ≥ 12 ("10+ years" keeps, "12+ years" skips). If unstated: keep the row; auto-mark qualified if title carries a Senior/Staff prefix, otherwise flag for manual review. | P0 |
| REQ-004-09 | Replace the AI-purity filter layer (`_ai_title_prefilter`, the AI-only rejection in `llm_filter_jobs`, `is_ai_tpm` gating — `agents/job_agent.py:632-653, 910-944, 1543-1616`) with a 5-track domain classifier. Vertical-bucket companies (AI/robotics/fintech/space/defense) qualify every TPM role; mid-large-tech companies qualify only roles matching one of the 5 tracks. Cloud/compute infrastructure roles (AWS/GCP/Azure infra, datacenter, silicon) count as AI track; payments-org roles (Google Pay, Apple Pay, Amazon Payments) count as Fintech track. | P0 |
| REQ-004-10 | Extract posting date from ATS JSON APIs already called (Greenhouse `updated_at`, Lever `createdAt`, Ashby `publishedDate`, Workday `postedOn`). Skip postings older than 15 days at scrape time. Tier the rest: Tier 1 = 1–2 days, Tier 2 = 3–7 days, Tier 3 = 8–14 days, recomputed each run from the actual posted date. Unknown date: keep + flag; best-effort backfill via Tavily-scoped LinkedIn/other-platform search; if not found, leave for manual lookup — never silently drop. | P0 |
| REQ-004-11 | Global work-authorization screen applied to every job across all buckets: skip if the JD requires US citizenship or a security clearance (including "must be able to obtain a clearance"). Keep if the JD states "US person"/permanent resident (ITAR standard, includes green card) or has no status requirement. Record the result in a `JD_Tracker` `Work-Auth Status` column. | P0 |
| REQ-004-12 | Tighten the job geo filter to keep only Greater Seattle / California / Texas / US-Remote (current behavior keeps all US locations — e.g., NYC-only postings must now be dropped). Remote continues to require US-remote per existing `_is_us` logic. | P0 |
| REQ-004-13 | Remove the two hidden result-count truncations: Workday fetch hardcoded `limit: 20` per company (`agents/job_agent.py:678`) → add pagination; Firecrawl map `limit=100` (`agents/job_agent.py:774`) → lift the cap. No artificial cap on scraped job count. | P0 |

### 4.3 Data & Excel (`shared/excel_store.py`)

| REQ ID | Description | Priority |
|--------|-------------|----------|
| REQ-004-14 | `JD_Tracker` schema: replace `Is AI TPM` with `Job Domain` (exactly 5 values: AI / Robotics / Fintech / Space / Defense — no "Core-company" value). Add `Posted Date`, `Freshness Tier`, `Min YoE`, `Work-Auth Status`, and manual-review flag columns (unknown date, unparsed YoE). `Company_List` `AI Domain` column semantics update to the new 6-bucket taxonomy (values only — see §7 for a naming question). | P0 |
| REQ-004-15 | Replace the current Seattle→Remote→Other tier sort (`shared/excel_store.py:849-908`) with a single combined 1–6 tier index: (1) Seattle+Remote/1-2d, (2) CA/TX/1-2d, (3) Seattle+Remote/3-7d, (4) CA/TX/3-7d, (5) Seattle+Remote/8-14d, (6) CA/TX/8-14d. Freshness is primary; within a freshness band, Seattle+Remote outranks CA/TX. | P0 |
| REQ-004-16 | Confirm/preserve row lifecycle: the pipeline never auto-deletes aged `JD_Tracker` rows; row removal remains a user-initiated manual action after each run. | P1 |

### 4.4 Scraper Reliability

| REQ ID | Description | Priority |
|--------|-------------|----------|
| REQ-004-17 | Add an Amazon.jobs adapter using the public `amazon.jobs/en/search.json` endpoint (titles, locations, posting dates), replacing the current fallback to the chronically-failing generic browser-crawl path for Amazon. | P1 |
| REQ-004-18 | Add a Google Careers adapter using the unofficial `careers.google.com` JSON search API, enabling job discovery (Google is currently JD-only, `domains: []`). Stretch goal — not a launch blocker. | P2 |
| REQ-004-19 | LinkedIn policy: use LinkedIn only as a Tavily-scoped search signal (`site:linkedin.com/jobs`) for company-discovery hints and posting-date backfill (REQ-004-10). Never scrape LinkedIn pages directly; route to the company's own ATS for actual job data. | P0 |
| REQ-004-20 | Verify the existing Tesla custom scraper (post BUG-32/BUG-15 fixes) still functions correctly under the new filters — regression check, not a rebuild. | P2 |

### 4.5 Match Layer (`agents/match_agent.py`, `agents/resume_optimizer.py`, `shared/prompts.py`)

| REQ ID | Description | Priority |
|--------|-------------|----------|
| REQ-004-21 | Fix the row selector: `get_ai_tpm_rows`/`get_jd_rows_for_match` (`shared/excel_store.py:526-528`) currently select only `Is AI TPM == True` rows. Change to "all valid JD rows" — under REQ-004-09, every written `JD_Tracker` row is already domain-qualified. | P0 |
| REQ-004-22 | Add 5 Recruiter/HM system-prompt pairs (AI / Robotics / Fintech / Space / Defense) to `shared/prompts.py`, each written from the persona of a recruiter/hiring manager who hires in that track. `match_agent` routes each JD to its series by `Job Domain`, replacing the single AI-framed pair (`RECRUITER_SYSTEM_PROMPT`/`HM_SYSTEM_PROMPT`, currently aliased as `COARSE_SYSTEM_PROMPT`/`FINE_SYSTEM_PROMPT` and called at `agents/match_agent.py:176,236,505`). The shared ATS dimension (`shared/ats_matcher.py`) is unchanged. | P0 |
| REQ-004-23 | `resume_optimizer` follows the same per-track routing for both tailoring and re-scoring (call sites `agents/resume_optimizer.py:175,253,483`) — before/after scores must come from the same track's prompt pair to remain comparable (preserves the REQ-052 byte-identical-prompt guarantee per track), and tailoring emphasis must fit the domain (e.g., do not push GenAI experience for a SpaceX role). | P0 |
| REQ-004-24 | Draft 5 candidate-positioning narratives (one per track), replacing the current single "big-tech TPM transitioning into an AI TPM role" framing. Drafted in this BRD (§4a); **requires explicit user review and approval before implementation** — the user owns their story. | P0 |

### 4.6 Operational

| REQ ID | Description | Priority |
|--------|-------------|----------|
| REQ-004-25 | Daily runs are a formal requirement: the 1–2-day freshness tier (REQ-004-10) is only meaningful with daily execution. The existing `launchd` daily runner (REQ-133, `scripts/run_pipeline_scheduled.sh`) must be extended so a failed daily run is surfaced (e.g., a detectable failure marker/log/alert), not silently absorbed. | P1 |
| REQ-004-26 | Deliver a cost/runtime sizing estimate before implementation begins (this document, §5), covering the new steady state of 500 companies × uncapped jobs × daily runs, and obtain explicit user confirmation before enabling full-scale rollout — per the project's standing rule to confirm before batch paid-API commitments. | P0 |

### 4a. Candidate Positioning Narratives — DRAFT (REQ-004-24, pending user approval)

These are first-pass strategic angles only, built from the profile summary on file (4 years SDE + 6 years big-tech TPM, green card, targeting senior TPM roles at 4–10 YoE). They are **not final copy** — resume/narrative language itself is out of scope for this BRD and remains authored by the user per the project's "user as author, AI as tool" framing convention; these are positioning *angles* for the per-track HM/Recruiter prompts and tailoring emphasis to key off of.

| Track | Draft Positioning Angle |
|-------|--------------------------|
| AI | Big-tech TPM background bringing cross-functional program discipline (roadmap ownership, eng/product/research coordination at scale) to fast-moving AI product and infrastructure orgs; emphasize any GenAI/ML-adjacent program exposure. |
| Robotics | SDE-to-TPM trajectory framed as systems-integration strength — hardware/software coordination experience from large-scale distributed systems applied to robotics program management (perception/planning/hardware team coordination). |
| Fintech | Big-tech-scale program rigor (compliance-adjacent, cross-team dependency management, launch coordination) applied to fintech's regulatory and reliability bar; emphasize any payments/risk/scale-critical system experience. |
| Space | 4 yrs SDE + 6 yrs big-tech TPM bringing large-scale systems discipline to hardware/mission programs — frame prior program scale (multi-team, multi-quarter roadmaps) as directly transferable to space program cadence and hardware-software integration. |
| Defense | Similar large-scale-systems-discipline framing as Space, emphasizing mission-critical reliability and cross-functional delivery; explicitly do not overstate clearance-adjacent experience the candidate does not hold (green-card status, not citizenship). |

**~~Action required~~ APPROVED (User, 2026-07-07)**: all five angles approved as drafted — REQ-004-24 gate cleared; REQ-004-22/23 unblocked.

---

## 5. Dependencies & Constraints

**External services (existing, increased volume):**
- **Gemini** (`google-generativeai`, model `gemini-3.1-flash-lite`) — company classification, JD structured extraction, domain/YoE/work-auth judgment calls, Recruiter/HM scoring (×5 tracks now), resume tailoring.
- **Tavily** — company discovery search, career-URL discovery, and now also LinkedIn-scoped posting-date backfill search (REQ-004-10/19).
- **Firecrawl** — career-page mapping/scraping (map cap removed per REQ-004-13) and non-ATS JD scraping.
- **ATS JSON APIs** (no new auth needed, existing integration pattern): Greenhouse, Lever, Ashby, Workday, Workable — extended with posting-date fields (REQ-004-10) and Workday pagination (REQ-004-13).

**New external dependency:**
- **Amazon.jobs public JSON search endpoint** (`amazon.jobs/en/search.json`) — undocumented but public, no API key required; same reliability class as the existing Workday/Ashby undocumented-JSON-API pattern already in production.
- **Google Careers unofficial JSON API** (`careers.google.com`) — stretch goal only (REQ-004-18); same undocumented-API risk class, deprioritized to P2.

**Data-contract / schema changes (backward compatibility):**
- `JD_Tracker`: `Is AI TPM` (boolean-like) → `Job Domain` (5-value enum) is a breaking column semantics change. Per the intake doc (§4, C3) the user wipes existing `JD_Tracker` rows pre-launch, so no in-place data migration is required — only the header/column-list change in `shared/excel_store.py`'s `JD_HEADERS` and every function keyed off it. The project's existing dynamic-column-lookup pattern (`_JD_COL` dict, introduced in BUG-52 specifically to eliminate hardcoded column numbers) should absorb this without touching read paths individually.
- `Company_List`: `AI Domain` column is **not** wiped — existing rows get re-bucketed in place (REQ-004-06). This is a softer, semantic-only migration (same column, new value vocabulary) and needs explicit handling for partial/failed reclassification (see §6 Risks).
- `MATCH_HEADERS` / `TAILORED_HEADERS`: no header changes required for the per-track prompt work (REQ-004-22/23) — scores stay in the same `Recruiter Score`/`HM Score` columns regardless of which track's prompt produced them; only the prompt selection logic changes.

**Process constraints (from intake doc, non-negotiable):**
- User pre-launch actions (manually pruning `Company_List`, wiping `JD_Tracker`) are blocking prerequisites for rollout but are explicitly the user's own action, not an engineering deliverable.
- REQ-004-24 (positioning narratives) has a hard user-approval gate before implementation — Tech Design cannot proceed on the match-layer prompt work until this is resolved.
- REQ-004-26 (cost estimate, below) has a hard user-confirmation gate before the first full-scale (500-company, uncapped, daily) run.

**Cost / runtime sizing (REQ-004-26 — informational, requires user confirmation):**

| Dimension | Current | Projected at full scale | Driver |
|---|---|---|---|
| Companies tracked | 203 (near 200 cap) | up to 500 | REQ-004-01; ~297 net-new companies to discover across 5 quota-constrained buckets, most one-time (discovery), not daily. |
| Companies scraped per daily run | up to 203 | up to 500 | ~2.5× more per-company career-page scrapes daily (Tavily/Firecrawl/ATS-API calls). |
| Jobs per company | capped (Workday ≤20, Firecrawl-map ≤100) | uncapped | REQ-004-13 removes both caps — the multiplier here is **unknown until measured**; large employers (Amazon, NVIDIA, Google) could return meaningfully more than 20-100 postings per company. This is the single biggest unquantified cost driver. |
| Gemini calls per kept job | 1 (JD structured extraction) | 1 + domain classification + YoE extraction (likely folded into the same structured-extraction call, no separate round-trip needed) | REQ-004-08/09 add fields, not necessarily new calls, if implemented as additional Pydantic schema fields on the existing extraction prompt. |
| Recruiter/HM scoring calls | 1 prompt pair (AI-framed) | 5 prompt pairs, but each JD still hits exactly 1 pair (its own track) | REQ-004-22 — no multiplicative cost increase per JD; the multiplication is in prompt *maintenance* surface, not runtime calls. |
| Run cadence | ad hoc | daily (REQ-004-25) | Multiplies whatever the per-run cost turns out to be by ~30×/month. |

**Recommendation**: because the uncapped-jobs-per-company multiplier (the largest unknown) cannot be sized from static code review, run one uncapped-but-not-yet-daily trial (all 500-company target list, or the current partial list, single run) before turning on the daily `launchd` schedule at full scope. Measure actual Gemini/Tavily/Firecrawl call counts from that trial run's `RunSummary` output, then confirm the resulting daily/monthly cost with the user before REQ-004-25 goes live.

**Gate clarification (per TPM review Finding 5)**: F2's "confirm before implementation" gate is satisfied by user confirmation of the **static sizing table above** at the BRD review. The **trial-run measurement** is a second, later confirmation gate that blocks only enabling REQ-004-25 daily automation — it does not block implementation. The trial run is a launch-phase checklist item, not an early task (a meaningful measurement needs the 500-company list, uncapped scraping, and the new filters all in place).

---

## 6. Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Uncapped job volume × 500 companies × daily runs has an unmeasured cost multiplier (biggest unknown in this BRD) | Could spike Gemini/Tavily/Firecrawl spend or hit rate limits unexpectedly | Run one uncapped trial before enabling daily automation (see §5 recommendation); monitor via existing `RunSummary`/rate-limiter; treat REQ-004-26 confirmation as a hard gate, not a formality. |
| Mid-large-tech domain-boundary judgment calls (REQ-004-09) are inherently fuzzy beyond the two given examples (cloud→AI, payments→Fintech) | Misclassified roles either pollute a track or wrongly exclude a qualifying "early division" role (the user's core thesis) | Maintain an explicit allow/deny example list in the classifier prompt; user spot-checks a sample each run early post-launch; see §7 open question on additional mapping examples. |
| YoE extraction (REQ-004-08) is a new, unproven Gemini extraction field; JD phrasing is often ambiguous ("5+ years enterprise software, TPM experience preferred") | Wrongly skips a qualifying role or keeps a non-qualifying one | Conservative default already specified (unstated → keep + flag, never silently skip); track the "Unparsed YoE" flag rate as an early quality signal. |
| Work-authorization screen (REQ-004-11) is a new global filter on high-stakes text patterns (clearance/citizenship phrasing varies widely, especially in space/defense JDs) | False negative shows an ineligible role to the user; false positive drops a legitimately eligible one | Never silently drop — always record `Work-Auth Status`; maintain an explicit pattern list; user audits the column, especially early in rollout. |
| `Company_List` re-bucketing (REQ-004-06) is a one-time LLM pass over ~200 existing rows with no ground truth | Systematic misclassification skews bucket quotas before discovery even starts | User spot-checks (already specified in intake doc); consider having the classifier emit a rationale/confidence note for audit; unclassifiable rows should be flagged, not silently dropped or forced into a bucket. |
| 5× prompt-pair surface (REQ-004-22/23) inherits existing LLM scoring-noise risk documented in open bugs BUG-58 (single-JD batch inflating recruiter score) and BUG-59 (HM-delta noise floor) — now across 5 tracks instead of 1 | Recruiter/HM score deltas may be noisy or systematically biased per track, undermining the tailoring feedback loop | Reuse the existing byte-identical-prompt-pair architecture (REQ-052 pattern) that already keeps before/after deltas comparable within a track; these are pre-existing, tracked, non-blocking issues — no new mitigation invented here, just flagged as compounding. |
| Positioning narratives (REQ-004-24) and cost estimate (REQ-004-26) are both hard user-approval/confirmation gates | Either gate being delayed blocks Tech Design or rollout respectively | Sequence Tech Design to request both approvals early and in parallel with other design work, not as a final-step blocker. |
| Google Careers adapter (REQ-004-18) and the Space early-company rule (REQ-004-04) are explicitly experimental/stretch | Risk of scope creep if treated as required rather than optional during Tech Design/Implementation | Both are marked P1/P2 in this BRD specifically to keep them decoupled from the P0 launch-blocking path; Tech Design should sequence them as optional follow-on work. |
| `Company_List` `AI Domain` column is migrated in place (not wiped) — partial/failed reclassification could leave mixed old/new taxonomy values mid-rollout | Downstream code (job_agent's domain filter) could silently misread an unmigrated legacy value | Treat any row whose `AI Domain` value doesn't match one of the 6 new bucket names as unmigrated and flag it for manual review, mirroring the existing manual-entry override pattern (CLAUDE.md) — never silently coerce or drop. |

---

## 7. Open Questions for Architect

1. **Column naming**: `Company_List`'s `AI Domain` column now spans 5 non-AI verticals plus AI-native. Should the header be renamed (e.g., to `Track`) for clarity, or does it stay `AI Domain` with new values to minimize code/doc churn? The intake doc specifies the *value* taxonomy change (§2 A1/A4) but not whether the header string itself changes.
2. **Mid-large-tech domain mapping beyond the two given examples**: B3 gives exactly two explicit sub-rules (cloud/compute infra → AI; payments → Fintech). Robotics, Space, and Defense sub-orgs inside mid-large tech are named only in the Background narrative (Amazon Leo, Project Kuiper, Azure Government) — should Tech Design derive additional explicit mapping rules for these three tracks analogous to the two given, or is single-JD LLM judgment (with no example anchor) sufficient?
3. **Freshness (B4) vs. row lifecycle (C3) interaction**: B4 says "skip postings older than 15 days at scrape time"; C3 says the pipeline never auto-deletes aged rows and the user manually decides what to remove. Please confirm the intended reading is that the 15-day skip applies only to **newly discovered** postings at scrape time, and an already-in-sheet row that ages past 15 days on a later run is **not** retroactively dropped (consistent with G7/REQ-004-16) — this BRD assumes that reading but it is not stated explicitly in the intake doc.
4. **Bucket quota enforcement after migration (A4/REQ-004-06)**: if the one-time re-bucketing of existing `Company_List` survivors leaves a bucket already at or over its new quota (e.g., disproportionately many AI-native survivors), should Tech Design trim/archive the excess to hit the quota exactly, or grandfather all survivors in (treating the 150/150/50/50/50/50 split as a target for *new* discovery only, not a hard cap on migrated rows)? The intake doc says "survivors count against their bucket's quota; discovery only tops up remaining slots" but doesn't address the over-quota case.

### Resolutions (User, 2026-07-07 BRD review)

1. **Q1 — RESOLVED**: Rename the `Company_List` header `AI Domain` → `Track`. Tech Design covers the rename and all read/write sites.
2. **Q2 — RESOLVED**: Tech Design adds explicit mapping example anchors for Robotics / Space / Defense sub-orgs inside mid-large tech (analogous to cloud→AI, payments→Fintech), rather than relying on unanchored per-JD LLM judgment.
3. **Q3 — RESOLVED**: Confirmed — the 15-day freshness skip is a write-time gate on newly discovered postings only; rows already in the sheet are never retroactively dropped (consistent with G7/REQ-004-16).
4. **Q4 — RESOLVED**: Grandfather all migrated survivors; the 150/150/50/50/50/50 quotas constrain new discovery only (a bucket at/over quota gets no new discovery slots but keeps its survivors).

Additionally at the same review: §4a positioning narratives approved as drafted (REQ-004-24 gate cleared); §5 static cost sizing confirmed (REQ-004-26/F2 "before implementation" gate cleared — the trial-run confirmation gate before daily automation remains).
