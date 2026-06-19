#!/usr/bin/env python3
"""
Apply rules-adjuster logic and push changes for onera, wb1 (wmb), and flo1 (flohom).

Run from project root:
    python scripts/rules_adjuster_automation.py
    python scripts/rules_adjuster_automation.py --dry-run
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv

load_dotenv(_project_root / ".env")

from rates.push.push_rates import push_rates_batch
from utils import backend_interface
from utils.date_manager import get_full_calculation_range, get_ui_default_range
from utils.rules_adjuster import apply_rules_to_live_rates

# Config keys in properties.yaml (aliases: wmb -> wb1, flohom -> flo1)
RULES_AUTOMATION_PROPERTIES = ["onera", "wb1", "flo1"]
PROPERTY_ALIASES = {"wmb": "wb1", "flohom": "flo1", "onera": "onera"}

LOG_DIR = _project_root / "logs"
RULES_LOG = LOG_DIR / "rules_adjuster_automation_summary.txt"


def resolve_property_keys(keys: Optional[List[str]] = None) -> List[str]:
    raw = keys or RULES_AUTOMATION_PROPERTIES
    resolved = []
    for key in raw:
        mapped = PROPERTY_ALIASES.get(key, key)
        if mapped not in resolved:
            resolved.append(mapped)
    return resolved


def get_currency_for_listing(listing_id: str, property_key: str, date_str: str) -> str:
    override_path = _project_root / "data" / property_key / f"{property_key}_nightly_pulled_overrides.csv"
    if override_path.exists():
        try:
            override_df = pd.read_csv(override_path)
            if "currency" in override_df.columns:
                match = override_df[
                    (override_df["listing_id"].astype(str) == str(listing_id))
                    & (override_df["date"] == date_str)
                ]
                if not match.empty:
                    currency = match.iloc[0]["currency"]
                    if pd.notna(currency) and currency:
                        return str(currency)
        except Exception:
            pass
    return "USD"


def load_rate_data_for_rules(property_keys: List[str]) -> Optional[pd.DataFrame]:
    """Load and filter rate data the same way the Streamlit app does for rules."""
    full_start, full_end = get_full_calculation_range()
    ui_start, ui_end = get_ui_default_range()

    print(f"📅 Generating rates for rules check: {ui_start} to {ui_end}")
    print(f"   (full calculation range: {full_start} to {full_end})")

    generated_df = backend_interface.trigger_rate_generation(
        property_selection=property_keys,
        start_date=full_start,
        end_date=full_end,
    )
    if generated_df is None or generated_df.empty:
        return None

    generated_df = generated_df.copy()
    generated_df["Date"] = pd.to_datetime(generated_df["Date"])
    filtered_df = generated_df[
        (generated_df["Date"].dt.date >= ui_start) & (generated_df["Date"].dt.date <= ui_end)
    ].copy()
    filtered_df["Date"] = filtered_df["Date"].dt.strftime("%Y-%m-%d")
    print(f"✅ Loaded {len(filtered_df)} rows for rules adjuster")
    return filtered_df


def prepare_rates_to_push(adjusted_rates: List[dict]) -> Dict[str, List[dict]]:
    """Build push payload using the same merge logic as the Streamlit table-view push."""
    rates_to_push: Dict[str, dict] = {}

    for rate in adjusted_rates:
        if not rate.get("change_applied", False):
            continue
        if rate["new_price"] == rate["original_price"] and rate["new_min_stay"] == rate["original_min_stay"]:
            continue

        listing_id = str(rate["listing_id"])
        date_key = rate["date"]
        currency = get_currency_for_listing(listing_id, rate.get("property"), date_key)

        if listing_id not in rates_to_push:
            rates_to_push[listing_id] = {}
        if date_key not in rates_to_push[listing_id]:
            rates_to_push[listing_id][date_key] = {
                "date": date_key,
                "price": rate["original_price"],
                "min_stay": rate["original_min_stay"],
                "currency": currency,
            }

        entry = rates_to_push[listing_id][date_key]
        if rate["new_price"] != rate["original_price"]:
            entry["price"] = rate["new_price"]
        if rate["new_min_stay"] != rate["original_min_stay"]:
            entry["min_stay"] = rate["new_min_stay"]

    return {lid: list(dates.values()) for lid, dates in rates_to_push.items()}


def _summarize_changes_by_property(adjusted_rates: List[dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for rate in adjusted_rates:
        if not rate.get("change_applied", False):
            continue
        prop = rate.get("property", "unknown")
        counts[prop] = counts.get(prop, 0) + 1
    return counts


def _write_rules_summary(
    property_keys: List[str],
    ui_start: date,
    ui_end: date,
    rules_ok: bool,
    push_ok: bool,
    dry_run: bool,
    results: dict,
    push_count: int,
    push_success_count: int,
    push_total_listings: int,
):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    changes_by_prop = _summarize_changes_by_property(results.get("adjusted_rates", []))
    lines = [
        "",
        "=" * 80,
        f"rules_adjuster_automation.py — run at {ts}",
        "=" * 80,
        f"Properties: {', '.join(property_keys)}",
        f"Date range: {ui_start} to {ui_end}",
        f"Dry run: {dry_run}",
        "",
        f"Rules check: {'✅ SUCCESS' if rules_ok else '❌ FAILURE'}",
        f"  {results.get('message', '')}",
        f"  Actual changes: {results.get('actual_changes', 0)}",
    ]
    if changes_by_prop:
        lines.append("  Changes by property:")
        for prop, count in sorted(changes_by_prop.items()):
            lines.append(f"    - {prop}: {count}")
    lines.extend(
        [
            "",
            f"Push: {'⏭️ SKIPPED (dry run)' if dry_run else ('✅ SUCCESS' if push_ok else '❌ FAILURE')}",
            f"  Rates to push: {push_count}",
            f"  Listings pushed: {push_success_count}/{push_total_listings}",
            "=" * 80,
        ]
    )
    RULES_LOG.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n📄 Rules summary written to: {RULES_LOG}")


def run_rules_adjuster_pipeline(
    property_keys: Optional[List[str]] = None,
    dry_run: bool = False,
) -> Tuple[bool, bool, dict]:
    """
    Check rules adjuster adjustments and optionally push to PriceLabs.

    Returns:
        (rules_ok, push_ok, results_dict)
    """
    resolved_keys = resolve_property_keys(property_keys)
    ui_start, ui_end = get_ui_default_range()

    print("🔧 Rules adjuster automation")
    print("=" * 80)
    print(f"Properties: {', '.join(resolved_keys)}")
    print(f"Date range: {ui_start} to {ui_end}")
    if dry_run:
        print("Mode: DRY RUN (check only, no push)")
    print("=" * 80)

    properties_config = backend_interface.load_properties_config() or {}
    missing = [k for k in resolved_keys if k not in properties_config]
    if missing:
        print(f"❌ Unknown properties in config: {missing}")
        return False, False, {"success": False, "message": f"Unknown properties: {missing}"}

    rate_df = load_rate_data_for_rules(resolved_keys)
    if rate_df is None or rate_df.empty:
        print("❌ No rate data available for rules check")
        return False, False, {"success": False, "message": "No rate data available"}

    print("\n🔍 Applying rules...")
    results = apply_rules_to_live_rates(rate_df, resolved_keys)
    rules_ok = bool(results.get("success"))

    if not rules_ok:
        print(f"❌ Rules check failed: {results.get('message')}")
        _write_rules_summary(resolved_keys, ui_start, ui_end, False, False, dry_run, results, 0, 0, 0)
        return False, False, results

    print(f"✅ {results.get('message')}")
    changes_by_prop = _summarize_changes_by_property(results.get("adjusted_rates", []))
    if changes_by_prop:
        for prop, count in sorted(changes_by_prop.items()):
            print(f"   • {prop}: {count} adjustment(s)")
    else:
        print("   • No adjustments required")

    rates_to_push = prepare_rates_to_push(results.get("adjusted_rates", []))
    push_count = sum(len(rates) for rates in rates_to_push.values())
    push_total_listings = len(rates_to_push)

    if push_count == 0:
        print("\nℹ️ Nothing to push — all rules evaluated with no actionable changes")
        _write_rules_summary(resolved_keys, ui_start, ui_end, True, True, dry_run, results, 0, 0, 0)
        return True, True, results

    print(f"\n📤 Prepared {push_count} rate override(s) across {push_total_listings} listing(s)")

    if dry_run:
        for listing_id, rates in rates_to_push.items():
            for rate in rates[:3]:
                print(f"   [dry-run] listing {listing_id} {rate['date']}: price={rate.get('price')} min_stay={rate.get('min_stay')}")
            if len(rates) > 3:
                print(f"   [dry-run] ... and {len(rates) - 3} more for listing {listing_id}")
        _write_rules_summary(resolved_keys, ui_start, ui_end, True, True, dry_run, results, push_count, 0, push_total_listings)
        return True, True, results

    print("\n🚀 Pushing to PriceLabs...")
    push_results = push_rates_batch(rates_to_push)
    push_success_count = sum(1 for result in push_results.values() if result.get("success"))
    push_ok = push_success_count == push_total_listings

    if push_ok:
        print(f"✅ Pushed {push_count} rate override(s) — {push_success_count}/{push_total_listings} listings successful")
    elif push_success_count > 0:
        print(f"⚠️ Partial push: {push_success_count}/{push_total_listings} listings successful")
        for listing_id, result in push_results.items():
            if not result.get("success"):
                print(f"   ❌ {listing_id}: {result.get('message', result.get('error_detail', 'unknown error'))}")
    else:
        print("❌ Push failed for all listings")
        for listing_id, result in push_results.items():
            print(f"   ❌ {listing_id}: {result.get('message', result.get('error_detail', 'unknown error'))}")

    _write_rules_summary(
        resolved_keys,
        ui_start,
        ui_end,
        True,
        push_ok,
        dry_run,
        results,
        push_count,
        push_success_count,
        push_total_listings,
    )
    return True, push_ok, results


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv[1:]
    rules_ok, push_ok, _ = run_rules_adjuster_pipeline(dry_run=dry_run)
    sys.exit(0 if (rules_ok and push_ok) else 1)
