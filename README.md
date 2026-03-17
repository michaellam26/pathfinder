# PathFinder

PathFinder is an autonomous AI-powered job discovery and matching system designed for Technical Program Manager (TPM) candidates. It automates the end-to-end workflow of finding AI companies, discovering TPM positions, evaluating resume-job fit, and tailoring resumes for top matches.

## How It Works

The system runs four independent agents in sequence:

1. **Company Agent** — Discovers AI companies via web search (Tavily), finds their career/ATS pages, and validates URLs
2. **Job Agent** — Scrapes career pages for TPM openings using ATS APIs (Greenhouse, Lever, Ashby) or web crawlers (Firecrawl, Crawl4AI), extracts structured JD data
3. **Match Agent** — Two-stage resume-to-JD matching: keyword pre-filter → Gemini LLM batch scoring → top 20% fine evaluation (4-dimension weighted scoring)
4. **Resume Optimizer** — Tailors resume for each matched JD using Gemini, then re-scores to measure improvement

All results are persisted to a local Excel dashboard (`pathfinder_dashboard.xlsx`).

## Project Structure

```
agents/              # 4 Runtime Agents
  company_agent.py   # AI company discovery + career URL finding
  job_agent.py       # TPM job discovery + JD extraction
  match_agent.py     # Resume-to-JD matching (2-stage)
  resume_optimizer.py # Resume tailoring + re-scoring
shared/              # Shared utilities
  excel_store.py     # Unified Excel persistence layer
  gemini_pool.py     # Gemini API key rotation
  rate_limiter.py    # Token-bucket rate limiter
  config.py          # Shared constants
tests/               # Unit tests (485+ cases)
profile/             # Candidate resume (.md/.txt)
docs/                # SDLC project documents
```

## Setup

### Prerequisites

- Python 3.11+

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

### Usage

```bash
source venv/bin/activate
python agents/company_agent.py    # Step 1: Discover companies
python agents/job_agent.py        # Step 2: Find TPM jobs
python agents/match_agent.py      # Step 3: Score matches
python agents/resume_optimizer.py # Step 4: Tailor resumes
```

Place your resume (`.md` or `.txt`) in the `profile/` directory before running the match agent.

## AI SDLC Development Team

This project uses a 12-member AI agent team to manage its own development lifecycle. At the center is **Claude Code (Opus)**, which serves as both **Tech Lead** and **Implementation Agent** — making architecture decisions, writing code and tests, and orchestrating the other 11 specialist agents on demand. All agents and skills are defined in the `.claude/` directory.

### The Team

| Role | Agent | Model | Purpose |
|------|-------|-------|---------|
| **Tech Lead + Implementer** | **Claude Code** | **Opus** | **Architecture decisions, code implementation, test authoring, team coordination — the only agent with write access** |
| Planning | Product Manager | Sonnet | BRD authoring, feasibility analysis, testing sign-off |
| Planning | TPM | Opus | Task decomposition, cross-team coordination, risk management, launch readiness |
| QA | Agent Reviewer | Opus | Code quality review, prompt design, cross-agent consistency |
| QA | API Debugger | Sonnet | Gemini/Tavily/Firecrawl/ATS API issue diagnosis |
| QA | Schema Validator | Sonnet | Excel sheet schema and inter-agent data contract validation |
| QA | Test Analyzer | Sonnet | Test failure analysis, coverage gaps, edge case suggestions |
| QA | Doc Sync | Sonnet | Documentation-to-code drift detection |
| QA | Bug Tracker | Sonnet | BUGS.md management, new bug scanning, regression test suggestions |
| Eval | Eval Engineer | Sonnet | AI output quality evaluation, scoring calibration, hallucination detection |
| Eval | Observability | Sonnet | Pipeline run reporting, data quality drift, anomaly alerting |
| Eval | Cost | Sonnet | API token usage estimation, quota monitoring, cost optimization |

> **Key distinction:** Claude Code is the only agent with code write permissions. The other 11 agents are strictly read-only (analysis, reporting, and review), dispatched by Claude Code as needed.

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
