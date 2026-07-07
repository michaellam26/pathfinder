# PRJ-004: Multi-Track Expansion

**Phase**: Phase 4 — Testing & Bug Fix
**Status**: 🟡 In Progress
**Priority**: P1
**Created**: 2026-07-07
**Last Updated**: 2026-07-07

## Task Checklist

### Phase 1: BRD
- [x] PM researches and writes BRD
- [x] User reviews BRD (2026-07-07, APPROVED — §7 questions resolved per recommendations; §4a narratives approved; static cost sizing confirmed)
- [x] TPM reviews BRD (2026-07-07, APPROVE WITH COMMENTS — reviews/brd-tpm-review.md; G6 split + gate clarification applied to BRD)
- [x] Engineer Lead reviews BRD (2026-07-07, APPROVE WITH COMMENTS — reviews/brd-engineer-review.md)

### Phase 2: Tech Design
- [x] Engineer Lead writes technical design (2026-07-07 — design.md; drafted via architect agent, anchors verified by Engineer Lead)
- [x] User reviews technical design (2026-07-07, APPROVED — §8 questions resolved per recommendations, D-15…D-19)
- [x] TPM reviews technical design (2026-07-07, APPROVE WITH COMMENTS — reviews/design-tpm-review.md; day-15 boundary pinned, critical path named, T5 parallelization noted)

### Phase 3: Implementation
- [x] Task decomposition and dependency ordering (TPM) — design.md §6 T1–T17; critical path T1→T5→T6→T9→T17
- [x] Code implementation (Engineer Lead) — T1–T15 complete across 9 commits (49e3b1b…f493ffd); T16 Google adapter deferred post-launch (P2 stretch, per design)
  - [x] T1 excel_store schema + shared functions (+ atomic test-fixture update, R-11)
  - [x] T2 row selector + qualified-count rework
  - [x] T3 company_agent taxonomy/quotas/rules
  - [x] T4 --migrate-tracks migration CLI
  - [x] T5 job_agent extraction core (YoE/domain/work-auth gates)
  - [x] T6 posting dates + freshness gate + backfill
  - [x] T7 geo tighten
  - [x] T8 Workday pagination + Firecrawl uncap
  - [x] T9 combined 1–6 sort
  - [x] T10 per-track prompt dicts
  - [x] T11 match_agent routing + per-track caches
  - [x] T12 resume_optimizer routing
  - [x] T13 launchd failure surfacing (P1)
  - [x] T14 Amazon.jobs adapter (P1)
  - [x] T15 Tesla regression verification (P2)
  - [ ] T16 Google Careers adapter (P2, stretch)
- [x] Code self-testing passes — suite 930 passed / 1 skipped (was 859 at baseline; +71 new PRJ-004 tests, 0 regressions)
- External prerequisites (user-owned, block T4/T17 rollout only): prune Company_List; wipe JD_Tracker; trial-run cost confirmation

### Phase 4: Testing & Bug Fix
- [x] QA Team review (2026-07-07 — 3 parallel reviews: code review APPROVE WITH COMMENTS, schema validation PASS, test analysis SUFFICIENT WITH GAPS; reviews/phase4-*.md)
- [x] PM functional acceptance (2026-07-07, ACCEPT WITH CONDITIONS — reviews/phase4-pm-acceptance.md; all conditions are launch-checklist items)
- [x] Bug fixes completed (commit 2cda556 — injection guards + gate hardening + all P0/P1 test gaps closed; BUG-62/63 logged for backlog; suite 945 passed)
- [x] QA sign-off (all actionable findings resolved and verified by tests; zero BLOCKER/MAJOR across all three reviews)
- [x] PM sign-off (conditions carried into the Phase 5 launch checklist)

### Phase 5: Launch Readiness
- [ ] TPM launch readiness report
- [ ] User final sign-off
- [ ] Engineer Lead confirmation
- [ ] PM confirmation

## Risk Register

