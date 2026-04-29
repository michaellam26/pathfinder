---
name: test-one
description: Run tests for a specific agent or module by name
allowed-tools: Bash, Read
user-invocable: true
---

# Run Single Test File

Run tests for one specific module. The user specifies the target via `$ARGUMENTS`.

## Test file mapping

| Shorthand | Test file |
|---|---|
| company | tests/test_company_agent.py |
| job | tests/test_job_agent.py |
| match | tests/test_match_agent.py |
| optimizer | tests/test_resume_optimizer.py |
| excel | tests/test_excel_store.py |
| acceptance | tests/test_acceptance.py |
| ai-quality | tests/test_ai_quality.py |
| ats | tests/test_ats_matcher.py |
| exception | tests/test_exception_classification.py |
| gemini-cache | tests/test_gemini_pool_cache.py |
| gemini-retry | tests/test_gemini_pool_retry.py |
| injection | tests/test_prompt_injection.py |
| run-summary | tests/test_run_summary.py |
| prompts | tests/test_shared_prompts.py |
| workday | tests/test_workday_url.py |

## Instructions

1. Parse `$ARGUMENTS` to determine which test file to run. If empty or invalid, list available test targets and ask the user to pick one.
2. If `$ARGUMENTS` does not match any shorthand above, also try matching as a literal filename under `tests/` (e.g. `test_match_agent` or `test_match_agent.py`) before failing.
3. Run the test:
   ```bash
   source venv/bin/activate && python -m pytest tests/<test_file>.py -v 2>&1
   ```
4. Summarize results. If any test fails, briefly explain the failure cause.
