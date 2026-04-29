"""Shared configuration constants."""
import os

MODEL = "gemini-3.1-flash-lite-preview"

AUTO_ARCHIVE_THRESHOLD = 3  # consecutive no-TPM runs before auto-archiving a company

# Computed independently to avoid importing from shared.excel_store (which itself
# imports config). Resolves to <repo root>/jd_cache.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JD_CACHE_DIR = os.path.join(_PROJECT_ROOT, "jd_cache")
