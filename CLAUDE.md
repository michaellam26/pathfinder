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

Load env vars in scripts with `python-dotenv` (`from dotenv import load_dotenv; load_dotenv()`).

## Project Structure

```
agents/              # 4 Runtime Agents (the product)
  company_agent.py   # AI company discovery + career URL finding
  job_agent.py       # TPM job discovery + JD extraction
  match_agent.py     # Resume-to-JD matching (2-stage)
  resume_optimizer.py # Resume tailoring + re-scoring
shared/              # Shared utilities reused across agents
  excel_store.py     # Unified Excel persistence layer
  gemini_pool.py     # Gemini API key rotation
  rate_limiter.py    # Token-bucket rate limiter
  config.py          # Shared constants (MODEL, AUTO_ARCHIVE_THRESHOLD)
tests/               # Unit tests (485+ cases)
docs/
  sdlc/              # SDLC project documents (index + per-project dirs)
.claude/
  agents/            # 11 Custom Agents (dev-time analysis, read-only)
  skills/            # 8 Skills (SDLC coordination + operational execution)
profile/             # Candidate resume (.md/.txt)
jd_cache/            # JD Markdown cache (auto-created)
tailored_resumes/    # Tailored resume output (auto-created)
venv/                # Python 3.11 virtualenv
.env                 # API keys (not committed)
```

## Architecture Intent

This is a **multi-agent AI project**. The expected pattern:
- `agents/` — each file or subdirectory is a self-contained agent with a specific role
- `shared/` — cross-agent utilities: tool wrappers, prompt templates, common helpers

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

## Running Agents

No build step. Run agents directly:

```bash
source venv/bin/activate
python agents/<agent_name>.py
```

## Custom Agents (`.claude/agents/`)

Development-time analysis agents invoked via the Agent tool:

| Agent | Model | Layer | Purpose |
|---|---|---|---|
| `product-manager` | sonnet | 📋 Planning | Research, feasibility analysis, BRD writing, testing sign-off, decision support |
| `tpm` | opus | 🔄 Coordination | Task decomposition, coordination, risk management, progress reporting, launch readiness |
| `agent-reviewer` | opus | 🔍 Quality | Review agent code quality, prompt design, cross-agent consistency |
| `api-debugger` | sonnet | 🔍 Quality | Debug Gemini/Tavily/Firecrawl/ATS API issues |
| `schema-validator` | sonnet | 🔍 Quality | Validate Excel sheet schemas and inter-agent data contracts |
| `test-analyzer` | sonnet | 🔍 Quality | Analyze test failures, identify coverage gaps |
| `doc-sync` | sonnet | 🔍 Quality | Detect documentation drift (REQUIREMENTS/ARCHITECTURE/BUGS/CHANGELOG) |
| `bug-tracker` | sonnet | 🔍 Quality | Manage BUGS.md: verify status, scan new bugs, suggest regression tests |
| `eval-engineer` | sonnet | 🔍 Quality | AI output quality evaluation: scoring calibration, prompt regression, hallucination detection |
| `observability` | sonnet | 🔍 Quality | Pipeline run reporting, output quality drift detection, anomaly alerting |
| `cost` | sonnet | 🔍 Quality | API token usage estimation, quota monitoring, cost optimization recommendations |

All agents are read-only (analysis/reporting only, no code modifications).

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
