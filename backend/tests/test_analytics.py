"""
test_analytics.py
Comprehensive offline test suite for Phase 3 Forecast Accuracy Analytics Engine.
Does NOT require live internet access or external API calls.
"""

import math
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from analytics import (
    calculate_core_metrics,
    calculate_daily_metrics,
    calculate_error_distribution,
    calculate_hour_of_day_metrics,
    calculate_worst_misses,
    filter_records_by_date,
    validate_and_extract_pairs,
)
from app import app, get_canonical_dataset


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture
def hand_calculated_dataset():
    """
    Standard hand-calculated test fixture:
    Pair 1: Forecast 110 MW, Actual 100 MW -> error = +10 MW, abs_error = 10 MW
    Pair 2: Forecast 90 MW, Actual 100 MW  -> error = -10 MW, abs_error = 10 MW
    Expected:
    MAE = 10 MW
    RMSE = 10 MW
    MBE = 0 MW
    MAPE = 10%
    """
    return [
        {
            "delivery_time_utc": "2026-01-01T00:00:00+00:00",
            "decision_cutoff_utc": "2025-12-31T11:00:00+00:00",
            "forecast_publish_time_utc": "2025-12-31T09:30:00+00:00",
            "forecast_generation_mw": 110.0,
            "actual_generation_mw": 100.0,
            "forecast_age_hours": 1.5,
            "forecast_available": True,
            "actual_available": True,
            "data_quality_flags": "OK"
        },
        {
            "delivery_time_utc": "2026-01-01T01:00:00+00:00",
            "decision_cutoff_utc": "2025-12-31T11:00:00+00:00",
            "forecast_publish_time_utc": "2025-12-31T09:30:00+00:00",
            "forecast_generation_mw": 90.0,
            "actual_generation_mw": 100.0,
            "forecast_age_hours": 1.5,
            "forecast_available": True,
            "actual_available": True,
            "data_quality_flags": "OK"
        }
    ]


@pytest.fixture
def multi_day_dataset():
    """Fixture containing 2 distinct days with known values."""
    records = []
    # Day 1: 2026-01-01 (2 intervals)
    records.append({
        "delivery_time_utc": "2026-01-01T10:00:00+00:00",
        "decision_cutoff_utc": "2025-12-31T11:00:00+00:00",
        "forecast_publish_time_utc": "2025-12-31T09:30:00+00:00",
        "forecast_generation_mw": 500.0,
        "actual_generation_mw": 400.0,
        "forecast_age_hours": 1.5,
        "forecast_available": True,
        "actual_available": True,
        "data_quality_flags": "OK"
    })
    records.append({
        "delivery_time_utc": "2026-01-01T11:00:00+00:00",
        "decision_cutoff_utc": "2025-12-31T11:00:00+00:00",
        "forecast_publish_time_utc": "2025-12-31T09:30:00+00:00",
        "forecast_generation_mw": 600.0,
        "actual_generation_mw": 500.0,
        "forecast_age_hours": 1.5,
        "forecast_available": True,
        "actual_available": True,
        "data_quality_flags": "OK"
    })
    # Day 2: 2026-01-02 (1 interval)
    records.append({
        "delivery_time_utc": "2026-01-02T12:00:00+00:00",
        "decision_cutoff_utc": "2026-01-01T11:00:00+00:00",
        "forecast_publish_time_utc": "2026-01-01T09:30:00+00:00",
        "forecast_generation_mw": 300.0,
        "actual_generation_mw": 350.0,
        "forecast_age_hours": 1.5,
        "forecast_available": True,
        "actual_available": True,
        "data_quality_flags": "OK"
    })
    return records


