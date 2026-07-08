# Engineer Lead Review: PRJ-004 BRD

**Reviewer**: Engineer Lead (Claude Code main thread)
**Date**: 2026-07-07
**Verdict**: APPROVE WITH COMMENTS

## Code-anchor verification

Every code reference in the BRD was spot-checked against the working tree on
branch `prj-004-multi-track-expansion` — all accurate:

| BRD claim | Verified |
|---|---|
| 6 AI-only buckets + `MAX_TOTAL = 200` (`agents/company_agent.py:59-90`) | ✅ `AI_DOMAIN_VALUES` tuple + `MAX_TOTAL = 200` present |
| Workday hardcoded `limit: 20` (`agents/job_agent.py:678`) | ✅ `payload = {"limit": 20, ...}` |
| Firecrawl map `limit=100` (`agents/job_agent.py:774`) | ✅ `app.map(..., limit=100)` |
| `FRESH_DAYS = 5` operates on Excel timestamp, not posting date (`agents/job_agent.py:53`) | ✅ |
| Row selector keyed on `Is AI TPM == True` (`shared/excel_store.py:526-542`) | ✅ `get_jd_rows_for_match` docstring + `_JD_COL["Is AI TPM"]` |
| Single AI-framed prompt pair aliased as COARSE/FINE, call sites `match_agent.py:176,236` and `resume_optimizer.py:253,483` | ✅ |

## Feasibility assessment

1. **REQ-004-08/09/10/11 (YoE / domain / date / work-auth extraction)** — feasible
   as additional Pydantic fields on the existing structured-extraction schema
   (`shared/schemas.py`), avoiding new Gemini round-trips per JD. The BRD's §5
   cost table already assumes this; Tech Design should hold that line.
2. **REQ-004-13 Workday pagination** — the API already takes `limit`/`offset`;
   pagination is a loop, low risk.
3. **REQ-004-14 schema change** — the `_JD_COL` dynamic-lookup pattern (BUG-52)
   means header changes propagate without touching read paths individually;
   the BRD correctly identifies this.
4. **REQ-004-15 sort change** — self-contained replacement of the tier function
   in `shared/excel_store.py:849-908`; freshness tier must be recomputed at sort
   time from `Posted Date`, not read stale from the sheet (BRD §4.2 REQ-004-10
   says "recomputed each run" — Tech Design must place that recompute in the
   sort path, not only the scrape path).
5. **REQ-004-17 Amazon adapter** — same undocumented-JSON-API risk class as the
   existing Workday/Ashby adapters; acceptable, isolate behind the existing
   adapter-registry pattern.

## Comments (non-blocking)

- **C1**: On BRD §7 Q1 (rename `AI Domain` → `Track`): engineering preference is
  to **rename**. The column-name indirection already exists for JD_Tracker; for
  Company_List the read sites are few. Keeping a header named `AI Domain` holding
  "Space"/"Fintech" values is a standing landmine for future maintenance.
- **C2**: BRD §7 Q3 (15-day skip vs no-auto-delete): engineering reading agrees
  with the BRD's assumption — the skip is a write-time gate on new rows only.
  Retroactive dropping would violate G7 and REQ-004-16.
- **C3**: The §5 recommendation (one uncapped trial run before enabling the daily
  schedule) is the correct engineering rollout sequence; recommend it be promoted
  from "recommendation" to an explicit launch-phase checklist item.
- **C4**: REQ-004-25 failure surfacing — the existing `RunSummary` structure is
  the natural carrier; a nonzero-exit + marker-file check in the launchd wrapper
  is sufficient. No new infrastructure needed.

## Conclusion

BRD is technically accurate, fully traceable to the intake doc, and buildable as
specified. Approve, with the four §7 open questions to be answered by the
Architect at the BRD user-review gate (my recommendation on Q1 and Q3 above).
