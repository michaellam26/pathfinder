"""
Company Agent — runs the least frequently (one-time or as needed).

Responsibilities:
  1. Read existing companies from Excel (avoid duplicates)
  2. Discover up to 50 NEW North American AI companies via Tavily + Gemini
     (capped at 200 total companies in the sheet)
  3. Find real career URLs via multi-strategy lookup (NO Gemini URL guessing)
  4. Phase 1.5: Validate & upgrade career URLs to ATS board URLs

URL discovery strategy (per company, in order):
  1. KNOWN_CAREER_URLS exact match
  2. Tavily targeted search → ATS/career URL extracted from results
  3. ATS slug probing (Greenhouse → Lever)
  4. Company homepage scraping → find careers link

Search distribution (rebalanced 2026-05 toward AI-TPM yield):
  - Big Tech (AI Investment)  : 25%
  - Consumer ML Tech          : 20%
  - AI Startups               : 25%
  - AI Infra / Compute / GPU  : 20%
  - Large Model Labs          : 10%

Run:
  python agents/company_agent.py
"""
import os
import sys
import json
import re
import logging
import time
from typing import Literal
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ── Project root on path so shared.* is importable ───────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.excel_store import (
    EXCEL_PATH, get_or_create_excel, count_company_rows,
    get_company_rows, get_company_rows_with_row_num, upsert_companies,
    update_company_career_url, update_company_track,
    get_company_names_without_tpm,
)
from shared.gemini_pool import _GeminiKeyPoolBase
from shared.config import MODEL
from shared.prompts import SECURITY_CLAUSE
from shared.run_summary import RunSummary

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')

# BUG-31: use _GeminiKeyPoolBase directly with genai_mod parameter
_GeminiKeyPool = _GeminiKeyPoolBase  # alias for backward compat (tests)

# PRJ-004 REQ-004-01: 6-track taxonomy at 500-company scale with per-bucket
# quotas. Quotas constrain NEW discovery only — migrated survivors over quota
# are grandfathered (D-12); a full bucket simply gets 0 new-discovery slots.
MAX_TOTAL  = 500   # sum of TRACK_QUOTAS
BATCH_SIZE = 50    # new companies to discover each run

TRACK_VALUES = ("AI-native", "Mid-large Tech", "Robotics", "Fintech", "Space", "Defense")
TRACK_QUOTAS = {"AI-native": 150, "Mid-large Tech": 150, "Robotics": 50,
                "Fintech": 50, "Space": 50, "Defense": 50}
VERTICAL_TRACKS = frozenset({"AI-native", "Robotics", "Fintech", "Space", "Defense"})

# REQ-004-03: defense legacy primes are hard-excluded deterministically —
# the exclusion must not depend on LLM compliance. Palantir is the explicit
# allowlist exception to the early-company rule.
DEFENSE_EXCLUDED_PRIMES = frozenset({
    "boeing", "lockheed martin", "lockheed", "raytheon", "rtx",
    "northrop grumman", "northrop", "general dynamics", "bae", "bae systems",
    "l3harris", "l3 harris",
})
DEFENSE_ALLOWLIST = frozenset({"palantir", "palantir technologies"})

_KEY_POOL: "_GeminiKeyPool | None" = None  # initialised in main()

# ── Pydantic schemas ──────────────────────────────────────────────────────────
class CompanyInfo(BaseModel):
    """Company info extracted by Gemini — NO career URL (found separately)."""
    company_name:   str = Field(description="The official name of the company.")
    track:          Literal[
        "AI-native",
        "Mid-large Tech",
        "Robotics",
        "Fintech",
        "Space",
        "Defense",
    ] = Field(
        description=(
            "The track bucket this company belongs to. "
            "Must be exactly one of the 6 listed values."
        )
    )
    business_focus: str = Field(
        description=(
            "3-4 sentence description covering: (1) what the company builds or sells, "
            "(2) who their primary customers are, (3) their key differentiator or "
            "competitive edge, and (4) notable products, funding, or market traction."
        )
    )

# Deprecated alias (pre-PRJ-004 name) — kept so external references fail soft.
AICompanyInfo = CompanyInfo

class CompanyInfoList(BaseModel):
    companies: list[CompanyInfo] = Field(description="A list of discovered companies.")


class TrackClassification(BaseModel):
    """One row of the REQ-004-06 --migrate-tracks re-bucketing pass."""
    company_name: str = Field(description="Company name exactly as given in the input list.")
    track:        Literal[
        "AI-native", "Mid-large Tech", "Robotics", "Fintech", "Space", "Defense",
    ] = Field(description="The best-fit track bucket for this company.")
    rationale:    str = Field(description="One sentence explaining the classification.")
    confident:    bool = Field(description="False if the classification is a guess.")


class TrackClassificationList(BaseModel):
    classifications: list[TrackClassification]

# ── ATS slug-validation config (Greenhouse + Lever only — public APIs) ────────
ATS_VALIDATORS = [
    {
        "platform":      "greenhouse",
        "api_template":  "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        "board_template":"https://job-boards.greenhouse.io/{slug}",
        "jobs_key":      "jobs",
    },
    {
        "platform":      "lever",
        "api_template":  "https://api.lever.co/v0/postings/{slug}?mode=json",
        "board_template":"https://jobs.lever.co/{slug}",
        "jobs_key":      None,
    },
    {
        "platform":      "ashby",
        "api_template":  "https://api.ashbyhq.com/posting-api/job-board/{slug}",
        "board_template":"https://jobs.ashbyhq.com/{slug}",
        "jobs_key":      "jobs",
    },
    {
        "platform":      "workable",
        "api_template":  "https://apply.workable.com/api/v1/widget/accounts/{slug}",
        "board_template":"https://apply.workable.com/{slug}/",
        "jobs_key":      "jobs",
    },
]

# Hard-coded overrides for companies with non-standard ATS URLs (e.g. Workday)
KNOWN_ATS_OVERRIDES = {
    "nvidia":          "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
    "tesla":           "https://www.tesla.com/careers",
    "google deepmind": "https://www.deepmind.com/careers",
    "deepmind":        "https://www.deepmind.com/careers",
    "xai":             "https://xai.com/careers",
}

