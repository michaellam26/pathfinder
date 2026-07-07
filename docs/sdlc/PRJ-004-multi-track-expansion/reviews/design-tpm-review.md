# TPM Review: PRJ-004 Tech Design

**Reviewer**: TPM Agent
**Date**: 2026-07-07
**Verdict**: APPROVE WITH COMMENTS

The design is a complete, high-fidelity realization of the approved BRD. All 26 REQs have a design home; all four §7 resolutions (D-09..D-12) are honored in code terms; the four BRD-review sequencing constraints are respected in the T1–T17 ordering; both approval gates are correctly placed (REQ-004-24 cleared and consumed at T10; REQ-004-26 second gate lives at rollout step 5 / T17). The G1 tolerance band (§5) is concrete and ready for Architect ratification. No BLOCKER or MAJOR findings. Comments are refinements plus three risk-register additions and per-question recommendations to make the user/architect gate efficient.

---

## REQ Coverage Map

| REQ | Description (short) | Design home | Task | Status |
|---|---|---|---|---|
| REQ-004-01 | 6-bucket taxonomy / 500 cap / per-bucket quotas | §1 table, §2.1 (TRACK_VALUES/QUOTAS, per-bucket `need`) | T3 | ✅ |
| REQ-004-02 | Early-company rule, 5 verticals | §2.1 early-company rule (prompt + audit) | T3 | ✅ |
| REQ-004-03 | Defense prime hard-exclude + Palantir allowlist | §2.1 `_apply_bucket_rules` (deterministic post-filter) | T3 | ✅ |
| REQ-004-04 | Space experimental early-rule (P1) | §2.1 (prompt-only, flagged post-launch) | T3 | ✅ |
| REQ-004-05 | "Hires in region" geo semantics | §2.1 geography prompt change | T3 | ✅ |
| REQ-004-06 | One-time re-bucket migration | §4.1 `--migrate-tracks`, grandfathering | T4 | ✅ |
| REQ-004-07 | Permissive title filter confirmed | §2.2.1 title filter (`TPM_KW` unchanged; prefilter renarrowed) | T5 | ✅ |
| REQ-004-08 | YoE [4,10] window + unstated fallback | §2.2.1 YoE gate | T5 | ✅ |
| REQ-004-09 | 5-track domain classifier + anchors | §2.2.1 extract_jd, mapping anchors, vertical override | T5 | ✅ |
| REQ-004-10 | Posting date / 15-day gate / 3 tiers | §2.2.3, `compute_freshness_tier` | T6 | ✅ (see F1) |
| REQ-004-11 | Global work-auth screen + audit col | §2.2.1 work-auth gate | T5 | ✅ |
| REQ-004-12 | Tightened geo filter (Sea/CA/TX/Remote) | §2.2.4 `classify_region` | T7 | ✅ |
| REQ-004-13 | Uncap Workday + Firecrawl | §2.2.5 (pagination loop; drop `limit=100`) | T8 | ✅ |
| REQ-004-14 | JD_Tracker schema (Job Domain + new cols) | §2.3.1 `JD_HEADERS`, assert-empty guard | T1 | ✅ |
| REQ-004-15 | Combined 1–6 sort tier | §2.3.3 `compute_sort_tier`, rewritten sorter | T9 | ✅ |
| REQ-004-16 | No auto-delete lifecycle | §2.3.3 (count-preserving, no delete path anywhere) | T1/T9 | ✅ |
| REQ-004-17 | Amazon.jobs adapter (P1, G6b) | §2.2.5 `_fetch_amazon_jobs` + prefetched routing | T14 | ✅ |
| REQ-004-18 | Google Careers adapter (P2, stretch) | §2.2.5 (fills stub, decoupled PR) | T16 | ✅ |
| REQ-004-19 | LinkedIn search-signal-only | §2.1 (`site:linkedin.com` scoping), §2.2.3 (backfill) | T6 | ✅ |
| REQ-004-20 | Tesla verify (regression only) | §2.2.5 (no code change; one regression test) | T15 | ✅ |
| REQ-004-21 | Row selector → all-valid-rows | §2.3.4 `get_jd_rows_for_match` rework | T2 | ✅ |
| REQ-004-22 | 5 Recruiter/HM prompt pairs + routing | §2.4.1 dicts, §2.4.2 match routing | T10, T11 | ✅ |
| REQ-004-23 | Optimizer same-track routing + emphasis | §2.4.3, byte-identity via shared constants | T12 | ✅ |
| REQ-004-24 | Positioning narratives (gate) | Cleared (D-13); consumed in §2.4.1 | T10 | ✅ gate cleared |
| REQ-004-25 | launchd failure surfacing (P1) | §2.5 marker files + RunSummary note | T13 | ✅ |
| REQ-004-26 | Cost sizing + trial-run gate | §4.4 step 5 rollout + §5 measurement | T17 | ✅ second gate placed |

