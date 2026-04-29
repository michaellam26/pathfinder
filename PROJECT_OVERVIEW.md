# PathFinder — Project Overview

> A curated technical overview for recruiters, hiring managers, and reviewers. For setup and usage, see [README.md](README.md).

---

## TL;DR

**PathFinder is an end-to-end, multi-agent AI system I designed and shipped to automate the AI-TPM job search** — it discovers AI companies, extracts TPM job postings, scores resume-to-JD fit, and produces per-role tailored resumes. The match + tailor stages run a **3-dimension scoring funnel** (ATS keyword coverage / Recruiter scan / HM deep eval) that mirrors the real North American hiring filter cascade — so the user sees exactly which filter their tailoring moved, instead of a single conflated score. It also demonstrates AI-augmented delivery: I designed an **11-agent Claude subagent review team** and used **Claude Code (Opus)** as my implementation partner across a full Software Development Life Cycle (BRD → Tech Design → Implementation → Testing → Launch).

**Live repo:** https://github.com/michaellam26/pathfinder
**Stack:** Python 3.11 · Gemini · Claude Code · Tavily · Firecrawl · Crawl4AI · Pydantic · openpyxl · pytest

---

## Why I Built This

I'm a Technical Program Manager at a North American big-tech company, targeting **TPM roles at AI-native companies** and **AI-TPM roles at big-tech**. PathFinder exists to demonstrate hands-on AI engineering depth — LLM orchestration, multi-agent coordination, evaluation rigor, and AI-assisted SDLC — that typically isn't visible from a TPM's day-job artifacts.

Every architectural choice, scoring design, SDLC gate, and review standard in this repo is mine. Claude Code (Opus) served as my implementation partner; an 11-agent Claude review team I designed ran parallel code / prompt / schema / eval / cost review. The runtime pipeline is one AI system; the way it was delivered is another. Both are showcased here.

---

## The Runtime Product — A 4-Agent LLM Pipeline

| Stage | Agent | What It Does | Key Techniques |
|---|---|---|---|
| 1. Discover | [`company_agent.py`](agents/company_agent.py) | Finds AI companies via Tavily search; resolves their ATS (Greenhouse/Lever/Ashby/Workday) career-page URLs | Web search, URL validation, slug-based ATS detection |
| 2. Extract | [`job_agent.py`](agents/job_agent.py) | Pulls TPM openings via ATS JSON APIs; falls back to Firecrawl/Crawl4AI browser scraping for gated sites (Tesla, Workday); extracts structured JD fields **including 8-15 ATS-relevant keywords per role** | Multi-source scraping, US geo-filtering, `pycountry` subdivisions, Pydantic-typed Gemini extraction |
| 3. Match | [`match_agent.py`](agents/match_agent.py) | **3-dimension scoring funnel** mirroring the real hiring cascade: **ATS Coverage** (deterministic keyword match, no LLM) + **Recruiter Score** (Gemini coarse, batch of 10) + **HM Score** (Gemini fine, 4-dim weighted on UNION of score≥threshold and top-N%) | Cost-aware filtering (free deterministic dim), per-dim calibration, structured Pydantic outputs, batched LLM calls |
| 4. Tailor | [`resume_optimizer.py`](agents/resume_optimizer.py) | Rewrites resume per JD; **re-scores all 3 dimensions independently** so the user can see ATS keyword gains separately from semantic strength changes; regression flag uses HM Delta only | Prompt chaining, before/after per-dimension evaluation, deterministic + LLM hybrid pipeline |

All agents share a Pydantic-typed contract and persist to a single Excel workbook (`pathfinder_dashboard.xlsx`), which serves as the durable, human-inspectable state store.

---

## How It Was Built — AI-Augmented Delivery

I structured delivery as AI-augmented program management: I made all architecture, scope, and review decisions; Claude Code implemented under my direction; and an 11-agent Claude review team I designed handled parallel QA across specialized domains.

### The Team

```
            ┌──────────────────────────────────────────┐
            │   Me — Architect, PM, Reviewer           │
            │   (all design, scope & review decisions) │
            └────────────────────┬─────────────────────┘
                                 │ direction + specs
            ┌────────────────────▼─────────────────────┐
            │   Claude Code (Opus)                     │
            │   Implementation Partner                 │
            │   (sole write access; executes my spec)  │
            └────────────────────┬─────────────────────┘
                                 │ dispatches for parallel review
       ┌─────────────────────────┼─────────────────────────┐
       │                         │                         │
   Planning                  Quality                   Evaluation
   ─────────               ─────────                 ───────────
   Product Manager         Agent Reviewer            Eval Engineer
   TPM                     API Debugger              Observability
                           Schema Validator          Cost
                           Test Analyzer
                           Doc Sync
                           Bug Tracker
```

