# PathFinder

PathFinder is an autonomous AI-powered job discovery and matching system designed for Technical Program Manager (TPM) candidates. It automates the end-to-end workflow of finding AI companies, discovering TPM positions, evaluating resume-job fit, and tailoring resumes for top matches.

> 📌 **For recruiters & hiring managers** — see **[PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)** for a curated technical overview: why the project exists, what the runtime pipeline does, how it was built by directing a four-group AI agent team (Planning / Implementation / Quality / Evaluation), and what competencies it demonstrates.

## At a Glance

- **What it is:** A 4-agent LLM pipeline — **Discover → Extract → Match → Tailor** — that automates AI-TPM job search end-to-end. The match + tailor stages run a **3-dimension scoring funnel** (ATS keyword coverage / Recruiter scan / HM deep eval) that mirrors the real North American hiring filter cascade.
- **How it was built:** AI-augmented program management — I own all architecture, scope, and review decisions, directing a four-group AI agent team: **Planning** (PM + TPM: requirements & milestones), **Implementation** (**Claude Code Opus** — sole code write access), **Quality** (6 agents: test plans & specialist reviews), **Evaluation** (3 agents: eval & cost reports), across a full SDLC.
- **Scale signals:** ~6K lines of Python · 859+ unit tests · Pydantic-typed inter-agent contracts · Gemini API pooling + token-bucket rate limiting · full BRD / Tech Design / Test / Launch artifacts under `docs/sdlc/`.
- **Stack:** Python 3.11 · Gemini · Claude Code · Tavily · Firecrawl · Crawl4AI · Pydantic · openpyxl · pytest.

## How It Works

The system runs four independent agents in sequence:

