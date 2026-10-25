"""
test_production_readiness.py
Phase 6 production readiness, security, and data integrity test suite.
Runs 100% offline with zero external network or database dependencies.
"""

import math
from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from analytics import (
    calculate_core_metrics,
    filter_records_by_date,
    load_canonical_dataset,
    load_ingestion_summary,
    validate_and_extract_pairs,
)
from app import app, get_canonical_dataset
from elexon_data import ElexonDataPipeline, PipelineConfig

client = TestClient(app)


# -----------------------------------------------------------------------------
# 1. Canonical Dataset Completeness (744 Intervals)
# -----------------------------------------------------------------------------
def test_canonical_dataset_has_744_hourly_intervals():
    """
    Verifies that the canonical January 2026 dataset contains exactly 744
    matched hourly intervals (31 days * 24 hours) with zero gaps or duplicates.
    """
    dataset = load_canonical_dataset()
    assert len(dataset) == 744, f"Expected 744 hourly intervals for Jan 2026, got {len(dataset)}"

    delivery_times = [r["delivery_time_utc"] for r in dataset]
    unique_times = set(delivery_times)
    assert len(unique_times) == 744, "Found duplicate delivery timestamps in canonical dataset"

    # Sorted order check: first interval is Jan 1 00:00, last is Jan 31 23:00
    sorted_times = sorted(delivery_times)
    assert sorted_times[0].startswith("2026-01-01T00:00:00")
    assert sorted_times[-1].startswith("2026-01-31T23:00:00")

    # Completeness of forecast and actual availability flags
    for rec in dataset:
        assert rec.get("forecast_available") is True, f"Missing forecast for {rec.get('delivery_time_utc')}"
        assert rec.get("actual_available") is True, f"Missing actual for {rec.get('delivery_time_utc')}"
        assert rec.get("forecast_generation_mw") is not None
        assert rec.get("actual_generation_mw") is not None


# -----------------------------------------------------------------------------
# 2. Half-hourly Actuals are Averaged (Not Summed)
# -----------------------------------------------------------------------------
def test_fuelhh_actuals_averaged_not_summed():
    """
    Confirms that half-hourly FUELHH actual records are normalized into hourly values
    using the arithmetic average (:00 + :30) / 2, representing average power in MW,
    and are NOT summed into 2x energy values.
    """
    config = PipelineConfig(delivery_start_date="2026-01-15", delivery_end_date="2026-01-15")
    pipeline = ElexonDataPipeline(config)

    raw_fuel = [
        {"startTime": "2026-01-15T12:00:00Z", "fuelType": "WIND", "generation": 400.0},
        {"startTime": "2026-01-15T12:30:00Z", "fuelType": "WIND", "generation": 600.0},
    ]

    hourly_actuals, summary = pipeline.aggregate_fuelhh_to_hourly(raw_fuel)
    hour_key = "2026-01-15T12:00:00+00:00"

    assert hour_key in hourly_actuals
    val = hourly_actuals[hour_key]["actual_generation_mw"]
    # (400 + 600) / 2 = 500 MW average power
    assert val == 500.0
    assert val != 1000.0, "Actual generation was summed instead of averaged"


# -----------------------------------------------------------------------------
# 3. Decision Cutoff Enforced (No Look-Ahead Leakage)
# -----------------------------------------------------------------------------
def test_forecast_selection_excludes_post_cutoff_publications():
    """
    Verifies that the forecast selection rule strictly excludes forecasts
    published after the configured decision cutoff (11:00 UTC on D-1).
    """
    # 1. Audit canonical dataset: every single record must satisfy pub <= cutoff
    dataset = load_canonical_dataset()
    for rec in dataset:
        pub_str = rec["forecast_publish_time_utc"].replace("Z", "+00:00")
        cut_str = rec["decision_cutoff_utc"].replace("Z", "+00:00")
        pub_dt = datetime.fromisoformat(pub_str)
        cut_dt = datetime.fromisoformat(cut_str)
        assert pub_dt <= cut_dt, f"Look-ahead violation: {pub_str} > {cut_str}"
        assert rec["forecast_age_hours"] >= 0.0

    # 2. Test validator function excludes post-cutoff forecast
    post_cutoff_rec = [
        {
            "delivery_time_utc": "2026-01-10T15:00:00+00:00",
            "decision_cutoff_utc": "2026-01-09T11:00:00+00:00",
            "forecast_publish_time_utc": "2026-01-09T14:30:00+00:00", # Published 3.5h AFTER cutoff
            "forecast_generation_mw": 8000.0,
            "actual_generation_mw": 7500.0,
            "forecast_available": True,
            "actual_available": True
        }
    ]
    valid_pairs, audit = validate_and_extract_pairs(post_cutoff_rec)
    assert len(valid_pairs) == 0, "Post-cutoff forecast was not excluded"
    assert audit["excluded_records_count"] == 1
    assert audit["exclusions"][0]["reason"] == "FORECAST_PUBLISHED_AFTER_CUTOFF"


