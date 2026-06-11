# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

The project uses a Python 3.11 virtualenv at `./venv`. Always activate it before running code:

```bash
source venv/bin/activate
```

API keys go in `.env` (already present but empty). Required keys:
- `GEMINI_API_KEY` — Google Gemini (via `google-generativeai`)
- `TAVILY_API_KEY` — Tavily search API
- `FIRECRAWL_API_KEY` — Firecrawl web scraping

Optional: `GEMINI_API_KEY_2` — second Gemini key for key-pool rotation (all 4 agents consume it when set).

Load env vars in scripts with `python-dotenv` (`from dotenv import load_dotenv; load_dotenv()`).

## Project Structure

```
agents/              # 4 Runtime Agents (the product)
  company_agent.py   # AI company discovery + career URL finding
  job_agent.py       # TPM job discovery + JD extraction (incl. ats_keywords)
  match_agent.py     # Resume-to-JD matching (3-dim: ATS / Recruiter / HM)
  resume_optimizer.py # Resume tailoring + 3-dim re-scoring
shared/              # Shared utilities reused across agents
  excel_store.py     # Unified Excel persistence layer
  gemini_pool.py     # Gemini API key rotation + transient retry
  rate_limiter.py    # Token-bucket rate limiter
  config.py          # Shared constants (MODEL, AUTO_ARCHIVE_THRESHOLD)
  prompts.py         # Shared LLM system prompts (RECRUITER, HM, TAILOR)
  schemas.py         # Pydantic response schemas for Gemini
  exceptions.py      # GeminiTransientError / GeminiStructuralError
  run_summary.py     # Structured run-log dataclass
  ats_matcher.py     # Deterministic ATS keyword coverage (PRJ-002)
  ats_synonyms.py    # Hand-curated ATS keyword synonym table (PRJ-002)
tests/               # Unit tests (859+ cases)
docs/
  sdlc/              # SDLC project documents (index + per-project dirs)
.claude/
  agents/            # 11 Custom Agents (Planning / Quality / Evaluation groups; no Edit/Write tools)
  skills/            # 8 Skills (SDLC coordination + operational execution)
profile/             # Candidate resume (.md/.txt/.pdf — picker priority in that order)
profile/.cache/      # Auto-generated MD from PDF input (deterministic, hash-keyed)
templates/           # PDF rendering assets
  resume.css         # ATS-safe CSS for tailored-resume PDF output
jd_cache/            # JD Markdown cache (auto-created)
tailored_resumes/    # Tailored resume output (auto-created; .md + .pdf per JD)
venv/                # Python 3.11 virtualenv
.env                 # API keys (not committed)
```

## Architecture Intent

This is a **multi-agent AI project**. The expected pattern:
- `agents/` — each file or subdirectory is a self-contained agent with a specific role
- `shared/` — cross-agent utilities: tool wrappers, prompt templates, common helpers

### Manual-entry override rule

The agents accept manually-inserted rows in `pathfinder_dashboard.xlsx` and
will enrich them on the next pipeline run:

- **Company_List** — insert a row with just `Company Name` + `AI Domain` (blank
  Career URL). `company_agent.run_phase_1_5` detects the blank URL and calls
  `find_career_url` to discover an ATS/Workday URL, writing it back. Tavily
  must be available; rows that resist discovery are reported and left blank
  for retry. `AI Domain` may use any of the 6 whitelisted buckets (Big Tech
  AI Investment / Consumer ML Tech / AI Startups / AI Infrastructure & Compute
  / Large Model Labs / Defense/Robotics AI), or a custom string (job_agent
  treats unknown buckets as `ai_native`).
- **JD_Tracker** — insert a row with just `JD URL` + `Company`. The job_agent
  picks it up via `get_incomplete_jd_rows` and runs full extraction.

## Key Libraries Available (installed in venv)

| Library | Purpose |
|---|---|
| `google-generativeai` | Gemini LLM (primary model) |
| `litellm` | Unified LLM API gateway |
| `openai` | OpenAI-compatible API calls |
| `tavily-python` | Web search via Tavily API |
| `firecrawl-py` | Web scraping/crawling |
| `crawl4ai` | AI-optimized web crawling |
| `aiohttp` / `httpx` | Async HTTP requests |
| `beautifulsoup4` | HTML parsing |
| `huggingface_hub` | HuggingFace model access |
| `pycountry` | US state/country name lookup for job geo-filtering |
| `pydantic` | Structured output schemas for Gemini JSON response validation |
| `requests` | HTTP requests for ATS API calls and JD scrape fallback |
| `openpyxl` | Excel file read/write (core data store) |
| `pdfplumber` | Deterministic PDF→text extraction with layout/font metadata (PRJ-003) |
| `weasyprint` | MD→PDF rendering for tailored resumes (PRJ-003) — requires `brew install pango` on macOS |

## Running Agents

No build step. Run agents directly:

```bash
source venv/bin/activate
python agents/<agent_name>.py
```

## Custom Agents (`.claude/agents/`)

Development-time agents invoked via the Agent tool, organized into three groups under the user (Architect / Product Owner), alongside the Implementation group (the Claude Code main thread itself):

| Agent | Model | Group | Purpose |
|---|---|---|---|
| `product-manager` | sonnet | 📋 Planning | Research, feasibility analysis, BRD writing, testing sign-off, decision support |
| `tpm` | opus | 📋 Planning | Task decomposition, coordination, risk management, progress reporting, launch readiness |
| `agent-reviewer` | opus | 🔍 Quality | Review agent code quality, prompt design, cross-agent consistency |
| `api-debugger` | sonnet | 🔍 Quality | Debug Gemini/Tavily/Firecrawl/ATS API issues |
| `schema-validator` | sonnet | 🔍 Quality | Validate Excel sheet schemas and inter-agent data contracts |
| `test-analyzer` | sonnet | 🔍 Quality | Analyze test failures, identify coverage gaps |
| `doc-sync` | sonnet | 🔍 Quality | Detect documentation drift (REQUIREMENTS/ARCHITECTURE/BUGS/CHANGELOG) |
| `bug-tracker` | sonnet | 🔍 Quality | Manage BUGS.md: verify status, scan new bugs, suggest regression tests |
| `eval-engineer` | sonnet | 📊 Evaluation | AI output quality evaluation: scoring calibration, prompt regression, hallucination detection |
| `observability` | sonnet | 📊 Evaluation | Pipeline run reporting, output quality drift detection, anomaly alerting |
| `cost` | sonnet | 📊 Evaluation | API token usage estimation, quota monitoring, cost optimization recommendations |

All 11 agents carry no Edit/Write tools (analysis-only by design; `allowed-tools: Read, Grep, Glob, Bash`). Each group authors its own deliverables (Planning: requirements & milestones; Quality: test plans & review reports; Evaluation: eval & cost reports), drafted by the agents and persisted via the Claude Code main thread — which alone holds code write access.

## SDLC Workflow (`docs/sdlc/`)

5-phase workflow coordinated by TPM Agent: BRD → Tech Design → Implementation → Testing → Launch.

Each project lives in `docs/sdlc/PRJ-xxx-<name>/` with `status.md` as single source of truth.

| Skill | Purpose |
|---|---|
| `/sdlc-init` | Initialize new SDLC project with ID, directory, and templates |
| `/sdlc-status` | View project status (single project or all active) |
| `/sdlc-review` | Trigger stage-specific reviews (brd/design/testing/launch) |

## Installing New Dependencies

```bash
source venv/bin/activate
pip install <package>
```
