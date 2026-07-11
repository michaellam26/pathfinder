"""
Tests for shared/tavily_pool.py (BUG-70)

Coverage:
  - key filtering / empty-pool ValueError
  - rotation on 402 / 429 / the real Tavily "usage limit" plan-limit text
  - one loud warning when ALL keys are quota-exhausted, then instant
    TavilyQuotaExhausted (message matches the existing BUG-44 call-site
    substring checks: contains "429" and "quota")
  - non-quota errors re-raise (callers keep their retry/fallback semantics)
  - client caching per key
  - build_pool_from_env key pickup
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from shared.tavily_pool import (
    TavilyKeyPool, TavilyQuotaExhausted, build_pool_from_env,
)

# The exact plan-limit message observed in logs/pipeline-20260709-040151.log —
# contains none of "402"/"429"/"quota", which is why call-site checks missed it.
_USAGE_LIMIT_MSG = ("This request exceeds your plan's set usage limit. "
                    "Please upgrade your plan or contact support@tavily.com")


def _pool_with_clients(keys, clients):
    """Build a pool whose per-key clients are pre-seeded mocks."""
    pool = TavilyKeyPool(keys)
    pool._clients = dict(zip(keys, clients))
    return pool


class TestTavilyKeyPool(unittest.TestCase):

    def test_empty_keys_raise(self):
        with self.assertRaises(ValueError):
            TavilyKeyPool([])
        with self.assertRaises(ValueError):
            TavilyKeyPool(["", None])

    def test_blank_keys_filtered(self):
        pool = TavilyKeyPool(["k1", "", None, "k2"])
        self.assertEqual(pool._keys, ["k1", "k2"])

    def test_rotates_to_second_key_on_402(self):
        c1 = MagicMock()
        c1.search.side_effect = Exception("402 Payment Required")
        c2 = MagicMock()
        c2.search.return_value = {"results": [{"url": "https://x.co"}]}
        pool = _pool_with_clients(["k1", "k2"], [c1, c2])
        result = pool.search(query="q", max_results=5)
        self.assertEqual(result, {"results": [{"url": "https://x.co"}]})
        self.assertFalse(pool.exhausted)
        # kwargs forwarded to the underlying client
        self.assertEqual(c2.search.call_args.kwargs["max_results"], 5)

    def test_rotates_on_real_usage_limit_text(self):
        """BUG-70: the observed plan-limit message must count as a quota error."""
        c1 = MagicMock()
        c1.search.side_effect = Exception(_USAGE_LIMIT_MSG)
        c2 = MagicMock()
        c2.search.return_value = {"results": []}
        pool = _pool_with_clients(["k1", "k2"], [c1, c2])
        result = pool.search(query="q")
        self.assertEqual(result, {"results": []})
        self.assertFalse(pool.exhausted)

    def test_all_keys_exhausted_prints_one_warning_then_raises(self):
        c1 = MagicMock(); c1.search.side_effect = Exception(_USAGE_LIMIT_MSG)
        c2 = MagicMock(); c2.search.side_effect = Exception("Rate limit exceeded (429)")
        pool = _pool_with_clients(["k1", "k2"], [c1, c2])
        buf = io.StringIO()
        with redirect_stdout(buf):
            with self.assertRaises(TavilyQuotaExhausted):
                pool.search(query="a")
            with self.assertRaises(TavilyQuotaExhausted):
                pool.search(query="b")
        self.assertTrue(pool.exhausted)
        self.assertEqual(buf.getvalue().count("Tavily quota/usage limit exhausted"), 1)
        # after exhaustion no client is called again
        self.assertEqual(c1.search.call_count + c2.search.call_count, 2)

    def test_exhausted_message_matches_call_site_checks(self):
        """The normalized error must satisfy the existing BUG-44 pattern:
        '402' in err or '429' in err or 'quota' in err.lower()."""
        c1 = MagicMock(); c1.search.side_effect = Exception(_USAGE_LIMIT_MSG)
        pool = _pool_with_clients(["k1"], [c1])
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(TavilyQuotaExhausted) as ctx:
                pool.search(query="q")
        err = str(ctx.exception)
        self.assertTrue("402" in err or "429" in err or "quota" in err.lower())

    def test_single_key_exhausts_immediately(self):
        c1 = MagicMock(); c1.search.side_effect = Exception("429 Too Many Requests")
        pool = _pool_with_clients(["k1"], [c1])
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(TavilyQuotaExhausted):
                pool.search(query="q")
        self.assertTrue(pool.exhausted)

    def test_non_quota_error_reraises(self):
        c1 = MagicMock(); c1.search.side_effect = Exception("connection timed out")
        pool = _pool_with_clients(["k1", "k2"], [c1, MagicMock()])
        with self.assertRaises(Exception) as ctx:
            pool.search(query="q")
        self.assertNotIsInstance(ctx.exception, TavilyQuotaExhausted)
        self.assertFalse(pool.exhausted)

    def test_client_cached_per_key(self):
        pool = TavilyKeyPool(["k1"])
        fake_client_cls = MagicMock()
        with patch.dict(sys.modules, {"tavily": MagicMock(TavilyClient=fake_client_cls)}):
            a = pool._get_client()
            b = pool._get_client()
        self.assertIs(a, b)
        fake_client_cls.assert_called_once_with(api_key="k1")


class TestBuildPoolFromEnv(unittest.TestCase):

    def test_both_keys_picked_up(self):
        with patch.dict(os.environ, {"TAVILY_API_KEY": "kA",
                                     "TAVILY_API_KEY_2": "kB"}):
            pool = build_pool_from_env()
        self.assertEqual(pool._keys, ["kA", "kB"])

    def test_single_key(self):
        env = {"TAVILY_API_KEY": "kA"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("TAVILY_API_KEY_2", None)
            pool = build_pool_from_env()
        self.assertEqual(pool._keys, ["kA"])

    def test_no_keys_returns_none(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TAVILY_API_KEY", None)
            os.environ.pop("TAVILY_API_KEY_2", None)
            self.assertIsNone(build_pool_from_env())


if __name__ == "__main__":
    unittest.main(verbosity=2)
