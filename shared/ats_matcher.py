"""Deterministic ATS keyword coverage matcher (no LLM).

Used by match_agent and resume_optimizer to compute the "ATS dimension"
of the 3-dimension scoring system: how many of the JD's ats_keywords
appear in the resume after lightweight normalization.

Normalization pipeline (applied identically to keyword and resume):
  1. Tokenize via _TOKEN_RE (handles C++, C#, K8s, GPT-4, Node.js, etc.)
  2. Lowercase
  3. Lightweight plural stem (-ies → y; -ches/-shes/-xes/-ses → strip -es;
     terminal -s → drop, except -ss)
  4. Re-join tokens with single spaces

Matching is space-padded substring (effectively token-boundary):
  f" {norm_keyword} " in f" {norm_resume} "

Synonyms come from shared.ats_synonyms.SYNONYM_GROUPS (hand-curated).
"""
import re
from typing import Iterable

from shared.ats_synonyms import SYNONYM_GROUPS


# Token grammar:
#   alnum-run, optionally extended one-or-more times by [.+/#-]+ followed
#   by an alnum-run, optionally with trailing + or # (so C++ and C# match).
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[.+/#-]+[A-Za-z0-9+#]+)*[+#]*")


def _stem(token: str) -> str:
    """Lightweight plural-only stem. Caller must lowercase first.

    Rules:
      * Tokens with embedded . + / # - are proper nouns / versions / paths
        (Node.js, GPT-4, C++, etc.) — never stemmed.
      * len <= 3 → never stemmed (avoids 'ai' / 'ml' / 'api' damage).
      * Terminal non-alpha → never stemmed.
      * -ies → y (libraries → library)
      * -sses / -xes / -ches / -shes → strip -es (classes → class, boxes → box)
      * -s (but not -ss) → strip s (models → model, databases → database)
    """
    if len(token) <= 3:
        return token
    if any(c in token for c in ".+/#-"):
        return token
    if not token[-1].isalpha():
        return token
    if token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith("sses") or token.endswith(("xes", "ches", "shes")):
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def normalize(text: str) -> str:
    """Lowercase + tokenize + stem; tokens rejoined with single spaces.

    Empty / whitespace-only / None input → "".
    """
    if not text:
        return ""
    return " ".join(_stem(m.group(0).lower()) for m in _TOKEN_RE.finditer(text))


# Pre-normalize the synonym groups once at import time.
_NORMALIZED_GROUPS: list[set[str]] = [
    {n for n in (normalize(term) for term in group) if n}
    for group in SYNONYM_GROUPS
]


def expand_synonyms(keyword: str) -> set[str]:
    """Return the set of normalized variants for `keyword`.

    The result always includes the normalized form of the input. Returns
    an empty set if the input normalizes to "" (e.g. blank, punctuation-only).
    """
    norm = normalize(keyword)
    if not norm:
        return set()
    result = {norm}
    for group in _NORMALIZED_GROUPS:
        if norm in group:
            result |= group
    return result


def _padded_contains(needle_norm: str, haystack_padded: str) -> bool:
    """Token-boundary substring check. haystack_padded is ' '+norm_resume+' '."""
    if not needle_norm:
        return False
    return f" {needle_norm} " in haystack_padded


def compute_coverage(
    ats_keywords: Iterable[str] | None,
    resume_text: str,
) -> dict:
    """Compute ATS keyword coverage of `ats_keywords` against `resume_text`.

    Returns a dict:
      {
        "percent":        float | None,  # None when no usable keywords
        "matched":        list[str],     # original keywords found (preserved casing)
        "missing":        list[str],     # original keywords not found
        "keyword_count":  int,           # # of keywords scored (post de-dup)
      }

    Behavior notes:
      * None / empty / blank-only ats_keywords → percent=None.
      * De-duplication is on the normalized form: "Kubernetes" and
        "kubernetes" collapse to one entry; first occurrence wins for
        the matched/missing display.
      * Synonyms expand outward — if any synonym matches, the keyword
        is counted as matched (under its original wording).
    """
    if ats_keywords is None:
        return {"percent": None, "matched": [], "missing": [], "keyword_count": 0}

    norm_resume = normalize(resume_text or "")
    padded = f" {norm_resume} "

    matched: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    for kw in ats_keywords:
        if not kw or not str(kw).strip():
            continue
        original = str(kw).strip()
        norm_kw = normalize(original)
        if not norm_kw or norm_kw in seen:
            continue
        seen.add(norm_kw)

        candidates = expand_synonyms(original)
        hit = any(_padded_contains(c, padded) for c in candidates)
        if hit:
            matched.append(original)
        else:
            missing.append(original)

    total = len(matched) + len(missing)
    if total == 0:
        return {"percent": None, "matched": [], "missing": [], "keyword_count": 0}

    return {
        "percent": round(len(matched) / total * 100, 1),
        "matched": matched,
        "missing": missing,
        "keyword_count": total,
    }
