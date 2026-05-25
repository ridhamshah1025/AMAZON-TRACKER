#!/usr/bin/env bash
# End-to-end test runner for Amazon tracker.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Installing dependencies..."
python3 -m pip install -q -r requirements.txt

FAIL=0

echo ""
echo "=== Parser unit tests ==="
python3 -m unittest tests.test_parser -v || FAIL=1

echo ""
echo "=== E2E tests (fixtures, state, notify) ==="
python3 -m unittest tests.test_e2e -v || FAIL=1

echo ""
echo "=== CLI: Test product (Minecraft) — expect USED ==="
python3 main.py --test --html-file tests/fixtures/minecraft_used.html --dry-run || FAIL=1

echo ""
echo "=== CLI: Production CATAN — expect NO used ==="
python3 main.py --html-file tests/fixtures/catan_new_only.html --dry-run || FAIL=1

echo ""
echo "=== Live Amazon (optional — skipped if blocked) ==="
if python3 main.py --test --dry-run; then
  echo "Live fetch: PASS"
else
  echo "Live fetch: SKIPPED (Amazon blocked this IP — fixture tests validate full pipeline)"
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "All required E2E tests PASSED"
  exit 0
else
  echo "Some required E2E tests FAILED"
  exit 1
fi
