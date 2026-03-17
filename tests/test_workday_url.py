"""
Tests for REQ-061: Workday URL format coverage extension.

Verifies that _fetch_workday_jobs() correctly parses both:
  - Standard format: company.wd5.myworkdayjobs.com/site
  - No-wd-prefix format: company.myworkdayjobs.com/site
  - Various wd numbers: wd1, wd5, wd12
  - URLs with query params and fragments
  - Invalid URLs
"""
import sys
import os
import re
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ── Stub heavy deps ───────────────────────────────────────────────────────────
for mod in ["google", "google.genai", "google.genai.types",
            "dotenv", "firecrawl", "crawl4ai", "pycountry"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

sys.modules["dotenv"].load_dotenv = lambda: None

import google
google.genai = MagicMock()
google.genai.types = MagicMock()

_US_STATES_RAW = [
    ("Alabama", "US-AL"), ("Alaska", "US-AK"), ("Arizona", "US-AZ"),
    ("Arkansas", "US-AR"), ("California", "US-CA"), ("Colorado", "US-CO"),
    ("Connecticut", "US-CT"), ("Delaware", "US-DE"), ("Florida", "US-FL"),
    ("Georgia", "US-GA"), ("Hawaii", "US-HI"), ("Idaho", "US-ID"),
    ("Illinois", "US-IL"), ("Indiana", "US-IN"), ("Iowa", "US-IA"),
    ("Kansas", "US-KS"), ("Kentucky", "US-KY"), ("Louisiana", "US-LA"),
    ("Maine", "US-ME"), ("Maryland", "US-MD"), ("Massachusetts", "US-MA"),
    ("Michigan", "US-MI"), ("Minnesota", "US-MN"), ("Mississippi", "US-MS"),
    ("Missouri", "US-MO"), ("Montana", "US-MT"), ("Nebraska", "US-NE"),
    ("Nevada", "US-NV"), ("New Hampshire", "US-NH"), ("New Jersey", "US-NJ"),
    ("New Mexico", "US-NM"), ("New York", "US-NY"), ("North Carolina", "US-NC"),
    ("North Dakota", "US-ND"), ("Ohio", "US-OH"), ("Oklahoma", "US-OK"),
    ("Oregon", "US-OR"), ("Pennsylvania", "US-PA"), ("Rhode Island", "US-RI"),
    ("South Carolina", "US-SC"), ("South Dakota", "US-SD"), ("Tennessee", "US-TN"),
    ("Texas", "US-TX"), ("Utah", "US-UT"), ("Vermont", "US-VT"),
    ("Virginia", "US-VA"), ("Washington", "US-WA"), ("West Virginia", "US-WV"),
    ("Wisconsin", "US-WI"), ("Wyoming", "US-WY"),
    ("District of Columbia", "US-DC"),
]

class _FakeSub:
    def __init__(self, name, code):
        self.name = name
        self.code = code

_fake_subdivisions = [_FakeSub(n, c) for n, c in _US_STATES_RAW]

pycountry_mock = sys.modules["pycountry"]
pycountry_mock.subdivisions = MagicMock()
pycountry_mock.subdivisions.get = MagicMock(return_value=_fake_subdivisions)

from agents.job_agent import _fetch_workday_jobs


# ─────────────────────────────────────────────────────────────────────────────
class TestWorkdayURLRegex(unittest.TestCase):
    """Unit-test the regex inside _fetch_workday_jobs without hitting the network."""

    # The regex used inside _fetch_workday_jobs (mirrors production code)
    REGEX = re.compile(r"https://([^.]+)(?:\.wd\d+)?\.myworkdayjobs\.com/([^/?#]+)")

    # ── Standard format (already supported) ──────────────────────────────────
    def test_standard_wd5(self):
        m = self.REGEX.match("https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "nvidia")
        self.assertEqual(m.group(2), "NVIDIAExternalCareerSite")

    def test_standard_wd1(self):
        m = self.REGEX.match("https://salesforce.wd1.myworkdayjobs.com/External")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "salesforce")
        self.assertEqual(m.group(2), "External")

    def test_standard_wd12(self):
        m = self.REGEX.match("https://bosch.wd12.myworkdayjobs.com/careers")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "bosch")
        self.assertEqual(m.group(2), "careers")

    # ── No-wd-prefix format (newly supported) ───────────────────────────────
    def test_no_wd_prefix(self):
        m = self.REGEX.match("https://adobe.myworkdayjobs.com/external_experienced")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "adobe")
        self.assertEqual(m.group(2), "external_experienced")

    def test_no_wd_prefix_simple(self):
        m = self.REGEX.match("https://company.myworkdayjobs.com/careers")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "company")
        self.assertEqual(m.group(2), "careers")

    # ── URLs with query params and fragments ─────────────────────────────────
    def test_url_with_query_params(self):
        m = self.REGEX.match("https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite?q=tpm&loc=US")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "nvidia")
        self.assertEqual(m.group(2), "NVIDIAExternalCareerSite")

    def test_url_with_fragment(self):
        m = self.REGEX.match("https://adobe.myworkdayjobs.com/external_experienced#results")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "adobe")
        self.assertEqual(m.group(2), "external_experienced")

    def test_url_with_query_and_fragment(self):
        m = self.REGEX.match("https://company.wd3.myworkdayjobs.com/jobs?page=2#section")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "company")
        self.assertEqual(m.group(2), "jobs")

    def test_no_wd_prefix_with_query(self):
        m = self.REGEX.match("https://company.myworkdayjobs.com/jobs?search=tpm")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "company")
        self.assertEqual(m.group(2), "jobs")

    # ── Invalid URLs ─────────────────────────────────────────────────────────
    def test_invalid_no_site_slug(self):
        """URL without a site path segment should not match."""
        m = self.REGEX.match("https://company.wd5.myworkdayjobs.com/")
        # The regex requires at least one char in group(2), so /  alone won't match
        self.assertIsNone(m)

    def test_invalid_different_domain(self):
        m = self.REGEX.match("https://company.wd5.notworkday.com/careers")
        self.assertIsNone(m)

    def test_invalid_http_scheme(self):
        m = self.REGEX.match("http://company.wd5.myworkdayjobs.com/careers")
        self.assertIsNone(m)


