# Task Tracker

## Active (2026-07-07): PRJ-004 Multi-Track Expansion — Phase 3 Implementation

**Source of truth**: `docs/sdlc/PRJ-004-multi-track-expansion/design.md` §6 (T1–T17)
**Branch**: `prj-004-multi-track-expansion`
**Critical path**: T1 → T5 → T6 → T9 → T17

### P0 (launch-blocking)
- [x] T1 excel_store schema (commit 49e3b1b — landed atomically with T2/T9; suite 876 green)
- [x] T2 row selector all-valid-rows + job_domain passthrough; qualified-count rework (49e3b1b)
- [x] T3 company_agent taxonomy/quotas/rules (suite 902 green)
- [x] T4 --migrate-tracks CLI (code done; RUN still blocked on user pruning; suite 907)
- [x] T5 job_agent extraction core (suite 923)
- [x] T6 posting dates + freshness gate + backfill (with T5 commit)
- [x] T7 geo tighten (with T5 commit)
- [x] T8 Workday pagination; Firecrawl limit removal (6ffd36c; suite 885)
- [x] T9 sort_jd_tracker_by_tier rewrite (49e3b1b — landed with T1; recompute-at-sort verified by test)
- [x] T10 prompts.py per-track pairs + accessors (986500b; suite 885)
- [x] T11 match_agent per-track routing + per-track caches (5fab05a + fixups)
- [x] T12 resume_optimizer per-track routing (suite 891 green)

### P1/P2 (non-blocking)
- [x] T13 launchd failure surfacing (2577913)
- [x] T14 Amazon.jobs adapter + prefetch routing (suite 930)
- [x] T15 Tesla regression verification (registry + schema tests)
- [ ] T16 Google Careers adapter (P2 stretch — deliberately deferred post-launch per design)

### Rollout (T17 — Phase 5 launch checklist; see docs/sdlc/PRJ-004-multi-track-expansion/launch-readiness.md §2)
- [x] User pruned; migrate-tracks 201/201, 0 UNMIGRATED, spot-check accepted
- [x] JD_Tracker was already wiped; schema upgraded cleanly
- [x] 10 discovery runs (347/500, Tavily quota-truncated; G1 option (a) accepted) → trial run clean (122 JDs, 93 tailored, ~$0.3-1 Gemini) → user GO 2026-07-08 → launchd daily 04:00 LIVE
- [ ] Step-9 early audits (first few daily cycles): G3 YoE 20+ spot-check, G5 work-auth sample, R-10 geo drops, R-02 domain boundaries, D-07 space-rule review; watch Tavily quota reset

**Working rules**: full suite after each task, never left red; tests in tests/; bugs found en route go to BUGS.md.

---

## Backlog (stale, 2026-04-28): REVIEW_2026-04-28 follow-up

**Source doc**: `docs/REVIEW_2026-04-28.md`
**Status**: P0 done (7/8, P0-8 WONTFIX); P1 5 fixed today + 2 fixed earlier; P2 3 fixed earlier
**Verification**: 8 read-only sub-agents re-checked remaining P1/P2 → results appended to `docs/REVIEW_2026-04-28.md` "验证回访" section
**Remaining**: 15 P1 STILL + 4 P1 PARTIAL + 9 P2 STILL + 1 P2 PARTIAL (24 STILL items total)
**Top-6 ROI** for next batch (per verification report):
- [ ] P1-22 — refactor 27 `inspect.getsource` tests to behavioral
- [ ] P1-7 + P1-8 — Excel header lookup + Resume Hash migration in `Tailored_Match_Results`
- [ ] P1-15 — gate `is_ai_tpm` on JD content even for ai_native companies
- [ ] P1-2 / P1-12 — RateLimiter: lazy Lock create + don't hold lock across `sleep`
- [ ] P1-13 — Tailored vs original diff (substring containment + length ratio)
- [ ] P2 doc drift — `excel_store.py:2` / `REQUIREMENTS.md:13` / `ARCHITECTURE.md archive/` (one commit)

---