# -----------------------------------------------------------------------------
# 1. MAE, RMSE and MBE with hand-calculated values
# -----------------------------------------------------------------------------
def test_mae_rmse_mbe_hand_calculated(hand_calculated_dataset):
    valid_pairs, _ = validate_and_extract_pairs(hand_calculated_dataset)
    metrics = calculate_core_metrics(valid_pairs)

    assert metrics["matched_pairs_count"] == 2
    assert metrics["mae_mw"] == 10.0
    assert metrics["rmse_mw"] == 10.0
    assert metrics["mbe_mw"] == 0.0
    assert metrics["mape_pct"] == 10.0
    assert metrics["mean_actual_mw"] == 100.0
    assert metrics["mean_forecast_mw"] == 100.0


# -----------------------------------------------------------------------------
# 2. Correct positive/negative error sign convention
# -----------------------------------------------------------------------------
def test_error_sign_convention():
    # Overforecast: Forecast 150 > Actual 100 -> error = +50 MW
    # Underforecast: Forecast 80 < Actual 100 -> error = -20 MW
    records = [
        {
            "delivery_time_utc": "2026-01-01T00:00:00+00:00",
            "forecast_generation_mw": 150.0,
            "actual_generation_mw": 100.0,
            "forecast_available": True,
            "actual_available": True
        },
        {
            "delivery_time_utc": "2026-01-01T01:00:00+00:00",
            "forecast_generation_mw": 80.0,
            "actual_generation_mw": 100.0,
            "forecast_available": True,
            "actual_available": True
        }
    ]
    valid_pairs, _ = validate_and_extract_pairs(records)
    assert valid_pairs[0]["error_mw"] == 50.0
    assert valid_pairs[1]["error_mw"] == -20.0

    metrics = calculate_core_metrics(valid_pairs)
    assert metrics["positive_error_count"] == 1
    assert metrics["negative_error_count"] == 1
    assert metrics["zero_error_count"] == 0
    # Mean bias error = (50 - 20) / 2 = +15.0 MW
    assert metrics["mbe_mw"] == 15.0


# -----------------------------------------------------------------------------
# 3. MAPE with nonzero actuals
# -----------------------------------------------------------------------------
def test_mape_with_nonzero_actuals():
    records = [
        {"delivery_time_utc": "2026-01-01T00:00:00Z", "forecast_generation_mw": 110.0, "actual_generation_mw": 100.0, "forecast_available": True, "actual_available": True},
        {"delivery_time_utc": "2026-01-01T01:00:00Z", "forecast_generation_mw": 180.0, "actual_generation_mw": 200.0, "forecast_available": True, "actual_available": True},
    ]
    # Errors: |110-100|/100 = 10%, |180-200|/200 = 10% -> Average = 10.0%
    valid_pairs, _ = validate_and_extract_pairs(records)
    metrics = calculate_core_metrics(valid_pairs)
    assert metrics["mape_pct"] == 10.0
    assert metrics["mape_included_count"] == 2
    assert metrics["mape_excluded_zero_actual_count"] == 0


# -----------------------------------------------------------------------------
# 4. MAPE with zero actuals and correct exclusion counts
# -----------------------------------------------------------------------------
def test_mape_with_zero_actuals():
    records = [
        {"delivery_time_utc": "2026-01-01T00:00:00Z", "forecast_generation_mw": 110.0, "actual_generation_mw": 100.0, "forecast_available": True, "actual_available": True},
        {"delivery_time_utc": "2026-01-01T01:00:00Z", "forecast_generation_mw": 50.0, "actual_generation_mw": 0.0, "forecast_available": True, "actual_available": True},
    ]
    valid_pairs, _ = validate_and_extract_pairs(records)
    metrics = calculate_core_metrics(valid_pairs)

    # 0.0 actual interval must be excluded from MAPE calculation, not cause division by zero
    assert metrics["mape_pct"] == 10.0
    assert metrics["mape_included_count"] == 1
    assert metrics["mape_excluded_zero_actual_count"] == 1

    # Case where ALL actuals are zero
    zero_records = [
        {"delivery_time_utc": "2026-01-01T00:00:00Z", "forecast_generation_mw": 50.0, "actual_generation_mw": 0.0, "forecast_available": True, "actual_available": True}
    ]
    v_pairs, _ = validate_and_extract_pairs(zero_records)
    m = calculate_core_metrics(v_pairs)
    assert m["mape_pct"] is None
    assert m["mape_included_count"] == 0
    assert m["mape_excluded_zero_actual_count"] == 1


