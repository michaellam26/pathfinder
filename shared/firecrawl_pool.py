"""Shared Firecrawl API key pool with rotation on quota/credit exhaustion.

BUG-68: Firecrawl 402 (credits exhausted) errors were caught by broad
``except Exception`` blocks and logged at debug level only — the run silently
degraded to fallback scrapers with no operator-visible signal, and
``_firecrawl_map`` burned retry delays on an error that can never succeed.

This pool mirrors ``shared.gemini_pool._GeminiKeyPoolBase``: multiple keys
(``FIRECRAWL_API_KEY`` + ``FIRECRAWL_API_KEY_2``), round-robin rotation when a
key hits a quota/credit error, and — once EVERY key has quota-failed — one
loud console warning (the Tavily BUG-44 pattern), after which all calls
return ``None`` instantly so callers skip straight to their free fallbacks
(crawl4ai / plain requests) without retry delays.

Non-quota errors re-raise so each call site keeps its own retry/fallback
semantics.
"""
import logging
import os
import threading

# Case-insensitive substrings marking a quota/credit error. 402 = credits
# exhausted (permanent for the run); 429 = rate limit — treated the same
# because map calls are already paced at 1 rpm, so a sustained 429 across all
# keys means the key(s) are effectively unusable this run.
_QUOTA_PATTERNS = ("402", "insufficient credits", "payment required",
                   "429", "rate limit")


def _is_quota_error(err_text: str) -> bool:
    low = err_text.lower()
    return any(p in low for p in _QUOTA_PATTERNS)


class FirecrawlKeyPool:
    """Holds multiple Firecrawl API keys and rotates on quota/credit errors."""

    def __init__(self, keys: list[str]):
        self._keys = [k for k in keys if k]
        if not self._keys:
            raise ValueError("[FirecrawlPool] No valid Firecrawl API keys provided.")
        self._idx = 0
        self._clients: dict[str, object] = {}  # client cache per key (BUG-34 pattern)
        self._lock = threading.Lock()          # thread-safe rotation (BUG-36 pattern)
        self._quota_failed: set[str] = set()
        self._exhausted = False

    @property
    def exhausted(self) -> bool:
        """True once every key has hit a quota/credit error this run."""
        return self._exhausted

    @property
    def current(self) -> str:
        return self._keys[self._idx]

    def rotate(self) -> bool:
        """Round-robin to the next key. Returns False if the pool has one key."""
        if len(self._keys) <= 1:
            return False
        self._idx = (self._idx + 1) % len(self._keys)
        logging.warning(f"[FirecrawlPool] Switched to API key #{self._idx + 1}")
        return True

    def _get_client(self):
        from firecrawl import FirecrawlApp
        key = self.current
        if key not in self._clients:
            self._clients[key] = FirecrawlApp(api_key=key)
        return self._clients[key]

    def _mark_exhausted(self) -> None:
        if not self._exhausted:
            self._exhausted = True
            print(f"⚠️  Firecrawl quota/credits exhausted on all {len(self._keys)} "
                  f"key(s) — skipping Firecrawl for the rest of this run "
                  f"(free fallback scrapers take over).")
            logging.error("[FirecrawlPool] All Firecrawl API keys quota-exhausted.")

    def _call(self, method: str, *args, **kwargs):
        while True:
            with self._lock:
                if self._exhausted:
                    return None
                client = self._get_client()
                cur = self.current
            try:
                return getattr(client, method)(*args, **kwargs)
            except Exception as e:
                err = str(e)
                if not _is_quota_error(err):
                    raise
                with self._lock:
                    self._quota_failed.add(cur)
                    logging.warning(
                        f"[FirecrawlPool] Key #{self._keys.index(cur) + 1} "
                        f"quota/credit error: {err}")
                    if len(self._quota_failed) >= len(self._keys) or not self.rotate():
                        self._mark_exhausted()
                        return None
                # A fresh key is active — retry the call on it.

    def scrape(self, *args, **kwargs):
        """FirecrawlApp.scrape via the pool. None when quota-exhausted."""
        return self._call("scrape", *args, **kwargs)

    def map(self, *args, **kwargs):
        """FirecrawlApp.map via the pool. None when quota-exhausted."""
        return self._call("map", *args, **kwargs)


def build_pool_from_env() -> "FirecrawlKeyPool | None":
    """Build a pool from FIRECRAWL_API_KEY (+ FIRECRAWL_API_KEY_2).
    Returns None when no key is set — callers treat that as Firecrawl-off."""
    keys = [k for k in (os.getenv("FIRECRAWL_API_KEY"),
                        os.getenv("FIRECRAWL_API_KEY_2")) if k]
    if not keys:
        return None
    logging.info(f"[FirecrawlPool] Loaded {len(keys)} Firecrawl API key(s).")
    return FirecrawlKeyPool(keys)