KNOWN_CAREER_URLS = {
    "Google":          "https://www.google.com/about/careers/applications/",
    "Google DeepMind": "https://www.deepmind.com/careers",
    "Meta":            "https://www.metacareers.com/",
    "Microsoft":       "https://careers.microsoft.com/",
    "Amazon":          "https://www.amazon.jobs/",
    "Apple":           "https://jobs.apple.com/",
    "Tesla":           "https://www.tesla.com/careers",
    "xAI":             "https://xai.com/careers",
    "NVIDIA":          "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
    "Salesforce":      "https://careers.salesforce.com/",
    "IBM":             "https://www.ibm.com/employment/",
    "Intel":           "https://jobs.intel.com/",
    "AMD":             "https://jobs.amd.com/",
    "Qualcomm":        "https://careers.qualcomm.com/",
    "Oracle":          "https://careers.oracle.com/",
    "SAP":             "https://jobs.sap.com/",
    "Palantir":        "https://www.palantir.com/careers/",
    "Databricks":      "https://www.databricks.com/company/careers",
    "Snowflake":       "https://careers.snowflake.com/",
    "Stripe":          "https://stripe.com/jobs",
    "Uber":            "https://www.uber.com/us/en/careers/",
    "Lyft":            "https://www.lyft.com/careers",
    "Airbnb":          "https://careers.airbnb.com/",
    "Twitter/X":       "https://careers.x.com/",
    "LinkedIn":        "https://careers.linkedin.com/",
    # Consumer ML Tech
    "Netflix":         "https://jobs.netflix.com/",
    "Spotify":         "https://www.lifeatspotify.com/jobs",
    "Pinterest":       "https://www.pinterestcareers.com/",
    "Disney":          "https://jobs.disneycareers.com/",
    "Roblox":          "https://corp.roblox.com/careers/",
    "eBay":            "https://careers.ebayinc.com/",
    "Snap":            "https://careers.snap.com/",
    "DoorDash":        "https://careers.doordash.com/",
    "Reddit":          "https://www.redditinc.com/careers",
    "OpenAI":          "https://openai.com/careers",
    "Anthropic":       "https://www.anthropic.com/careers",
    "Cohere":          "https://cohere.com/about/careers",
    "Scale AI":        "https://scale.com/careers",
    "Hugging Face":    "https://apply.workable.com/huggingface/",
}

# ── Tavily search queries (PRJ-004: 6 tracks, biased to Seattle/CA/TX hiring) ──
TAVILY_QUERIES = [
    # ── AI-native (labs, startups, infra) ─────────────────────────────────────
    (
        "frontier AI labs and AI startups hiring 2026 OpenAI Anthropic xAI Perplexity "
        "Scale AI Glean Sierra careers technical program manager San Francisco Seattle"
    ),
    (
        "AI infrastructure compute GPU cloud 2026 CoreWeave Lambda Together AI Groq "
        "Cerebras Crusoe Fireworks Modal careers hiring TPM California Texas"
    ),
    # ── Mid-large tech (incl. early-bet divisions) ─────────────────────────────
    (
        "big tech new-bet divisions hiring TPM 2026 Amazon Kuiper Leo Azure Government "
        "Google Cloud Meta Reality Labs Apple special projects careers Seattle Bay Area"
    ),
    (
        "mid-size tech companies technical program manager hiring 2026 Databricks Snowflake "
        "Uber Netflix Salesforce ServiceNow careers Seattle California Austin"
    ),
    # ── Robotics ───────────────────────────────────────────────────────────────
    (
        "robotics companies hiring 2026 Figure AI Apptronik Physical Intelligence Zipline "
        "Nuro Waymo Skild humanoid autonomy careers technical program manager California Texas"
    ),
    # ── Fintech ────────────────────────────────────────────────────────────────
    (
        "fintech companies hiring technical program manager 2026 Stripe Plaid Ramp Brex "
        "Chime Affirm Block Coinbase careers San Francisco Seattle Austin"
    ),
    # ── Space ──────────────────────────────────────────────────────────────────
    (
        "space startups hiring 2026 SpaceX Relativity Stoke Space Rocket Lab Firefly "
        "Astranis Varda True Anomaly careers program manager El Segundo Hawthorne Long Beach Seattle"
    ),
    # ── Defense ────────────────────────────────────────────────────────────────
    (
        "venture-backed defense tech companies hiring 2026 Anduril Shield AI Saronic "
        "Castelion Epirus Vannevar Palantir careers technical program manager "
        "El Segundo Costa Mesa Washington state Texas"
    ),
]

# ── URL helpers ───────────────────────────────────────────────────────────────
_CAREER_DOMAINS   = ["greenhouse.io", "lever.co", "ashbyhq.com", "myworkdayjobs.com",
                     "job-boards.greenhouse.io", "jobs.lever.co",
                     "workable.com", "apply.workable.com"]
_CAREER_PATH_KWDS = ["/careers", "/jobs", "/hiring", "/work-with-us",
                     "/join-us", "/join", "/opportunities", "/open-roles"]

def _is_likely_career_url(url: str) -> bool:
    """Heuristic: does this URL look like a career/jobs page?"""
    u = url.lower()
    return (any(d in u for d in _CAREER_DOMAINS) or
            any(kw in u for kw in _CAREER_PATH_KWDS))


# Hosts whose /jobs/<slug> path wraps a single underlying portfolio company.
# When career_url points at one of these, the slug names the real company —
# extract it and re-resolve to that company's actual ATS via slug-probing.
_VC_PORTFOLIO_HOSTS = {
    "jobs.a16z.com", "jobs.battery.com", "jobs.gaingels.com", "jobs.01a.com",
}