# -----------------------------------------------------------------------------
# 5. Empty input handling
# -----------------------------------------------------------------------------
def test_empty_input():
    metrics = calculate_core_metrics([])
    assert metrics["matched_pairs_count"] == 0
    assert metrics["mae_mw"] is None
    assert metrics["rmse_mw"] is None
    assert metrics["mbe_mw"] is None
    assert metrics["mape_pct"] is None


# -----------------------------------------------------------------------------
# 6. Missing actual or forecast values excluded
# -----------------------------------------------------------------------------
def test_missing_actual_or_forecast_values():
    records = [
        # Missing actual
        {"delivery_time_utc": "2026-01-01T00:00:00Z", "forecast_generation_mw": 100.0, "actual_generation_mw": None, "forecast_available": True, "actual_available": False},
        # Missing forecast
        {"delivery_time_utc": "2026-01-01T01:00:00Z", "forecast_generation_mw": None, "actual_generation_mw": 100.0, "forecast_available": False, "actual_available": True},
        # Valid pair
        {"delivery_time_utc": "2026-01-01T02:00:00Z", "forecast_generation_mw": 120.0, "actual_generation_mw": 100.0, "forecast_available": True, "actual_available": True},
    ]
    valid_pairs, audit = validate_and_extract_pairs(records)
    assert len(valid_pairs) == 1
    assert audit["excluded_records_count"] == 2
    reasons = [e["reason"] for e in audit["exclusions"]]
    assert "MISSING_ACTUAL" in reasons
    assert "MISSING_FORECAST" in reasons


# -----------------------------------------------------------------------------
# 7. NaN and Infinity rejection
# -----------------------------------------------------------------------------
def test_nan_and_infinity_rejection():
    records = [
        {"delivery_time_utc": "2026-01-01T00:00:00Z", "forecast_generation_mw": float("nan"), "actual_generation_mw": 100.0, "forecast_available": True, "actual_available": True},
        {"delivery_time_utc": "2026-01-01T01:00:00Z", "forecast_generation_mw": 100.0, "actual_generation_mw": float("inf"), "forecast_available": True, "actual_available": True},
        {"delivery_time_utc": "2026-01-01T02:00:00Z", "forecast_generation_mw": 100.0, "actual_generation_mw": 100.0, "forecast_available": True, "actual_available": True},
    ]
    valid_pairs, audit = validate_and_extract_pairs(records)
    assert len(valid_pairs) == 1
    assert audit["excluded_records_count"] == 2
    assert audit["exclusions"][0]["reason"] == "NON_FINITE_NUMERIC_VALUE"
    assert audit["exclusions"][1]["reason"] == "NON_FINITE_NUMERIC_VALUE"


# -----------------------------------------------------------------------------
# 8. Duplicate delivery timestamps detection
# -----------------------------------------------------------------------------
def test_duplicate_delivery_timestamps():
    records = [
        {"delivery_time_utc": "2026-01-01T00:00:00Z", "forecast_generation_mw": 100.0, "actual_generation_mw": 100.0, "forecast_available": True, "actual_available": True},
        {"delivery_time_utc": "2026-01-01T00:00:00Z", "forecast_generation_mw": 120.0, "actual_generation_mw": 100.0, "forecast_available": True, "actual_available": True},
    ]
    valid_pairs, audit = validate_and_extract_pairs(records)
    assert len(valid_pairs) == 1
    assert audit["excluded_records_count"] == 1
    assert audit["exclusions"][0]["reason"] == "DUPLICATE_DELIVERY_TIMESTAMP"


