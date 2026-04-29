"""Shared Pydantic output schemas for Gemini structured responses.

Single source of truth — match_agent and resume_optimizer must reference
the same MatchResult class so the original score and tailored re-score
use identical schemas.
"""
from pydantic import BaseModel, Field, field_validator


def _clamp_0_100(v: int) -> int:
    """P1-16: enforce 0-100 range at the schema layer so out-of-range Gemini
    output is normalized once instead of relying on each caller to clamp."""
    return max(0, min(100, int(v)))


class CoarseItem(BaseModel):
    index: int = Field(description="0-based index of the JD in the batch.")
    score: int = Field(description="0-100 coarse fit score.")

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, v: int) -> int:
        return _clamp_0_100(v)


class BatchCoarseResult(BaseModel):
    items: list[CoarseItem] = Field(description="One entry per JD in the batch.")


class MatchResult(BaseModel):
    compatibility_score:   int       = Field(description="0–100 fit score.")
    key_strengths:         list[str]
    critical_gaps:         list[str]
    recommendation_reason: str       = Field(description="Specific, weighted analysis per criteria.")

    @field_validator("compatibility_score")
    @classmethod
    def _clamp_compat(cls, v: int) -> int:
        return _clamp_0_100(v)


class TailoredResume(BaseModel):
    tailored_resume_markdown: str = Field(description="Complete tailored resume in Markdown.")
    optimization_summary: str = Field(description="3-5 key changes made and which JD requirements they target.")


class BatchTailoredItem(BaseModel):
    index: int = Field(description="0-based index of the JD in the batch.")
    tailored_resume_markdown: str = Field(description="Complete tailored resume in Markdown.")
    optimization_summary: str = Field(description="3-5 key changes made and which JD requirements they target.")


class BatchTailoredResult(BaseModel):
    items: list[BatchTailoredItem] = Field(description="One entry per JD in the batch.")


class ATSCoverageResult(BaseModel):
    """Output of shared.ats_matcher.compute_coverage.

    Not used as a Gemini response_schema — this models the deterministic
    matcher's return value so downstream code can validate / round-trip
    coverage data through Pydantic when needed.
    """
    percent: float | None = Field(description="matched / total * 100, or None when no keywords.")
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    keyword_count: int = Field(description="Total keywords scored after de-dup.")
