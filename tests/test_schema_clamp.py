"""P1-16: schema-level clamp on compatibility_score / coarse score.

Locks the contract that out-of-range Gemini output is normalized to [0, 100]
at the Pydantic layer, so callers can rely on it instead of each adding
their own max(...)/min(...) wrappers.
"""
import json
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from shared.schemas import CoarseItem, MatchResult


class CoarseItemClampTest(unittest.TestCase):
    def test_above_100_clamped(self):
        item = CoarseItem(index=0, score=150)
        self.assertEqual(item.score, 100)

    def test_below_0_clamped(self):
        item = CoarseItem(index=0, score=-7)
        self.assertEqual(item.score, 0)

    def test_in_range_passthrough(self):
        item = CoarseItem(index=0, score=42)
        self.assertEqual(item.score, 42)

    def test_boundary_values(self):
        self.assertEqual(CoarseItem(index=0, score=0).score, 0)
        self.assertEqual(CoarseItem(index=0, score=100).score, 100)


class MatchResultClampTest(unittest.TestCase):
    @staticmethod
    def _build(score):
        return MatchResult(
            compatibility_score=score,
            key_strengths=["x"],
            critical_gaps=["y"],
            recommendation_reason="r",
        )

    def test_above_100_clamped(self):
        self.assertEqual(self._build(200).compatibility_score, 100)

    def test_below_0_clamped(self):
        self.assertEqual(self._build(-50).compatibility_score, 0)

    def test_json_roundtrip_clamps(self):
        # Mirrors the Gemini path: response.text → model_validate_json.
        m = MatchResult.model_validate_json(json.dumps({
            "compatibility_score": 105,
            "key_strengths": ["a"],
            "critical_gaps": ["b"],
            "recommendation_reason": "r",
        }))
        self.assertEqual(m.compatibility_score, 100)


if __name__ == "__main__":
    unittest.main()