def _unwrap_career_url(url: str) -> str | None:
    """Extract underlying company name hint from a wrapper career URL.

    Handles two wrapper families that appear in our company list but aren't
    real ATS endpoints:
      - linkedin.com/jobs/<slug>-jobs           → "<slug>" (hyphens → spaces)
      - linkedin.com/company/<slug>/jobs[/...]  → "<slug>"
      - jobs.<vc>.com/jobs/<slug>[?...]         → "<slug>"  (vc in _VC_PORTFOLIO_HOSTS)

    Returns None for normal ATS URLs, raw company sites, or unsupported
    LinkedIn forms (e.g. linkedin.com/jobs/view/<id> has no name to extract).
    """
    if not url:
        return None
    u = url.lower().strip()
    # LinkedIn jobs page: linkedin.com/jobs/<slug>-jobs (trailing "-jobs")
    m = re.search(r"linkedin\.com/jobs/([a-z0-9][a-z0-9\-]*?)-jobs(?:/|$|\?)", u)
    if m:
        return m.group(1).replace("-", " ").strip()
    # LinkedIn company-jobs page: linkedin.com/company/<slug>/jobs
    m = re.search(r"linkedin\.com/company/([a-z0-9][a-z0-9\-]*)/jobs", u)
    if m:
        return m.group(1).replace("-", " ").strip()
    # VC-portfolio wrappers: jobs.<vc>.com/jobs/<slug>
    for host in _VC_PORTFOLIO_HOSTS:
        m = re.search(re.escape(host) + r"/jobs/([^/?#]+)", u)
        if m:
            return m.group(1).replace("-", " ").strip()
    return None


def validate_career_url(url: str) -> bool:
    """Return True if the URL resolves successfully (HTTP < 400)."""
    if not url or url in ("N/A", "") or not url.startswith("http"):
        return False
    try:
        r = requests.get(
            url, timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                   "AppleWebKit/537.36 Chrome/120 Safari/537.36"},
            allow_redirects=True,
        )
        if r.status_code < 400:
            return True
        logging.warning(f"[URLCheck] {url} → HTTP {r.status_code}")
        return False
    except Exception as e:
        logging.warning(f"[URLCheck] {url} → {e}")
        return False


# ── ATS slug helpers ──────────────────────────────────────────────────────────
def _slug_candidates(company_name: str) -> list:
    name = company_name.lower().strip()

    # Generate slugs BEFORE stripping suffixes so "Scale AI" → "scale-ai" is kept
    pre_hyphen  = re.sub(r'[^a-z0-9]+', '-', name).strip('-')
    pre_nospace = re.sub(r'[^a-z0-9]+', '', name)

    for suffix in [" inc", " inc.", " llc", " ltd", " corp", " corporation",
                   " technologies", " ai"]:
        name = name.replace(suffix, "")
    name     = name.strip()
    hyphen   = re.sub(r'[^a-z0-9]+', '-', name).strip('-')
    nospace  = re.sub(r'[^a-z0-9]+', '', name)
    parts    = hyphen.split('-')

    seen, out = set(), []
    for c in [hyphen, nospace, pre_hyphen, pre_nospace,
              parts[-1] if parts else '', parts[0] if parts else '']:
        if c and c not in seen:
            seen.add(c); out.append(c)
    return out


def _check_ats_slug(slug: str, validator: dict) -> tuple:
    url = validator["api_template"].format(slug=slug)
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "PathFinder/1.0"})
        if r.status_code != 200:
            return False, 0
        data = r.json()
        key  = validator["jobs_key"]
        n    = len(data) if key is None else len(data.get(key, []))
        return n > 0, n
    except Exception:
        return False, 0


def _find_ats_url(company_name: str) -> str | None:
    """Try Greenhouse then Lever slug patterns for the company."""
    for slug in _slug_candidates(company_name)[:3]:
        for v in ATS_VALIDATORS:
            hit, _ = _check_ats_slug(slug, v)
            if hit:
                return v["board_template"].format(slug=slug)
            time.sleep(0.2)
    return None


# ── Homepage scraping ─────────────────────────────────────────────────────────
def _scrape_homepage_for_career_link(company_name: str) -> str | None:
    """Guess company domain, scrape homepage, extract first valid career link."""
    name_clean = re.sub(r'[^a-z0-9]', '', company_name.lower().strip())
    domain_guesses = [
        f"https://www.{name_clean}.com",
        f"https://{name_clean}.com",
        f"https://{name_clean}.ai",
    ]
    hdrs = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 Chrome/120 Safari/537.36"}
    for base in domain_guesses:
        try:
            r = requests.get(base, timeout=10, headers=hdrs, allow_redirects=True)
            if r.status_code >= 400:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True).lower()
                href_lower = href.lower()
                if any(kw in href_lower or kw in text
                       for kw in ["career", "job", "hiring", "work with us", "join us", "join"]):
                    full = urljoin(r.url, href)
                    if full.startswith("http") and validate_career_url(full):
                        return full
        except Exception:
            pass
    return None


# ── Multi-strategy career URL finder ─────────────────────────────────────────
def find_career_url(company_name: str, tavily_client) -> str | None:
    """
    Find a valid career URL for a company using multiple strategies:
      1. KNOWN_CAREER_URLS exact match
      2. Tavily targeted ATS search
      3. Tavily general careers search
      4. ATS slug probing (Greenhouse + Lever)
      5. Company homepage scraping
    """
    name_lower = company_name.lower().strip()

    # 1. Known career URLs (case-insensitive exact match)
    for k, v in KNOWN_CAREER_URLS.items():
        if k.lower() == name_lower:
            if validate_career_url(v):
                logging.info(f"[CareerURL] {company_name}: known URL → {v}")
                return v

    # 2. Tavily: ATS-specific search
    ats_query = (
        f'"{company_name}" careers jobs '
        f'site:greenhouse.io OR site:lever.co OR site:ashbyhq.com OR site:myworkdayjobs.com'
    )
    url = _tavily_extract_career_url(company_name, ats_query, tavily_client)
    if url:
        logging.info(f"[CareerURL] {company_name}: Tavily ATS → {url}")
        return url

    # 3. Tavily: general careers search
    gen_query = f'"{company_name}" careers hiring jobs 2026 official career page'
    url = _tavily_extract_career_url(company_name, gen_query, tavily_client)
    if url:
        logging.info(f"[CareerURL] {company_name}: Tavily general → {url}")
        return url

    # 4. ATS slug probing
    url = _find_ats_url(company_name)
    if url:
        logging.info(f"[CareerURL] {company_name}: ATS slug → {url}")
        return url

    # 5. Homepage scraping
    url = _scrape_homepage_for_career_link(company_name)
    if url:
        logging.info(f"[CareerURL] {company_name}: homepage scrape → {url}")
        return url

    return None


