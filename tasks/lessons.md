# Lessons Learned

## 2026-07-07 — Session handoff means deliverable only, not the next step
- **What happened**: User asked for a new branch + a clear requirements record so a fresh session could run the SDLC cycle. I additionally started running `/sdlc-init` (creating the PRJ-004 skeleton). User rejected the write and restated the instruction.
- **Lesson**: When work is being handed off to a future session, deliver exactly the handoff artifact requested. Do not pre-run steps that belong to the next session's workflow — the receiving session owns its own process (e.g., `/sdlc-init` assigns its own project ID and skeleton).
- **Prevention**: Before adding a step the user didn't name, ask whether it belongs to this session or the next one. Default: it belongs to the next one.

## 2026-07-07 — Pipeline exit codes mask test failures
**What happened**: `pytest ... | tail -2 && git commit` committed T11 with a
red suite — the pipe made the command's exit status `tail`'s (0), not pytest's.
**Rule**: never chain `git commit` behind a piped pytest. Run pytest bare (or
with `set -o pipefail`) and commit as a separate command after seeing the tally.
