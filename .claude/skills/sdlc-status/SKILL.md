---
name: sdlc-status
description: View SDLC project status - single project detail or all active projects overview
allowed-tools: Read, Glob, Bash
user-invocable: true
---

# SDLC Project Status View

View SDLC project status. Supports single project detail or global overview.

## Arguments

`$ARGUMENTS`: optional project ID (e.g. `PRJ-001`)

## Instructions

### With project ID: Single project detail

1. Use Glob to search `docs/sdlc/PRJ-xxx-*/status.md` to locate the corresponding project directory
2. Read `status.md` and display:
   - Current phase and status
   - Task completion progress per phase (completed/total)
   - Risk register
   - Current blockers
   - Recent decision log entries
3. If `brd.md`, `tech-design.md`, or `launch-readiness.md` exist, indicate their status
4. Check the `reviews/` directory and list existing review records

### Without arguments: Global overview

1. Read `docs/sdlc/index.md`
2. If the index table is empty, display: "No active SDLC projects. Use /sdlc-init to create a new project."
3. For each active project (status is not ✅ Complete), read its `status.md` and extract key information
4. Generate a summary report:

   ```markdown
   ## SDLC Project Status Overview

   **Date**: YYYY-MM-DD

   | Project ID | Name | Phase | Progress | Risks | Blockers |
   |------------|------|-------|----------|-------|----------|

   ### Projects Requiring Attention
   [List projects with risks or blockers; if none, note "All projects progressing normally"]
   ```
