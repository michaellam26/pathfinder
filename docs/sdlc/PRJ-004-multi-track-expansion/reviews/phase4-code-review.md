# Code Review: PRJ-004 Implementation

**Reviewer**: agent-reviewer (Quality group)
**Date**: 2026-07-07
**Verdict**: APPROVE WITH COMMENTS

Implemented faithfully to design.md. Five filter gates, job_domain cross-agent
flow, per-track prompt selection, byte-identity guarantee, 20-column JD schema,
and both migration paths all match the approved design. No correctness BLOCKER;
no path silently drops or coerces a row in violation of never-silently-drop.
Scope: agents/* + shared/excel_store.py + shared/prompts.py, commits 49e3b1b..d1fb80d.

## Findings

1. **[MINOR — fix]** company_agent discovery (:731-761) and migrate_tracks
   (:1089-1124) prompts omit SECURITY_CLAUSE and embed untrusted Tavily
   content / business_focus without <scraped_content> fencing. Design requires
   the clause on every system prompt. Pre-existing gap (present at baseline),
   but PRJ-004 rewrote both prompts without closing it. Blast radius limited
   (deterministic _apply_bucket_rules still hard-drops primes; junk companies
   fail find_career_url) — fix as fast-follow within Phase 4.
2. **[MINOR — fix]** YoE gate keeps min_yoe == 11 (correct per design ≤3/≥12
   rule) but comment + skip message say "[4,10]" — misleading label only.
3. **[OBSERVATION]** Design §2.2.3 "post-parse otherwise" freshness gating is
   not implemented for backfilled dates; code follows the same section's
   stronger "backfill is never a drop condition" rule (aged backfilled rows
   sink to Sort Tier 9 instead). The two design sentences conflict; code chose
   never-drop. Add a one-line design note to remove the ambiguity.
4. **[MINOR — harden]** Pre-scrape freshness gate treats compute_freshness_tier
   None as "aged", which would silently drop unknown-date rows IF an adapter
   ever emitted a non-empty unparseable posted_date. Currently safe (all 6
   adapters normalize through _parse_iso_date/_parse_workday_posted_on → ""
   on unparseable), but the invariant is fragile — gate should distinguish
   aged from unparseable.
5. **[MINOR — pre-existing, backlog]** Extraction returning empty company drops
   the JD with only a log line (no JSON ERROR audit row) and infinite per-run
   retry. Pre-existing behavior, not a PRJ-004 change. → BUGS.md backlog.

## Verified correct (highlights)

20-column schema alignment; day-14/15 boundary pinned identically in gate and
tier ceiling; domain/work-auth gates with vertical override making "None"
unreachable for verticals; D-17 unmigrated handling; migration safety (loud
RuntimeError guard, idempotent migrate_tracks, deterministic prime forcing,
zero delete paths); REQ-052 byte identity via shared interned HM_PROMPTS
objects; no track mixing in any Gemini batch; per-track caches torn down in
finally; SECURITY_CLAUSE on all match/job prompts.

## Consistency Matrix — job_domain flow

| Hop | Status |
|---|---|
| job_agent write (forced/LLM → col 9; "None" gated pre-write) | OK |
| selector (col 9 → dict + jd_json; invalid → "AI" + warning, never drops) | OK |
| match_agent routing (_track_batches; get_prompt_pair fallback "AI") | OK |
| resume_optimizer routing (same Excel source ⇒ before/after tracks match) | OK |

**Recommendation**: merge-ready; fix Findings 1–2 now, harden 4, note 3 in
design, log 5 to BUGS.md.
