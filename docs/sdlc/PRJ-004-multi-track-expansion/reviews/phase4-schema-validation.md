# Schema Validation: PRJ-004

**Reviewer**: schema-validator (Quality group)
**Date**: 2026-07-07
**Verdict**: PASS

All Excel schemas and inter-agent data contracts implement design.md §3/§2.3
correctly. Every header/position/key-name pairing checked (writer↔reader,
Pydantic↔Excel, cross-agent prompt routing) was consistent. No BLOCKER or
MAJOR findings.

## Contract Table (all PASS)

| Contract | Evidence |
|---|---|
| JD_HEADERS = 20 cols per design §3.1 (Job Domain@9, Sort Tier@14, new cols 15–20) | shared/excel_store.py:26-37 |
| _jd_row_data → 20 values in header order | shared/excel_store.py:597-616 |
| _JD_ERROR_ROW → 20 values; "JSON ERROR" domain filtered by dq=="failed" before domain check | shared/excel_store.py:619-622 |
| _JD_COL consumers all dynamic, no stale indices | shared/excel_store.py:443-768 |
| COMPANY_HEADERS carry Track(2)/Qualified Jobs(7); positional reads unaffected | excel_store.py:20-21; job_agent.py:2054-2056 |
| Header-keyed writes resolve renamed headers | excel_store.py:779-781, 397-399 |
| upsert_companies "track" key matches CompanyInfo.model_dump() | excel_store.py:317; company_agent.py:1009-1011 |
| Migrations rename header cells only — data rows untouched | excel_store.py:101-115 |
| Round-trip: producer keys → _jd_row_data → selector → match/optimizer job_domain | job_agent.py:1971-2046; excel_store.py:584-591; match_agent.py:170; resume_optimizer.py:370,412 |
| JobDetails Literal vocab == JOB_DOMAIN_VALUES (+"None" write-time sentinel, gate-blocked) | job_agent.py:208-214, 2010-2012 |
| CompanyInfo/TrackClassification Literal == TRACK_VALUES (3 sites identical) | company_agent.py:66-69, 87-99, 118-120 |
| shared/schemas.py unchanged (design §3.3) | read in full |
| REQ-052 byte identity: both agents call get_prompt_pair(domain)[1] → same interned object | match_agent.py:261; resume_optimizer.py:264; prompts.py:110-181,194-202 |

## Findings

1. **[MINOR]** YoE gate log says "outside [4,10]" but the actual keep window is
   min ∈ [4,11] (skip iff ≤3 or ≥12; 10+ keeps, 12+ skips, matching BRD/design).
   Log-string imprecision only; gate logic correct. (job_agent.py:2016-2017)
2. **[MINOR]** design.md line-number citations have drifted from implemented
   code (expected — semantic anchors all verified present). No action unless
   design.md must stay a permanently accurate index.
3. **[NOTE]** _apply_bucket_rules(companies, need_by_track) is a superset of
   the design's stated signature (adds deterministic quota trim) — consistent
   with REQ-004-01/03 intent; documented-vs-actual mismatch only.

## Real Workbook Prediction (check 5)

pathfinder_dashboard.xlsx (repo root, 203 Company_List rows) is on the legacy
schema and **JD_Tracker has zero data rows — the user's wipe precondition
(intake C3) is already satisfied**. On the next get_or_create_excel():
company sheets rename in place (203 rows preserved; Track VALUES stay legacy
until --migrate-tracks); JD_Tracker header row silently upgrades to the
20-column schema (the loud RuntimeError guard correctly does not fire because
no data rows exist); all other blocks no-op. No data loss, no error.
