# Test Analysis: PRJ-004

**Reviewer**: test-analyzer (Quality group)
**Date**: 2026-07-07
**Verdict**: SUFFICIENT WITH GAPS

Suite: 930 passed / 1 skipped (pre-existing conditional skip, unrelated).
+71 vs 859 baseline, 0 regressions — G9 holds.

## Coverage by design §7 group

| Group | Status |
|---|---|
| Taxonomy & quotas | COVERED (TestTrackWhitelist/ComputeNeedByTrack/AllocateBatch/ApplyBucketRules) |
| Migration | COVERED (TestMigrateTracks/UpdateCompanyTrack + JD guard tests) |
| Domain classifier | PARTIAL — no prompt-content assertion for the 5 mapping anchors; llm_filter_jobs rule selection untested |
| YoE | COVERED (boundary table + both unstated paths) |
| Freshness | PARTIAL — pure functions covered; the pre-scrape gate loop in process_company has no behavioral test |
| Work-auth | COVERED |
| Geo | COVERED (region matrix) |
| Scrapers | COVERED (Workday pagination incl. NVIDIA>20 proxy, Firecrawl no-limit, Amazon adapter + zero-crawler prefetch) |
| Sort | COVERED (6-cell matrix, tier-9, recompute, idempotence, count preservation) |
| Selector | COVERED |
| Prompt pairs | PARTIAL — match side covered; resume_optimizer had zero track-routing tests (G8's other half) |
| Operational | MISSING — no test for LAST_RUN_FAILED/LAST_RUN_OK wrapper markers |

## Acceptance seeds (intake §9.4)
4/5 directly asserted ("12+ years never reaches sheet"; "no kept row requires
citizenship/clearance"; NVIDIA >20 proxy; Amazon zero-crawler). "Every row has
a tier or a flag" proven piecewise only — no single OR-invariant fixture test.

## Top-5 untested risks (each with suggested test)
1. P0 — pre-scrape freshness gate in process_company (enforcement point of G4)
2. P0 — wrapper-script marker files (the entire Operational group)
3. P1 — resume_optimizer per-track routing (REQ-004-23/G8 byte identity)
4. P1 — extract_jd mapping-anchor prompt content
5. P1 — llm_filter_jobs vertical-vs-mid-large rule selection

P2 suggestions: combined tier-XOR-flag fixture test; RunSummary "gemini usage:"
note assertion. Mock quality: no over-mocking; gaps are omission, not misuse.