- **1 director, 1 writer, 11 reviewers.** I held design and review authority. Claude Code held sole write access. The 11 specialist subagents were strictly read-only — they analyzed, evaluated, and reported; change recommendations flowed through me for prioritization, then to Claude Code for execution.
- **8 reproducible skills** I designed (`/pipeline`, `/run-agent`, `/test-all`, `/sdlc-init`, `/sdlc-review`, etc.) encode the operational workflow so every run is deterministic and every review stage is repeatable.
- **Full SDLC artifacts** under [`docs/sdlc/PRJ-001-pathfinder-v1/`](docs/sdlc/PRJ-001-pathfinder-v1/): BRD, Tech Design, Test Plan, Test Execution Report, Launch Review — authored by agents against my specs and acceptance criteria.

---

## Engineering Rigor

- **725+ unit tests** covering scoring logic, Excel schemas, scrape fallbacks, geo-filter edge cases, ATS URL extraction, and the 3-dimension scoring funnel (deterministic matcher + per-dim upserts + regression precedence)
- **Pydantic-typed inter-agent data contracts** — every agent consumes and produces schema-validated structured data
- **Gemini API key pooling, token-bucket rate limiter, transient-error backoff retry** ([`shared/gemini_pool.py`](shared/gemini_pool.py), [`shared/rate_limiter.py`](shared/rate_limiter.py)) — sustains throughput inside free-tier quotas across parallel runs; 5xx / UNAVAILABLE / timeout retried with bounded exponential backoff before raising
- **3-dimension scoring funnel matched to real-world filters** — deterministic ATS keyword coverage runs free; Gemini coarse-then-fine handles the human-judgment dimensions only when warranted; UNION gating between stages protects against both flat-high and flat-low score distributions
- **Schema migration as a first-class concern** — every Excel column addition (4 across PRJ-002) ships with idempotent auto-migration logic and dedicated regression tests, so existing user dashboards survive every release
- **Maintained operational docs:** [`REQUIREMENTS.md`](REQUIREMENTS.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`BUGS.md`](BUGS.md), [`CHANGELOG.md`](CHANGELOG.md)
- **Excel as the state store** — deliberate choice: durable, auditable by humans, zero infra dependency, portable across machines

---

## Designing the 3-Dimension Scoring Funnel (PRJ-002)

The original single LLM-derived "fit score" was good for prioritization but didn't model the actual hiring funnel a candidate runs through. Real applications cascade through three independent filters: **(1)** ATS keyword filter (mechanical), **(2)** recruiter quick scan (30 sec, holistic), **(3)** hiring manager deep eval (full 4-dimension review). Conflating these into one number meant Score Delta after tailoring couldn't tell the user *what actually changed* — was it keywords? semantic strength? both? neither?

I scoped, designed, and shipped PRJ-002 to fix this. Each design decision is recorded in [`docs/sdlc/PRJ-002-3d-scoring/status.md`](docs/sdlc/PRJ-002-3d-scoring/status.md) with full BRD / Tech Design / Phase 4 review artifacts.