# ─────────────────────────────────────────────────────────────────────────────
class TestFetchWorkdayJobsStandardURL(unittest.TestCase):
    """_fetch_workday_jobs with standard wd-prefix URL: regex + API URL + base URL."""

    @patch("agents.job_agent.requests.post")
    def test_standard_url_api_call(self, mock_post):
        """Standard URL should produce correct API URL with original host."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"jobPostings": [
            {"externalPath": "/job/SF/TPM/12345", "title": "Technical Program Manager",
             "locationsText": "San Francisco, CA"},
        ]}
        mock_post.return_value = mock_resp

        url = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"
        result = _fetch_workday_jobs(url)

        # Verify API URL preserves original host
        called_url = mock_post.call_args[0][0]
        self.assertEqual(called_url,
                         "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs")

        # Verify results
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Technical Program Manager")
        self.assertTrue(result[0]["url"].startswith("https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"))
        self.assertTrue(result[0]["_workday"])

    @patch("agents.job_agent.requests.post")
    def test_standard_wd1_url(self, mock_post):
        """wd1 variant should work identically."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"jobPostings": []}
        mock_post.return_value = mock_resp

        _fetch_workday_jobs("https://salesforce.wd1.myworkdayjobs.com/External")
        called_url = mock_post.call_args[0][0]
        self.assertEqual(called_url,
                         "https://salesforce.wd1.myworkdayjobs.com/wday/cxs/salesforce/External/jobs")

    @patch("agents.job_agent.requests.post")
    def test_standard_wd12_url(self, mock_post):
        """Double-digit wd number should work."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"jobPostings": []}
        mock_post.return_value = mock_resp

        _fetch_workday_jobs("https://bosch.wd12.myworkdayjobs.com/careers")
        called_url = mock_post.call_args[0][0]
        self.assertEqual(called_url,
                         "https://bosch.wd12.myworkdayjobs.com/wday/cxs/bosch/careers/jobs")


# ─────────────────────────────────────────────────────────────────────────────
class TestFetchWorkdayJobsNoWdPrefix(unittest.TestCase):
    """_fetch_workday_jobs with no-wd-prefix URL format (REQ-061 core change)."""

    @patch("agents.job_agent.requests.post")
    def test_no_wd_prefix_api_call(self, mock_post):
        """No-wd-prefix URL should produce correct API URL."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"jobPostings": [
            {"externalPath": "/job/NY/TPM/67890", "title": "Sr TPM",
             "locationsText": "New York, NY"},
        ]}
        mock_post.return_value = mock_resp

        url = "https://adobe.myworkdayjobs.com/external_experienced"
        result = _fetch_workday_jobs(url)

        # Verify API URL uses original host (no wd prefix)
        called_url = mock_post.call_args[0][0]
        self.assertEqual(called_url,
                         "https://adobe.myworkdayjobs.com/wday/cxs/adobe/external_experienced/jobs")

        # Verify result URLs use original host
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["url"].startswith("https://adobe.myworkdayjobs.com/external_experienced"))

    @patch("agents.job_agent.requests.post")
    def test_no_wd_prefix_base_url(self, mock_post):
        """Base URL for job links should preserve the no-wd-prefix host."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"jobPostings": [
            {"externalPath": "/job/US/TPM/11111", "title": "TPM", "locationsText": "Remote"},
        ]}
        mock_post.return_value = mock_resp

        result = _fetch_workday_jobs("https://company.myworkdayjobs.com/careers")
        self.assertEqual(result[0]["url"], "https://company.myworkdayjobs.com/careers/job/US/TPM/11111")


# ─────────────────────────────────────────────────────────────────────────────
class TestFetchWorkdayJobsQueryAndFragment(unittest.TestCase):
    """URLs with query parameters and fragments should be parsed correctly."""

    @patch("agents.job_agent.requests.post")
    def test_query_params_stripped_from_site_slug(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"jobPostings": []}
        mock_post.return_value = mock_resp

        _fetch_workday_jobs("https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite?q=tpm")
        called_url = mock_post.call_args[0][0]
        self.assertIn("/NVIDIAExternalCareerSite/jobs", called_url)
        self.assertNotIn("?", called_url)

    @patch("agents.job_agent.requests.post")
    def test_fragment_stripped_from_site_slug(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"jobPostings": []}
        mock_post.return_value = mock_resp

        _fetch_workday_jobs("https://adobe.myworkdayjobs.com/external_experienced#results")
        called_url = mock_post.call_args[0][0]
        self.assertIn("/external_experienced/jobs", called_url)
        self.assertNotIn("#", called_url)


# ─────────────────────────────────────────────────────────────────────────────
class TestFetchWorkdayJobsInvalidURL(unittest.TestCase):
    """Invalid URLs should return empty list without crashing."""

    def test_non_workday_url(self):
        result = _fetch_workday_jobs("https://example.com/careers")
        self.assertEqual(result, [])

    def test_workday_url_without_site(self):
        result = _fetch_workday_jobs("https://company.wd5.myworkdayjobs.com/")
        self.assertEqual(result, [])

    def test_empty_string(self):
        result = _fetch_workday_jobs("")
        self.assertEqual(result, [])

    @patch("agents.job_agent.requests.post")
    def test_api_returns_non_200(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_post.return_value = mock_resp

        result = _fetch_workday_jobs("https://company.myworkdayjobs.com/careers")
        self.assertEqual(result, [])

    @patch("agents.job_agent.requests.post")
    def test_api_raises_exception(self, mock_post):
        mock_post.side_effect = Exception("Connection timeout")

        result = _fetch_workday_jobs("https://company.myworkdayjobs.com/careers")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