def _tavily_extract_career_url(company_name: str, query: str, client) -> str | None:
    """Run one Tavily query and return the first validated career URL found."""
    try:
        r = client.search(query=query, search_depth="basic", max_results=5)
        for item in r.get("results", []):
            url = item.get("url", "")
            if _is_likely_career_url(url) and validate_career_url(url):
                return url
    except Exception as e:
        err_str = str(e)
        if "402" in err_str or "429" in err_str or "quota" in err_str.lower():
            logging.error(f"[CareerURL] Tavily quota exhausted for {company_name}: {e}")
        else:
            logging.warning(f"[CareerURL] Tavily query failed for {company_name}: {e}")
    return None


def _workday_subdomain_matches_company(url: str, company_name: str) -> bool:
    """Validate that a Workday URL's subdomain belongs to `company_name`.

    Tavily's `site:myworkdayjobs.com` query happily returns URLs from
    *other* companies that mention `company_name` somewhere in their JD
    (e.g. "AMD" → `argonne.wd1.myworkdayjobs.com`, "Oracle" → `pwc.wd3...`).
    Reject any result whose subdomain doesn't approximately match the
    company name's slug candidates.
    """
    m = re.match(r"https?://([^.]+)\.wd\d+\.myworkdayjobs\.com", url, re.IGNORECASE)
    if not m:
        return False
    sub = m.group(1).lower().strip()
    sub_compact = re.sub(r'[^a-z0-9]', '', sub)
    # Equality only — no substring/prefix matching. Substring rules let
    # "apple" → "applebank", "clay" → "claycountybcc", "western" →
    # "westernunion" all leak through, which produces wrong-company URLs.
    for c in _slug_candidates(company_name):
        c_lower = c.lower()
        c_compact = re.sub(r'[^a-z0-9]', '', c_lower)
        if c_lower == sub or (c_compact and c_compact == sub_compact):
            return True
    return False


def _find_workday_url(company_name: str, tavily_client) -> str | None:
    """Tavily-search for a company's Workday board URL.

    Workday subdomains are unguessable (e.g. `nvidia.wd5`, `arista.wd1`,
    `intel.wd1`) so slug-probing can't find them. This helper queries Tavily
    with a Workday-scoped site filter and returns the first result whose URL
    is on `myworkdayjobs.com` AND whose subdomain matches the company name.
    The subdomain check is critical: Tavily will otherwise return any
    Workday URL whose page mentions the company (e.g. "AMD" → Argonne Lab
    job postings that reference AMD silicon).

    Returns None if Tavily yields no validated Workday match or on any error.
    """
    if not tavily_client:
        return None
    query = f'"{company_name}" careers site:myworkdayjobs.com'
    try:
        r = tavily_client.search(query=query, search_depth="basic", max_results=5)
        for item in r.get("results", []):
            url = (item.get("url") or "").strip()
            if ("myworkdayjobs.com" in url
                    and _workday_subdomain_matches_company(url, company_name)
                    and validate_career_url(url)):
                return url
    except Exception as e:
        err_str = str(e)
        if "402" in err_str or "429" in err_str or "quota" in err_str.lower():
            logging.error(f"[Workday] Tavily quota exhausted for {company_name}: {e}")
        else:
            logging.warning(f"[Workday] Tavily query failed for {company_name}: {e}")
    return None


# ── Company name dedup helpers ────────────────────────────────────────────────
_COMPANY_SUFFIXES = re.compile(
    r'\b(inc|corp|corporation|llc|ltd|technologies|labs?|'
    r'ai|platform|systems|computing)\b\.?',
    re.IGNORECASE,
)


