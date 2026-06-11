# PathFinder — Project Overview

> A curated technical overview for recruiters, hiring managers, and reviewers. For setup and usage, see [README.md](README.md).

---

## TL;DR

**PathFinder is an end-to-end, multi-agent AI system I designed and shipped to automate the AI-TPM job search** — it discovers AI companies, extracts TPM job postings, scores resume-to-JD fit, and produces per-role tailored resumes. The match + tailor stages run a **3-dimension scoring funnel** (ATS keyword coverage / Recruiter scan / HM deep eval) that mirrors the real North American hiring filter cascade — so the user sees exactly which filter their tailoring moved, instead of a single conflated score. It also demonstrates AI-augmented delivery: I directed a **four-group AI agent team** — Planning (PM + TPM), Implementation (**Claude Code Opus**, sole code write access), Quality (6 agents), and Evaluation (3 agents) — across a full Software Development Life Cycle (BRD → Tech Design → Implementation → Testing → Launch).

**Live repo:** https://github.com/michaellam26/pathfinder
**Stack:** Python 3.11 · Gemini · Claude Code · Tavily · Firecrawl · Crawl4AI · Pydantic · openpyxl · pytest

---

## Why I Built This

I'm a Technical Program Manager at a North American big-tech company, targeting **TPM roles at AI-native companies** and **AI-TPM roles at big-tech**. PathFinder exists to demonstrate hands-on AI engineering depth — LLM orchestration, multi-agent coordination, evaluation rigor, and AI-assisted SDLC — that typically isn't visible from a TPM's day-job artifacts.

Every architectural choice, scoring design, SDLC gate, and review standard in this repo is mine. I directed four AI agent groups: Planning (PM + TPM) authored requirements and milestones, Claude Code (Opus) implemented with sole code write access, and the Quality and Evaluation groups ran parallel test planning, specialist review, and eval/cost reporting. The runtime pipeline is one AI system; the way it was delivered is another. Both are showcased here.

---

## The Runtime Product — A 4-Agent LLM Pipeline

| Stage | Agent | What It Does | Key Techniques |
|---|---|---|---|
| 1. Discover | [`company_agent.py`](agents/company_agent.py) | Finds AI companies via Tavily search; resolves their ATS (Greenhouse/Lever/Ashby/**Workable**/Workday) career-page URLs; **unwraps LinkedIn / VC-portfolio wrapper URLs** back to the underlying ATS board; **Workday-via-Tavily fallback** with strict subdomain-equality guard for unguessable subdomains; **manual-entry override** backfills Career URL on hand-inserted rows | Web search, URL validation, slug-based ATS detection, URL unwrapping, Tavily-guarded fallback with false-positive guard |
| 2. Extract | [`job_agent.py`](agents/job_agent.py) | Pulls TPM openings via ATS JSON APIs; falls back to Firecrawl/Crawl4AI browser scraping for gated sites (Tesla, Workday); extracts structured JD fields **including 8-15 ATS-relevant keywords per role**; auto-sorts `JD_Tracker` into Greater Seattle / Remote / Other tiers after each run | Multi-source scraping, US geo-filtering, `pycountry` subdivisions, Pydantic-typed Gemini extraction, HTTP retry with exponential backoff on 429/5xx |
| 3. Match | [`match_agent.py`](agents/match_agent.py) | **3-dimension scoring funnel** mirroring the real hiring cascade: **ATS Coverage** (deterministic keyword match, no LLM) + **Recruiter Score** (Gemini coarse, batch of 10) + **HM Score** (Gemini fine, 4-dim weighted on UNION of score≥threshold and top-N%); accepts `.md` / `.txt` / `.pdf` resumes (PDF auto-converted via `pdfplumber`, cached) | Cost-aware filtering (free deterministic dim), per-dim calibration, structured Pydantic outputs, batched LLM calls, deterministic PDF→MD conversion |
| 4. Tailor | [`resume_optimizer.py`](agents/resume_optimizer.py) | Rewrites resume per JD; **re-scores all 3 dimensions independently** so the user can see ATS keyword gains separately from semantic strength changes; regression flag uses HM Delta only; renders each tailored `.md` as a sibling **ATS-safe `.pdf`** (WeasyPrint, single column / standard fonts / selectable text); **user-edit protection** — sha256-tracked, skips overwrite if user hand-polished the `.md` between runs | Prompt chaining, before/after per-dimension evaluation, deterministic + LLM hybrid pipeline, ATS-safe PDF rendering, on-disk tamper detection |

