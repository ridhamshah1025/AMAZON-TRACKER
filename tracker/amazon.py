"""Fetch and parse Amazon.ca pages for used buying options."""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.amazon.ca"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

USED_SIGNALS = [
    "usedaccordionrow",
    'data-csa-c-buying-option-type="used"',
    "save with used",
    "used - like new",
    "used - good",
    "used - very good",
    "used - acceptable",
    "condition: used",
    "buying-option-type=used",
]

BLOCKED_MARKERS = [
    "opfcaptcha",
    "automated access to amazon",
    "sorry, we just need to make sure you're not a robot",
    "type the characters you see",
    "robot check",
    "enter the characters you see below",
]
MIN_PRODUCT_PAGE_BYTES = 50_000


@dataclass
class UsedOffer:
    condition: str
    price: Optional[str]
    seller: Optional[str]
    source: str


@dataclass
class CheckResult:
    asin: str
    has_used: bool
    offers: list[UsedOffer]
    product_url: str
    fetch_errors: list[str] = field(default_factory=list)
    blocked: bool = False


class AmazonFetchError(Exception):
    """All fetch attempts failed or were blocked."""

    def __init__(self, message: str, *, blocked: bool = False):
        super().__init__(message)
        self.blocked = blocked


def product_url(asin: str) -> str:
    return f"{BASE_URL}/dp/{asin}"


def offer_listing_url(asin: str) -> str:
    return f"{BASE_URL}/gp/offer-listing/{asin}/ref=olp_tab_all"


def aod_ajax_urls(asin: str) -> list[str]:
    return [
        f"{BASE_URL}/gp/aod/ajax/ref=dp_aod_unknown_m1?asin={asin}&pc=dp",
        f"{BASE_URL}/gp/aod/ajax/ref=aod_page_old?asin={asin}",
        f"{BASE_URL}/gp/product/ajax/ref=auto_load_aod?asin={asin}&pc=dp",
    ]


def _is_blocked(html: str, status_code: int, source: str = "") -> bool:
    if status_code in (403, 503):
        return True
    lower = html.lower()
    if any(marker in lower for marker in BLOCKED_MARKERS):
        return True
    if source == "product" and len(html) < MIN_PRODUCT_PAGE_BYTES:
        return True
    return False


def _build_session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update(DEFAULT_HEADERS)
    return sess


def _warmup_session(sess: requests.Session) -> None:
    try:
        sess.get(f"{BASE_URL}/", timeout=30)
        time.sleep(random.uniform(1.5, 3.0))
    except requests.RequestException:
        pass


def _fetch_with_source(
    session: requests.Session,
    url: str,
    source: str,
    retries: int = 3,
) -> tuple[str, int]:
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            resp = session.get(url, timeout=45)
            if _is_blocked(resp.text, resp.status_code, source=source):
                raise AmazonFetchError(
                    f"Blocked at {url} (status {resp.status_code})", blocked=True
                )
            resp.raise_for_status()
            return resp.text, resp.status_code
        except (requests.RequestException, AmazonFetchError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep((2**attempt) + random.uniform(0.5, 1.5))
    raise AmazonFetchError(f"Failed to fetch {url}: {last_error}") from last_error


def _fetch_with_playwright(url: str) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                user_agent=DEFAULT_HEADERS["User-Agent"],
                locale="en-CA",
                timezone_id="America/Edmonton",
            )
            page = context.new_page()
            page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(1.0, 2.0))
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(1.0, 2.0))
            html = page.content()
        finally:
            browser.close()
    if _is_blocked(html, 200, source="product"):
        raise AmazonFetchError(f"Blocked at {url} (playwright)", blocked=True)
    return html


def _fetch_url(
    session: requests.Session,
    url: str,
    source: str,
    use_playwright_fallback: bool = True,
) -> str:
    try:
        html, _ = _fetch_with_source(session, url, source)
        return html
    except AmazonFetchError as exc:
        if not use_playwright_fallback or not exc.blocked:
            raise
        print(f"Requests blocked for {url}, trying Playwright...")
        return _fetch_with_playwright(url)


def check_used_from_html(html: str, asin: str, source: str = "fixture") -> CheckResult:
    """Check used offers from saved HTML (for tests and offline validation)."""
    offers = _parse_used_from_html(html, source)
    return CheckResult(
        asin=asin,
        has_used=len(offers) > 0,
        offers=offers,
        product_url=product_url(asin),
        fetch_errors=[],
        blocked=False,
    )