**No REQ is without a design home. No scope invention.** REQ-052 byte-identity guarantee is structurally preserved (§2.4.1 — same interned constant per track).

---

## Findings

**1. [MINOR] Day-15 freshness boundary dead zone.** The write-time gate skips `Age > 15 days` (§2.2.1 item 4 / §2.2.3), but `compute_freshness_tier` returns `None` for `>14d` (§2.2.3). A posting exactly 15 days old is therefore *kept* (not >15) but *untierable* (>14) → lands in Sort Tier 9. Functionally safe (visible, never dropped, sinks to bottom), but the gate boundary (>15) and the tier ceiling (14) are off by one day, and BRD REQ-004-10 phrases the cut as "older than 15 days" which is itself ambiguous at exactly 15. Recommend the Engineer Lead pin one convention and align the §7 freshness test boundary table accordingly (it currently tests 14/15 and a "16-day" skip, leaving day-15 untested). Not launch-blocking.

**2. [MINOR] Critical path is implied but never named.** §6 gives correct, acyclic dependencies but does not state the critical path, which Phase 3 planning needs. Derived: the P0 code critical path is **T1 → T5(L) → T6 → T9**, with two parallel P0 chains **T1 → T3 → T4** (externally blocked on user pruning) and **T1 → T2 → T11 → T12**; all converge on **T17** (rollout, gated on all P0). T5 (the sole L) is the single longest-pole task. Recommend adding one line naming this so the schedule and any parallelization are explicit.

**3. [MINOR] T5 is a 4-REQ critical-path bottleneck.** T5 bundles REQ-004-07/08/09/11 (JobDetails fields, track-aware `extract_jd` + mapping anchors + deterministic override, three write-time gates, prefilter renarrow, `llm_filter_jobs` rewrite, `track` renames) and gates T6, T14, T15. The coupling is real (all share `extract_jd`), so a full split may not be worthwhile — but as the longest pole it deserves either internal sub-checkpoints or an explicit note that T11/T12 can be built against T2's `job_domain` contract in parallel (they do not need T5 complete to compile/test, only the selector key). Confirm the parallelization intent.

