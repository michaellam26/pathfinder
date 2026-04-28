"""
P0-1: Gemini Context Caching helpers in shared.gemini_pool.

The new google-genai SDK exposes client.caches.create / delete and a
config.cached_content field. This file tests the wrapper helpers, with
emphasis on graceful fallback when the API or model does not support
caching (preview models often don't).
"""
import sys
import os
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ── Stub heavy deps before import ────────────────────────────────────────────
for mod in ["google", "google.genai", "google.genai.types", "dotenv"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

sys.modules["dotenv"].load_dotenv = lambda: None

import google
google.genai = MagicMock()
google.genai.types = MagicMock()

from shared.gemini_pool import _GeminiKeyPoolBase


def _build_pool_with_caches_api(create_returns=None, delete_raises=None):
    cache_obj = MagicMock()
    cache_obj.name = "cachedContents/abc123" if create_returns is None else create_returns
    client = MagicMock()
    client.caches.create.return_value = cache_obj
    if delete_raises:
        client.caches.delete.side_effect = delete_raises
    genai_mod = MagicMock()
    genai_mod.Client.return_value = client
    # Provide a real-ish CreateCachedContentConfig stub
    genai_mod.types = MagicMock()
    genai_mod.types.CreateCachedContentConfig = MagicMock(return_value=MagicMock())
    pool = _GeminiKeyPoolBase(["k0"], genai_mod=genai_mod)
    return pool, client


class TestCreateCache(unittest.TestCase):

    def test_create_cache_returns_name_on_success(self):
        pool, client = _build_pool_with_caches_api()
        name = pool.create_cache(model="m", system_instruction="sys",
                                 contents=[MagicMock()])
        self.assertEqual(name, "cachedContents/abc123")
        client.caches.create.assert_called_once()

    def test_create_cache_returns_none_when_caches_api_missing(self):
        client = MagicMock()
        # No .caches attribute that supports .create
        client.caches.create.side_effect = AttributeError("no caches")
        genai_mod = MagicMock()
        genai_mod.Client.return_value = client
        genai_mod.types = MagicMock()
        genai_mod.types.CreateCachedContentConfig = MagicMock()
        pool = _GeminiKeyPoolBase(["k0"], genai_mod=genai_mod)
        name = pool.create_cache(model="m", system_instruction="sys",
                                 contents=[MagicMock()])
        self.assertIsNone(name)

    def test_create_cache_returns_none_on_unsupported_model(self):
        client = MagicMock()
        client.caches.create.side_effect = Exception(
            "Model gemini-3.1-flash-lite-preview does not support caching")
        genai_mod = MagicMock()
        genai_mod.Client.return_value = client
        genai_mod.types = MagicMock()
        genai_mod.types.CreateCachedContentConfig = MagicMock()
        pool = _GeminiKeyPoolBase(["k0"], genai_mod=genai_mod)
        name = pool.create_cache(model="m", system_instruction="sys",
                                 contents=[MagicMock()])
        self.assertIsNone(name)

    def test_create_cache_passes_system_instruction_and_ttl(self):
        pool, client = _build_pool_with_caches_api()
        pool.create_cache(model="m", system_instruction="MY_SYS",
                          contents=[MagicMock()], ttl="3600s",
                          display_name="match-test")
        # The SDK was called with model and a config object.
        call = client.caches.create.call_args
        self.assertEqual(call.kwargs.get("model"), "m")
        self.assertIsNotNone(call.kwargs.get("config"))


class TestDeleteCache(unittest.TestCase):

    def test_delete_cache_calls_sdk(self):
        pool, client = _build_pool_with_caches_api()
        pool.delete_cache("cachedContents/abc123")
        client.caches.delete.assert_called_once_with(name="cachedContents/abc123")

    def test_delete_cache_swallows_errors(self):
        pool, client = _build_pool_with_caches_api(
            delete_raises=Exception("API down"))
        # Must not raise — best-effort teardown.
        pool.delete_cache("cachedContents/abc")

    def test_delete_cache_no_op_for_empty_name(self):
        pool, client = _build_pool_with_caches_api()
        pool.delete_cache("")
        pool.delete_cache(None)
        client.caches.delete.assert_not_called()


class TestEvaluateMatchUsesCachedContent(unittest.TestCase):
    """When _FINE_CACHE_NAME is set, evaluate_match must use cached_content
    in the config and NOT include the resume in contents."""

    def setUp(self):
        import agents.match_agent as match_mod
        self.match_mod = match_mod
        self.pool = MagicMock()
        response = MagicMock()
        response.text = '{"compatibility_score": 80, "key_strengths": [], "critical_gaps": [], "recommendation_reason": ""}'
        self.pool.generate_content.return_value = response
        match_mod._KEY_POOL = self.pool

    def tearDown(self):
        self.match_mod._KEY_POOL = None
        self.match_mod._FINE_CACHE_NAME = None

    def test_no_cache_includes_resume_in_contents(self):
        self.match_mod._FINE_CACHE_NAME = None
        self.match_mod.evaluate_match("RESUME_BODY", '{"job_title":"X"}')
        kwargs = self.pool.generate_content.call_args.kwargs
        self.assertIn("RESUME_BODY", kwargs["contents"])

    def test_with_cache_omits_resume_from_contents(self):
        self.match_mod._FINE_CACHE_NAME = "cachedContents/abc"
        self.match_mod.evaluate_match("RESUME_BODY", '{"job_title":"X"}')
        kwargs = self.pool.generate_content.call_args.kwargs
        self.assertNotIn("RESUME_BODY", kwargs["contents"],
                         "When using cached_content, resume must not be sent again")
        self.assertIn('{"job_title":"X"}', kwargs["contents"])


if __name__ == "__main__":
    unittest.main()