1. **Company Agent** — Discovers AI companies via web search (Tavily), finds their career/ATS pages, validates URLs, and unwraps LinkedIn / VC-portfolio wrapper URLs back to the underlying ATS board; for unguessable-subdomain Workday boards, falls back to a Tavily-guarded lookup with a strict subdomain-equality guard. Also backfills the Career URL on any row the user drops into `Company_List` by hand.
2. **Job Agent** — Scrapes career pages for TPM openings using ATS APIs (Greenhouse, Lever, Ashby, **Workable**) or web crawlers (Firecrawl, Crawl4AI). Extracts structured JD data including 8-15 ATS-relevant keywords per role. Auto-sorts `JD_Tracker` into Greater Seattle / Remote / Other tiers after each run.
3. **Match Agent** — **3-dimension scoring funnel** modeled on the real NA hiring cascade: **ATS Coverage** (deterministic keyword match, no LLM) + **Recruiter Score** (Gemini batch coarse) + **HM Score** (Gemini fine, 4-dim weighted), with UNION-of-threshold-and-top-N% gating into the deep-eval stage. Accepts `.md`, `.txt`, or `.pdf` resumes (PDF auto-converted via `pdfplumber`).
4. **Resume Optimizer** — Tailors resume per JD using Gemini, then **re-scores all 3 dimensions independently** so per-application improvement is visible per filter (regression flag uses HM Delta only — ATS keyword gains aren't false-positive regressions). Renders each tailored `.md` as a sibling ATS-safe `.pdf` (WeasyPrint). User-edit protection: if you hand-polish a tailored `.md`, the next run detects the sha256 mismatch and skips the overwrite.

All results are persisted to a local Excel dashboard (`pathfinder_dashboard.xlsx`).

## Project Structure

```
agents/              # 4 Runtime Agents
  company_agent.py   # AI company discovery + career URL finding
  job_agent.py       # TPM job discovery + JD extraction (incl. ats_keywords)
  match_agent.py     # 3-dim scoring (ATS / Recruiter / HM)
  resume_optimizer.py # Resume tailoring + 3-dim re-scoring
shared/              # Shared utilities
  excel_store.py     # Unified Excel persistence layer + auto-migration
  gemini_pool.py     # Gemini key rotation + transient retry backoff
  rate_limiter.py    # Token-bucket rate limiter
  config.py          # Shared constants
  prompts.py         # System prompts (Recruiter / HM / Tailor)
  schemas.py         # Pydantic response schemas for Gemini
  exceptions.py      # Transient vs. structural error classification
  run_summary.py     # Structured per-run log dataclass
  ats_matcher.py     # Deterministic ATS keyword coverage (PRJ-002)
  ats_synonyms.py    # Hand-curated ATS keyword synonym table (PRJ-002)
  resume_io.py       # Unified resume loader (.md/.txt/.pdf) + MD→PDF render (PRJ-003)
templates/           # PDF rendering assets
  resume.css         # ATS-safe CSS for tailored-resume PDF output
scripts/             # Operational scripts
  run_pipeline_scheduled.sh  # Daily full-pipeline runner (launchd)
tests/               # Unit tests (859+ cases)
profile/             # Candidate resume (.md / .txt / .pdf — picker priority in that order)
  .cache/            # PDF→MD conversion cache (auto-created)
docs/                # SDLC project documents
```

## Setup

### Prerequisites

- Python 3.11+
- macOS: `brew install pango` (required by WeasyPrint for tailored-resume PDF rendering)

### Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### API Keys

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

Required keys:
- `GEMINI_API_KEY` — Google Gemini (primary LLM)
- `TAVILY_API_KEY` — Tavily search API
- `FIRECRAWL_API_KEY` — Firecrawl web scraping

Optional:
- `GEMINI_API_KEY_2` — second Gemini key; enables key-pool rotation for higher throughput inside free-tier quotas

### Usage

```bash
source venv/bin/activate
python agents/company_agent.py    # Step 1: Discover companies
python agents/job_agent.py        # Step 2: Find TPM jobs
python agents/match_agent.py      # Step 3: Score matches
python agents/resume_optimizer.py # Step 4: Tailor resumes
```

Place your resume (`.md`, `.txt`, or `.pdf`) in the `profile/` directory before running the match agent. Picker priority is `.md > .txt > .pdf` — drop a PDF straight in and the agents auto-convert via `pdfplumber` (deterministic, cached at `profile/.cache/`).

## AI SDLC Development Team

This project is delivered via AI-augmented program management. I'm the **Architect / Product Owner** — all design, scope, and review decisions are mine. Reporting to me are **four AI agent groups**: Planning authors requirements and milestones, Implementation (Claude Code, Opus) is the only agent with code write access, Quality authors test plans and specialist reviews, and Evaluation produces eval and cost reports. All agent definitions and skills are in the `.claude/` directory.

### The Team

| Group | Agent | Model | Deliverables |
|------|-------|-------|---------|
| **Planning** | Product Manager | Sonnet | BRD authoring, feasibility analysis, testing sign-off |
| **Planning** | TPM | Opus | Milestone decomposition, cross-team coordination, risk management, launch readiness |
| **Implementation** | **Claude Code** | **Opus** | **Sole code write access — implements code, tests, and docs against my specs; also the runtime harness that dispatches every other agent** |
| Quality | Agent Reviewer | Opus | Code quality review, prompt design, cross-agent consistency |
| Quality | API Debugger | Sonnet | Gemini/Tavily/Firecrawl/ATS API issue diagnosis |
| Quality | Schema Validator | Sonnet | Excel sheet schema and inter-agent data contract validation |
| Quality | Test Analyzer | Sonnet | Test failure analysis, coverage gaps, edge case suggestions |
| Quality | Doc Sync | Sonnet | Documentation-to-code drift detection |
| Quality | Bug Tracker | Sonnet | BUGS.md management, new bug scanning, regression test suggestions |
| Evaluation | Eval Engineer | Sonnet | AI output quality evaluation, scoring calibration, hallucination detection |
| Evaluation | Observability | Sonnet | Pipeline run reporting, data quality drift, anomaly alerting |
| Evaluation | Cost | Sonnet | API token usage estimation, quota monitoring, cost optimization |

> **Write-permission model:** Each group authors its own deliverables — Planning drafts requirements and milestones, Quality drafts test plans and review reports, Evaluation drafts eval reports — but **code write access belongs to Claude Code alone**. The 11 specialist subagents carry no Edit/Write tools (analysis-only by design); their drafts and findings are persisted via the Claude Code harness and flow through me for prioritization.

### Delivery Path

```
Me: architecture & scope → PM: requirements (BRD) → TPM: milestones
  → Claude Code: implementation → Quality: testing → Evaluation: eval reports → Launch
```

### Skills

**Operational:**

| Skill | Command | Purpose |
|-------|---------|---------|
| Run Agent | `/run-agent <name>` | Run a specific runtime agent |
| Pipeline | `/pipeline` | Run all 4 agents in sequence |
| Test All | `/test-all` | Run the full test suite |
| Test One | `/test-one <name>` | Run tests for a specific module |
| Check Env | `/check-env` | Verify API key configuration |

**SDLC Management:**

| Skill | Command | Purpose |
|-------|---------|---------|
| SDLC Init | `/sdlc-init <name>` | Initialize a new SDLC project with templates |
| SDLC Status | `/sdlc-status [PRJ-ID]` | View project status (single or all active) |
| SDLC Review | `/sdlc-review <PRJ-ID> <stage>` | Trigger multi-agent stage review |

### SDLC Workflow

```
BRD → Tech Design → Implementation → Testing → Launch
```

Each project lives in `docs/sdlc/PRJ-xxx-<name>/` with `status.md` as the single source of truth. The `/sdlc-review` skill coordinates multiple agents at each stage — for example, the Testing stage dispatches Test Analyzer, Bug Tracker, Doc Sync, API Debugger, and Eval Engineer for a comprehensive review.

## Testing

```bash
source venv/bin/activate
python -m pytest tests/ -v
```
