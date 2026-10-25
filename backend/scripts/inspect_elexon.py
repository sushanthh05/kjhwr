#!/usr/bin/env python3
"""
inspect_elexon.py
Diagnostic utility to query and validate official Elexon BMRS API endpoints:
- FUELHH stream: Actual half-hourly generation (filtering for WIND)
- WINDFOR stream: Wind generation forecasts

Queries small, bounded samples for January 2026, measures response metrics,
inspects schema and timestamps, detects duplicates/conflicts, and verifies
day-ahead cutoff selection logic.
"""

import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Add backend directory to sys.path to import validator
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    import httpx
except ImportError:
    print("[ERROR] httpx is not installed in the active environment.", file=sys.stderr)
    sys.exit(1)

from elexon_validator import (
    validate_fuelhh_records,
    validate_windfor_records,
    select_decision_forecast,
    parse_iso_timestamp
)

ELEXON_BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
TIMEOUT_CONFIG = httpx.Timeout(connect=10.0, read=25.0, write=10.0, pool=10.0)


def fetch_bounded_sample(
    client: httpx.Client,
    endpoint_path: str,
    params: Dict[str, Any],
    dataset_name: str
) -> Optional[Any]:
    """
    Executes a bounded GET request to an Elexon BMRS endpoint.
    Prints request telemetry and handles connection, timeout, and HTTP errors gracefully.
    """
    url = f"{ELEXON_BASE_URL}{endpoint_path}"
    print(f"\n========================================================")
    print(f"QUERYING DATASET: {dataset_name}")
    print(f"Endpoint: {endpoint_path}")
    print(f"Parameters: {params}")
    print(f"Target URL: {url}")
    print(f"--------------------------------------------------------")

    start_time = time.perf_counter()
    try:
        response = client.get(url, params=params)
        elapsed_sec = time.perf_counter() - start_time
    except httpx.ConnectTimeout:
        print(f"[FAIL] Connection timed out after 10.0s trying to reach {url}")
        return None
    except httpx.ReadTimeout:
        print(f"[FAIL] Read timed out after 25.0s waiting for response from {url}")
        return None
    except httpx.ConnectError as err:
        print(f"[FAIL] Network connection error: {err}")
        return None
    except Exception as err:
        print(f"[FAIL] Unexpected network exception: {err}")
        return None

    content_type = response.headers.get("content-type", "unknown")
    print(f"HTTP Status: {response.status_code} ({response.reason_phrase})")
    print(f"Elapsed Time: {elapsed_sec:.3f} seconds")
    print(f"Content-Type: {content_type}")

    if response.status_code != 200:
        print(f"[ERROR] API returned non-200 status code: {response.status_code}")
        try:
            error_body = response.json()
            print(f"API Error Details: {error_body}")
        except Exception:
            print(f"Raw Response snippet: {response.text[:300]}")
        return None

    try:
        data = response.json()
        return data
    except Exception as err:
        print(f"[ERROR] Failed to parse JSON response: {err}")
        print(f"Raw Response snippet: {response.text[:300]}")
        return None


