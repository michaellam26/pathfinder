# Requirements Record: Multi-Track Expansion

**Status**: Signed off by user — ready for SDLC intake (BRD phase)
**Date**: 2026-07-07
**Decision maker**: User (Architect / Product Owner)
**Branch**: `prj-004-multi-track-expansion` — ALL work for this change happens on this branch
**Next step for a new session**: run `/sdlc-init multi-track-expansion` and use this document as the authoritative intake for the BRD. Every requirement below was explicitly discussed and confirmed with the user; do not re-litigate settled decisions — open items are listed in §9.

---

## 1. Background & Rationale

The user is a big-tech TPM (4 years SDE + 6 years TPM experience) planning their next role. PathFinder currently targets **North-American AI companies only** (6 AI-domain buckets, 200-company cap). The user's updated thesis: six tracks have a strong 10-year runway, and the winning strategy is to join **"early companies, and early divisions inside established companies"** — young vertical companies (AI, robotics, fintech, space, defense) plus the new-bet orgs inside big/mid tech (e.g., Amazon Leo, Project Kuiper, Azure Government, Google Pay).

Second driver: **job applications are time-sensitive.** Postings older than ~15 days have sharply lower response rates, so freshness becomes a first-class pipeline signal.

Third driver: **seniority must be judged by JD content, not title.** Title conventions vary too much across companies (e.g., Oracle "Principal TPM" ≈ 8 years). The user targets roles requiring 4–10 years of experience.

---

## 2. Company Discovery (company_agent)

### A1. New taxonomy — 6 buckets, 500 companies total
Replaces the 6 AI-domain buckets and the `MAX_TOTAL = 200` cap (`agents/company_agent.py:59-90`).

| Bucket | Quota |
|---|---|
| AI-native (all sizes: labs, startups, infra) | 150 |
| Mid-large tech | 150 |
| Robotics | 50 |
| Fintech | 50 |
| Space | 50 |
| Defense | 50 |
| **Total** | **500** |

### A2. Early-company rule (all five vertical buckets)
- Vertical buckets (AI, robotics, fintech, space, defense) target companies founded **~2000 or later**.
- Legacy incumbents (Boeing, Visa, PayPal, Intuit, Boston Dynamics, ABB, …) are **excluded from vertical buckets**; if attractive, they qualify via the **mid-large-tech** bucket, where their track-relevant TPM roles pass the domain filter (B3).
- Defense additionally **hard-excludes legacy primes**: Boeing, Lockheed Martin, Raytheon/RTX, Northrop Grumman, General Dynamics, BAE, L3Harris. Discovery targets venture-backed / founded-roughly-post-2010 defense tech (Anduril, Shield AI, Saronic, Castelion, …). **Palantir is in scope.**
- Early-company rule applies to **space experimentally** (prefer SpaceX/Relativity/Stoke over ULA/Boeing space divisions) — revisit after seeing results.

### A3. Geography — "hires in the region" semantics
- Regions: **Greater Seattle**, **California (Bay Area + Southern California)**, **Texas**. SoCal included because many space/defense companies are there (El Segundo, Hawthorne, Long Beach, Irvine, San Diego…).
- A company qualifies if it **hires TPMs in these regions**, not by HQ location.
- **No percentage quotas across regions** — the bucket caps do the balancing.

### A4. Existing Company_List migration
- Keep the existing Excel file. The **user manually prunes** Company_List first (pre-launch step, owned by user).
- The agent then **re-buckets the surviving rows** into the new 6-bucket taxonomy (LLM classification pass; user spot-checks).
- Survivors count against their bucket's quota; discovery only tops up remaining slots.

---

## 3. Job Discovery & Filtering (job_agent)

### B1. Title filter — permissive
Any TPM-keyword title passes (existing substring match on "technical program manager" / "tpm" etc., `agents/job_agent.py:449-450` — already matches Senior/Staff/Principal/Director prefixes). **Title is NOT a seniority signal** — do not exclude Principal/Director by title.

### B2. Seniority via years-of-experience window (NEW — no such filter exists today)
- Extract the JD's **minimum required years of experience** (new extraction field).
- **Keep** if min ∈ [4, 10]. **Skip** if min ≤ 3 (junior) or min ≥ 12 (true principal). Boundary: "10+ years" → keep; "12+ years" → skip.
- **No years stated**: keep the row; if title carries Senior/Staff prefix → auto-mark qualified; otherwise flag for the user's manual review.

