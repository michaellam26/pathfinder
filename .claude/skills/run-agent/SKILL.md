---
name: run-agent
description: Run a specific pathfinder agent by name (company, job, match, optimizer)
allowed-tools: Bash, Read
user-invocable: true
---

# Run Agent

Run a pathfinder agent. The user specifies which agent to run via `$ARGUMENTS`.

## Agent name mapping

| Shorthand | Full file |
|---|---|
| company | agents/company_agent.py |
| job | agents/job_agent.py |
| match | agents/match_agent.py |
| optimizer | agents/resume_optimizer.py |

## Instructions

1. Parse `$ARGUMENTS` to determine which agent to run. If empty or invalid, list the 4 available agents and ask the user to pick one.
2. Run the agent:
   ```bash
   source venv/bin/activate && python agents/<agent_file>.py 2>&1
   ```
3. Show the output to the user. If the agent fails, analyze the error and suggest fixes.
