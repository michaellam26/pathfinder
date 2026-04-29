---
name: check-env
description: Verify that all required API keys in .env are set and non-empty
allowed-tools: Bash
user-invocable: true
---

# Check Environment

Verify that all API keys declared in `.env` are set and non-empty.

The check **scans `.env` itself** for any variable name containing `_API_KEY`,
so adding new keys (e.g. `GEMINI_API_KEY_2`, `OPENAI_API_KEY`) is auto-detected
without editing this skill.

## Instructions

1. Run this check:
   ```bash
   source venv/bin/activate && python -c "
   import os, re
   from pathlib import Path
   from dotenv import load_dotenv
   load_dotenv()
   env_path = Path('.env')
   declared = []
   if env_path.exists():
       for raw in env_path.read_text().splitlines():
           line = raw.strip()
           if not line or line.startswith('#'):
               continue
           m = re.match(r'^([A-Z][A-Z0-9_]*)\s*=', line)
           if m and '_API_KEY' in m.group(1):
               declared.append(m.group(1))
   if not declared:
       print('No *_API_KEY* variables declared in .env')
   else:
       missing = 0
       for k in declared:
           v = os.getenv(k, '')
           status = 'SET' if v else 'MISSING'
           preview = v[:6] + '...' if len(v) > 6 else (v if v else '')
           print(f'  {k}: {status}' + (f' ({preview})' if preview else ''))
           if not v:
               missing += 1
       print(f'\nTotal: {len(declared)} declared, {missing} missing')
   " 2>&1
   ```
2. Report which keys are set and which are missing. Do NOT reveal full key values.
