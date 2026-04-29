# PRJ-002: 3-Dimension Scoring (ATS / Recruiter / HM)

**Phase**: Phase 5 — Launch Readiness (Conditional Go pending user verification)
**Status**: 🟢 Code Ship-Ready, awaiting user empirical verification + P0 merge
**Priority**: P1
**Created**: 2026-04-28
**Last Updated**: 2026-04-28

## Task Checklist

### Phase 1: BRD
- [x] PM researches and writes BRD (Engineer Lead authored synchronously with user; `brd.md` covers REQ-100~112)
- [x] User reviews BRD (interactive design discussion 2026-04-28; D1-D7 in Decision Log)
- [x] TPM reviews BRD (5-PR split + risk register signed off in same session)
- [x] Engineer Lead reviews BRD (authored)

### Phase 2: Tech Design
- [x] Engineer Lead writes technical design (`tech-design.md`)
- [x] User reviews technical design (5-PR split approved)
- [x] TPM reviews technical design (sequencing + branch strategy in same session)

### Phase 3: Implementation
- [x] Task decomposition and dependency ordering (TPM)
- [x] PR 1 — Foundation: ATS matcher + JD schema (`shared/ats_matcher.py`, `shared/schemas.py`, `agents/job_agent.py`, `tests/test_ats_matcher.py`) ✅ commit ba7ed51, 669 tests passing
- [x] PR 2 — Excel schema + prompt rename (`shared/excel_store.py`, `shared/prompts.py`, tests) ✅ commit 28eee7e, 686 tests passing
- [x] PR 3 — Match agent 3-dim scoring (`agents/match_agent.py`, `shared/excel_store.py`, tests) ✅ commit 09df10b, 703 tests passing
- [x] PR 4 — Optimizer 3-dim rescore (`agents/resume_optimizer.py`, `shared/excel_store.py`, tests) ✅ commit 32afd46, 718 tests passing
- [x] PR 5 — Documentation + alias deprecation (CHANGELOG / ARCHITECTURE / REQUIREMENTS / shared/prompts.py) ✅ commit 9834b46
- [x] Code self-testing passes (718 tests)

### Phase 4: Testing & Bug Fix
- [x] QA Team review (5 parallel review agents: agent-reviewer, test-analyzer, eval-engineer, schema-validator, doc-sync) — see `reviews/phase4-review.md`
- [ ] PM functional acceptance
- [x] Bug fixes completed (BUG-56 P0 ship-blocker fixed in commit `bf25dcb`; BUG-57~61 logged as deferred)
- [x] QA sign-off (Engineer Lead confirms 725 tests pass, no regressions, ship-blocker resolved)
- [ ] PM sign-off

### Phase 5: Launch Readiness
- [x] TPM launch readiness report — see `reviews/phase4-review.md` and the in-session TPM run output (Conditional Go)
- [x] Engineer Lead confirmation — 725 tests passing, ship-blocker fixed, branch pushed to origin
- [ ] **User final sign-off** — gated on:
    - (a) `fix/p0-review-2026-04-28` merged to `main` first
    - (b) `feat/3d-scoring` rebased onto updated `main`
    - (c) Empirical verification per `reviews/phase4-review.md` §5: re-run `job_agent` on at least 5 cached JDs, confirm `ATS Keywords` column populates, then run `match_agent` and confirm `ATS Coverage %` is non-None
    - (d) PRJ-002 PR opened against `main`
- [ ] PM confirmation (functional acceptance against BRD G1-G7; G4/G5 require post-launch sample data)

## Risk Register

| ID | Risk Description | Impact | Probability | Mitigation | Status |
|----|------------------|--------|-------------|------------|--------|
| R1 | LLM-extracted ATS keywords drift over JDs (inconsistent quality) | Medium | Medium | Hand-curate synonym table; surface missing-keyword reports for review | Open → tracked as BUG-57 |
| R2 | Excel schema migration breaks existing user data | High | Low | Auto-migrate on open with backfill logic + tests (verified by 7 migration tests) | **Mitigated** |
| R3 | Coarse → Recruiter rename breaks downstream callers / tests | Medium | High | Pure rename + back-compat aliases; tests pass via `is`-identity | **Mitigated** |
| R4 | Stem rules without nltk too lossy → false misses on covered keywords | Medium | Medium | Hand-rolled stem + synonyms cover the lossy "kubernete" case | **Mitigated** |
| R5 | P0 branch not merged to main → feat branch needs rebase | Low | High | Rebase feat/3d-scoring onto main once P0 PR merges | Open (in launch sequence) |
| R6 | (NEW, post-impl) ATS keywords silently dropped in JD_Tracker → ATS dim non-functional | High | High (was occurring) | Found by Phase 4 schema-validator review; fixed in commit bf25dcb (BUG-56) | **Mitigated** |
| R7 | (NEW, post-impl) Recruiter rescore single-batch may inflate scores vs. 10-batch original | Medium | Medium | recruiter_delta is informational only; not in regression rule. BUG-58 logged for empirical follow-up | **Mitigated by design** |
| R8 | (NEW, post-impl) HM Delta < 0 too sensitive given LLM noise floor | Medium | Medium | Conservative until empirical noise measurement; BUG-59 logged | Open (accept-risk) |

## Decision Log

| ID | Decision | Date | Decision Maker |
|----|----------|------|----------------|
| D1 | ATS as parallel dimension, not sequential stage | 2026-04-28 | User |
| D2 | LLM extracts `ats_keywords` in job_agent (not separate pass) | 2026-04-28 | User |
| D3 | Matching = exact + lowercase + hand-rolled stem + small synonym table (no nltk) | 2026-04-28 | User |
| D4 | Soft dimension: <30% coverage → ⚠️ flag, not drop | 2026-04-28 | User |
| D5 | Keep coarse stage, rename to "Recruiter Score"; HM = current FINE | 2026-04-28 | User |
| D6 | 5-PR sequential split (each PR ≤4 files) | 2026-04-28 | User |
| D7 | Feature branch `feat/3d-scoring` from `fix/p0-review-2026-04-28` | 2026-04-28 | User |

## Blockers

No current blockers.