### B3. Domain filter (replaces the current AI-purity filter layer)
- AI / robotics / fintech / space / defense companies → **every TPM role qualifies** (job domain = company's track).
- Mid-large tech → only TPM roles **in one of the five tracks** qualify (e.g., Amazon Leo yes; Office 365 TPM no).
  - **Cloud/compute infrastructure** roles (AWS/GCP/Azure infra, datacenter, silicon) count as **AI** track.
  - **Payments orgs** (Google Pay, Apple Pay, Amazon Payments) count as **Fintech** track.
- The current AI-relevance machinery (`_ai_title_prefilter`, the "reject non-AI TPM" rule in `llm_filter_jobs`, `is_ai_tpm` gating) is superseded by this 5-track classifier.

### B4. Freshness (NEW — no posting-date extraction exists today)
- **Skip** postings older than **15 days** at scrape time.
- Tier the rest by posting date: **Tier 1 = 1–2 days, Tier 2 = 3–7 days, Tier 3 = 8–14 days**, recomputed each run from the actual posted date.
- Posting dates are available in the ATS JSON APIs already called: Greenhouse `updated_at`, Lever `createdAt`, Ashby `publishedDate`, Workday `postedOn`.
- **Unknown date** (mainly generic-crawled sites): keep + flag; best-effort backfill by searching LinkedIn/other platforms for the posting; if not found, leave for the user's manual lookup. Never silently drop for a missing date.

### B5. Work-authorization screen (NEW, GLOBAL — applies to every job, all buckets)
- **Skip** if the JD requires **US citizenship** or a **security clearance** — including "must be able to obtain a clearance" (obtaining one requires citizenship; user is a green-card holder).
- **Keep** if the JD says **"US person" / US permanent resident** (ITAR standard — includes green card) or has **no status requirement**.
- Record the screening result in a JD_Tracker column so kept rows are auditable.
- Rationale: ITAR/clearance language pervades space and defense JDs and appears in big-tech gov-cloud roles.

### B6. Job geo filter — tightened
Keep only: **Greater Seattle / California / Texas / US-Remote**. (Current behavior keeps all US locations — that changes; e.g., NYC-only postings are dropped.) Remote must be US-remote (existing `_is_us` logic).

### B7. No cap on job count
Scrape whatever exists. Remove the two hidden truncations:
- Workday fetch hardcoded `limit: 20` per company (`agents/job_agent.py:678`) → add pagination (this is the likely NVIDIA truncation).
- Firecrawl map `limit=100` (`agents/job_agent.py:774`) → lift.

---

## 4. Data & Excel (excel_store)

### C1. Schema changes (JD_Tracker)
- **Replace `Is AI TPM` with `Job Domain`** — exactly 5 values: `AI / Robotics / Fintech / Space / Defense`. (No "Core-company" value: at vertical companies the domain is the company's track; at mid-large tech only the five tracks qualify.)
- New columns: **Posted Date**, **Freshness Tier**, **Min YoE**, **Work-Auth Status**, and manual-review flags (unknown date, unparsed YoE).
- Company_List: `AI Domain` column semantics change to the new 6-bucket taxonomy.

### C2. Sort order — single combined tier index 1–6
1. Seattle + Remote, 1–2 days
2. CA / TX, 1–2 days
3. Seattle + Remote, 3–7 days
4. CA / TX, 3–7 days
5. Seattle + Remote, 8–14 days
6. CA / TX, 8–14 days

(Freshness is primary; within each freshness band, Seattle+Remote outranks CA/TX. Replaces the current Seattle → Remote → Other tier sort in `shared/excel_store.py:849-908`.)

### C3. Row lifecycle
- The pipeline **never auto-deletes** aged JD rows. After each run the **user manually decides** what to remove.
- Pre-launch: the **user wipes all current JD_Tracker rows** themselves (fresh start under the new schema).

---

## 5. Scraper Reliability (in scope — user's original architecture ask)

- **D1. Amazon.jobs adapter** — Amazon currently has NO adapter and falls to the generic browser-crawl path (chronic failure). Amazon.jobs exposes a public JSON search endpoint (`amazon.jobs/en/search.json`) returning titles, locations, and posting dates.
- **D2. Workday pagination** — fixes NVIDIA (routed via `nvidia.wd5.myworkdayjobs.com`) truncating at 20 jobs.
- **D3. Google careers adapter — stretch goal.** Google is currently JD-only (`domains: []`, cannot discover jobs). `careers.google.com` has an unofficial JSON search API.
- **LinkedIn policy (decided)**: LinkedIn is used **only as a search-based signal** — company discovery hints and posting-date backfill via Tavily-scoped searches (`site:linkedin.com/jobs`). **Never scrape LinkedIn pages directly** (ToS + aggressive blocking). Route to the company's own ATS for actual data.
- Tesla's custom scraper exists and is currently working (post BUG-32/BUG-15 fixes) — verify, don't rebuild.

---

## 6. Match Layer (match_agent + resume_optimizer + shared/prompts)

- **E1. Row selector compatibility fix**: `get_ai_tpm_rows` (`shared/excel_store.py:528`) selects only `Is AI TPM == True` rows — must become "all valid JD rows" (under B3, every written row is domain-qualified).
- **E2. Per-track match-agent series**: 5 Recruiter/HM prompt pairs (AI / Robotics / Fintech / Space / Defense), each written from the persona of a recruiter/HM who hires in that track. Each JD routes to its series by `Job Domain`. The current single AI-framed prompt pair (`shared/prompts.py:37-62`) is replaced. The **ATS dimension stays shared and unchanged** (deterministic keyword coverage, `shared/ats_matcher.py`).
- **E3. resume_optimizer follows the same routing** for both tailoring and re-scoring — before/after scores must come from the same track's prompts to be comparable, and tailoring emphasis must fit the domain (e.g., don't push GenAI experience for a SpaceX role).
- **E4. Five candidate-positioning narratives** — the current framing is "big-tech TPM transitioning into an AI TPM role"; each track needs its own angle (e.g., space/defense: 4 yrs SDE + 6 yrs big-tech TPM bringing large-scale systems discipline to hardware/mission programs). **Drafted during BRD phase; user reviews before implementation** (explicit review checkpoint — the user owns their story).

---

## 7. Operational Requirements

- **F1. Daily runs are a formal requirement** — the 1–2-day freshness tier is only meaningful if the pipeline runs daily (launchd daily runner already exists). A failed daily run must be surfaced, not silent.
- **F2. Cost/runtime estimate in the BRD** before implementation: new steady state is 500 companies × uncapped jobs × daily runs — size Gemini / Tavily / Firecrawl consumption and get user confirmation (standing rule: confirm before batch paid-API commitments).

---

## 8. Out of Scope

- Scraping LinkedIn job pages directly (policy decision, see §5).
- Any change to the ATS keyword-matching dimension (`ats_matcher` / `ats_synonyms`).
- Regional percentage quotas (explicitly dropped in favor of bucket caps).

## 9. Open Items / Checkpoints (the only things not yet settled)

1. **User pre-launch actions** (blocking implementation rollout, owned by user): manually prune Company_List; wipe current JD_Tracker rows.
2. **E4 positioning narratives**: draft in BRD, user must review and approve.
3. **Space-track early-company rule** is experimental — flag for post-launch review.
4. Acceptance-criteria seeds for the BRD: "a JD with '12+ years' never appears in the sheet"; "every row has a freshness tier or a manual-check flag"; "no kept row requires citizenship/clearance"; "Nvidia returns >20 jobs when >20 exist"; "Amazon jobs are discovered without the generic crawler".

## 10. Current-Code Anchors (verified 2026-07-07)

| Area | Location |
|---|---|
| Bucket taxonomy + 200 cap | `agents/company_agent.py:59-90` |
| Discovery Tavily queries + Gemini prompt | `agents/company_agent.py:184-218, 593-631` |
| Career-URL discovery / ATS validators | `agents/company_agent.py:104-181, 373-420` |
| TPM title keywords + US geo filter | `agents/job_agent.py:401-450, 618-629` |
| AI-purity filters to be superseded | `agents/job_agent.py:632-653, 910-944, 1543-1616` |
| Workday `limit: 20` | `agents/job_agent.py:678` |
| Firecrawl map `limit=100` | `agents/job_agent.py:774` |
| Freshness = Excel timestamp only (`FRESH_DAYS = 5`) | `agents/job_agent.py:53, 1786-1796` |
| JD_Tracker headers | `shared/excel_store.py:20-30` |
| Location-tier sort | `shared/excel_store.py:769-798, 849-908` |
| Match row selector (`Is AI TPM == True`) | `shared/excel_store.py:528-542` |
| AI-framed Recruiter/HM prompts | `shared/prompts.py:37-62` |
