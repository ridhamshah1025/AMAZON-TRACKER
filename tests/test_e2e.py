"""End-to-end tests: parser fixtures, state dedup, live Amazon (when reachable)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tracker.amazon import AmazonFetchError, check_used_from_html, check_used_offers
from tracker.notify import send_notifications
from tracker.state import load_state, should_notify, update_state

ROOT = Path(__file__).resolve().parent.parent
TEST_ASIN = "B0DDL4LNMT"
PROD_ASIN = "B0DYK1ZH2D"

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
MINECRAFT_FIXTURE = FIXTURE_DIR / "minecraft_used.html"
CATAN_FIXTURE = FIXTURE_DIR / "catan_new_only.html"

USED_FIXTURE = """
<html><body>
<div id="usedAccordionRow">
  <div id="usedAccordionCaption_feature_div">
    <span class="a-text-bold"> Save with Used - Like New </span>
  </div>
  <div data-csa-c-buying-option-type="USED"></div>
  <span class="a-size-small"> Sold by: </span><span class="a-size-small"> Warehouse Deals </span>
</div>
</body></html>
"""

NEW_ONLY_FIXTURE = """
<html><body><span>New (3) from $56.95</span></body></html>
"""


class TestFixtureE2E(unittest.TestCase):
    """E2E with saved HTML snapshots."""

    def test_minecraft_fixture_detects_used(self):
        self.assertTrue(MINECRAFT_FIXTURE.exists(), f"Missing {MINECRAFT_FIXTURE}")
        html = MINECRAFT_FIXTURE.read_text(encoding="utf-8", errors="replace")
        result = check_used_from_html(html, TEST_ASIN, source="minecraft-fixture")
        self.assertTrue(
            result.has_used,
            "Minecraft test product must detect used offers",
        )
        self.assertGreater(len(result.offers), 0)
        conditions = " ".join(o.condition for o in result.offers).lower()
        self.assertIn("used", conditions)

    def test_catan_fixture_no_used(self):
        self.assertTrue(CATAN_FIXTURE.exists(), f"Missing {CATAN_FIXTURE}")
        html = CATAN_FIXTURE.read_text(encoding="utf-8", errors="replace")
        result = check_used_from_html(html, PROD_ASIN, source="catan-fixture")
        self.assertFalse(
            result.has_used,
            "CATAN fixture should have no used offers",
        )


class TestStateE2E(unittest.TestCase):
    def test_notify_only_on_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            self.assertTrue(should_notify(PROD_ASIN, True, state_path))
            update_state(PROD_ASIN, has_used=True, notified=True, path=state_path)
            self.assertFalse(
                should_notify(PROD_ASIN, True, state_path),
                "Should not re-notify while still used",
            )
            update_state(PROD_ASIN, has_used=False, path=state_path)
            self.assertTrue(
                should_notify(PROD_ASIN, True, state_path),
                "Should notify again after used disappears then returns",
            )


class TestNotifyE2E(unittest.TestCase):
    def test_dry_run_notification(self):
        result = check_used_from_html(USED_FIXTURE, TEST_ASIN)
        with patch("sys.stdout") as _:
            channels = send_notifications(
                result, "Minecraft Labyrinth (test)", dry_run=True
            )
        self.assertEqual(channels, ["dry-run"])


class TestLiveAmazonE2E(unittest.TestCase):
    """Live fetch against Amazon.ca — skipped if blocked."""

    def test_live_minecraft_has_used(self):
        try:
            result = check_used_offers(TEST_ASIN)
        except AmazonFetchError as exc:
            self.skipTest(f"Amazon blocked live fetch: {exc}")
        self.assertTrue(
            result.has_used,
            f"Test ASIN {TEST_ASIN} should have used offers. "
            f"Errors: {result.fetch_errors}",
        )

    def test_live_catan_check_runs(self):
        try:
            result = check_used_offers(PROD_ASIN)
        except AmazonFetchError as exc:
            self.skipTest(f"Amazon blocked live fetch: {exc}")
        # Production may or may not have used; we only assert fetch succeeded
        self.assertIsNotNone(result.asin)


if __name__ == "__main__":
    unittest.main(verbosity=2)