| Design Decision | Rationale | Code |
|---|---|---|
| **ATS as a parallel deterministic dimension, not a hard gate** | Real ATS systems are mechanical keyword scanners — using an LLM to model them is wasteful and inaccurate. Pure-Python matcher (~120 lines, no new pip deps) with case-insensitive matching, lightweight plural stem (`-ies` / `-sses` / `-xes` / `-ches` / `-shes` / `-s`), token-boundary substring check, and a hand-curated synonym table. <30% prints a ⚠️ marker but never drops the JD — soft signal, not hard gate. **API cost: zero.** | [`shared/ats_matcher.py`](shared/ats_matcher.py), [`shared/ats_synonyms.py`](shared/ats_synonyms.py) |
| **LLM extracts ATS keywords once at JD ingest, not at match time** | Match runs need to be cheap and re-runnable; keyword extraction is structurally one-shot per JD. One Gemini call per new JD produces 8-15 high-signal noun phrases (tools / frameworks / certifications), persisted to JD_Tracker. Match scans against the cache. | [`agents/job_agent.py`](agents/job_agent.py) `JobDetails.ats_keywords`, extract_jd prompt |
| **Regression flag = `HM Delta < 0` only** | A tailored resume that boosts ATS coverage but leaves HM unchanged isn't a regression — it's a strategic trade-off (better keywords, same fit). Only HM degradation triggers the "keep base resume" warning. The single-score delta would have flagged keyword-driven score shifts as false-positive regressions. | [`agents/resume_optimizer.py`](agents/resume_optimizer.py) Phase 3 assembly; [`shared/excel_store.py`](shared/excel_store.py) regression precedence |
| **5-PR sequential rollout with parallel multi-agent review** | I split implementation into 5 PRs (foundation → schema → match → optimizer → docs), each ≤4 files. After implementation I dispatched 5 specialist review subagents in parallel (agent-reviewer / test-analyzer / eval-engineer / schema-validator / doc-sync). The review caught one **production ship-blocker** (BUG-56: `ats_keywords` was being silently dropped before reaching the matcher because JD_Tracker had no column for it) and surfaced 5 quality risks (BUG-57~61) — each triaged with explicit verdict (fix / mitigate / accept-risk). | [`docs/sdlc/PRJ-002-3d-scoring/reviews/phase4-review.md`](docs/sdlc/PRJ-002-3d-scoring/reviews/phase4-review.md) |

**Result**: `Tailored_Match_Results` now has 9 per-dimension columns (Original / Tailored / Delta × {ATS, Recruiter, HM}). The user sees exactly which lever the tailoring moved on each application.

---

## What This Project Demonstrates

For an **AI-TPM hiring manager**, PathFinder is evidence of:

| Competency | Where to Look |
|---|---|
| **Multi-agent system design** | `agents/` — 4 agents with clean separation and typed contracts |
| **LLM orchestration** | `match_agent.py` (3-dim funnel: deterministic ATS + Gemini Recruiter batch + Gemini HM fine), `resume_optimizer.py` (3-dim re-score loop + delta tracking) |
| **Funnel modeling matched to real-world filters** | PRJ-002 — designing scoring around the actual ATS → Recruiter → HM cascade rather than a single LLM-derived number; see `docs/sdlc/PRJ-002-3d-scoring/` for the full design trail |
| **Evaluation thinking** | Per-dimension delta surfacing, HM-delta-only regression rule (no false-positive on keyword-driven score shifts), 4-dim weighted HM scoring, before/after match-lift measurement, `.claude/agents/eval-engineer.md` |
| **Cost awareness at scale** | Key pooling, rate limiting, deterministic ATS dim (zero LLM cost), coarse-to-fine LLM dims, `.claude/agents/cost.md` |
| **Structured output discipline** | Pydantic schemas on every LLM call, strict validation, `JobDetails.ats_keywords` field with `default_factory=list` for clean back-compat round-trip |
| **Schema migration as a first-class concern** | Idempotent auto-migration on every Excel column addition (PRJ-002 added 14 columns across 3 sheets — all back-compatible with existing dashboards) |
| **AI-augmented program management** | `.claude/agents/` (11 review subagents I designed), `.claude/skills/` (8 skills I authored), `docs/sdlc/` (full phase gates), parallel multi-reviewer dispatch model used to catch BUG-56 before launch |
| **TPM-grade process discipline** | BRD, risk registers, decision logs, multi-phase reviews, regression test gating, launch readiness checklists — for a personal project |

---

## Resume One-liner

> *Designed and shipped a 4-agent LLM pipeline for end-to-end AI-TPM job discovery, matching, and resume tailoring, including a 3-dimension scoring funnel (deterministic ATS keyword coverage + Gemini recruiter coarse + Gemini HM fine eval) modeled on the real North American hiring filter cascade. Architected an 11-agent Claude subagent review team and used Claude Code as implementation partner across a full SDLC (BRD → Design → Implementation → Testing → Launch), with Pydantic-typed inter-agent contracts and 725+ unit tests.*

---

## Links

- **Repository:** https://github.com/michaellam26/pathfinder
- **Architecture deep-dive:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **Requirements tracking:** [REQUIREMENTS.md](REQUIREMENTS.md)
- **SDLC artifacts:** [docs/sdlc/PRJ-001-pathfinder-v1/](docs/sdlc/PRJ-001-pathfinder-v1/)
- **Change history:** [CHANGELOG.md](CHANGELOG.md)
