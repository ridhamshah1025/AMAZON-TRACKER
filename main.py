#!/usr/bin/env python3
"""Amazon.ca used-offer tracker for CATAN 6th Edition."""

from __future__ import annotations

import argparse
import os
import sys

from pathlib import Path

from tracker.amazon import AmazonFetchError, check_used_from_html, check_used_offers
from tracker.notify import send_notifications
from tracker.state import should_notify, update_state

DEFAULT_ASIN = "B0DYK1ZH2D"
TEST_ASIN = "B0DDL4LNMT"
PRODUCT_NAMES = {
    "B0DYK1ZH2D": "CATAN 6th Edition",
    "B0DDL4LNMT": "Minecraft Labyrinth (test)",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Amazon.ca for used offers")
    parser.add_argument(
        "--asin",
        default=os.environ.get("TARGET_ASIN", DEFAULT_ASIN),
        help="Amazon ASIN to check",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help=f"Use test ASIN ({TEST_ASIN}) with known used offers",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check and print results without saving state or sending alerts",
    )
    parser.add_argument(
        "--force-notify",
        action="store_true",
        help="Send notification even if already notified (for testing)",
    )
    parser.add_argument(
        "--html-file",
        type=Path,
        help="Parse saved HTML instead of fetching Amazon (offline test)",
    )
    args = parser.parse_args()

    asin = TEST_ASIN if args.test else args.asin
    product_name = PRODUCT_NAMES.get(asin, f"Product {asin}")

    print(f"Checking ASIN {asin} ({product_name})...")

    try:
        if args.html_file:
            html = args.html_file.read_text(encoding="utf-8", errors="replace")
            result = check_used_from_html(html, asin, source=str(args.html_file))
        else:
            result = check_used_offers(asin)
    except AmazonFetchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if result.fetch_errors:
        for err in result.fetch_errors:
            print(f"Warning: {err}")

    if result.has_used:
        print(f"USED offers found ({len(result.offers)}):")
        for o in result.offers:
            parts = [o.condition]
            if o.price:
                parts.append(o.price)
            if o.seller:
                parts.append(f"— {o.seller}")
            print(f"  - {' '.join(parts)} [{o.source}]")
    else:
        print("No used offers detected.")

    if args.dry_run:
        if result.has_used:
            print("\n--- Notification preview ---")
            send_notifications(result, product_name, dry_run=True)
        return 0

    notify = result.has_used and (args.force_notify or should_notify(asin, result.has_used))

    if notify:
        print("Sending notification (new used availability)...")
        channels = send_notifications(result, product_name)
        print(f"Notified via: {', '.join(channels)}")
        update_state(asin, has_used=True, notified=True)
    else:
        if result.has_used:
            print("Used offers present but already notified; skipping.")
        update_state(asin, has_used=result.has_used, notified=False)

    return 0


if __name__ == "__main__":
    sys.exit(main())