All agents share a Pydantic-typed contract and persist to a single Excel workbook (`pathfinder_dashboard.xlsx`), which serves as the durable, human-inspectable state store.

---

## How It Was Built — AI-Augmented Delivery

I structured delivery as AI-augmented program management: I made all architecture, scope, and review decisions, directing four AI agent groups — Planning, Implementation, Quality, and Evaluation.

### The Team

```
            ┌──────────────────────────────────────────┐
            │   Me — Architect / Product Owner         │
            │   (all design, scope & review decisions) │
            └────────────────────┬─────────────────────┘
                                 │  direction + specs
       ┌───────────────┬─────────┴────────┬───────────────────┐
       ▼               ▼                  ▼                   ▼
   Planning       Implementation       Quality            Evaluation
   ─────────      ──────────────       ─────────          ──────────
   Product        Claude Code          Agent Reviewer     Eval Engineer
   Manager        (Opus)               API Debugger       Observability
   TPM                                 Schema Validator   Cost
                  sole code            Test Analyzer
   authors reqs   write access         Doc Sync           authors eval
   & milestones                        Bug Tracker        & cost reports

                                       authors test
                                       plans & reviews
```

- **1 owner, 4 groups, 12 agents.** I hold all design and review authority. Each group authors its own deliverables — requirements and milestones (Planning), test plans and specialist reviews (Quality), eval and cost reports (Evaluation) — while **Claude Code holds sole code write access** and serves as the runtime harness that dispatches the 11 specialist subagents (no Edit/Write tools — analysis-only by design) on my priorities.
- **Delivery path:** I define architecture and scope → PM authors the BRD → TPM decomposes milestones → Claude Code implements → Quality group tests → Evaluation group reports → launch review.
- **8 reproducible skills** I designed (`/pipeline`, `/run-agent`, `/test-all`, `/sdlc-init`, `/sdlc-review`, etc.) encode the operational workflow so every run is deterministic and every review stage is repeatable.
- **Full SDLC artifacts** under [`docs/sdlc/`](docs/sdlc/): BRD, Tech Design, Test Plan, Test Execution Report, Launch Review — authored by the owning group against my specs and acceptance criteria.

---

## Engineering Rigor

- **859+ unit tests** covering scoring logic, Excel schemas, scrape fallbacks, geo-filter edge cases, ATS URL extraction, and the 3-dimension scoring funnel (deterministic matcher + per-dim upserts + regression precedence)
- **Pydantic-typed inter-agent data contracts** — every agent consumes and produces schema-validated structured data
- **Gemini API key pooling, token-bucket rate limiter, transient-error backoff retry** ([`shared/gemini_pool.py`](shared/gemini_pool.py), [`shared/rate_limiter.py`](shared/rate_limiter.py)) — sustains throughput inside free-tier quotas across parallel runs; 5xx / UNAVAILABLE / timeout retried with bounded exponential backoff before raising
- **3-dimension scoring funnel matched to real-world hiring filters** — deterministic ATS keyword coverage runs at zero LLM cost; Gemini recruiter coarse pass batches 10 JDs per call; Gemini HM fine eval is gated on the UNION of score≥threshold and top-N% so neither flat-high nor flat-low distributions break the cascade; ATS keywords are extracted once at JD ingest and cached in `JD_Tracker`, so match re-runs incur zero re-extraction cost; HM-delta-only regression rule prevents false-positive flags on keyword-driven score shifts after tailoring
- **Schema migration as a first-class concern** — every Excel column addition ships with idempotent auto-migration logic and dedicated regression tests, so existing user dashboards survive every release
- **PDF I/O without LLM dependence** — input PDFs converted deterministically via `pdfplumber` (layout-aware section / bullet detection, cached at `profile/.cache/`); tailored output rendered ATS-safe by construction via WeasyPrint + a single CSS stylesheet (single column, standard fonts, selectable text, no images / multi-column / headers)
- **User-edit protection on tailored outputs** — `sha256` of the last-written `.md` stored in `Tailored_Match_Results.Last Written Hash`; subsequent runs detect hand-polished edits and skip overwriting, so the launchd-scheduled daily refresh never silently clobbers manual work
- **Maintained operational docs:** [`REQUIREMENTS.md`](REQUIREMENTS.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`BUGS.md`](BUGS.md), [`CHANGELOG.md`](CHANGELOG.md)
- **Excel as the state store** — deliberate choice: durable, auditable by humans, zero infra dependency, portable across machines

---

## What This Project Demonstrates

For an **AI-TPM hiring manager**, PathFinder is evidence of:

