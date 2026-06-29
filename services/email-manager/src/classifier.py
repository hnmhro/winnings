"""E-Mail-Klassifizierung via Claude AI (Scraper-Analyzer wird wiederverwendet)."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "services", "scraper", "src"))

from analyzer import classify_email  # noqa: F401