def run_diagnostics() -> int:
    """
    Runs the full Elexon diagnostic suite for FUELHH and WINDFOR.
    Returns 0 on successful validation, or 1 if fatal errors occur.
    """
    print("=" * 60)
    print("Elexon BMRS API Diagnostic & Validation Suite (Phase 1)")
    print(f"Base API: {ELEXON_BASE_URL}")
    print(f"Target Period: January 2026 (Sample)")
    print("=" * 60)

    with httpx.Client(timeout=TIMEOUT_CONFIG, follow_redirects=True) as client:
        # ---------------------------------------------------------
        # 1. Investigate FUELHH (Actual Generation by Fuel Type)
        # ---------------------------------------------------------
        # Documented query parameters: settlementDateFrom, settlementDateTo, fuelType
        fuel_params = {
            "settlementDateFrom": "2026-01-01",
            "settlementDateTo": "2026-01-02",
            "fuelType": "WIND"
        }
        fuel_raw = fetch_bounded_sample(
            client=client,
            endpoint_path="/datasets/FUELHH/stream",
            params=fuel_params,
            dataset_name="FUELHH (Actual Generation)"
        )

        fuel_summary = None
        if fuel_raw is not None:
            fuel_summary = validate_fuelhh_records(fuel_raw)
            print("\n[FUELHH Diagnostic Summary]")
            print(f"  Total records received: {fuel_summary['total_records']}")
            print(f"  Valid records: {fuel_summary['valid_records_count']}")
            print(f"  Invalid records: {fuel_summary['invalid_records_count']}")
            print(f"  Fuel types observed: {fuel_summary['fuel_types']}")
            print(f"  Distinct delivery intervals (startTime): {fuel_summary['distinct_start_times']}")
            print(f"  Min delivery time: {fuel_summary['min_start_time']}")
            print(f"  Max delivery time: {fuel_summary['max_start_time']}")
            print(f"  Duplicates detected: {len(fuel_summary['duplicates'])}")
            print(f"  Value conflicts detected: {len(fuel_summary['conflicts'])}")

            if fuel_summary["valid_records"]:
                sample = fuel_summary["valid_records"][0]
                print(f"  Fields returned: {list(sample.keys())}")
                print(f"  Sample Record 0: startTime={sample['startTime']}, fuelType={sample['fuelType']}, generation={sample['generation']} MW")
                if len(fuel_summary["valid_records"]) > 1:
                    sample2 = fuel_summary["valid_records"][1]
                    print(f"  Sample Record 1: startTime={sample2['startTime']}, fuelType={sample2['fuelType']}, generation={sample2['generation']} MW")

        # ---------------------------------------------------------
        # 2. Investigate WINDFOR (Wind Generation Forecast)
        # ---------------------------------------------------------
        # Documented query parameters: publishDateTimeFrom, publishDateTimeTo
        wind_params = {
            "publishDateTimeFrom": "2026-01-01T00:00:00Z",
            "publishDateTimeTo": "2026-01-01T12:00:00Z"
        }
        wind_raw = fetch_bounded_sample(
            client=client,
            endpoint_path="/datasets/WINDFOR/stream",
            params=wind_params,
            dataset_name="WINDFOR (Wind Generation Forecast)"
        )

        wind_summary = None
        if wind_raw is not None:
            wind_summary = validate_windfor_records(wind_raw)
            print("\n[WINDFOR Diagnostic Summary]")
            print(f"  Total records received: {wind_summary['total_records']}")
            print(f"  Valid records: {wind_summary['valid_records_count']}")
            print(f"  Invalid records: {wind_summary['invalid_records_count']}")
            print(f"  Distinct publication runs (publishTime): {wind_summary['distinct_publish_times']}")
            print(f"  Distinct forecast intervals (startTime): {wind_summary['distinct_start_times']}")
            print(f"  Publication range: {wind_summary['min_publish_time']} -> {wind_summary['max_publish_time']}")
            print(f"  Forecast target range: {wind_summary['min_start_time']} -> {wind_summary['max_start_time']}")
            print(f"  Duplicates detected: {len(wind_summary['duplicates'])}")
            print(f"  Value conflicts detected: {len(wind_summary['conflicts'])}")

            if wind_summary["valid_records"]:
                sample = wind_summary["valid_records"][0]
                print(f"  Fields returned: {list(sample.keys())}")
                print(f"  Sample Record 0: publishTime={sample['publishTime']}, startTime={sample['startTime']}, generation={sample['generation']} MW")
                if len(wind_summary["valid_records"]) > 1:
                    sample2 = wind_summary["valid_records"][1]
                    print(f"  Sample Record 1: publishTime={sample2['publishTime']}, startTime={sample2['startTime']}, generation={sample2['generation']} MW")

        # ---------------------------------------------------------
        # 3. Decision Cutoff Forecast Selection Verification
        # ---------------------------------------------------------
        if wind_summary and wind_summary["valid_records"]:
            print("\n--------------------------------------------------------")
            print("DAY-AHEAD DECISION CUTOFF SELECTION CHECK ON LIVE SAMPLE")
            print("--------------------------------------------------------")
            
            # Select a target delivery interval present in the forecast sample
            test_delivery_target = "2026-01-02T12:00:00Z"
            # Scenario A: Decision cutoff at 06:00 on 2026-01-01 (should pick publishTime <= 06:00)
            cutoff_a = "2026-01-01T06:00:00Z"
            selected_a = select_decision_forecast(wind_summary["valid_records"], test_delivery_target, cutoff_a)
            
            # Scenario B: Decision cutoff at 11:00 on 2026-01-01 (should pick newer publishTime <= 11:00)
            cutoff_b = "2026-01-01T11:00:00Z"
            selected_b = select_decision_forecast(wind_summary["valid_records"], test_delivery_target, cutoff_b)

            print(f"Target Delivery Interval: {test_delivery_target}")
            if selected_a:
                print(f"Cutoff {cutoff_a}: Selected publishTime={selected_a['publishTime']} -> Forecast: {selected_a['generation']} MW")
            else:
                print(f"Cutoff {cutoff_a}: No eligible forecast found published prior to cutoff.")

            if selected_b:
                print(f"Cutoff {cutoff_b}: Selected publishTime={selected_b['publishTime']} -> Forecast: {selected_b['generation']} MW")
            else:
                print(f"Cutoff {cutoff_b}: No eligible forecast found published prior to cutoff.")

    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETION STATUS:")
    fuel_ok = fuel_summary is not None and fuel_summary["valid_records_count"] > 0
    wind_ok = wind_summary is not None and wind_summary["valid_records_count"] > 0

    if fuel_ok and wind_ok:
        print("[SUCCESS] Both FUELHH and WINDFOR samples verified successfully.")
        print("[NOTE] This diagnostic examined a bounded sample for January 2026.")
        print("       No claims are made regarding complete monthly coverage.")
        return 0
    else:
        print("[WARNING] One or more endpoints failed or returned no valid records.")
        return 1


if __name__ == "__main__":
    exit_code = run_diagnostics()
    sys.exit(exit_code)