**4. [MINOR] Three design-level risks in §8 are not yet in the register (R-01..R-10).** Recommend adding: **R-11 test-suite churn concentration** (T1's rename fans into 5 test files at once — mitigation: atomic T1+fixtures PR so the 859-suite is never red across commits); **R-12 Workday relative-date granularity** (`postedOn` floors at day resolution and "30+ Days Ago" saturates — mitigation: unknown-date keep+flag fallback, unparseable treated as unknown not aged); **R-13 per-track context-cache fan-out** (worst case 5 caches/run vs 1 today — mitigation: transparent uncached fallback already absorbs `create_cache` failures; well within quota). None are blockers; registering them preserves traceability into launch assessment.

**5. [MINOR] Open Q1/Q2/Q5 are largely Engineer-Lead/BRD-decidable and shouldn't consume architect bandwidth as true unknowns.** Only Q4 is genuinely delegated to the Architect by the BRD (G1 explicitly names the band as a design-review number). Q1 and Q5 are effectively already answered by BRD §6 mitigations / REQ-004-10 text; Q2 is a low-churn scope confirm. Per-question recommendations below make the gate a fast yes/no rather than an open design debate.

---

## Task-Breakdown Assessment

- **Dependencies acyclic and correct.** Verified no cycles; T1 and the independent roots (T8, T10, T13) are correctly rootless. Match layer correctly chains through schema (T11/T12 → T2 → T1) and prompts (→ T10), honoring the BRD-review "match layer has a hard upstream dependency on the job-layer schema" note.
- **Sequencing constraints — all four honored:**
  - *Schema-first* — T1 is the root; T2/T3/T5/T9/T11 all depend on it. ✅
  - *Sort after freshness + geo* — T9 depends on T6 (freshness) **and** T7 (geo). ✅
  - *Migration blocked on user pruning* — T4 explicitly tagged "blocked externally on user pruning." ✅
  - *Trial run late-stage* — T17 depends on "all P0"; the measured cost number arrives last, approval requests scheduled early via R-08. ✅
- **P0 set coherent with BRD priorities.** The P0-flagged tasks (T1–T12, T17) map exactly to the BRD's P0 REQs; P1/P2 items (T13 launchd, T14 Amazon, T15 Tesla, T16 Google) are correctly non-blocking and decoupled. G6a (Workday, T8, P0) and G6b (Amazon, T14, P1) are cleanly separated — the BRD-review Finding 1 split is honored.
- **Freshness/alerting decoupling honored.** §2.5 states explicitly that P0 freshness tiering has no functional dependency on P1 T13 (tiers recompute from `Posted Date` at every sort) — directly satisfying BRD-review Finding 2.
- **Sizes plausible.** T5 = L is the correct single largest; the M/S distribution is reasonable. Only caveat is T5's bottleneck status (F3).
- **Critical path** (add to design): **T1 → T5 → T6 → T9 → T17**, parallel P0 chains T1→T2→T11→T12 and T1→T3→T4 (external block), converging at T17.

---

## G1 Tolerance Band Assessment (§5)

Ready for Architect ratification. The proposal is concrete and measurable: convergence point defined (first run with <5 net-new companies, or 10 discovery runs, whichever first); per-bucket floor 80% (AI ≥120, Mid-large ≥120, each vertical ≥40); total floor ≥450 (90%); ceiling = quota + recorded grandfathered overage; value-validity 100% as a hard requirement (no band), with `UNMIGRATED — manual review` rows required resolved before sign-off. Per-bucket-with-exception-list fail handling is the right call given the genuinely supply-constrained Space/Defense universe. This is the BRD's one explicitly delegated number (G1 / Open Q4) and is the single item that must be ratified at design review.

---

## Open-Question Recommendations (one per §8 question)

1. **Unmigrated-track fallback (strict vs skip).** *Recommend: confirm the design's choice — route through the mid-large-tech (strict) classifier + logged warning.* Already the safest reading and consistent with BRD §6 ("never silently coerce or drop") and R-06. Skipping would silently lose a possibly-valid company. Engineer-Lead-decidable; surface only as a one-line confirm.
2. **`AI TPM Jobs` → `Qualified Jobs` rename.** *Recommend: approve the rename.* It rides the same in-place migration block as the D-09 `AI Domain`→`Track` rename (minimal added churn), and a stale "AI TPM Jobs" header over a now-multi-track count is actively misleading. Log as D-15 if approved.
3. **Pre-scrape freshness gating (audit-trace tradeoff).** *Recommend: accept the efficiency reading.* Pre-scrape skip directly attacks R-01 (the largest cost unknown) by avoiding Firecrawl/Gemini spend on stale postings, and a log line is the same audit level already used by the domain/YoE/work-auth write-time gates — a never-written row leaves no sheet trace by design consistency, not omission.
4. **G1 tolerance band ratification.** *Recommend: ratify §5 as proposed (80%/bucket, 90% total, 100% validity).* This is the one genuinely architect-owned decision (BRD delegates it explicitly). The reasoning (supply-constrained verticals, structural ceiling) is sound; ratify or adjust the percentages, but a number must be pinned here or G1 is unverifiable at launch.
5. **Tavily as optional job_agent dependency.** *Recommend: accept — it is REQ-mandated, not scope creep.* REQ-004-10 explicitly requires "best-effort backfill via Tavily-scoped search"; the design already degrades gracefully (runs only when `TAVILY_API_KEY` set; keep+flag path satisfies the REQ without it). No deferral needed. Engineer-Lead-decidable.

Net: only **Q4** requires a substantive Architect decision; Q1/Q2/Q3/Q5 are fast confirms.

---

## Recommended status.md Updates

1. **Mark "TPM reviews technical design" complete** (this report, `reviews/design-tpm-review.md`).
2. **Add three risk rows** carried from design §8: R-11 test-suite churn concentration; R-12 Workday relative-date granularity; R-13 per-track context-cache fan-out.
3. **Add decision-log entries** (record on user/architect sign-off): D-15 `Qualified Jobs` rename approved (Q2); D-16 G1 band ratified per §5 (Q4); D-17 unmigrated→strict-path (Q1); D-18 pre-scrape freshness gating accepted (Q3); D-19 Tavily optional dep in job_agent accepted (Q5).
4. **Gate to Phase 3:** the five §8 open questions (esp. Q4 band) plus User + TPM design sign-off gate entry to Phase 3. Recommend resolving Q1–Q5 as the first design-review agenda items — Q4 shapes G1 verifiability and must not carry into implementation unresolved.
5. **Phase 3 seed:** on entry, port the T1–T17 breakdown into the status task list with the critical path **T1→T5→T6→T9→T17** named, and tag T4 and T17 with their external/user-owned prerequisites (Company_List prune; JD_Tracker wipe; trial-run cost confirmation).
