# Claude Opus 4.7 vs Gemini 3.1 Flash Lite — Tailor-Step Evaluation

**Scope**: should we replace `MODEL = gemini-3.1-flash-lite` with **Claude Opus 4.7** for the **`tailor_resume` / `batch_tailor_resume`** calls only? Match (Stage 1 coarse + Stage 2 fine), Recruiter rescore, and HM rescore stay on Gemini regardless — they are score-only and benefit from Gemini's high TPM/RPM headroom.

**Verdict (TL;DR)**: **No — do not adopt Opus 4.7 for the tailor step**, in any form (full swap or opt-in fallback). The cost / latency penalty is too steep for the expected quality lift. The Gemini 3.1 Flash Lite tailor path stays as-is. Decision finalized 2026-05-05; no follow-up A/B planned. Cost / latency / integration analysis below is preserved as historical record so the decision can be revisited if Opus pricing or rate limits change materially.

---

## 1. Per-call cost math

The tailor step's payload looks like this in the current code (see [resume_optimizer.py:122-148](../../../agents/resume_optimizer.py:122)):

| Component | Approx. tokens (per single-JD call) |
|---|---|
| `TAILOR_SYSTEM_PROMPT` | ~600 |
| Resume Markdown | ~2,000 |
| JD Markdown | ~2,500 |
| **Input total** | **~5,100** |
| Tailored resume Markdown (output) | ~2,000 |
| `optimization_summary` (output) | ~150 |
| **Output total** | **~2,150** |

Batch calls (`BATCH_TAILOR_SIZE = 2`) double the JD payload but share the system prompt + resume, so amortized input is roughly the same per JD.

### Published list prices (USD per 1M tokens, May 2026)

| Model | Input | Output | Notes |
|---|---|---|---|
| Gemini 3.1 Flash Lite (preview) | Free tier currently in use; paid tier ~$0.10 / $0.40 | | Multi-key pooling absorbs RPM cap |
| Claude Opus 4.7 (1M context) | ~$15 / ~$75 (assume Opus-class pricing) | | No free tier |

### Per-call $ estimates (paid Gemini for like-for-like)

| Model | Input cost | Output cost | **Per JD** | 100 JDs | 500 JDs |
|---|---|---|---|---|---|
| Gemini 3.1 Flash Lite (paid) | 5,100 × $0.10/M = $0.00051 | 2,150 × $0.40/M = $0.00086 | **~$0.0014** | $0.14 | $0.70 |
| Claude Opus 4.7 | 5,100 × $15/M = $0.0765 | 2,150 × $75/M = $0.1613 | **~$0.24** | $24 | $120 |

**Cost ratio: Opus is ~170× more expensive per tailor call** at list pricing. Even with prompt caching (system prompt + resume cached → ~50% input discount on cache hits), Opus stays ~150× pricier.

For a typical run targeting **50 high-fit JDs**, the upgrade is roughly **$12 of Opus tokens vs ~$0.07 of Gemini tokens** per pipeline run.

## 2. Latency

| Model | TTFB (typical) | Tokens/sec (output) | Tailor call wall time |
|---|---|---|---|
| Gemini 3.1 Flash Lite | ~0.5–1.5s | ~150 t/s | ~15s |
| Claude Opus 4.7 | ~2–4s | ~50–80 t/s | ~30–45s |

Opus is **~2–3× slower per call**. With `BATCH_TAILOR_SIZE = 2` and `RESCORE_CONCURRENCY = 3`, end-to-end optimizer wall time would roughly double if Opus replaced Gemini.

## 3. Quality lift hypothesis (no A/B run — short memo)

Opus is broadly stronger on long-context reasoning, instruction adherence, and structured output. For resume tailoring specifically:

**Where Opus likely wins**
- Better preservation of factual claims (less hallucination of metrics or scope) — relevant to REQ-052's "no fabricated achievements" guard
- More natural rephrasing that echoes JD vocabulary without keyword-stuffing artifacts
- Better at JDs with implicit asks ("you'll mentor", "drive ambiguous programs") that need semantic, not lexical, matching

**Where Gemini is already adequate**
- ATS keyword surfacing is deterministic post-tailor (`shared/ats_matcher.compute_coverage`) — model choice does not change ATS%
- Recruiter dim is a single integer score — Opus's reasoning depth is overkill
- HM dim already uses the same `FINE_SYSTEM_PROMPT` as match Stage 2; switching only the tailor changes inputs to the rescore but not the rescore model itself

**Realistic delta estimate** (without an A/B run): tailored HM score gains of **+1 to +4 points on average**, larger on JDs where the current Gemini output regresses (`regression=True` in `Tailored_Match_Results`). Most of the value is concentrated in the regression tail.

## 4. Integration shape

LiteLLM is already in `requirements.txt` (see `CLAUDE.md`'s library table), so a model swap is one config change at the call site, not a new SDK:

```python
# shared/config.py
MODEL = "gemini/gemini-3.1-flash-lite"  # current
TAILOR_MODEL = os.getenv("TAILOR_MODEL", MODEL)  # new override
```

```python
# agents/resume_optimizer.py
import litellm
resp = litellm.completion(
    model=TAILOR_MODEL,
    messages=[...],
    response_format={"type": "json_schema", "schema": TailoredResume.model_json_schema()},
)
```

**No new key pool needed for a small experiment** — Anthropic single-key concurrency is fine at our volume. If we ever scale Opus across the whole run, mirror `shared/gemini_pool.py` for `claude_pool.py` (multi-key rotation + transient retry).

## 5. Decision (2026-05-05): not pursued

User decision after reviewing §1–§4: the cost (~170× per call) and latency (~2–3× slower) penalties are not justified by the expected quality lift, especially since the lift is concentrated in a small regression tail (5–15% of JDs).

**Action items**: none. The tailor step stays on `gemini-3.1-flash-lite` indefinitely. No `TAILOR_MODEL` / `TAILOR_FALLBACK` env override, no `claude_pool.py`, no schema adapter, no A/B run.

**Re-open trigger**: revisit only if any of the following change:
- Anthropic publishes a Haiku-tier or cached-input pricing that brings per-call cost within 3× of Gemini Flash Lite
- Gemini Flash Lite output quality regresses meaningfully on tailored resume HM scores (watch `Tailored_Match_Results.Regression` rate over time)
- The user upgrades to a paid Opus plan for unrelated reasons (cost becomes sunk, fallback becomes a freebie)

The cost / latency / integration analysis above is retained as historical record so a future revisit doesn't have to redo it.
