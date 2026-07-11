"""One-off subset run for the self-audit P0/P1 validation.

Runs `process_company` for Microsoft + Hugging Face + Intel only, so we can
measure the impact of the round-1/round-2 fixes without burning the full
146-company quota. Mirrors the bootstrapping that `job_agent.main` does
(env loading, Gemini key pool, browser context) but skips the rest of the
companies.

Run from project root:
    source venv/bin/activate
    python scripts/audit_subset_run.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from google import genai

import agents.job_agent as ja
from shared.excel_store import (
    EXCEL_PATH, get_or_create_excel, get_company_rows, get_jd_url_meta,
    get_triaged_jd_urls,
)
from shared.firecrawl_pool import build_pool_from_env
from shared.gemini_pool import _GeminiKeyPoolBase

TARGETS = {"zebra technologies", "oracle", "microsoft"}


async def _run() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - [%(levelname)s] - %(message)s")

    gemini_keys = [k for k in [os.getenv("GEMINI_API_KEY"),
                               os.getenv("GEMINI_API_KEY_2")] if k]
    fc_pool = build_pool_from_env()
    if not gemini_keys or fc_pool is None:
        sys.exit("Missing GEMINI_API_KEY or FIRECRAWL_API_KEY")

    ja._KEY_POOL = _GeminiKeyPoolBase(gemini_keys, genai_mod=genai)
    ja._FC_POOL = fc_pool

    xlsx_path = get_or_create_excel()
    all_companies = get_company_rows(xlsx_path)
    rows = [r for r in all_companies if str(r[0]).strip().lower() in TARGETS]
    print(f"Subset: {[r[0] for r in rows]}")
    if len(rows) != len(TARGETS):
        missing = TARGETS - {str(r[0]).strip().lower() for r in rows}
        print(f"  ⚠️  Missing from company list: {missing}")

    known_url_meta = get_jd_url_meta(xlsx_path)
    triaged_set = get_triaged_jd_urls(xlsx_path)
    lock = asyncio.Lock()

    from crawl4ai import AsyncWebCrawler, BrowserConfig
    print("🌐 Initializing browser…")
    async with AsyncWebCrawler(config=BrowserConfig(headless=True)) as crawler:
        for r in rows:
            try:
                await ja.process_company(r, known_url_meta, xlsx_path,
                                         lock, crawler,
                                         triaged_set=triaged_set)
            except Exception as exc:
                logging.exception(f"[subset-run] {r[0]}: {exc}")

    print("\n✅ Subset run done.")


if __name__ == "__main__":
    asyncio.run(_run())
