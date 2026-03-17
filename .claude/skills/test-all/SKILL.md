---
name: test-all
description: Run the full test suite for all pathfinder agents and shared modules
allowed-tools: Bash, Read
user-invocable: true
---

# Run All Tests

Run the complete test suite under `tests/`.

## Instructions

1. Run all tests with verbose output:
   ```bash
   source venv/bin/activate && python -m pytest tests/ -v 2>&1
   ```
2. Summarize results: total passed, failed, errors.
3. If any test fails, briefly explain the failure cause.
