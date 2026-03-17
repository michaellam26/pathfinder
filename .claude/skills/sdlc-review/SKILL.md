---
name: sdlc-review
description: Trigger stage-specific reviews for an SDLC project and save results to reviews/
allowed-tools: Read, Write, Edit, Glob, Bash, Agent
user-invocable: true
---

# SDLC Stage Review

Invoke the corresponding agent for review based on the project phase, and save results to the project's `reviews/` directory.

## Arguments

`$ARGUMENTS` format: `<Project ID> <stage>`

- Project ID: e.g. `PRJ-001`
- Stage: `brd` / `design` / `testing` / `launch`

## Instructions

1. Parse the project ID and stage from `$ARGUMENTS`
2. Use Glob to search `docs/sdlc/PRJ-xxx-*/status.md` to locate the project directory
3. Execute the corresponding review based on the stage:

### Stage: `brd`
- Invoke TPM Agent (subagent_type: `tpm`) to execute `review-brd PRJ-xxx` review
- Invoke PM Agent (subagent_type: `product-manager`) to execute `impact` analysis evaluating the impact of requirements in the BRD
- Merge both review results and save to `reviews/brd-review-YYYY-MM-DD.md`

### Stage: `design`
- Invoke TPM Agent (subagent_type: `tpm`) to execute `review-design PRJ-xxx` review
- Invoke Agent Reviewer (subagent_type: `agent-reviewer`) to review code quality related to the technical design
- Invoke Schema Validator (subagent_type: `schema-validator`) to validate data contracts referenced in the design
- Invoke Eval Engineer (subagent_type: `eval-engineer`) to review whether prompt changes in the design include evaluation plans
- Save review results to `reviews/design-review-YYYY-MM-DD.md`

### Stage: `testing`
- Invoke Test Analyzer (subagent_type: `test-analyzer`) to analyze test coverage and failure causes
- Invoke Bug Tracker (subagent_type: `bug-tracker`) to scan for new bugs and verify existing bug statuses
- Invoke Doc Sync (subagent_type: `doc-sync`) to check consistency between code and documentation
- Invoke API Debugger (subagent_type: `api-debugger`) if the project involves API changes
- Invoke Eval Engineer (subagent_type: `eval-engineer`) to evaluate AI output quality (scoring calibration, hallucination detection, evaluation test coverage)
- Save review results to `reviews/testing-review-YYYY-MM-DD.md`

### Stage: `launch`
- Invoke TPM Agent (subagent_type: `tpm`) to execute `launch PRJ-xxx` launch readiness assessment
- Invoke PM Agent (subagent_type: `product-manager`) to execute `signoff PRJ-xxx` for PM sign-off evaluation
- Save assessment results to `reviews/launch-review-YYYY-MM-DD.md`

4. Output review results summary, noting pass / conditional pass / needs revision
5. List Action Items and their corresponding assignees
