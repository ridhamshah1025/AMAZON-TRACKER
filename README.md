# Amazon CATAN Used-Offer Tracker

Monitors [CATAN 6th Edition on Amazon.ca](https://www.amazon.ca/dp/B0DYK1ZH2D) for **used** buying options (Warehouse Deals / "See All Buying Options") and alerts you when they appear.

Runs automatically every **2 hours** via GitHub Actions (at **:17** past even hours **UTC** — e.g. 12:17, 2:17, 4:17 UTC).

## How it works

1. Fetches the product page, offer-listing page, and All Offers Display (AOD) ajax endpoint.
2. Detects used offers (`usedAccordionRow`, "Save with Used", AOD used rows, etc.).
3. Sends an alert **only when used stock newly appears** (not on every run).
4. Default notification: **GitHub Issue** (emails you if you watch the repo).

## Setup (one-time)

1. Push this repo to GitHub (`ridhamshah1025/AMAZON-TRACKER`).
2. On GitHub, click **Watch → Custom → Issues** so new issues email you.
3. Enable GitHub Actions (Settings → Actions → Allow).
4. Run the workflow manually once: **Actions → Check Amazon Used Offers → Run workflow**.

### Optional notifications

| Secret | Purpose |
|--------|---------|
| `NTFY_TOPIC` | Push alerts to [ntfy.sh](https://ntfy.sh) (install app, subscribe to your topic) |
| `DISCORD_WEBHOOK_URL` | Post to a Discord channel |

No Gmail or SMTP setup required for the default GitHub Issue alerts.

## Local testing

```bash
pip install -r requirements.txt

# Test product with known used offers (Minecraft)
python main.py --test --dry-run

# Production product (CATAN)
python main.py --dry-run

# Force a test notification on GitHub (needs GITHUB_TOKEN + GITHUB_REPOSITORY)
python main.py --test --force-notify

# Parse a saved Amazon HTML page (offline, no network)
python main.py --html-file saved-page.html --dry-run
```

Parser unit tests (no network):

```bash
python -m unittest tests.test_parser -v
```

Full end-to-end test (fixtures + state + CLI; live Amazon optional):

```bash
./scripts/run_e2e.sh
```

## Test vs production ASINs

| ASIN | Product | Expected |
|------|---------|----------|
| `B0DYK1ZH2D` | CATAN 6th Edition | Monitored in production |
| `B0DDL4LNMT` | Minecraft Labyrinth | Test ASIN (`--test`) — has used offers |

## Scheduled runs not showing?

The cron is already in the workflow — you do **not** add a separate cron in GitHub settings.

1. **Wait for the next slot** — After the first push, the first scheduled run is usually at the **next even hour, minute 17 UTC** (not immediately). Manual runs show as `workflow_dispatch`; scheduled runs show as **`schedule`**.
2. **Check the right place** — **Actions** → click **Check Amazon Used Offers** in the left list → runs appear on the right with a **schedule** badge.
3. **Yellow banner** — If Actions shows “Scheduled workflows are disabled”, click **Enable**.
4. **Repo Settings** → **Actions** → **General** → **Workflow permissions** → **Read and write permissions** (needed for the state-file commit step).
5. **UTC times** — Alberta (MDT) is UTC−6. Example: **2:17 UTC** = **8:17 PM MDT** the previous calendar day.

Convert your local time: https://crontab.guru/#17_*/2_*_*_*

## Amazon blocking

GitHub Actions runners use datacenter IPs. Amazon may return CAPTCHAs or block requests. If workflows fail with fetch errors:

- Re-run manually later.
- Consider adding `NTFY_TOPIC` for faster awareness of failures.
- A future upgrade could use Playwright (heavier, slower).

## Files

- `main.py` — CLI entry point
- `tracker/amazon.py` — fetch and parse logic
- `tracker/notify.py` — GitHub Issue / ntfy / Discord
- `tracker/state.py` — deduplication state
- `.tracker-state.json` — persisted between runs