| Competency | Where to Look |
|---|---|
| **Multi-agent system design** | `agents/` — 4 runtime agents (Discover → Extract → Match → Tailor) with clean role separation and Pydantic-typed contracts at every hand-off; a single Excel workbook serves as the durable, human-inspectable shared state store |
| **LLM orchestration** | `match_agent.py` 3-dimension funnel — deterministic ATS coverage + Gemini recruiter coarse pass (batched 10 JDs per call) + Gemini HM fine eval (4-dim weighted, gated on UNION of score≥threshold and top-N%); `resume_optimizer.py` re-scores all 3 dimensions independently after tailoring so each lever is observable; `job_agent.py` extracts 8-15 ATS-relevant keywords per JD as a one-shot LLM call cached on JD_Tracker |
| **Cost awareness at scale** | Deterministic ATS dim runs at zero LLM cost; recruiter scoring batched 10 JDs per call; ATS keywords extracted once at JD ingest and cached so match re-runs are free; `shared/gemini_pool.py` Gemini key pooling + `shared/rate_limiter.py` token-bucket rate limiter + bounded exponential-backoff retry on 5xx / UNAVAILABLE / timeout sustain throughput inside free-tier quotas; `.claude/agents/cost.md` |
| **AI-augmented program management (Claude Code harness)** | `.claude/agents/` — a four-group agent team I designed: 11 specialist subagents (Planning / Quality / Evaluation) + Claude Code (Implementation; sole code write access); `.claude/skills/` — 8 reproducible skills I authored (`/pipeline`, `/run-agent`, `/test-all`, `/sdlc-init`, `/sdlc-review`, …) that encode the operational workflow; parallel multi-reviewer dispatch model flagged 1 production ship-blocker (fixed pre-launch) + 4 quick wins (applied) + 5 deferred quality risks before launch |
| **Structured output discipline** | Pydantic response schemas on every Gemini call (`shared/schemas.py`); strict validation surfaces malformed JSON at the LLM boundary instead of three stages downstream; `JobDetails.ats_keywords` uses `default_factory=list` for clean back-compat round-trip on JDs ingested before the field existed |
| **TPM-grade process discipline** | Full BRD → Tech Design → Implementation → Testing → Launch artifacts under `docs/sdlc/`; risk registers, decision logs, multi-phase reviews, regression test gating, launch readiness checklists — applied to a personal project; `REQUIREMENTS.md` / `ARCHITECTURE.md` / `BUGS.md` / `CHANGELOG.md` maintained continuously |
| **Schema-first inter-agent contracts (Pydantic)** | Every cross-agent data hand-off is a typed Pydantic model — no dict-passing between stages; idempotent auto-migration on every Excel column addition so existing user dashboards survive each release; 859+ unit tests cover scoring logic, schema migrations, scrape fallbacks, geo-filter edge cases, and the 3-dimension scoring funnel |
| **Evaluation thinking** | Per-dimension delta surfacing — `Tailored_Match_Results` exposes 9 columns (Original / Tailored / Delta × {ATS, Recruiter, HM}) so the user sees *which* lever tailoring moved; HM-delta-only regression rule avoids false-positive flags on keyword-driven score shifts; 4-dim weighted HM scoring; before/after match-lift measurement; `.claude/agents/eval-engineer.md` |

---

## Resume One-liner

> *AI-TPM portfolio project — designed and shipped an end-to-end multi-agent LLM pipeline (Gemini + Pydantic-typed inter-agent contracts) that automates AI-company discovery, JD extraction, resume-to-JD matching, and per-role tailoring. Engineered a cost-aware 3-dimension scoring funnel — deterministic ATS keyword coverage (zero LLM cost) + Gemini recruiter coarse pass (batched 10 JDs/call) + Gemini hiring-manager fine eval — modeled on the real ATS → recruiter → HM hiring cascade. Drove full SDLC (BRD → Tech Design → Implementation → Testing → Launch) by directing a four-group AI agent team I designed — Planning (PM/TPM) authored requirements and milestones, Claude Code (Opus) implemented with sole code write access, Quality and Evaluation groups ran parallel test planning, QA review, and eval/cost reporting; 859+ unit tests, idempotent Excel schema migrations, Gemini key pooling + token-bucket rate limiting + transient-error backoff retry.*

---

## Links

- **Repository:** https://github.com/michaellam26/pathfinder
- **Architecture deep-dive:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **Requirements tracking:** [REQUIREMENTS.md](REQUIREMENTS.md)
- **SDLC artifacts:** [docs/sdlc/](docs/sdlc/)
- **Change history:** [CHANGELOG.md](CHANGELOG.md)