# -----------------------------------------------------------------------------
# 9. Daily grouping and incomplete-day handling
# -----------------------------------------------------------------------------
def test_daily_grouping(multi_day_dataset):
    daily = calculate_daily_metrics(multi_day_dataset)
    assert len(daily) == 2

    day1 = [d for d in daily if d["delivery_date"] == "2026-01-01"][0]
    assert day1["matched_interval_count"] == 2
    assert day1["is_complete"] is False  # Incomplete day (2 < 24)
    # Day 1: errors +100 and +100 -> MAE = 100, MBE = 100
    assert day1["mae_mw"] == 100.0
    assert day1["mbe_mw"] == 100.0

    day2 = [d for d in daily if d["delivery_date"] == "2026-01-02"][0]
    assert day2["matched_interval_count"] == 1
    assert day2["mae_mw"] == 50.0
    assert day2["mbe_mw"] == -50.0


# -----------------------------------------------------------------------------
# 10. Histogram counts sum to number of valid matched pairs
# -----------------------------------------------------------------------------
def test_histogram_counts_exact_sum():
    # 5 test pairs
    pairs = [
        {"error_mw": -20.0, "absolute_error_mw": 20.0},
        {"error_mw": -10.0, "absolute_error_mw": 10.0},
        {"error_mw": 0.0, "absolute_error_mw": 0.0},
        {"error_mw": 15.0, "absolute_error_mw": 15.0},
        {"error_mw": 35.0, "absolute_error_mw": 35.0},
    ]
    dist = calculate_error_distribution(pairs, num_bins=4)
    total_in_bins = sum(b["count"] for b in dist["histogram_bins"])
    assert total_in_bins == len(pairs)
    assert dist["total_observations"] == 5
    assert dist["positive_error_count"] == 2
    assert dist["negative_error_count"] == 2
    assert dist["zero_error_count"] == 1


# -----------------------------------------------------------------------------
# 11. Absolute-error quantiles
# -----------------------------------------------------------------------------
def test_absolute_error_quantiles():
    pairs = [{"error_mw": float(i), "absolute_error_mw": float(i)} for i in range(1, 101)]
    dist = calculate_error_distribution(pairs)
    abs_q = dist["quantiles_absolute_mw"]

    assert abs_q["min"] == 1.0
    assert abs_q["max"] == 100.0
    assert abs_q["p50_median"] == 50.5
    assert abs_q["p90"] == 90.1


# -----------------------------------------------------------------------------
# 12. Worst misses sorted correctly with deterministic tie-breaking
# -----------------------------------------------------------------------------
def test_worst_misses_deterministic_sorting():
    pairs = [
        {"delivery_time_utc": "2026-01-01T05:00:00Z", "absolute_error_mw": 100.0, "error_mw": 100.0, "forecast_generation_mw": 200.0, "actual_generation_mw": 100.0, "absolute_percentage_error": 100.0, "forecast_publish_time_utc": "2025-12-31T09:30:00Z", "decision_cutoff_utc": "2025-12-31T11:00:00Z", "forecast_age_hours": 1.5},
        {"delivery_time_utc": "2026-01-01T02:00:00Z", "absolute_error_mw": 500.0, "error_mw": -500.0, "forecast_generation_mw": 100.0, "actual_generation_mw": 600.0, "absolute_percentage_error": 83.3, "forecast_publish_time_utc": "2025-12-31T09:30:00Z", "decision_cutoff_utc": "2025-12-31T11:00:00Z", "forecast_age_hours": 1.5},
        # Tie in absolute error with first record: earlier delivery timestamp should break tie
        {"delivery_time_utc": "2026-01-01T01:00:00Z", "absolute_error_mw": 100.0, "error_mw": 100.0, "forecast_generation_mw": 200.0, "actual_generation_mw": 100.0, "absolute_percentage_error": 100.0, "forecast_publish_time_utc": "2025-12-31T09:30:00Z", "decision_cutoff_utc": "2025-12-31T11:00:00Z", "forecast_age_hours": 1.5},
    ]

    worst = calculate_worst_misses(pairs, limit=3)
    assert worst[0]["absolute_error_mw"] == 500.0
    assert worst[1]["absolute_error_mw"] == 100.0
    assert worst[1]["delivery_time_utc"] == "2026-01-01T01:00:00Z"  # Tie-breaker (01:00 before 05:00)
    assert worst[2]["delivery_time_utc"] == "2026-01-01T05:00:00Z"


