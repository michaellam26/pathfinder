# PRJ-003: PDF Resume I/O + Claude Opus Tailor Evaluation

**Phase**: Implementation Complete
**Status**: 🟢 Ready for review
**Priority**: P2
**Created**: 2026-05-05
**Last Updated**: 2026-05-05

## Scope

Three sub-deliverables:

1. **PDF → MD input**: drop a `.pdf` into `profile/`, agents auto-convert to Markdown via `pdfplumber` (no LLM), cached at `profile/.cache/{stem}.{md5}.md`.
2. **MD → PDF output (ATS-safe)**: every tailored resume is also written as a sibling `.pdf` next to the `.md`, styled to mimic the input PDF's typography while enforcing ATS-safe rules (single column, standard fonts, selectable text, no images).
3. **Claude Opus tailor evaluation memo**: a short memo (`eval.md`) deciding whether to swap the tailor step from Gemini 3.1 Flash Lite to Claude Opus 4.7. **Recommendation: not as a full swap; opt-in fallback only.**

## Files Changed

### New
- `shared/resume_io.py` — unified `load_resume()`, `pdf_to_markdown()`, `markdown_to_pdf()`, `get_style_for_resume()`
- `templates/resume.css` — ATS-safe PDF stylesheet with CSS variable overrides for source typography
- `tests/test_resume_io.py` — 13 tests covering picker priority, PDF→MD, cache reuse, MD→PDF, style overrides, HTML escaping
- `docs/sdlc/PRJ-003-pdf-io-opus-eval/eval.md` — Claude Opus eval memo
- `docs/sdlc/PRJ-003-pdf-io-opus-eval/status.md` — this file

### Modified
- `agents/match_agent.py` — local `load_resume()` removed; imports from `shared.resume_io`
- `agents/resume_optimizer.py` — same; `_save_tailored_resume()` now also writes a `.pdf` via `markdown_to_pdf()`; `_RESUME_STYLE` populated in `main()` from input PDF (if any)

### System dependencies (one-time)
- `pip install pdfplumber weasyprint` (added to venv)
- `brew install pango` (pulls cairo/glib/gdk-pixbuf — required by WeasyPrint on macOS)

## Test Results

```
$ python -m pytest tests/ -q
749 passed in 46.49s
```

- 13 new tests in `test_resume_io.py` (all green)
- 736 existing tests still pass — no regression from refactor

## Decision Log

| ID | Decision | Rationale |
|---|---|---|
| D1 | PDF→MD uses `pdfplumber`, not LLM | User explicit: "NO LLM" — keeps conversion deterministic and free |
| D2 | Picker priority `.md > .txt > .pdf` | A hand-edited `.md` always wins; PDF cache is a fallback path |
| D3 | Cache key = MD5 of PDF bytes (truncated to 10 chars) | Resume edits → new hash → fresh conversion automatically |
| D4 | Generate PDF for **all** tailored resumes (no top-N gating) | User explicit: "generate PDF for all" |
| D5 | "Follow input PDF format" interpreted as: capture **font family + body size** from source PDF, apply via CSS variables | Pixel-perfect layout fidelity is impossible from MD; typography mimicry is the achievable equivalent. ATS-safe rules win where they conflict. |
| D6 | Body-size clamped to [9pt, 12pt] in CSS injection | Prevents tiny or oversized fonts from confusing ATS parsers |
| D7 | PDF generation failures log a warning but don't fail the pipeline | PDF is a presentation artifact; the `.md` is the source of truth that drives Excel records |
| D8 | Claude Opus: not a full swap, recommend opt-in fallback | Cost ratio is ~170× per call; quality lift concentrated in the regression tail (~5–15% of JDs) |

## Risk Register

| ID | Risk | Impact | Probability | Mitigation | Status |
|---|---|---|---|---|---|
| R1 | WeasyPrint system deps (pango/cairo) missing on fresh dev machines | Pipeline crashes on `markdown_to_pdf` | Medium | Documented in `CLAUDE.md`; `_save_tailored_resume` catches and warns instead of crashing | Mitigated |
| R2 | PDF→MD heuristics misclassify section headers on unusual resumes | Lower quality MD, downstream tailor lower quality | Low | Picker priority means user can drop a hand-edited `.md` to override | Mitigated |
| R3 | ATS parser still rejects WeasyPrint output despite ATS-safe CSS | User submissions get filtered | Low | Output is selectable text + standard fonts; spot-check via `pdfplumber.extract_text` confirmed in tests | Open (needs real ATS test) |
| R4 | Cache directory `profile/.cache/` accidentally committed | Bloated repo / leaked PDF copies | Low | `profile/` and `tailored_resumes/` are already in `.gitignore` (covers `.cache/` and generated `.pdf` files) | Mitigated |

## Out of Scope

- LLM-assisted PDF parsing (user said no LLM)
- Score-based PDF gating (user said all)
- Wiring Opus into the tailor path — eval memo only
- Multi-resume support (one resume per `profile/` still assumed)

## Follow-ups

- [ ] (If desired) Implement Opus fallback per `eval.md` §5
- [ ] (If desired) Real A/B run on 10 JDs to validate Opus quality estimate
