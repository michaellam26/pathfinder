"""
Tests for shared/firecrawl_pool.py (BUG-68)

Coverage:
  - key filtering / empty-pool ValueError
  - rotation on 402 / insufficient-credits / 429
  - one loud warning when ALL keys are quota-exhausted, then instant None
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

from shared.firecrawl_pool import FirecrawlKeyPool, build_pool_from_env


def _pool_with_clients(keys, clients):
    """Build a pool whose per-key clients are pre-seeded mocks."""
    pool = FirecrawlKeyPool(keys)
    pool._clients = dict(zip(keys, clients))
    return pool


class TestFirecrawlKeyPool(unittest.TestCase):

    def test_empty_keys_raise(self):
        with self.assertRaises(ValueError):
            FirecrawlKeyPool([])
        with self.assertRaises(ValueError):
            FirecrawlKeyPool(["", None])

    def test_blank_keys_filtered(self):
        pool = FirecrawlKeyPool(["k1", "", None, "k2"])
        self.assertEqual(pool._keys, ["k1", "k2"])

    def test_rotates_to_second_key_on_402(self):
        c1 = MagicMock()
        c1.scrape.side_effect = Exception("402 Payment Required: insufficient credits")
        c2 = MagicMock()
        c2.scrape.return_value = {"markdown": "# ok"}
        pool = _pool_with_clients(["k1", "k2"], [c1, c2])
        result = pool.scrape("https://x.co", formats=["markdown"])
        self.assertEqual(result, {"markdown": "# ok"})
        self.assertFalse(pool.exhausted)
        # kwargs forwarded to the underlying client
        self.assertEqual(c2.scrape.call_args.kwargs["formats"], ["markdown"])

    def test_all_keys_exhausted_prints_one_warning_then_none(self):
        c1 = MagicMock(); c1.map.side_effect = Exception("402 insufficient credits")
        c2 = MagicMock(); c2.map.side_effect = Exception("Rate limit exceeded (429)")
        pool = _pool_with_clients(["k1", "k2"], [c1, c2])
        buf = io.StringIO()
        with redirect_stdout(buf):
            first  = pool.map(url="https://a.co")
            second = pool.map(url="https://b.co")
            third  = pool.scrape("https://c.co")
        self.assertIsNone(first)
        self.assertIsNone(second)
        self.assertIsNone(third)
        self.assertTrue(pool.exhausted)
        self.assertEqual(buf.getvalue().count("Firecrawl quota/credits exhausted"), 1)
        # after exhaustion no client is called again
        self.assertEqual(c1.map.call_count + c2.map.call_count, 2)

    def test_single_key_exhausts_immediately_on_402(self):
        c1 = MagicMock(); c1.scrape.side_effect = Exception("Payment Required")
        pool = _pool_with_clients(["k1"], [c1])
        with redirect_stdout(io.StringIO()):
            self.assertIsNone(pool.scrape("https://x.co"))
        self.assertTrue(pool.exhausted)

    def test_non_quota_error_reraises(self):
        c1 = MagicMock(); c1.scrape.side_effect = Exception("connection timed out")
        pool = _pool_with_clients(["k1", "k2"], [c1, MagicMock()])
        with self.assertRaises(Exception):
            pool.scrape("https://x.co")
        self.assertFalse(pool.exhausted)

    def test_client_cached_per_key(self):
        pool = FirecrawlKeyPool(["k1"])
        fake_app_cls = MagicMock()
        with patch.dict(sys.modules, {"firecrawl": MagicMock(FirecrawlApp=fake_app_cls)}):
            a = pool._get_client()
            b = pool._get_client()
        self.assertIs(a, b)
        fake_app_cls.assert_called_once_with(api_key="k1")


class TestBuildPoolFromEnv(unittest.TestCase):

    def test_both_keys_picked_up(self):
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "kA",
                                     "FIRECRAWL_API_KEY_2": "kB"}):
            pool = build_pool_from_env()
        self.assertEqual(pool._keys, ["kA", "kB"])

    def test_single_key(self):
        env = {"FIRECRAWL_API_KEY": "kA"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("FIRECRAWL_API_KEY_2", None)
            pool = build_pool_from_env()
        self.assertEqual(pool._keys, ["kA"])

    def test_no_keys_returns_none(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FIRECRAWL_API_KEY", None)
            os.environ.pop("FIRECRAWL_API_KEY_2", None)
            self.assertIsNone(build_pool_from_env())


if __name__ == "__main__":
    unittest.main(verbosity=2)
