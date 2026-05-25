"""Send alerts via GitHub Issues, ntfy, or Discord."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional

from tracker.amazon import CheckResult


def _format_message(result: CheckResult, product_name: str = "CATAN 6th Edition") -> str:
    lines = [
        f"**Used offer detected** for {product_name}",
        "",
        f"- **ASIN:** {result.asin}",
        f"- **Product:** {result.product_url}",
        f"- **Offer listing:** https://www.amazon.ca/gp/offer-listing/{result.asin}",
        "",
    ]
    if result.offers:
        lines.append("**Offers:**")
        for i, o in enumerate(result.offers, 1):
            parts = [f"{i}. {o.condition}"]
            if o.price:
                parts.append(f"— {o.price}")
            if o.seller:
                parts.append(f"({o.seller})")
            parts.append(f"[{o.source}]")
            lines.append(" ".join(parts))
    else:
        lines.append("_Used availability detected (details unavailable)._")
    if result.fetch_errors:
        lines.extend(["", "**Fetch warnings:**", *[f"- {e}" for e in result.fetch_errors]])
    return "\n".join(lines)


def notify_github_issue(
    result: CheckResult,
    product_name: str = "CATAN 6th Edition",
    token: Optional[str] = None,
    repo: Optional[str] = None,
) -> None:
    token = token or os.environ.get("GITHUB_TOKEN")
    repo = repo or os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        raise RuntimeError("GITHUB_TOKEN and GITHUB_REPOSITORY required for issue notifications")

    title = f"Used offer: {product_name} ({result.asin})"
    body = _format_message(result, product_name)
    payload = json.dumps({"title": title, "body": body}).encode("utf-8")
    url = f"https://api.github.com/repos/{repo}/issues"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status not in (200, 201):
            raise RuntimeError(f"GitHub API returned {resp.status}")


def notify_ntfy(
    result: CheckResult,
    topic: Optional[str] = None,
    product_name: str = "CATAN 6th Edition",
) -> None:
    topic = topic or os.environ.get("NTFY_TOPIC")
    if not topic:
        return
    title = f"Used {product_name} on Amazon.ca"
    body = _format_message(result, product_name)
    url = f"https://ntfy.sh/{topic}"
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={"Title": title, "Priority": "high", "Tags": "amazon,used"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=15)


def notify_discord(
    result: CheckResult,
    webhook_url: Optional[str] = None,
    product_name: str = "CATAN 6th Edition",
) -> None:
    webhook_url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    content = _format_message(result, product_name)[:2000]
    payload = json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=15)


def send_notifications(
    result: CheckResult,
    product_name: str = "CATAN 6th Edition",
    dry_run: bool = False,
) -> list[str]:
    """Send all configured notifications. Returns list of channels used."""
    if dry_run:
        print(_format_message(result, product_name))
        return ["dry-run"]

    channels: list[str] = []
    if os.environ.get("GITHUB_TOKEN") and os.environ.get("GITHUB_REPOSITORY"):
        notify_github_issue(result, product_name)
        channels.append("github-issue")

    try:
        if os.environ.get("NTFY_TOPIC"):
            notify_ntfy(result, product_name=product_name)
            channels.append("ntfy")
    except (urllib.error.URLError, OSError) as exc:
        print(f"Warning: ntfy notification failed: {exc}")

    try:
        if os.environ.get("DISCORD_WEBHOOK_URL"):
            notify_discord(result, product_name=product_name)
            channels.append("discord")
    except (urllib.error.URLError, OSError) as exc:
        print(f"Warning: Discord notification failed: {exc}")

    if not channels:
        print(_format_message(result, product_name))
        channels.append("stdout")
    return channels