# -----------------------------------------------------------------------------
# 4. Error Sign Convention: Forecast Minus Actual
# -----------------------------------------------------------------------------
def test_error_sign_convention_forecast_minus_actual():
    """
    Verifies the strict signed error definition:
    error_mw = forecast_generation_mw - actual_generation_mw
    Positive -> Overforecast
    Negative -> Underforecast
    """
    over_pair = [
        {
            "delivery_time_utc": "2026-01-01T01:00:00+00:00",
            "forecast_generation_mw": 12000.0,
            "actual_generation_mw": 10000.0,
            "forecast_available": True,
            "actual_available": True
        }
    ]
    valid_pairs, _ = validate_and_extract_pairs(over_pair)
    assert valid_pairs[0]["error_mw"] == 2000.0  # +2000 MW Overforecast

    under_pair = [
        {
            "delivery_time_utc": "2026-01-01T02:00:00+00:00",
            "forecast_generation_mw": 8000.0,
            "actual_generation_mw": 10000.0,
            "forecast_available": True,
            "actual_available": True
        }
    ]
    valid_pairs, _ = validate_and_extract_pairs(under_pair)
    assert valid_pairs[0]["error_mw"] == -2000.0  # -2000 MW Underforecast


# -----------------------------------------------------------------------------
# 5. Core Metric Calculations Verification on Canonical Dataset
# -----------------------------------------------------------------------------
def test_canonical_metrics_mathematical_precision():
    """
    Confirms that MAE, RMSE, MBE, MAPE, and direction counts calculated on the
    canonical January 2026 dataset match the benchmark reference results.
    """
    dataset = load_canonical_dataset()
    valid_pairs, audit = validate_and_extract_pairs(dataset)
    metrics = calculate_core_metrics(valid_pairs, total_expected_intervals=744)

    assert audit["excluded_records_count"] == 0
    assert metrics["matched_pairs_count"] == 744
    assert metrics["matched_coverage_pct"] == 100.0

    # Benchmark results for January 2026:
    assert math.isclose(metrics["mae_mw"], 2122.81, abs_tol=0.05)
    assert math.isclose(metrics["rmse_mw"], 2616.69, abs_tol=0.05)
    assert math.isclose(metrics["mbe_mw"], 1840.30, abs_tol=0.05)
    assert math.isclose(metrics["mape_pct"], 22.06, abs_tol=0.05)
    assert math.isclose(metrics["mean_actual_mw"], 11580.74, abs_tol=0.05)
    assert math.isclose(metrics["mean_forecast_mw"], 13421.03, abs_tol=0.05)
    assert metrics["positive_error_count"] == 628
    assert metrics["negative_error_count"] == 116
    assert metrics["max_absolute_error_mw"] == 6833.0


# -----------------------------------------------------------------------------
# 6. API Security: No Local Filesystem Paths or Stack Traces Leaked
# -----------------------------------------------------------------------------
def test_api_does_not_expose_local_filesystem_paths_on_missing_dataset():
    """
    Verifies that when dataset loading fails, the API returns HTTP 503 without
    leaking the server's local file paths in the JSON response.
    """
    from unittest.mock import patch

    secret_path = "C:\\Users\\admin\\secret_workspace\\canonical_dataset.json"
    with patch("app.load_canonical_dataset", side_effect=FileNotFoundError(f"Missing file at '{secret_path}'")):
        response = client.get("/api/analytics/overview")
        assert response.status_code == 503
        payload = response.json()
        assert "detail" in payload
        # Ensure raw path and server details are sanitized and not exposed
        assert "C:\\Users" not in payload["detail"]
        assert "secret_workspace" not in payload["detail"]
        assert "unavailable on the server" in payload["detail"]


def test_api_does_not_expose_local_paths_on_corrupt_dataset():
    """
    Verifies that when dataset parsing fails, the API returns HTTP 500 without
    leaking internal file traces or local directory trees.
    """
    from unittest.mock import patch

    secret_path = "/var/secret/corrupt_data.json"
    with patch("app.load_canonical_dataset", side_effect=ValueError(f"Corrupt JSON at '{secret_path}'")):
        response = client.get("/api/analytics/overview")
        assert response.status_code == 500
        payload = response.json()
        assert "detail" in payload
        assert "/var/secret" not in payload["detail"]
        assert "failed validation" in payload["detail"]


def test_api_date_query_validation():
    """
    Tests that invalid date queries are rejected with HTTP 400 Bad Request
    and informative, safe error messages.
    """
    # 1. Start date after end date
    res1 = client.get("/api/analytics/overview?start_date=2026-01-20&end_date=2026-01-10")
    assert res1.status_code == 400
    assert "cannot be after" in res1.json()["detail"]

    # 2. Malformed date string
    res2 = client.get("/api/analytics/overview?start_date=invalid-date")
    assert res2.status_code == 400
    assert "Invalid date parameter" in res2.json()["detail"]


def test_api_worst_misses_limit_bounds():
    """
    Tests that the limit parameter is bounded between 1 and 100.
    """
    # Out of range limit: 0 or 150
    res_low = client.get("/api/analytics/worst-misses?limit=0")
    assert res_low.status_code == 422

    res_high = client.get("/api/analytics/worst-misses?limit=150")
    assert res_high.status_code == 422

    # Valid limit: 5
    res_valid = client.get("/api/analytics/worst-misses?limit=5")
    assert res_valid.status_code == 200
    assert len(res_valid.json()["data"]) == 5


def test_health_check_lightweight_and_clean():
    """
    Tests that /health is fast, returns 200 {"status": "healthy"}, and does not load dataset.
    """
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}
