"""Unit tests for used-offer HTML parsing (no live Amazon requests)."""

import unittest

from tracker.amazon import check_used_from_html, parse_used_from_html

USED_FIXTURE = """
<html><body>
<div id="usedAccordionRow" data-a-accordion-row-name="usedAccordionRow">
  <div id="usedAccordionCaption_feature_div">
    <span class="a-text-bold"> Save with Used - Like New </span>
  </div>
  <div data-csa-c-buying-option-type="USED">
    <span class="a-price"><span class="a-offscreen">$24.99</span></span>
  </div>
  <div class="a-row"><span class="a-size-small"> Sold by: </span>
    <span class="a-size-small"> Warehouse Deals </span></div>
</div>
</body></html>
"""

NEW_ONLY_FIXTURE = """
<html><body>
<div id="newAccordionRow_0">
  <span>New (3) from $56.95</span>
</div>
<p>Other sellers on Amazon</p>
<p>New (3) from $56.95 & FREE Shipping.</p>
</body></html>
"""

AOD_FIXTURE = """
<html><body>
<div id="aod-offer" class="aod-offer">
  <span>Used - Good</span>
  <span class="a-price">$19.99</span>
  <span>Sold by: Some Seller</span>
</div>
</body></html>
"""


class TestParser(unittest.TestCase):
    def test_detects_used_accordion(self):
        offers = parse_used_from_html(USED_FIXTURE, "fixture")
        self.assertTrue(len(offers) >= 1)
        self.assertIn("Used", offers[0].condition)

    def test_no_used_on_new_only_page(self):
        offers = parse_used_from_html(NEW_ONLY_FIXTURE, "fixture")
        self.assertEqual(offers, [])

    def test_aod_used_offer(self):
        offers = parse_used_from_html(AOD_FIXTURE, "aod-ajax")
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].condition, "Used - Good")
        self.assertEqual(offers[0].price, "$19.99")

    def test_check_used_from_html(self):
        result = check_used_from_html(USED_FIXTURE, "B0DDL4LNMT")
        self.assertTrue(result.has_used)
        result2 = check_used_from_html(NEW_ONLY_FIXTURE, "B0DYK1ZH2D")
        self.assertFalse(result2.has_used)


if __name__ == "__main__":
    unittest.main()
