#!/usr/bin/env python3
"""
Morning data pipeline: generate pl_daily, pull nightly overrides, rules adjuster push.

Run from project root:
    ./scripts/run_morning_data_pipeline.sh
    python scripts/run_morning_data_pipeline.py
    python scripts/run_morning_data_pipeline.py --dry-run          # rules check only, no push
    python scripts/run_morning_data_pipeline.py --rules-push-only  # rules step only
"""

import os
import sys
from datetime import datetime
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
_venv_python = _project_root / "venv" / "bin" / "python"


def _in_project_venv():
    return Path(sys.prefix).resolve() == (_project_root / "venv").resolve()


def _ensure_venv():
    """Re-exec with project venv Python if not already using it."""
    if not _venv_python.exists():
        print(f"❌ Virtual environment not found at {_venv_python.parent.parent}")
        print("   Create it with: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt")
        sys.exit(1)
    if not _in_project_venv():
        print(f"🔄 Activating venv: {_venv_python}")
        sys.stdout.flush()
        sys.stderr.flush()
        os.execv(str(_venv_python), [str(_venv_python)] + sys.argv)


_ensure_venv()

_scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_scripts_dir))
os.chdir(_project_root)

from generate_all_properties import process_all_properties, _write_summary_log
from rates.pull.nightly_pull import EXECUTION_LOG_FILE, run_nightly_pull
from rules_adjuster_automation import run_rules_adjuster_pipeline

LOG_DIR = _project_root / "logs"
PIPELINE_LOG = LOG_DIR / "morning_data_pipeline_summary.txt"


def _write_pipeline_summary(
    start_date,
    end_date,
    pl_successful,
    pl_failed,
    nightly_pull_ok,
    rules_ok,
    rules_push_ok,
    pipeline_ok,
):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "",
        "=" * 80,
        f"run_morning_data_pipeline.py — run at {ts}",
        "=" * 80,
        f"Date range (pl_daily): {start_date} to {end_date}",
        "",
        "Step 1 — generate_all_properties.py",
        f"  ✅ Successful: {len(pl_successful)} properties",
        f"  ❌ Failed: {len(pl_failed)} properties",
    ]
    if pl_successful:
        lines.append("  Successful properties:")
        for prop in pl_successful:
            lines.append(f"    - {prop}")
    if pl_failed:
        lines.append("  Failed properties:")
        for prop in pl_failed:
            lines.append(f"    - {prop}")
    lines.extend(
        [
            "",
            "Step 2 — nightly_pull.py",
            f"  {'✅ SUCCESS' if nightly_pull_ok else '❌ FAILURE'}",
            "",
            "Step 3 — rules adjuster (onera, wb1, flo1)",
            f"  {'✅ SUCCESS' if rules_ok and rules_push_ok else '❌ FAILURE'}",
            "",
            f"Overall pipeline: {'✅ SUCCESS' if pipeline_ok else '❌ FAILURE'}",
            "=" * 80,
        ]
    )
    PIPELINE_LOG.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n📄 Pipeline summary written to: {PIPELINE_LOG}")


def _nightly_pull_succeeded(log_path: Path, start_pos: int) -> bool:
    if not log_path.exists():
        return False
    with open(log_path, "r", encoding="utf-8") as f:
        f.seek(start_pos)
        new_content = f.read()
    if "FAILURE - Override pull failed" in new_content:
        return False
    return "SUCCESS - Override pull completed." in new_content


def run_pipeline(
    start_date=None,
    end_date=None,
    skip_data_steps=False,
    rules_push_only=False,
    rules_dry_run=False,
):
    print("🌅 Morning data pipeline")
    print("=" * 80)

    pl_successful, pl_failed = [], []
    nightly_pull_ok = True
    rules_ok = True
    rules_push_ok = True

    if rules_push_only:
        skip_data_steps = True
        print("⏭️ Rules push only mode (--rules-push-only)")
    elif not skip_data_steps:
        print("Step 1/3: generate pl_daily for all properties")
        print("=" * 80)

        pl_successful, pl_failed = process_all_properties(start_date, end_date)

        from utils.date_manager import get_bulk_processing_range

        if start_date is None or end_date is None:
            start_obj, end_obj = get_bulk_processing_range()
            start_date = start_obj.strftime("%Y-%m-%d")
            end_date = end_obj.strftime("%Y-%m-%d")

        _write_summary_log(start_date, end_date, pl_successful, pl_failed)

        print("\n" + "=" * 80)
        print("Step 2/3: pull nightly overrides from PriceLabs")
        print("=" * 80)

        log_start_pos = EXECUTION_LOG_FILE.stat().st_size if EXECUTION_LOG_FILE.exists() else 0
        run_nightly_pull()
        nightly_pull_ok = _nightly_pull_succeeded(EXECUTION_LOG_FILE, log_start_pos)
    else:
        start_date = start_date or "skipped"
        end_date = end_date or "skipped"

    print("\n" + "=" * 80)
    print("Step 3/3: rules adjuster check and push (onera, wb1, flo1)")
    print("=" * 80)
    rules_ok, rules_push_ok, _ = run_rules_adjuster_pipeline(dry_run=rules_dry_run)

    data_ok = not pl_failed and nightly_pull_ok
    pipeline_ok = data_ok and rules_ok and rules_push_ok

    print("\n" + "=" * 80)
    print("📊 PIPELINE SUMMARY")
    print("=" * 80)
    if not skip_data_steps:
        print(f"Step 1 (pl_daily): {len(pl_successful)} ok, {len(pl_failed)} failed")
        print(f"Step 2 (nightly pull): {'SUCCESS' if nightly_pull_ok else 'FAILURE'}")
    print(f"Step 3 (rules adjuster): {'SUCCESS' if rules_ok and rules_push_ok else 'FAILURE'}")
    print(f"Overall pipeline: {'SUCCESS' if pipeline_ok else 'FAILURE'}")

    _write_pipeline_summary(
        start_date,
        end_date,
        pl_successful,
        pl_failed,
        nightly_pull_ok,
        rules_ok,
        rules_push_ok,
        pipeline_ok,
    )

    return pipeline_ok


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    argv = sys.argv[1:]
    rules_push_only = "--rules-push-only" in argv
    rules_dry_run = "--dry-run" in argv
    args = [a for a in argv if a not in ("--rules-push-only", "--dry-run")]

    if len(args) > 2:
        cli_start_date = args[0]
        cli_end_date = args[1]
    else:
        cli_start_date = None
        cli_end_date = None

    success = run_pipeline(
        cli_start_date,
        cli_end_date,
        skip_data_steps=rules_push_only,
        rules_push_only=rules_push_only,
        rules_dry_run=rules_dry_run,
    )
    sys.exit(0 if success else 1)
