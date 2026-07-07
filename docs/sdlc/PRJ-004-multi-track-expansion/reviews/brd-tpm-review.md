# TPM Review: PRJ-004 BRD

**Reviewer**: TPM Agent
**Date**: 2026-07-07
**Verdict**: APPROVE WITH COMMENTS

The BRD is a faithful, high-fidelity translation of the signed-off intake doc. Traceability is complete (26 REQs cover every intake item; no scope invention), the approval gates are correctly identified, and the risk register is substantive. Comments below are refinements, not blockers — the one item worth pinning before launch-readiness is the G6 success-criterion coupling (Finding 1).

---

## Coverage Map

Every intake item maps to a REQ; no orphan REQs (no REQ lacking an intake basis).

| Intake item | BRD REQ | Notes |
|---|---|---|
| A1 — 6 buckets / 500 cap | REQ-004-01 | ✓ quotas carried verbatim (150/150/50/50/50/50) |
| A2 — early-company rule (5 verticals) | REQ-004-02, -04 | ✓ space-experimental split into -04 (P1) |
| A2 — defense hard-exclude primes + Palantir | REQ-004-03 | ✓ full prime list + Palantir allowlist |
| A3 — "hires in region" geo, no % quotas | REQ-004-05 | ✓ |
| A4 — Company_List re-bucket migration | REQ-004-06 | ✓ survivors count against quota |
| B1 — permissive title filter | REQ-004-07 | ✓ |
| B2 — YoE [4,10] window | REQ-004-08 | ✓ boundary rules (10+ keep / 12+ skip) preserved |
| B3 — 5-track domain classifier | REQ-004-09 | ✓ cloud→AI, payments→Fintech sub-rules included |
| B4 — freshness / 15-day cut / 3 tiers | REQ-004-10 | ✓ ATS date fields enumerated |
| B5 — global work-auth screen | REQ-004-11 | ✓ ITAR/citizenship/clearance logic + audit column |
| B6 — tightened geo filter | REQ-004-12 | ✓ |
| B7 — no job cap (Workday/Firecrawl) | REQ-004-13 | ✓ folds intake D2 (Workday pagination) — correct, B7 already names it |
| C1 — JD_Tracker schema | REQ-004-14 | ✓ |
| C2 — 1–6 combined sort tier | REQ-004-15 | ✓ |
| C3 — no-auto-delete lifecycle | REQ-004-16 | ✓ |
| D1 — Amazon.jobs adapter | REQ-004-17 | ✓ (P1 — see Finding 1) |
| D2 — Workday pagination | REQ-004-13 | ✓ merged (P0) |
| D3 — Google careers adapter (stretch) | REQ-004-18 | ✓ (P2) |
| LinkedIn search-signal-only policy | REQ-004-19 | ✓ |
| Tesla verify (don't rebuild) | REQ-004-20 | ✓ (P2) |
| E1 — row-selector fix | REQ-004-21 | ✓ dependency on REQ-004-09 noted |
| E2 — 5 per-track prompt pairs | REQ-004-22 | ✓ ATS dimension unchanged |
| E3 — optimizer same-track routing | REQ-004-23 | ✓ REQ-052 byte-identical guarantee preserved |
| E4 — 5 positioning narratives (draft+approve) | REQ-004-24 + §4a | ✓ draft delivered, approval gate flagged |
| F1 — daily run + failure surfacing | REQ-004-25 | ✓ (P1 — see Finding 2) |
| F2 — cost/runtime estimate + confirm gate | REQ-004-26 + §5 | ✓ static sizing + trial-run plan |
| §9.4 acceptance-criteria seeds | G3/G4/G5/G6 | ✓ all four seeds became success criteria |

**No gaps. No scope invention.** Open Questions §7 are legitimate architect hand-offs, not unilateral scope additions.

---

## Findings

**1. [MAJOR] G6 couples a P0 and a P1 item into one launch gate.** G6 reads as a launch success criterion but bundles NVIDIA/Workday pagination (REQ-004-13, **P0**) with the Amazon.jobs adapter (REQ-004-17, **P1**). If REQ-004-17 can legitimately slip past launch (its P1 rating says it can), then G6 is unsatisfiable-yet-non-blocking, which will produce an ambiguous Go/No-Go at launch assessment. Recommend splitting G6 into **G6a (Workday pagination, launch-blocking)** and **G6b (Amazon adapter, non-blocking / fast-follow)**, or promoting REQ-004-17 to P0. Pick one; do not leave the priority and the success criterion contradicting each other.

**2. [MINOR] REQ-004-25 (daily-run failure surfacing) at P1 sits under a P0 dependency.** The Tier-1 (1–2 day) freshness tier — part of P0 REQ-004-10 and success criterion G4 — is, by the BRD's own §5 language, "only meaningful with daily execution." Marking the *failure-surfacing* work P1 is defensible (the launchd runner already exists per REQ-133; this is monitoring hardening, not the run itself). Acceptable as-is, but Tech Design should state explicitly that P0 freshness tiering does not *functionally* depend on the P1 alerting work, so an engineer scoping the minimal launch doesn't drop freshness by association.

**3. [MINOR] G1 defers its own pass/fail threshold to Tech Design.** "Converges toward 500 rows … within a tolerance band agreed in Tech Design" is not verifiable until that band exists. This is a reasonable deferral (the migration-vs-quota interaction is genuinely unknown pre-design — it's Open Question §7.4), but flag it as an explicit Tech Design deliverable so it isn't lost: **the numeric tolerance band for G1 must be pinned during Phase 2**, else launch has no measurable G1.

**4. [MINOR] Risk register is missing three rows.** §6 is strong (8 real risks, actionable mitigations), but as coordinator I'd add: (a) **undocumented-endpoint breakage** — amazon.jobs / careers.google.com JSON APIs are unofficial and can change/rate-limit without notice; mitigation: same reliability class as existing Workday/Ashby pattern, treat adapter failures as fall-back-to-existing-path not hard failure. (b) **Geo-filter false drops** — REQ-004-12 newly *drops* all-non-Seattle/CA/TX/Remote rows; an imperfect `_is_us`/region parse could silently discard desired roles (behavior change from "keep all US"); mitigation: spot-check dropped-row sample early post-launch. (c) **Schedule risk from the two approval gates** — REQ-004-24 and REQ-004-26 can each stall the critical path; the BRD's §6 already flags this but it belongs as a formal register row with a probability rating.

**5. [MINOR] The cost gate (REQ-004-26 / F2) is effectively two gates, and only one can be satisfied "before implementation."** §5 handles this well — a static sizing table now, plus a trial-run measurement before daily rollout — but the BRD should state plainly that F2's "confirm before implementation" is satisfied by the **static** table, while the **trial-run** confirmation is a second, later gate blocking only REQ-004-25 daily automation. Right now a reader could think one confirmation covers both. This is a wording clarification, not a design change.

---

## Sequencing Notes

The BRD identifies the two headline gates correctly (REQ-004-24 narratives before -22/-23; REQ-004-26 cost before daily rollout). Additional ordering constraints for Phase 3 task decomposition — mostly implicit in the BRD, worth making explicit in Tech Design:

- **Schema-first:** REQ-004-14 (Job Domain + new columns) must land before REQ-004-09 (classifier writes Job Domain), REQ-004-21 (selector reads it), and REQ-004-22/-23 (match/optimizer route on it). The match layer has a hard upstream dependency on the job-layer schema.
- **Migration depends on user pre-launch pruning** (Open Item §9.1): REQ-004-06 cannot run until the user manually prunes Company_List. This is a user-owned blocking prerequisite, not an engineering task — track it as a Phase 3 external dependency.
- **JD_Tracker wipe (C3) is the enabler that lets REQ-004-14 skip in-place data migration.** If the user has not wiped rows pre-launch, the "no in-place migration needed" assumption in §5 breaks. Confirm the wipe happened before shipping the schema change.
- **Sort (REQ-004-15) depends on populated freshness (REQ-004-10) + geo (REQ-004-12)** fields — the 1–6 tier index is computed from both. Sequence the sort change after those two filters.
- **The cost trial-run (§5) is late-stage, not early.** A meaningful measurement needs the 500-company list (REQ-004-01/06) + uncapped jobs (REQ-004-13) + the new filters in place. Do not schedule the trial before P0 implementation is substantially complete; schedule the REQ-004-24/-26 *approval requests* early (per §6 mitigation), but the *measured* number arrives late.

---

## Recommended status.md Updates

Port the BRD's risks into the (currently empty) status.md risk register, add the Finding-4 gaps (R-09/R-10), and log the intake doc's settled decisions (D-01…D-07) for traceability. Mark "TPM reviews BRD" complete once this report is filed; the remaining Phase-1 items (User review, Engineer Lead review) plus resolution of Open Questions §7.1–7.4 gate entry to Phase 2. Recommend the four Open Questions be resolved as the first Tech Design inputs, since three of them (7.2 mapping rules, 7.3 freshness×lifecycle, 7.4 over-quota migration) directly shape P0 implementation.