# -----------------------------------------------------------------------------
# 13. Hour-of-day grouping using Europe/London
# -----------------------------------------------------------------------------
def test_hour_of_day_grouping():
    # 2 intervals at 14:00 UTC (14:00 GMT London)
    pairs = [
        {"delivery_time_utc": "2026-01-01T14:00:00+00:00", "error_mw": 50.0, "absolute_error_mw": 50.0, "forecast_generation_mw": 150.0, "actual_generation_mw": 100.0, "absolute_percentage_error": 50.0},
        {"delivery_time_utc": "2026-01-02T14:00:00+00:00", "error_mw": -30.0, "absolute_error_mw": 30.0, "forecast_generation_mw": 70.0, "actual_generation_mw": 100.0, "absolute_percentage_error": 30.0},
    ]
    hod = calculate_hour_of_day_metrics(pairs, tz_name="Europe/London")
    assert len(hod) == 24
    h14 = hod[14]
    assert h14["hour_of_day_local"] == 14
    assert h14["observation_count"] == 2
    assert h14["mae_mw"] == 40.0
    assert h14["mbe_mw"] == 10.0


# -----------------------------------------------------------------------------
# 14. UTC timestamp serialization
# -----------------------------------------------------------------------------
def test_utc_timestamp_serialization(hand_calculated_dataset):
    valid_pairs, _ = validate_and_extract_pairs(hand_calculated_dataset)
    for p in valid_pairs:
        assert "+00:00" in p["delivery_time_utc"] or p["delivery_time_utc"].endswith("Z")


# -----------------------------------------------------------------------------
# 15. Date filters including invalid and reversed ranges
# -----------------------------------------------------------------------------
def test_date_filters(multi_day_dataset):
    filtered = filter_records_by_date(multi_day_dataset, start_date="2026-01-01", end_date="2026-01-01")
    assert len(filtered) == 2

    # Reversed range should raise ValueError
    with pytest.raises(ValueError, match="cannot be after end_date"):
        filter_records_by_date(multi_day_dataset, start_date="2026-01-05", end_date="2026-01-01")

    # Invalid date string
    with pytest.raises(ValueError, match="Invalid date parameter"):
        filter_records_by_date(multi_day_dataset, start_date="not-a-date")


# -----------------------------------------------------------------------------
# 16. Invalid limit values
# -----------------------------------------------------------------------------
def test_invalid_limit_values():
    pairs = [{"delivery_time_utc": "2026-01-01T00:00:00Z", "absolute_error_mw": 10.0}]
    with pytest.raises(ValueError, match="must be between 1 and 100"):
        calculate_worst_misses(pairs, limit=0)
    with pytest.raises(ValueError, match="must be between 1 and 100"):
        calculate_worst_misses(pairs, limit=101)


# -----------------------------------------------------------------------------
# 17. Forecast publication after cutoff is flagged/excluded
# -----------------------------------------------------------------------------
def test_forecast_published_after_cutoff_excluded():
    # Record with publishTime AFTER cutoff
    records = [
        {
            "delivery_time_utc": "2026-01-02T12:00:00+00:00",
            "decision_cutoff_utc": "2026-01-01T11:00:00+00:00",
            "forecast_publish_time_utc": "2026-01-01T16:30:00+00:00",  # Published AFTER 11:00!
            "forecast_generation_mw": 15000.0,
            "actual_generation_mw": 12000.0,
            "forecast_available": True,
            "actual_available": True
        }
    ]
    valid_pairs, audit = validate_and_extract_pairs(records)
    assert len(valid_pairs) == 0
    assert audit["excluded_records_count"] == 1
    assert audit["exclusions"][0]["reason"] == "FORECAST_PUBLISHED_AFTER_CUTOFF"


