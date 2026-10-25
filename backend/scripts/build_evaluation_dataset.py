#!/usr/bin/env python3
"""
build_evaluation_dataset.py
CLI entry point to execute the Elexon Data Ingestion and Normalization Pipeline.

Default scope: January 1 to January 31, 2026.
Default decision cutoff: 11:00 UTC day-ahead.

Usage:
    python scripts/build_evaluation_dataset.py [OPTIONS]

Options:
    --start-date TEXT   Delivery start date (YYYY-MM-DD) [default: 2026-01-01]
    --end-date TEXT     Delivery end date (YYYY-MM-DD) [default: 2026-01-31]
    --cutoff-time TEXT  Day-ahead decision cutoff time (HH:MM) [default: 11:00]
    --timezone TEXT     Decision timezone [default: UTC]
    --output-dir PATH   Output data directory [default: backend/data]
    --refresh           Force re-download of raw data from API [default: False]
"""

import argparse
import sys
from pathlib import Path

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from elexon_data import ElexonDataPipeline, PipelineConfig


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the canonical evaluation dataset for UK wind forecast intelligence (Phase 2)."
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2026-01-01",
        help="Delivery start date in YYYY-MM-DD format (default: 2026-01-01)"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="2026-01-31",
        help="Delivery end date in YYYY-MM-DD format (default: 2026-01-31)"
    )
    parser.add_argument(
        "--cutoff-time",
        type=str,
        default="11:00",
        help="Day-ahead decision cutoff time in HH:MM format (default: 11:00)"
    )
    parser.add_argument(
        "--timezone",
        type=str,
        default="UTC",
        help="Decision timezone (default: UTC)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(BACKEND_DIR / "data"),
        help="Target data directory (default: backend/data)"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        default=False,
        help="Force refresh raw data from API even if cached locally"
    )

    args = parser.parse_args()

    config = PipelineConfig(
        delivery_start_date=args.start_date,
        delivery_end_date=args.end_date,
        decision_cutoff_time=args.cutoff_time,
        decision_timezone=args.timezone,
        data_dir=Path(args.output_dir),
        refresh=args.refresh
    )

    print("=" * 68)
    print("  UK WIND FORECAST INTELLIGENCE - DATA INGESTION PIPELINE (PHASE 2)")
    print("=" * 68)
    print(f"  Delivery Scope:    {config.delivery_start_date} to {config.delivery_end_date}")
    print(f"  Decision Cutoff:   {config.decision_cutoff_time} {config.decision_timezone} (Day-Ahead)")
    print(f"  Data Directory:    {config.data_dir}")
    print(f"  Cache Mode:        {'Force Refresh (API)' if config.refresh else 'Reuse Cache if Available'}")
    print("-" * 68)

    pipeline = ElexonDataPipeline(config)
    try:
        canonical_rows, summary = pipeline.run()
    except Exception as exc:
        print(f"\n[FATAL ERROR] Pipeline execution failed: {exc}", file=sys.stderr)
        return 1

    act_ing = summary["actuals_ingestion"]
    fc_ing = summary["forecasts_ingestion"]
    act_norm = summary["actuals_normalization"]
    fc_norm = summary["forecasts_normalization"]
    eval_ds = summary["evaluation_dataset"]

    print("\n--- INGESTION & NORMALIZATION SUMMARY ---")
    print(f"  Actuals Retrieved (FUELHH):      {act_ing['raw_records_count']} records (Source: {act_ing.get('source', 'unknown')})")
    print(f"  Forecasts Retrieved (WINDFOR):   {fc_ing['raw_records_count']} records (Source: {fc_ing.get('source', 'unknown')})")
    print(f"  Failed API Requests:             {len(act_ing.get('failed_requests', [])) + len(fc_ing.get('failed_chunks', []))}")
    print(f"  Hourly Actuals Produced:         {act_norm['complete_hours']} complete / {act_norm['total_expected_hours']} expected")
    print(f"  Deduplicated Forecasts:          {fc_norm['deduplicated_count']} (Duplicates removed: {fc_norm['duplicate_count']})")
    print(f"  Forecast Value Conflicts:        {fc_norm['conflicts_detected']}")
    print(f"  Distinct Publication Vintages:   {fc_norm['distinct_publish_times']}")

    print("\n--- CANONICAL EVALUATION DATASET ---")
    print(f"  Total Hourly Delivery Intervals: {eval_ds['total_intervals']}")
    print(f"  Complete Matched Pairs (FC+ACT): {eval_ds['complete_evaluation_pairs']}")
    print(f"  Intervals Missing Forecast:      {eval_ds['intervals_missing_forecast']}")
    print(f"  Intervals Missing Actual:        {eval_ds['intervals_missing_actual']}")
    print(f"  Earliest Delivery Time:          {eval_ds['earliest_delivery']}")
    print(f"  Latest Delivery Time:            {eval_ds['latest_delivery']}")

    print("\n--- OUTPUT ARTIFACTS ---")
    for name, path in summary["output_files"].items():
        print(f"  {name}: {path}")

    print("\n" + "=" * 68)
    if eval_ds["is_fully_complete"]:
        print("  STATUS: [SUCCESS] Canonical dataset built with 100% COMPLETE coverage.")
        print("=" * 68)
        return 0
    else:
        print(f"  STATUS: [PARTIAL COVERAGE] {eval_ds['complete_evaluation_pairs']}/{eval_ds['total_intervals']} complete intervals.")
        print("=" * 68)
        # If any critical API requests failed, return non-zero
        if act_ing.get("failed_requests") or fc_ing.get("failed_chunks"):
            return 1
        return 0


if __name__ == "__main__":
    sys.exit(main())
