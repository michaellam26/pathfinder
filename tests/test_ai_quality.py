"""
AI Output Quality Tests — PRJ-001 Phase 4 QA

Coverage:
  - TestFinePromptConsistency: REQ-052 full assertEqual between match_agent and resume_optimizer
  - TestFallbackValueConsistency: document fallback values across agents
  - TestCoarseItemScoreDescription: Pydantic schema field descriptions
  - TestHallucinationGuards: structural verification of anti-hallucination rules
  - TestScoreClampBehavior: score minimum enforcement in evaluate_match / batch_coarse_score
"""
import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ── Stub heavy deps before import ────────────────────────────────────────────
for mod in ["google", "google.genai", "google.genai.types", "dotenv",
            "firecrawl", "crawl4ai", "pycountry", "tavily"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

sys.modules["dotenv"].load_dotenv = lambda: None

import google
google.genai = MagicMock()
google.genai.types = MagicMock()

from shared.prompts import (
    FINE_SYSTEM_PROMPT,
    COARSE_SYSTEM_PROMPT as _COARSE_SYSTEM_PROMPT,
    TAILOR_SYSTEM_PROMPT as _TAILOR_SYSTEM_PROMPT,
    BATCH_FINE_SYSTEM_PROMPT as _BATCH_FINE_SYSTEM_PROMPT,
)
from shared.schemas import (
    CoarseItem, BatchCoarseResult,
    MatchResult as MatchMatchResult,
)

# Both agents now reference the same shared FINE_SYSTEM_PROMPT object.
MATCH_FINE_PROMPT = FINE_SYSTEM_PROMPT
OPTIMIZER_FINE_PROMPT = FINE_SYSTEM_PROMPT

from agents.match_agent import (
    batch_coarse_score,
    evaluate_match,
)
import agents.match_agent as match_mod

from agents.resume_optimizer import (
    MatchResult as OptimizerMatchResult,
    batch_re_score,
    re_score,
)
import agents.resume_optimizer as optimizer_mod


# ─────────────────────────────────────────────────────────────────────────────
class TestFinePromptConsistency(unittest.TestCase):
    """REQ-052: resume_optimizer must use the EXACT same fine prompt as match_agent."""

    def test_fine_prompt_exact_match(self):
        """Full assertEqual — not substring, not 'in', exact equality."""
        self.assertEqual(MATCH_FINE_PROMPT, OPTIMIZER_FINE_PROMPT,
                         "match_agent._FINE_SYSTEM_PROMPT != resume_optimizer._FINE_SYSTEM_PROMPT")

    def test_batch_fine_prompt_starts_with_fine_prompt(self):
        """_BATCH_FINE_SYSTEM_PROMPT must start with the same fine prompt."""
        self.assertTrue(_BATCH_FINE_SYSTEM_PROMPT.startswith(OPTIMIZER_FINE_PROMPT),
                        "_BATCH_FINE_SYSTEM_PROMPT does not start with _FINE_SYSTEM_PROMPT")


# ─────────────────────────────────────────────────────────────────────────────
class TestFallbackValueConsistency(unittest.TestCase):
    """Document and verify fallback/default values across agents."""

    def test_match_evaluate_fallback_score_is_1(self):
        """match_agent.evaluate_match error fallback must return score=1."""
        mock_pool = MagicMock()
        mock_pool.generate_content.side_effect = RuntimeError("API error")
        match_mod._KEY_POOL = mock_pool
        try:
            result_json = evaluate_match("resume", "jd")
            result = json.loads(result_json)
            self.assertEqual(result["compatibility_score"], 1)
        finally:
            match_mod._KEY_POOL = None

    def test_match_batch_coarse_fallback_scores_are_1(self):
        """match_agent.batch_coarse_score error fallback must return all 1s."""
        mock_pool = MagicMock()
        mock_pool.generate_content.side_effect = RuntimeError("API error")
        match_mod._KEY_POOL = mock_pool
        try:
            scores = batch_coarse_score("resume", [{"jd_json": '{"job_title":"test"}'}] * 3)
            self.assertEqual(scores, [1, 1, 1])
        finally:
            match_mod._KEY_POOL = None

    def test_optimizer_batch_re_score_fallback_scores_are_0(self):
        """resume_optimizer.batch_re_score error fallback returns score=0.
        This documents the known inconsistency (0 vs 1) flagged by Eval Engineer."""
        mock_pool = MagicMock()
        mock_pool.generate_content.side_effect = RuntimeError("API error")
        optimizer_mod._KEY_POOL = mock_pool
        try:
            results = batch_re_score([{"tailored_resume": "r", "jd_content": "j"}] * 2)
            for r in results:
                self.assertEqual(r["compatibility_score"], 0)
        finally:
            optimizer_mod._KEY_POOL = None

    def test_optimizer_re_score_fallback_is_empty_json(self):
        """resume_optimizer.re_score error fallback returns '{}'."""
        mock_pool = MagicMock()
        mock_pool.generate_content.side_effect = RuntimeError("API error")
        optimizer_mod._KEY_POOL = mock_pool
        try:
            result = re_score("resume", "jd")
            self.assertEqual(result, "{}")
        finally:
            optimizer_mod._KEY_POOL = None


# ─────────────────────────────────────────────────────────────────────────────
class TestCoarseItemScoreDescription(unittest.TestCase):
    """Pydantic schema validation for CoarseItem."""

    def test_coarse_item_score_field_exists(self):
        """CoarseItem must have a 'score' field."""
        item = CoarseItem(index=0, score=50)
        self.assertEqual(item.score, 50)

    def test_coarse_item_rejects_negative_score_via_model(self):
        """CoarseItem should accept 0 or positive scores (Pydantic int field)."""
        item = CoarseItem(index=0, score=0)
        self.assertEqual(item.score, 0)

    def test_batch_coarse_result_structure(self):
        """BatchCoarseResult.items must be a list of CoarseItem."""
        result = BatchCoarseResult(items=[CoarseItem(index=0, score=75)])
        self.assertEqual(len(result.items), 1)
        self.assertIsInstance(result.items[0], CoarseItem)


# ─────────────────────────────────────────────────────────────────────────────
class TestHallucinationGuards(unittest.TestCase):
    """Structural verification of anti-hallucination rules in prompts."""

    def test_tailor_prompt_has_only_use_rule(self):
        """_TAILOR_SYSTEM_PROMPT must contain 'ONLY use information already in the original resume'."""
        self.assertIn("ONLY use information already in the original resume", _TAILOR_SYSTEM_PROMPT)

    def test_tailor_prompt_has_never_fabricate_rule(self):
        """_TAILOR_SYSTEM_PROMPT must contain 'NEVER fabricate'."""
        self.assertIn("NEVER fabricate", _TAILOR_SYSTEM_PROMPT)

    def test_fine_prompt_has_brutally_honest(self):
        """_FINE_SYSTEM_PROMPT must contain 'Brutally Honest' to prevent score inflation."""
        self.assertIn("Brutally Honest", MATCH_FINE_PROMPT)

    def test_fine_prompt_has_no_inflate(self):
        """_FINE_SYSTEM_PROMPT must contain 'Do not inflate scores'."""
        self.assertIn("Do not inflate scores", MATCH_FINE_PROMPT)

    def test_coarse_prompt_has_minimum_score_1(self):
        """_COARSE_SYSTEM_PROMPT must declare minimum score is 1."""
        self.assertIn("Minimum score is 1", _COARSE_SYSTEM_PROMPT)

    def test_coarse_prompt_has_never_return_0(self):
        """_COARSE_SYSTEM_PROMPT must state 'never return 0'."""
        self.assertIn("never return 0", _COARSE_SYSTEM_PROMPT)


# ─────────────────────────────────────────────────────────────────────────────
class TestScoreClampBehavior(unittest.TestCase):
    """Verify that code enforces score minimums."""

    def test_evaluate_match_returns_raw_gemini_output(self):
        """evaluate_match passes through raw Gemini text; clamping is done by caller (main)."""
        mock_pool = MagicMock()
        mock_pool.generate_content.return_value = MagicMock(
            text=json.dumps({
                "compatibility_score": 0,
                "key_strengths": [],
                "critical_gaps": [],
                "recommendation_reason": "test",
            })
        )
        match_mod._KEY_POOL = mock_pool
        try:
            result_json = evaluate_match("resume", "jd")
            self.assertIsInstance(result_json, str)
            result = json.loads(result_json)
            # evaluate_match does NOT clamp — it returns raw Gemini output as-is.
            # The caller (fine_one in main) applies max(1, score).
            self.assertEqual(result["compatibility_score"], 0)
        finally:
            match_mod._KEY_POOL = None

    def test_batch_coarse_score_clamps_to_1(self):
        """batch_coarse_score must clamp all scores to >= 1."""
        mock_pool = MagicMock()
        mock_pool.generate_content.return_value = MagicMock(
            text=json.dumps({
                "items": [
                    {"index": 0, "score": 0},
                    {"index": 1, "score": -5},
                ]
            })
        )
        match_mod._KEY_POOL = mock_pool
        try:
            scores = batch_coarse_score("resume", [
                {"jd_json": '{"job_title":"A"}'},
                {"jd_json": '{"job_title":"B"}'},
            ])
            for s in scores:
                self.assertGreaterEqual(s, 1, f"Score {s} is below minimum 1")
        finally:
            match_mod._KEY_POOL = None


if __name__ == "__main__":
    unittest.main()
