#!/usr/bin/env python3
"""
Verify that pushing from a parent listing updates a child (update_children=True).

Usage (from repo root, with .env / PRICELABS_API_KEY set):

  ./venv/bin/python scripts/test_parent_child_push.py \\
    --parent PARENT_LISTING_ID --child CHILD_LISTING_ID \\
    --date 2026-12-01 --price 500 --pms guesty

  # Fetch only (no push):
  ./venv/bin/python scripts/test_parent_child_push.py --dry-run ...

Pick a date far in the future you can revert in PriceLabs if needed.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from rates.api_client import PriceLabsAPI
from rates.push.push_rates import push_rates_to_pricelabs


def _override_for_date(overrides_payload: dict, target_date: str) -> Optional[Dict]:
    rows = overrides_payload.get("overrides") or []
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("date") == target_date:
            return row
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Test parent push -> child override propagation")
    ap.add_argument("--parent", required=True, help="PriceLabs parent listing ID")
    ap.add_argument("--child", required=True, help="PriceLabs child listing ID to check")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--price", type=float, default=None, help="Test fixed price (required unless --dry-run)")
    ap.add_argument("--pms", default="guesty", help="PMS (default guesty)")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Only GET child overrides; do not push",
    )
    args = ap.parse_args()
    if not args.dry_run and args.price is None:
        ap.error("--price is required unless --dry-run")

    api = PriceLabsAPI()
    before = api.get_listing_overrides(args.child, pms=args.pms)
    print("=== Child GET /overrides (before), row for date ===")
    print(json.dumps(_override_for_date(before, args.date), indent=2))

    if args.dry_run:
        print("Dry-run: no push.")
        return

    result = push_rates_to_pricelabs(
        listing_id=args.parent,
        rates=[{"date": args.date, "price": args.price}],
        pms=args.pms,
    )
    print("=== push_rates_to_pricelabs result ===")
    print(json.dumps(result, indent=2, default=str))
    if not result.get("success"):
        sys.exit(1)

    after = api.get_listing_overrides(args.child, pms=args.pms)
    row = _override_for_date(after, args.date)
    print("=== Child GET /overrides (after), row for date ===")
    print(json.dumps(row, indent=2))
    if row is None:
        print(
            "No override row for that date on the child yet. "
            "Confirm parent/child linkage in PriceLabs or response shape (see raw keys below)."
        )
        print("Keys in response:", list(after.keys()) if isinstance(after, dict) else type(after))


if __name__ == "__main__":
    main()
