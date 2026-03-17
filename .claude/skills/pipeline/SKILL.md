---
name: pipeline
description: Run the full pathfinder agent pipeline in sequence (company → job → match → optimizer)
allowed-tools: Bash, Read
user-invocable: true
---

# Run Full Pipeline

Execute all 4 agents in the correct order. Each stage depends on the previous one's output.

## Pipeline order

1. `company_agent.py` — Discover companies and career URLs
2. `job_agent.py` — Find TPM job postings from discovered companies
3. `match_agent.py` — Score resume against discovered JDs
4. `resume_optimizer.py` — Tailor resume for top matches

## Instructions

1. If `$ARGUMENTS` contains a stage number (1-4), start from that stage. Otherwise start from stage 1.
2. Before running, confirm with the user: "About to run the pipeline in sequence (stage X → 4). This will call external APIs and consume quota. Confirm execution?"
3. Run each agent sequentially:
   ```bash
   source venv/bin/activate && python agents/<agent>.py 2>&1
   ```
4. After each stage, report success/failure. If a stage fails, stop and report the error — do not continue to the next stage.
5. After all stages complete, provide a brief summary of results.
