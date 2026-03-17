---
name: sdlc-init
description: Initialize a new SDLC project with ID, directory structure, and template files
allowed-tools: Read, Write, Edit, Bash, Glob
user-invocable: true
---

# SDLC Project Initialization

Create the SDLC skeleton documents and directory structure for a new project.

## Arguments

`$ARGUMENTS` format: `<project-short-name> [priority P0/P1/P2]`

- Project short name: hyphen-separated English short name, e.g. `resume-scoring-v2`
- Priority: optional, defaults to P1

## Instructions

1. Read `docs/sdlc/index.md`, parse existing PRJ numbers, and assign the next one (e.g. PRJ-001, PRJ-002...)

2. Extract the project short name and priority (default P1) from `$ARGUMENTS`

3. Create the project directory:
   ```
   docs/sdlc/PRJ-xxx-<short-name>/
   docs/sdlc/PRJ-xxx-<short-name>/reviews/
   ```

4. Create `docs/sdlc/PRJ-xxx-<short-name>/status.md`:
   ```markdown
   # PRJ-xxx: <Project Name>

   **Phase**: Phase 1 — BRD
   **Status**: 🟡 In Progress
   **Priority**: <priority>
   **Created**: <today's date>
   **Last Updated**: <today's date>

   ## Task Checklist

   ### Phase 1: BRD
   - [ ] PM researches and writes BRD
   - [ ] User reviews BRD
   - [ ] TPM reviews BRD
   - [ ] Engineer Lead reviews BRD

   ### Phase 2: Tech Design
   - [ ] Engineer Lead writes technical design
   - [ ] User reviews technical design
   - [ ] TPM reviews technical design

   ### Phase 3: Implementation
   - [ ] Task decomposition and dependency ordering (TPM)
   - [ ] Code implementation (Engineer Lead)
   - [ ] Code self-testing passes

   ### Phase 4: Testing & Bug Fix
   - [ ] QA Team review
   - [ ] PM functional acceptance
   - [ ] Bug fixes completed
   - [ ] QA sign-off
   - [ ] PM sign-off

   ### Phase 5: Launch Readiness
   - [ ] TPM launch readiness report
   - [ ] User final sign-off
   - [ ] Engineer Lead confirmation
   - [ ] PM confirmation

   ## Risk Register

   | ID | Risk Description | Impact | Probability | Mitigation | Status |
   |----|------------------|--------|-------------|------------|--------|

   ## Decision Log

   | ID | Decision | Date | Decision Maker |
   |----|----------|------|----------------|

   ## Blockers

   No current blockers.
   ```

5. Create `docs/sdlc/PRJ-xxx-<short-name>/brd.md`:
   ```markdown
   # BRD: <Project Name>

   **Project ID**: PRJ-xxx
   **Author**: PM Agent
   **Status**: Draft
   **Date**: <today's date>

   ## 1. Background & Problem Statement
   [To be filled by PM]

   ## 2. Goals & Success Criteria
   [To be filled by PM — must be measurable]

   ## 3. Scope
   ### In-Scope
   ### Out-of-Scope

   ## 4. Functional Requirements
   | REQ ID | Description | Priority |
   |--------|-------------|----------|

   ## 5. Dependencies & Constraints

   ## 6. Risks & Mitigation
   ```

6. Append a row to the table at the end of `docs/sdlc/index.md`:
   ```
   | PRJ-xxx | <Project Name> | Phase 1 — BRD | 🟡 In Progress | <today's date> | <today's date> |
   ```

7. Output confirmation:
   - Project ID and directory path
   - Next step: ask PM Agent to write the BRD (provide invocation suggestion)
