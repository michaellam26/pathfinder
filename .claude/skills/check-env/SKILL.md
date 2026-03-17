---
name: check-env
description: Verify that all required API keys in .env are set and non-empty
allowed-tools: Bash
user-invocable: true
---

# Check Environment

Verify that all required API keys are configured in `.env`.

## Required keys

- `GEMINI_API_KEY`
- `TAVILY_API_KEY`
- `FIRECRAWL_API_KEY`

## Instructions

1. Run this check:
   ```bash
   source venv/bin/activate && python -c "
   from dotenv import load_dotenv; import os; load_dotenv()
   keys = ['GEMINI_API_KEY', 'TAVILY_API_KEY', 'FIRECRAWL_API_KEY']
   for k in keys:
       v = os.getenv(k, '')
       status = 'SET' if v else 'MISSING'
       preview = v[:6] + '...' if len(v) > 6 else v if v else ''
       print(f'  {k}: {status}' + (f' ({preview})' if preview else ''))
   " 2>&1
   ```
2. Report which keys are set and which are missing. Do NOT reveal full key values.
