"""P1-17: usage_metadata accumulation in shared.gemini_pool.

Locks the contract that every successful generate_content call updates the
module-level token counters, and that get_usage_summary / reset work as
intended. Mocks google.genai so the test runs offline.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

for mod in ["google", "google.genai", "google.genai.types", "dotenv"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
sys.modules["dotenv"].load_dotenv = lambda: None

from shared.gemini_pool import (
    _GeminiKeyPoolBase,
    get_usage_summary,
    reset_usage_summary,
)


def _make_genai(prompt=10, candidates=5, cached=2):
    """Build a fake genai module whose Client returns a successful response
    carrying usage_metadata."""
    um = MagicMock()
    um.prompt_token_count = prompt
    um.candidates_token_count = candidates
    um.cached_content_token_count = cached
    resp = MagicMock()
    resp.text = "{}"
    resp.usage_metadata = um
    client = MagicMock()
    client.models.generate_content.return_value = resp
    genai_mod = MagicMock()
    genai_mod.Client.return_value = client
    return genai_mod


class UsageMetadataTest(unittest.TestCase):
    def setUp(self):
        reset_usage_summary()

    def test_single_call_records_tokens(self):
        pool = _GeminiKeyPoolBase(["k1"], genai_mod=_make_genai(100, 50, 30))
        pool.generate_content("m", "c", None)
        self.assertEqual(get_usage_summary(), {
            "prompt_tokens": 100,
            "candidates_tokens": 50,
            "cached_content_tokens": 30,
            "total_calls": 1,
        })

    def test_multiple_calls_accumulate(self):
        pool = _GeminiKeyPoolBase(["k1"], genai_mod=_make_genai(20, 10, 0))
        for _ in range(3):
            pool.generate_content("m", "c", None)
        s = get_usage_summary()
        self.assertEqual(s["prompt_tokens"], 60)
        self.assertEqual(s["candidates_tokens"], 30)
        self.assertEqual(s["cached_content_tokens"], 0)
        self.assertEqual(s["total_calls"], 3)

    def test_reset_zeroes_counters(self):
        pool = _GeminiKeyPoolBase(["k1"], genai_mod=_make_genai())
        pool.generate_content("m", "c", None)
        reset_usage_summary()
        self.assertEqual(get_usage_summary(), {
            "prompt_tokens": 0,
            "candidates_tokens": 0,
            "cached_content_tokens": 0,
            "total_calls": 0,
        })

    def test_missing_usage_metadata_does_not_crash(self):
        # Some Gemini responses (e.g. error paths) may omit usage_metadata.
        # The recorder must no-op rather than raise.
        resp = MagicMock()
        resp.text = "{}"
        resp.usage_metadata = None
        client = MagicMock()
        client.models.generate_content.return_value = resp
        genai_mod = MagicMock()
        genai_mod.Client.return_value = client
        pool = _GeminiKeyPoolBase(["k1"], genai_mod=genai_mod)
        pool.generate_content("m", "c", None)  # must not raise
        self.assertEqual(get_usage_summary()["total_calls"], 0)


if __name__ == "__main__":
    unittest.main()
