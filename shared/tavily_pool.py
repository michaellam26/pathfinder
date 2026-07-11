"""Shared Tavily API key pool with rotation on quota/usage-limit exhaustion.

BUG-70: Tavily's real plan-limit error text is "This request exceeds your
plan's set usage limit" — it contains none of "402"/"429"/"quota", so every
call-site quota-abort check (the BUG-44 pattern in ``discover_ai_companies``,
``_tavily_extract_career_url``, ``_find_workday_url``,
``run_reenrich_business_focus``) missed it and the 2026-07-09 run kept
spinning through doomed Tavily calls.

This pool mirrors ``shared.firecrawl_pool.FirecrawlKeyPool``: multiple keys
(``TAVILY_API_KEY`` + ``TAVILY_API_KEY_2``), round-robin rotation when a key
hits a quota/usage-limit error, one loud console warning once EVERY key has
quota-failed. Divergence from the Firecrawl pool: Tavily callers have no free
fallback — they rely on *catching quota exceptions* to abort their loops. So
an exhausted pool raises ``TavilyQuotaExhausted`` (message contains "429" and
"quota", keeping every existing call-site substring check working) instantly
on every call, instead of returning None.

The pool is duck-type compatible with ``tavily.TavilyClient`` (exposes
``search``), so it drops into every call site that receives a
``tavily_client``. Non-quota errors re-raise so each call site keeps its own
retry/fallback semantics.
"""
import logging
import os
import threading

# Case-insensitive substrings marking a quota/usage-limit error. Superset of
# the Firecrawl pool list plus Tavily's observed plan-limit message.
_QUOTA_PATTERNS = ("402", "429", "quota", "rate limit", "payment required",
                   "usage limit", "exceeds your plan")


def _is_quota_error(err_text: str) -> bool:
    low = err_text.lower()
    return any(p in low for p in _QUOTA_PATTERNS)


class TavilyQuotaExhausted(Exception):
    """Raised once every key in the pool has hit a quota/usage-limit error.

    The message deliberately contains "429" and "quota" so existing
    call-site checks ('"402" in err or "429" in err or "quota" in
    err.lower()') recognize it without modification.
    """


class TavilyKeyPool:
    """Holds multiple Tavily API keys and rotates on quota/usage-limit errors."""

    def __init__(self, keys: list[str]):
        self._keys = [k for k in keys if k]
        if not self._keys:
            raise ValueError("[TavilyPool] No valid Tavily API keys provided.")
        self._idx = 0
        self._clients: dict[str, object] = {}  # client cache per key (BUG-34 pattern)
        self._lock = threading.Lock()          # thread-safe rotation (BUG-36 pattern)
        self._quota_failed: set[str] = set()
        self._exhausted = False

    @property
    def exhausted(self) -> bool:
        """True once every key has hit a quota/usage-limit error this run."""
        return self._exhausted

    @property
    def current(self) -> str:
        return self._keys[self._idx]

    def rotate(self) -> bool:
        """Round-robin to the next key. Returns False if the pool has one key."""
        if len(self._keys) <= 1:
            return False
        self._idx = (self._idx + 1) % len(self._keys)
        logging.warning(f"[TavilyPool] Switched to API key #{self._idx + 1}")
        return True

    def _get_client(self):
        from tavily import TavilyClient
        key = self.current
        if key not in self._clients:
            self._clients[key] = TavilyClient(api_key=key)
        return self._clients[key]

    def _mark_exhausted(self) -> None:
        if not self._exhausted:
            self._exhausted = True
            print(f"⚠️  Tavily quota/usage limit exhausted on all "
                  f"{len(self._keys)} key(s) — Tavily-dependent steps abort "
                  f"for the rest of this run and retry next run.")
            logging.error("[TavilyPool] All Tavily API keys quota-exhausted.")

    def _raise_exhausted(self):
        raise TavilyQuotaExhausted(
            f"429 Tavily quota exhausted on all {len(self._keys)} API key(s)")

    def _call(self, method: str, *args, **kwargs):
        while True:
            with self._lock:
                if self._exhausted:
                    self._raise_exhausted()
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
                        f"[TavilyPool] Key #{self._keys.index(cur) + 1} "
                        f"quota/usage-limit error: {err}")
                    if len(self._quota_failed) >= len(self._keys) or not self.rotate():
                        self._mark_exhausted()
                        self._raise_exhausted()
                # A fresh key is active — retry the call on it.

    def search(self, *args, **kwargs):
        """TavilyClient.search via the pool. Raises TavilyQuotaExhausted once
        every key has quota-failed."""
        return self._call("search", *args, **kwargs)


def build_pool_from_env() -> "TavilyKeyPool | None":
    """Build a pool from TAVILY_API_KEY (+ TAVILY_API_KEY_2).
    Returns None when no key is set — callers treat that as Tavily-off."""
    keys = [k for k in (os.getenv("TAVILY_API_KEY"),
                        os.getenv("TAVILY_API_KEY_2")) if k]
    if not keys:
        return None
    logging.info(f"[TavilyPool] Loaded {len(keys)} Tavily API key(s).")
    return TavilyKeyPool(keys)