def _extract_prices(text: str) -> list[str]:
    return re.findall(r"\$\d+(?:\.\d{2})?", text)


def parse_used_from_html(html: str, source: str) -> list[UsedOffer]:
    """Public parser for HTML (also used by unit tests)."""
    return _parse_used_from_html(html, source)


def _parse_used_from_html(html: str, source: str) -> list[UsedOffer]:
    offers: list[UsedOffer] = []
    soup = BeautifulSoup(html, "html.parser")
    lower_html = html.lower()

    if "usedaccordionrow" in lower_html or 'buying-option-type="used"' in lower_html:
        condition = "Used"
        caption = soup.find(id="usedAccordionCaption_feature_div")
        if caption:
            text = caption.get_text(" ", strip=True)
            if text:
                condition = text
        price_el = soup.select_one(
            "#usedAccordionRow .a-price .a-offscreen, "
            "#usedAccordionRow .a-price-whole"
        )
        price = price_el.get_text(strip=True) if price_el else None
        if not price:
            row = soup.find(id="usedAccordionRow")
            prices = _extract_prices(row.get_text(" ", strip=True) if row else "")
            price = prices[0] if prices else None
        seller = None
        for row in soup.select("#usedAccordionRow .a-row"):
            t = row.get_text(" ", strip=True)
            if "Sold by:" in t or "Warehouse" in t:
                seller = t
                break
        offers.append(
            UsedOffer(condition=condition, price=price, seller=seller, source=source)
        )

    for block in soup.select("#aod-offer, .aod-offer, #olpOfferList .a-row"):
        text = block.get_text(" ", strip=True)
        lower = text.lower()
        if "used" not in lower:
            continue
        condition = "Used"
        for phrase in (
            "Used - Like New",
            "Used - Very Good",
            "Used - Good",
            "Used - Acceptable",
            "Save with Used",
        ):
            if phrase.lower() in lower:
                condition = phrase
                break
        prices = _extract_prices(text)
        seller = None
        if "sold by" in lower:
            m = re.search(r"Sold by:\s*([^|]+)", text, re.I)
            if m:
                seller = m.group(1).strip()
        offers.append(
            UsedOffer(
                condition=condition,
                price=prices[0] if prices else None,
                seller=seller,
                source=source,
            )
        )

    if not offers and any(sig in lower_html for sig in USED_SIGNALS):
        prices = _extract_prices(html)
        offers.append(
            UsedOffer(
                condition="Used (detected in page)",
                price=prices[0] if prices else None,
                seller=None,
                source=source,
            )
        )

    seen: set[tuple] = set()
    unique: list[UsedOffer] = []
    for o in offers:
        key = (o.condition, o.price, o.seller)
        if key not in seen:
            seen.add(key)
            unique.append(o)
    return unique


def check_used_offers(
    asin: str,
    session: Optional[requests.Session] = None,
    use_playwright_fallback: bool = True,
) -> CheckResult:
    """Check product page, offer listing, and AOD ajax for used offers."""
    sess = session or _build_session()
    _warmup_session(sess)

    fetch_targets: list[tuple[str, str]] = [
        ("product", product_url(asin)),
        ("offer-listing", offer_listing_url(asin)),
    ]
    for i, aod_url in enumerate(aod_ajax_urls(asin)):
        fetch_targets.append((f"aod-ajax-{i}", aod_url))

    all_offers: list[UsedOffer] = []
    errors: list[str] = []
    any_success = False
    all_blocked = True

    for source, url in fetch_targets:
        try:
            time.sleep(random.uniform(2.0, 4.0))
            html = _fetch_url(sess, url, source, use_playwright_fallback)
            any_success = True
            all_blocked = False
            found = _parse_used_from_html(html, source)
            all_offers.extend(found)
        except AmazonFetchError as exc:
            errors.append(str(exc))
            if not exc.blocked:
                all_blocked = False

    if not any_success:
        raise AmazonFetchError(
            f"All sources failed for ASIN {asin}: {'; '.join(errors)}",
            blocked=all_blocked,
        )

    seen: set[tuple] = set()
    unique: list[UsedOffer] = []
    for o in all_offers:
        key = (o.condition, o.price, o.seller, o.source)
        if key not in seen:
            seen.add(key)
            unique.append(o)

    return CheckResult(
        asin=asin,
        has_used=len(unique) > 0,
        offers=unique,
        product_url=product_url(asin),
        fetch_errors=errors,
        blocked=False,
    )
