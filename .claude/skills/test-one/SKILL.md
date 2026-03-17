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

## Instructions

1. Parse `$ARGUMENTS` to determine which test file to run. If empty or invalid, list available test targets and ask the user to pick one.
2. Run the test:
   ```bash
   source venv/bin/activate && python -m pytest tests/<test_file>.py -v 2>&1
   ```
3. Summarize results. If any test fails, briefly explain the failure cause.