## Completed: PRJ-002 — 3-Dimension Scoring (ATS / Recruiter / HM)

**Branch**: `feat/3d-scoring` (merged via PR #2 → main)
**SDLC**: `docs/sdlc/PRJ-002-3d-scoring/`
**Started**: 2026-04-28

### PR 1 — Foundation: ATS matcher + JD schema ✅ DONE (commit ba7ed51)
- [x] `shared/ats_synonyms.py` — 18 entries
- [x] `shared/ats_matcher.py` — normalize/expand_synonyms/compute_coverage
- [x] `shared/schemas.py` — added `ATSCoverageResult`
- [x] `agents/job_agent.py` — `JobDetails.ats_keywords` field + extraction prompt
- [x] `tests/test_ats_matcher.py` — 50 new tests
- [x] Full suite 669 passed (was 619, +50 new, 0 regression)
- [x] Committed (not yet pushed — awaiting user review)

### PR 2 — Excel + prompt rename ✅ DONE (commit 28eee7e)
- [x] `shared/prompts.py` — RECRUITER/HM names + back-compat aliases (pure rename, no content drift)
- [x] `shared/excel_store.py` — MATCH_HEADERS +4 cols, TAILORED_HEADERS +9 cols, migration logic
- [x] `tests/test_shared_prompts.py` — alias identity tests + content-drift guard
- [x] `tests/test_excel_store.py` — migration tests for both sheets + headers tests
- [x] Full suite 686 passed (was 669, +17 new, 0 regression)
- [x] Committed (not yet pushed — awaiting user review)
### PR 3 — Match agent 3-dim scoring ✅ DONE (commit 09df10b)
- [x] `agents/match_agent.py` — ATS dim helpers + 3-dim coarse/fine record writes
- [x] `shared/excel_store.py` — `batch_upsert_match_records` accepts dict (preserves on key-absent)
- [x] `tests/test_match_agent.py` — 9 new tests (extract / compute_for_jds / threshold)
- [x] `tests/test_excel_store.py` — 7 new tests (dict format, preservation, mixed)
- [x] Full suite 703 passed (was 686, +17 new, 0 regression)
- [x] Committed (not yet pushed — awaiting user review)
### PR 4 — Optimizer 3-dim rescore ✅ DONE (commit 32afd46)
- [x] `shared/excel_store.py` — `get_scored_matches` surfaces per-dim; `batch_upsert_tailored_records` accepts 9 per-dim keys; regression precedence (explicit > hm_delta > score_delta)
- [x] `agents/resume_optimizer.py` — 3-dim rescore (ATS det. + Recruiter LLM + HM LLM); regression = `hm_delta < 0`; per-JD print shows all 3 dims; cross-agent key pool sharing
- [x] `tests/test_resume_optimizer.py` — 5 new tests (imports / call sites / record keys / legacy mirroring / pool sharing) + updated regression test
- [x] `tests/test_excel_store.py` — 10 new tests (per-dim writes, regression precedence, ATS drop ≠ regression)
- [x] Full suite 718 passed (was 703, +15 new, 0 regression)
- [x] Committed (not yet pushed — awaiting user review)
### PR 5 — Documentation + alias deprecation ✅ DONE (commit 9834b46)
- [x] `CHANGELOG.md` — 2026-04-28 entry covering PRJ-002 + 4 P0 follow-ups
- [x] `REQUIREMENTS.md` — new section 9 (REQ-100~112), fixed REQ-033/035/052 drift, v1.9 history
- [x] `ARCHITECTURE.md` — 3.3 Match / 3.4 Optimizer flows updated; Excel schema table; v1.6 history
- [x] `shared/prompts.py` — alias DEPRECATED note (NOT removed; cross-cutting rename deferred to dedicated future PR)
- [x] Full suite 718 passed (unchanged from PR 4)
- [x] Committed (not yet pushed)

All 5 PRs complete; merged to `main` via PR #2 (commit 3a1f86b closed the SDLC project).

## Open lessons
See `tasks/lessons.md` (created when first lesson lands).