| ID | Risk Description | Impact | Probability | Mitigation | Status |
|----|------------------|--------|-------------|------------|--------|
| R-01 | Uncapped jobs × 500 companies × daily runs — unmeasured cost multiplier | High | Med | Uncapped trial run before daily automation; REQ-004-26 hard gate; monitor via RunSummary/rate-limiter | Open |
| R-02 | Mid-large-tech domain-boundary calls (REQ-004-09) fuzzy beyond 2 given examples | Med | High | Allow/deny example list in classifier prompt; user spot-checks early; Open Q §7.2 | Open |
| R-03 | YoE extraction (REQ-004-08) new/unproven, ambiguous JD phrasing | Med | Med | Unstated→keep+flag default; track Unparsed-YoE flag rate | Open |
| R-04 | Work-auth screen (REQ-004-11) new global filter on high-variance clearance/citizenship text | High | Med | Never silently drop; record Work-Auth Status; explicit pattern list; user audits early | Open |
| R-05 | Company_List re-bucketing (REQ-004-06) one-time LLM pass, no ground truth | Med | Med | User spot-checks; classifier emits rationale/confidence; flag unclassifiable rows | Open |
| R-06 | Company_List in-place migration leaves mixed old/new taxonomy values | Med | Low | Treat non-matching AI Domain value as unmigrated → manual-review flag | Open |
| R-07 | 5× prompt-pair surface inherits BUG-58/BUG-59 scoring noise across all tracks | Low | Med | Reuse REQ-052 byte-identical-pair architecture; pre-existing tracked issues | Open |
| R-08 | Approval gates (REQ-004-24, -26) can each stall critical path | Med | Med | Request both approvals early/in parallel, not final-step | Open |
| R-09 | Undocumented endpoints (amazon.jobs, careers.google.com) may break/rate-limit | Med | Med | Same reliability class as Workday/Ashby; adapter failure falls back, not hard-fails | Open |
| R-10 | Geo-filter tightening (REQ-004-12) may false-drop desired roles | Med | Low | Spot-check dropped-row sample early post-launch | Open |
| R-11 | Test-suite churn concentration — T1 rename fans into 5 test files at once | Med | High | Land T1 + fixture updates as one atomic commit so the 859-suite is never red | Open |
| R-12 | Workday `postedOn` day-floor granularity / "30+ Days Ago" saturation | Low | Med | Unparseable text treated as unknown (keep+flag), never as aged | Open |
| R-13 | Per-track context-cache fan-out (≤5 caches/run vs 1 today) | Low | Low | Transparent uncached fallback absorbs create_cache failures | Open |

## Decision Log

| ID | Decision | Date | Decision Maker |
|----|----------|------|----------------|
| D-01 | Six-track / 500-company scope replaces AI-only 200-cap | 2026-07-07 | User |
| D-02 | Bucket caps only — no cross-region percentage quotas | 2026-07-07 | User |
| D-03 | Seniority via extracted YoE window [4,10]; title is not a seniority signal | 2026-07-07 | User |
| D-04 | LinkedIn is search-signal-only; never scraped directly | 2026-07-07 | User |
| D-05 | No auto-delete of aged JD rows; user-initiated removal only | 2026-07-07 | User |
| D-06 | ATS keyword dimension stays shared/unchanged across all 5 tracks | 2026-07-07 | User |
| D-07 | Space early-company rule is experimental, post-launch review (REQ-004-04) | 2026-07-07 | User |
| D-08 | BRD approved (with TPM/Engineer review fixes applied) | 2026-07-07 | User |
| D-09 | Rename Company_List header `AI Domain` → `Track` (BRD §7 Q1) | 2026-07-07 | User |
| D-10 | Explicit mapping anchors for Robotics/Space/Defense big-tech sub-orgs in classifier prompt (BRD §7 Q2) | 2026-07-07 | User |
| D-11 | 15-day freshness skip is write-time only; no retroactive row drops (BRD §7 Q3) | 2026-07-07 | User |
| D-12 | Grandfather over-quota migrated survivors; quotas constrain new discovery only (BRD §7 Q4) | 2026-07-07 | User |
| D-13 | §4a positioning narratives approved as drafted (REQ-004-24 gate cleared) | 2026-07-07 | User |
| D-14 | Static cost sizing confirmed; trial-run gate remains before daily automation (REQ-004-26) | 2026-07-07 | User |
| D-15 | `AI TPM Jobs` → `Qualified Jobs` header rename approved (design Q2) | 2026-07-07 | User |
| D-16 | G1 tolerance band ratified: ≥80%/bucket, ≥450 total, 100% valid values (design Q4) | 2026-07-07 | User |
| D-17 | Unmigrated Track values → strict mid-large-tech classifier path + warning (design Q1) | 2026-07-07 | User |
| D-18 | Pre-scrape freshness gating accepted; log-line audit sufficient (design Q3) | 2026-07-07 | User |
| D-19 | Tavily accepted as optional job_agent dependency for date backfill (design Q5) | 2026-07-07 | User |
| D-20 | Tech design approved | 2026-07-07 | User |

## Blockers

No current blockers.