def _normalize_company_name(name: str) -> str:
    """Normalize company name for dedup: lowercase, strip, remove common suffixes."""
    n = name.lower().strip()
    n = _COMPANY_SUFFIXES.sub('', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def _is_duplicate_company(
    candidate: str,
    existing_names: set[str],
    existing_normalized: set[str] | None = None,
) -> bool:
    """Check if candidate is a duplicate of any existing company name.

    Strategy:
      1. Exact case-insensitive match
      2. Normalized name match (stripped common suffixes)
      3. Bidirectional startswith check (min 4 chars to avoid short-name collisions)
    """
    cand_lower = candidate.lower().strip()

    # 1. Exact case-insensitive
    if cand_lower in {n.lower() for n in existing_names}:
        return True

    # 2. Normalized match
    cand_norm = _normalize_company_name(candidate)
    if existing_normalized is None:
        existing_normalized = {_normalize_company_name(n) for n in existing_names}
    if cand_norm in existing_normalized:
        return True

    # 3. Bidirectional startswith (only if shortest name >= 4 chars)
    for existing in existing_names:
        ex_lower = existing.lower().strip()
        shorter = min(len(cand_lower), len(ex_lower))
        if shorter < 4:
            continue
        if cand_lower.startswith(ex_lower) or ex_lower.startswith(cand_lower):
            return True

    return False


# ── Company discovery ─────────────────────────────────────────────────────────
def compute_need_by_track(existing_rows: list) -> dict:
    """PRJ-004 REQ-004-01: open discovery slots per bucket.

    need[bucket] = max(0, quota - current_count) — a bucket at/over quota
    (grandfathered survivors, D-12) gets 0 and is never trimmed. Rows whose
    Track value is not one of the 6 buckets (unmigrated) count toward no
    bucket; they are surfaced with a warning and resolved by --migrate-tracks.
    """
    counts = {t: 0 for t in TRACK_VALUES}
    unmigrated = 0
    for row in existing_rows:
        track = str(row[1] if len(row) > 1 else "").strip()
        if track in counts:
            counts[track] += 1
        elif row and row[0]:
            unmigrated += 1
    if unmigrated:
        logging.warning(f"[Track] {unmigrated} Company_List row(s) have an "
                        "unmigrated Track value — run "
                        "`python agents/company_agent.py --migrate-tracks`.")
    return {t: max(0, TRACK_QUOTAS[t] - counts[t]) for t in TRACK_VALUES}


def allocate_batch(need_by_track: dict, batch_size: int) -> dict:
    """Allocate one run's discovery budget across open buckets, proportional
    to open slots (largest-remainder rounding), capped at batch_size total."""
    total_open = sum(need_by_track.values())
    if total_open <= batch_size:
        return dict(need_by_track)
    shares = {t: n * batch_size / total_open for t, n in need_by_track.items()}
    alloc  = {t: int(s) for t, s in shares.items()}
    leftover = batch_size - sum(alloc.values())
    for t in sorted(shares, key=lambda t: shares[t] - alloc[t], reverse=True):
        if leftover <= 0:
            break
        if alloc[t] < need_by_track[t]:
            alloc[t] += 1
            leftover -= 1
    return alloc


def _apply_bucket_rules(companies: list, need_by_track: dict) -> list:
    """PRJ-004 REQ-004-03 + quota trim, deterministic (never trust the LLM for
    hard exclusions): drop Defense-bucket legacy primes (unless allowlisted),
    and cap accepted companies per bucket at that bucket's open slots."""
    remaining = dict(need_by_track)
    out = []
    for c in companies:
        name  = _normalize_company_name(c.get("company_name", ""))
        track = c.get("track", "")
        if track == "Defense" and name in DEFENSE_EXCLUDED_PRIMES \
                and name not in DEFENSE_ALLOWLIST:
            logging.info(f"[BucketRules] Dropped defense legacy prime: {name}")
            continue
        if remaining.get(track, 0) <= 0:
            logging.info(f"[BucketRules] Bucket {track!r} full — dropped {name}")
            continue
        remaining[track] -= 1
        out.append(c)
    return out


def discover_ai_companies(tavily_key: str, existing_names: set,
                          need_by_track: dict) -> list:
    """
    Discover new companies not in `existing_names`, up to each track's open
    slots in `need_by_track` ({track: slots}). Returns a list of dicts with
    keys: company_name, track, business_focus, career_url.

    Flow:
      1. Tavily batch search → raw article/news results
      2. Gemini extracts structured company info (NO URL generation)
      3. Deterministic bucket rules (defense prime exclusion, quota trim)
      4. Per-company multi-strategy career URL lookup
    """
    if _KEY_POOL is None:
        raise RuntimeError("_KEY_POOL not initialized — call main() first or set _KEY_POOL before invoking discover_ai_companies()")
    from tavily import TavilyClient

    need = sum(need_by_track.values())
    logging.info(f"Searching for {need} new companies across "
                 f"{sum(1 for v in need_by_track.values() if v)} open buckets "
                 f"(existing: {len(existing_names)})...")
    client   = TavilyClient(api_key=tavily_key)
    raw, seen_urls = [], set()

    # Step 1: Batch Tavily search for company discovery
    for q in TAVILY_QUERIES:
        try:
            r = client.search(query=q, search_depth="advanced", max_results=10)
            for item in r.get("results", []):
                u = item.get("url", "")
                if u not in seen_urls:
                    seen_urls.add(u)
                    raw.append(item)
        except Exception as e:
            err_str = str(e)
            if "402" in err_str or "429" in err_str or "quota" in err_str.lower():
                print(f"  ⚠️  Tavily API quota exhausted: {e}")
                logging.error(f"Tavily quota exhausted: {e}")
                break  # no point continuing with more queries
            logging.warning(f"Tavily query failed: {e}")

    results = raw[:120]
    logging.info(f"Tavily: {len(results)} deduplicated results collected.")

    # Step 2: Gemini extracts company info only — no URL generation
    existing_list = sorted(existing_names)[:150]
    logging.info("Feeding context to Gemini for company extraction (no URL generation)...")
    _bucket_guidance = {
        "AI-native": (
            "AI-native companies of any size — frontier labs, AI product startups, "
            "AI infrastructure/compute (OpenAI, Anthropic, xAI, Perplexity, Scale AI, "
            "Glean, Sierra, CoreWeave, Groq, Together AI, Cerebras, etc.). Founded "
            "~2000 or later. NO tiny pre-seed companies — real headcount and a "
            "public job board."),
        "Mid-large Tech": (
            "established mid-large tech companies with strong TPM organizations, "
            "especially those with early-bet divisions (Google, Microsoft, Amazon, "
            "Meta, Apple, NVIDIA, Databricks, Snowflake, Uber, Netflix, Salesforce, "
            "ServiceNow, etc.). No founding-year restriction — this is the only "
            "bucket where legacy incumbents belong."),
        "Robotics": (
            "robotics companies founded ~2000 or later (Figure AI, Apptronik, "
            "Physical Intelligence, Skild, Zipline, Nuro, Waymo, etc.). EXCLUDE "
            "legacy incumbents (e.g. ABB, Boston Dynamics' parent conglomerates) — "
            "those belong in Mid-large Tech if anywhere."),
        "Fintech": (
            "fintech companies founded ~2000 or later (Stripe, Plaid, Ramp, Brex, "
            "Chime, Affirm, Block, Coinbase, etc.). EXCLUDE legacy incumbents "
            "(Visa, PayPal, Intuit, Mastercard) — those belong in Mid-large Tech "
            "if anywhere."),
        "Space": (
            "space companies founded ~2000 or later (SpaceX, Relativity Space, "
            "Stoke Space, Rocket Lab, Firefly, Astranis, Varda, True Anomaly, "
            "etc.) — prefer these over incumbent space divisions (ULA, Boeing "
            "space)."),
        "Defense": (
            "venture-backed defense tech founded roughly 2010 or later (Anduril, "
            "Shield AI, Saronic, Castelion, Epirus, Vannevar Labs, etc.). "
            "Palantir IS in scope (explicit exception). NEVER include legacy "
            "primes: Boeing, Lockheed Martin, Raytheon/RTX, Northrop Grumman, "
            "General Dynamics, BAE, L3Harris."),
    }
    distribution = "\n".join(
        f'  - "{track}": {n} companies — {_bucket_guidance[track]}'
        for track, n in need_by_track.items() if n > 0
    )
    config = types.GenerateContentConfig(
        system_instruction=(
            "You are an expert technology-industry analyst. From the web search "
            f"context, extract exactly {need} distinct companies that are NOT in "
            "the EXISTING_COMPANIES list. Every company must have a real TPM "
            "(Technical Program Manager) hiring function.\n"
            "GEOGRAPHY: a company qualifies if it HIRES TPMs in Greater Seattle, "
            "California (Bay Area or Southern California — El Segundo, Hawthorne, "
            "Long Beach, Irvine, San Diego), or Texas. Qualification is by hiring "
            "footprint in these regions, NOT by HQ location.\n"
            "Follow this bucket distribution strictly (use the EXACT label string "
            "for the track field):\n"
            f"{distribution}\n"
            "The track field MUST be one of the 6 exact strings — do not invent "
            "variants.\n"
            "For business_focus: write 3-4 sentences covering what the company "
            "builds, who their customers are, their key competitive differentiator, "
            "and notable products/funding/traction.\n"
            "DO NOT include any career_url or URL fields — URLs are handled separately."
            + SECURITY_CLAUSE  # P0-3: Tavily snippets are untrusted third-party content
        ),
        temperature=0.1,
        response_mime_type="application/json",
        response_schema=CompanyInfoList,
    )
    prompt = (
        f"Search context:\n<scraped_content>\n{json.dumps(results)}\n</scraped_content>\n\n"
        f"EXISTING_COMPANIES (DO NOT include these):\n{json.dumps(existing_list)}\n\n"
        f"Extract exactly {need} NEW companies with: company_name, "
        f"track (one of: {' / '.join(TRACK_VALUES)}), "
        "business_focus (3-4 sentences)."
    )
    try:
        resp      = _KEY_POOL.generate_content(model=MODEL, contents=prompt, config=config)
        companies = json.loads(resp.text).get("companies", [])
    except Exception as e:
        logging.error(f"Company extraction failed: {e}")
        return []

    # Filter out any Gemini accidentally returned in existing list
    # BUG-49: use local copies to avoid mutating the caller's set
    local_names = set(existing_names)
    existing_normalized = {_normalize_company_name(n) for n in local_names}
    filtered = []
    for c in companies:
        name = c.get("company_name", "").strip()
        if not name:
            continue
        if _is_duplicate_company(name, local_names, existing_normalized):
            logging.info(f"[Dedup] Skipped duplicate: {name}")
            continue
        # Add to tracking sets so later items in this batch also dedup
        local_names.add(name)
        existing_normalized.add(_normalize_company_name(name))
        filtered.append(c)
    logging.info(f"After dedup filter: {len(filtered)} new companies.")

    # Step 2.5: deterministic bucket rules (defense prime exclusion + quota
    # trim) BEFORE career-URL discovery, so excluded companies never spend
    # Tavily/validation calls.
    filtered = _apply_bucket_rules(filtered, need_by_track)
    logging.info(f"After bucket rules: {len(filtered)} companies.")

    # Step 3: Per-company career URL discovery
    validated = []
    for c in filtered:
        name = c.get("company_name", "")
        logging.info(f"[CareerURL] Finding URL for: {name}")
        url = find_career_url(name, client)
        if url:
            c["career_url"] = url
            validated.append(c)
            logging.info(f"[CareerURL] ✅ {name} → {url}")
        else:
            logging.warning(f"[CareerURL] ❌ {name}: no valid career URL found — SKIPPED")
        time.sleep(0.5)

    logging.info(f"Career URL discovery: {len(validated)}/{len(filtered)} companies kept.")
    return validated


# ── ATS upgrade (Phase 1.5) ───────────────────────────────────────────────────
def validate_and_upgrade_ats_url(company_name: str, current_url: str,
                                  tavily_client=None) -> str:
    """Return upgraded ATS board URL, or original if no ATS found.

    When `tavily_client` is provided, falls back to a Workday-scoped Tavily
    search for companies whose slug-probe yields no Greenhouse/Lever/Ashby/
    Workable match — recovers cos with unguessable Workday subdomains
    (e.g. `nvidia.wd5`, `arista.wd1`).
    """
    name_lower = company_name.lower().strip()

    # 1. Hard-coded overrides (highest priority)
    # Use word-boundary matching (not substring) to avoid "xai" matching "MaxAI" etc.
    for kw, url in KNOWN_ATS_OVERRIDES.items():
        if re.search(r'(?:^|\s)' + re.escape(kw) + r'(?:\s|$)', name_lower):
            logging.info(f"[Phase1.5] {company_name}: override → {url}")
            return url

    # 1.5. Wrapper URL (LinkedIn / VC-portfolio) → re-resolve via underlying slug
    hint = _unwrap_career_url(current_url)
    if hint:
        for slug in _slug_candidates(hint):
            for v in ATS_VALIDATORS:
                hit, n = _check_ats_slug(slug, v)
                if hit:
                    upgraded = v["board_template"].format(slug=slug)
                    logging.info(f"[Phase1.5] {company_name}: unwrapped "
                                 f"'{current_url}' → {v['platform']}/{slug} "
                                 f"jobs={n} → {upgraded}")
                    return upgraded
                time.sleep(0.3)
        logging.info(f"[Phase1.5] {company_name}: unwrap hint '{hint}' "
                     f"yielded no ATS match")

    # 2. Already an ATS URL
    if any(d in current_url for d in ["greenhouse.io", "lever.co", "ashbyhq.com",
                                       "myworkdayjobs.com", "workable.com"]):
        return current_url

    # 3. Probe Greenhouse + Lever + Ashby + Workable slugs
    for slug in _slug_candidates(company_name):
        for v in ATS_VALIDATORS:
            hit, n = _check_ats_slug(slug, v)
            if hit:
                upgraded = v["board_template"].format(slug=slug)
                logging.info(f"[Phase1.5] {company_name}: {v['platform']} "
                             f"slug='{slug}' jobs={n} → {upgraded}")
                return upgraded
            time.sleep(0.3)

    # 4. Workday-via-Tavily fallback (unguessable subdomains)
    if tavily_client is not None:
        wd_url = _find_workday_url(company_name, tavily_client)
        if wd_url:
            logging.info(f"[Phase1.5] {company_name}: workday-via-tavily → {wd_url}")
            return wd_url

    return current_url


def run_phase_1_5(xlsx_path: str, tavily_client=None):
    """Re-validate every non-ATS career URL in the companies sheet.

    `tavily_client` enables the Workday-via-Tavily fallback (step 4 of
    `validate_and_upgrade_ats_url`). When None and TAVILY_API_KEY is set in
    env, a client is created automatically.
    """
    if tavily_client is None:
        tavily_key = os.getenv("TAVILY_API_KEY")
        if tavily_key:
            try:
                from tavily import TavilyClient
                tavily_client = TavilyClient(api_key=tavily_key)
            except Exception as e:
                logging.warning(f"[Phase1.5] Tavily client init failed: {e}")
                tavily_client = None

    print("\n" + "="*60)
    print("PHASE 1.5: ATS URL VALIDATION & UPGRADE")
    print("="*60)
    if tavily_client is None:
        print("  ⚠️  No Tavily client — Workday fallback disabled.")
    rows = get_company_rows_with_row_num(xlsx_path)
    if not rows:
        print("⚠️  No companies found. Skipping.")
        return

    upgraded = no_ats = backfilled = backfill_failed = 0
    ATS_DOMAINS = ["greenhouse.io", "lever.co", "ashbyhq.com", "myworkdayjobs.com",
                   "workable.com"]

    for excel_row, row in rows:
        name = str(row[0]).strip() if row[0] else ""
        url  = str(row[3]).strip() if row[3] else ""
        if not name:
            continue

        # Manual-row override: row exists with a name but no Career URL
        # (typically inserted by hand). Discover one via find_career_url.
        if not url or url == "N/A":
            if tavily_client is None:
                print(f"  ⚠️  {name}: Career URL blank — Tavily disabled, skipping backfill.")
                backfill_failed += 1
                continue
            print(f"  🆕 {name}: Career URL blank — backfilling...")
            new_url = find_career_url(name, tavily_client)
            if new_url:
                update_company_career_url(xlsx_path, excel_row, new_url)
                print(f"  ✅ {name}: backfilled → {new_url}")
                backfilled += 1
            else:
                print(f"  ❌ {name}: backfill failed (no valid URL found).")
                backfill_failed += 1
            time.sleep(1)
            continue

        if any(d in url for d in ATS_DOMAINS):
            print(f"  ⏭️  {name}: Already ATS → {url}")
            continue

        print(f"  🔍 {name}...")
        new_url = validate_and_upgrade_ats_url(name, url, tavily_client=tavily_client)
        if new_url != url:
            update_company_career_url(xlsx_path, excel_row, new_url)
            print(f"  ✅ {name}: {url} → {new_url}")
            upgraded += 1
        else:
            print(f"  ⚪ {name}: No ATS found.")
            no_ats += 1
        time.sleep(1)

    print(f"\n  Upgraded={upgraded}  No ATS={no_ats}  "
          f"Backfilled={backfilled}  Backfill failed={backfill_failed}")
    print("="*60 + "\n")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global _KEY_POOL
    summary = RunSummary(agent="company")
    try:
        tavily_key  = os.getenv("TAVILY_API_KEY")
        gemini_keys = [k for k in [
            os.getenv("GEMINI_API_KEY"),
            os.getenv("GEMINI_API_KEY_2"),
        ] if k]
        missing = []
        if not gemini_keys:
            missing.append("GEMINI_API_KEY")
        if not tavily_key:
            missing.append("TAVILY_API_KEY")
        if missing:
            print(f"❌ Missing env vars: {missing}")
            summary.note(f"Missing env vars: {missing}")
            return

        _KEY_POOL = _GeminiKeyPoolBase(gemini_keys, genai_mod=genai)
        logging.info(f"[KeyPool] Loaded {len(gemini_keys)} Gemini API key(s).")

        print("\n" + "="*60)
        print("COMPANY AGENT")
        print("="*60 + "\n")

        xlsx_path = get_or_create_excel()
        print(f"📊 Dashboard: {xlsx_path}")

        # ── Step 1: Read existing companies (both lists) ──────────────────────────
        current_count     = count_company_rows(xlsx_path)
        existing_rows     = get_company_rows(xlsx_path)
        names_main        = {str(r[0]).strip() for r in existing_rows if r[0]}
        names_without_tpm = get_company_names_without_tpm(xlsx_path)
        existing_names    = names_main | names_without_tpm
        print(f"📋 Existing companies in Company_List: {current_count}")
        print(f"📋 Companies in Company_Without_TPM: {len(names_without_tpm)}")
        print(f"📋 Total known companies (dedup exclusion list): {len(existing_names)}")

        # ── Step 2: Per-bucket slot accounting (PRJ-004 REQ-004-01 / D-12) ────────
        # Count existing rows per Track value; a bucket at/over quota (e.g.
        # grandfathered migration survivors) gets 0 new-discovery slots and is
        # never trimmed. The per-run total stays capped at BATCH_SIZE,
        # allocated across open buckets proportionally to their open slots.
        need_by_track = compute_need_by_track(existing_rows)
        total_open = sum(need_by_track.values())
        if total_open <= 0:
            print(f"✅ All buckets at quota ({MAX_TOTAL} companies). Skipping discovery.")
            summary.note(f"All buckets at quota; discovery skipped.")
        else:
            need_by_track = allocate_batch(need_by_track, BATCH_SIZE)
            need = sum(need_by_track.values())
            open_desc = ", ".join(f"{t}: {n}" for t, n in need_by_track.items() if n)
            print(f"🔍 Will discover up to {need} new companies this run "
                  f"({open_desc}; total open slots: {total_open})...")
            summary.attempted = need

            companies = discover_ai_companies(tavily_key, existing_names, need_by_track)

            if companies:
                data = [c.model_dump() if hasattr(c, "model_dump") else dict(c)
                        for c in companies]
                upsert_companies(xlsx_path, data)
                new_count = count_company_rows(xlsx_path)
                print(f"✅ Added {len(data)} companies. Total: {new_count}")
                summary.succeeded = len(data)
                summary.failed = max(0, need - len(data))
            else:
                print("⚠️  No new companies returned.")
                summary.failed = need

        # ── Step 3: Phase 1.5 — upgrade ATS URLs ─────────────────────────────────
        run_phase_1_5(xlsx_path)

        print("🎉 Company Agent complete.")
    except Exception as e:
        # P0-7: capture pre-finally so summary reflects the failure mode.
        from shared.exceptions import GeminiTransientError
        if isinstance(e, GeminiTransientError):
            summary.transient_errors += 1
            summary.note(f"Run aborted (transient): {e}")
        else:
            summary.note(f"Run aborted: {type(e).__name__}: {e}")
        raise
    finally:
        # PRJ-004 REQ-004-25/26: token-usage snapshot in every run log —
        # the measurement carrier for the trial-run cost gate.
        try:
            from shared.gemini_pool import get_usage_summary
            summary.note(f"gemini usage: {get_usage_summary()}")
        except Exception:
            pass
        summary.mark_finished()
        log_path = summary.write()
        print(f"📊 Run summary: {log_path}")
        print(summary.to_json())


def migrate_tracks(xlsx_path: str | None = None) -> dict:
    """PRJ-004 REQ-004-06: one-time re-bucketing of existing Company_List rows
    into the 6-track taxonomy via a Gemini classification pass.

    Precondition (user-owned): the user has manually pruned Company_List.
    Idempotent — rows whose Track is already one of the 6 values are skipped,
    so a partial failure can simply be re-run. Nothing is ever deleted:
    unconfident classifications get 'UNMIGRATED — manual review' and defense
    legacy primes are deterministically forced to Mid-large Tech (a prime can
    survive only there). Prints a full audit table for the user spot-check.

    Returns {"migrated": n, "skipped": n, "flagged": n} for tests/reporting.
    """
    global _KEY_POOL
    gemini_keys = [k for k in [os.getenv("GEMINI_API_KEY"),
                               os.getenv("GEMINI_API_KEY_2")] if k]
    if not gemini_keys:
        print("❌ Missing GEMINI_API_KEY in .env")
        return {"migrated": 0, "skipped": 0, "flagged": 0}
    if _KEY_POOL is None:
        _KEY_POOL = _GeminiKeyPoolBase(gemini_keys, genai_mod=genai)

    xlsx_path = xlsx_path or get_or_create_excel()  # header renames self-heal here
    rows = get_company_rows_with_row_num(xlsx_path)
    pending = []   # (excel_row, name, old_value, business_focus)
    skipped = 0
    for excel_row, row in rows:
        name  = str(row[0]).strip() if row and row[0] else ""
        track = str(row[1]).strip() if len(row) > 1 else ""
        focus = str(row[2]).strip() if len(row) > 2 else ""
        if not name:
            continue
        if track in TRACK_VALUES:
            skipped += 1
            continue
        pending.append((excel_row, name, track, focus))

    print(f"🔀 Track migration: {len(pending)} row(s) to classify, "
          f"{skipped} already migrated (skipped).")
    if not pending:
        return {"migrated": 0, "skipped": skipped, "flagged": 0}

    system_instruction = (
        "You classify companies into exactly one of 6 track buckets for a "
        "TPM job-search pipeline. Buckets:\n"
        '  - "AI-native": AI labs / AI product startups / AI infra-compute, founded ~2000+\n'
        '  - "Mid-large Tech": established mid-large tech companies (the only bucket '
        "where legacy incumbents belong, e.g. Boeing, Visa, PayPal, Intuit)\n"
        '  - "Robotics": robotics companies founded ~2000+\n'
        '  - "Fintech": fintech companies founded ~2000+\n'
        '  - "Space": space companies founded ~2000+\n'
        '  - "Defense": venture-backed defense tech founded roughly 2010+. Palantir '
        "belongs here (explicit exception). Legacy primes (Boeing, Lockheed Martin, "
        "Raytheon/RTX, Northrop Grumman, General Dynamics, BAE, L3Harris) NEVER "
        "belong here — classify them as Mid-large Tech.\n"
        "Return one TrackClassification per input company, company_name copied "
        "verbatim. Set confident=false when the business description is too thin "
        "to decide — do not guess."
        + SECURITY_CLAUSE  # P0-3: business_focus text originated from scraped web content
    )

    migrated, flagged = 0, 0
    audit: list[tuple] = []
    tally: dict = {}
    BATCH = 25
    for b in range(0, len(pending), BATCH):
        chunk = pending[b : b + BATCH]
        payload = json.dumps([{"company_name": n, "business_focus": f[:600]}
                              for _, n, _, f in chunk])
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=TrackClassificationList,
        )
        try:
            resp = _KEY_POOL.generate_content(
                model=MODEL,
                contents=("Classify these companies:\n"
                          f"<scraped_content>\n{payload}\n</scraped_content>"),
                config=config,
            )
            results = {c.get("company_name", "").strip(): c
                       for c in json.loads(resp.text).get("classifications", [])}
        except Exception as e:
            logging.error(f"[Migrate] batch {b // BATCH + 1} failed: {e} — "
                          "rows left unmigrated; re-run to retry.")
            results = {}
        for excel_row, name, old_value, _focus in chunk:
            r = results.get(name)
            if r is None:
                new_track, rationale = "UNMIGRATED — manual review", "no classification returned"
            elif _normalize_company_name(name) in DEFENSE_EXCLUDED_PRIMES:
                # Deterministic: a prime can survive only in Mid-large Tech.
                new_track, rationale = "Mid-large Tech", "defense legacy prime (forced)"
            elif not r.get("confident", False):
                new_track, rationale = "UNMIGRATED — manual review", r.get("rationale", "unconfident")
            else:
                new_track, rationale = r["track"], r.get("rationale", "")
            update_company_track(xlsx_path, excel_row, new_track)
            audit.append((name, old_value, new_track, rationale))
            if new_track in TRACK_VALUES:
                migrated += 1
                tally[new_track] = tally.get(new_track, 0) + 1
            else:
                flagged += 1
        time.sleep(0.5)

    print("\n── Migration audit (spot-check me) ─────────────────────────────")
    for name, old, new, why in audit:
        print(f"  {name}: {old or '(blank)'} → {new}   [{why}]")
    print("\n── Per-bucket tally ─────────────────────────────────────────────")
    for track in TRACK_VALUES:
        print(f"  {track}: +{tally.get(track, 0)}")
    if flagged:
        print(f"  ⚠️  UNMIGRATED — manual review: {flagged} row(s)")
    print(f"\n✅ Migrated {migrated}, flagged {flagged}, already-done {skipped}. "
          "Re-run after fixing flagged rows — the pass is idempotent.")
    return {"migrated": migrated, "skipped": skipped, "flagged": flagged}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PathFinder company agent")
    parser.add_argument("--migrate-tracks", action="store_true",
                        help="One-time PRJ-004 re-bucketing of Company_List "
                             "into the 6-track taxonomy (REQ-004-06). "
                             "Run AFTER manually pruning Company_List.")
    args = parser.parse_args()
    if args.migrate_tracks:
        migrate_tracks()
    else:
        main()