# -----------------------------------------------------------------------------
# 18. Overview coverage and expected interval counts
# -----------------------------------------------------------------------------
def test_overview_coverage():
    # 2 valid pairs out of 4 expected
    pairs = [
        {"error_mw": 10.0, "absolute_error_mw": 10.0, "forecast_generation_mw": 110.0, "actual_generation_mw": 100.0, "absolute_percentage_error": 10.0},
        {"error_mw": -10.0, "absolute_error_mw": 10.0, "forecast_generation_mw": 90.0, "actual_generation_mw": 100.0, "absolute_percentage_error": 10.0},
    ]
    metrics = calculate_core_metrics(pairs, total_expected_intervals=4)
    assert metrics["matched_pairs_count"] == 2
    assert metrics["expected_intervals_count"] == 4
    assert metrics["matched_coverage_pct"] == 50.0


# -----------------------------------------------------------------------------
# 19. Existing root and health endpoints still work
# -----------------------------------------------------------------------------
def test_root_and_health_endpoints():
    client = TestClient(app)
    resp_root = client.get("/")
    assert resp_root.status_code == 200
    assert resp_root.json()["status"] == "ok"

    resp_health = client.get("/health")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "healthy"


# -----------------------------------------------------------------------------
# 20. FastAPI Analytics Endpoints via TestClient (Mocked Dependency)
# -----------------------------------------------------------------------------
def test_fastapi_analytics_endpoints(hand_calculated_dataset):
    # Inject test fixtures into FastAPI dependency
    app.dependency_overrides[get_canonical_dataset] = lambda: hand_calculated_dataset
    client = TestClient(app)

    try:
        # GET /api/analytics/overview
        r_over = client.get("/api/analytics/overview")
        assert r_over.status_code == 200
        data_over = r_over.json()
        assert data_over["metrics"]["mae_mw"] == 10.0
        assert data_over["metrics"]["rmse_mw"] == 10.0
        assert data_over["metrics"]["mbe_mw"] == 0.0
        assert data_over["coverage"]["matched_pairs_count"] == 2

        # GET /api/analytics/timeseries
        r_ts = client.get("/api/analytics/timeseries")
        assert r_ts.status_code == 200
        data_ts = r_ts.json()
        assert data_ts["count"] == 2
        assert len(data_ts["data"]) == 2

        # GET /api/analytics/timeseries with invalid reversed dates
        r_inv = client.get("/api/analytics/timeseries?start_date=2026-01-10&end_date=2026-01-05")
        assert r_inv.status_code == 400

        # GET /api/analytics/daily
        r_daily = client.get("/api/analytics/daily")
        assert r_daily.status_code == 200
        assert len(r_daily.json()["data"]) == 1

        # GET /api/analytics/errors
        r_err = client.get("/api/analytics/errors")
        assert r_err.status_code == 200
        data_err = r_err.json()
        assert data_err["total_observations"] == 2
        assert len(data_err["histogram_bins"]) > 0

        # GET /api/analytics/worst-misses
        r_worst = client.get("/api/analytics/worst-misses?limit=2")
        assert r_worst.status_code == 200
        assert len(r_worst.json()["data"]) == 2

        # GET /api/analytics/worst-misses invalid limit
        r_bad_limit = client.get("/api/analytics/worst-misses?limit=0")
        assert r_bad_limit.status_code in (400, 422)

        # GET /api/analytics/hour-of-day
        r_hod = client.get("/api/analytics/hour-of-day")
        assert r_hod.status_code == 200
        assert len(r_hod.json()["data"]) == 24

        # GET /api/analytics/metadata
        r_meta = client.get("/api/analytics/metadata")
        assert r_meta.status_code == 200
        assert "Elexon BMRS FUELHH" in str(r_meta.json()["data_sources"])

    finally:
        app.dependency_overrides.clear()
