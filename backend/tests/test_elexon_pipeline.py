"""
test_elexon_pipeline.py
Offline automated test suite for Phase 2 Elexon data ingestion and normalization.
Mocks all HTTP network calls; requires no live internet connection.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from elexon_data import (
    ElexonDataPipeline,
    PipelineConfig,
    calculate_decision_cutoff,
    generate_expected_delivery_hours,
)


# -----------------------------------------------------------------------------
# 1. Half-hourly actuals aggregate to correct hourly average
# -----------------------------------------------------------------------------
def test_half_hourly_actuals_aggregate_to_hourly_average():
    config = PipelineConfig(delivery_start_date="2026-01-01", delivery_end_date="2026-01-01")
    pipeline = ElexonDataPipeline(config)

    raw_fuel = [
        {"startTime": "2026-01-01T14:00:00Z", "fuelType": "WIND", "generation": 120.0},
        {"startTime": "2026-01-01T14:30:00Z", "fuelType": "WIND", "generation": 180.0},
    ]

    hourly_actuals, summary = pipeline.aggregate_fuelhh_to_hourly(raw_fuel)
    hour_key = "2026-01-01T14:00:00+00:00"

    assert hour_key in hourly_actuals
    assert hourly_actuals[hour_key]["actual_available"] is True
    # Average of 120.0 and 180.0 is 150.0 MW
    assert hourly_actuals[hour_key]["actual_generation_mw"] == 150.0


# -----------------------------------------------------------------------------
# 2. Two 100 MW half-hours yield 100 MW hourly average, not 200 MW
# -----------------------------------------------------------------------------
def test_two_100mw_half_hours_yield_100mw_not_200mw():
    config = PipelineConfig(delivery_start_date="2026-01-01", delivery_end_date="2026-01-01")
    pipeline = ElexonDataPipeline(config)

    raw_fuel = [
        {"startTime": "2026-01-01T10:00:00Z", "fuelType": "WIND", "generation": 100.0},
        {"startTime": "2026-01-01T10:30:00Z", "fuelType": "WIND", "generation": 100.0},
    ]

    hourly_actuals, _ = pipeline.aggregate_fuelhh_to_hourly(raw_fuel)
    hour_key = "2026-01-01T10:00:00+00:00"

    avg_val = hourly_actuals[hour_key]["actual_generation_mw"]
    assert avg_val == 100.0
    assert avg_val != 200.0  # Confirms power averaging rather than energy summing


# -----------------------------------------------------------------------------
# 3. Missing one half-hour makes hour unavailable and records quality flag
# -----------------------------------------------------------------------------
def test_missing_one_half_hour_makes_hour_unavailable_with_quality_flag():
    config = PipelineConfig(delivery_start_date="2026-01-01", delivery_end_date="2026-01-01")
    pipeline = ElexonDataPipeline(config)

    # Only :00 is present; :30 is missing
    raw_fuel = [
        {"startTime": "2026-01-01T08:00:00Z", "fuelType": "WIND", "generation": 250.0}
    ]

    hourly_actuals, _ = pipeline.aggregate_fuelhh_to_hourly(raw_fuel)
    hour_key = "2026-01-01T08:00:00+00:00"

    assert hourly_actuals[hour_key]["actual_available"] is False
    assert hourly_actuals[hour_key]["actual_generation_mw"] is None
    flags = hourly_actuals[hour_key]["quality_flags"]
    assert "MISSING_SECOND_HALF_HOUR" in flags
    assert "INCOMPLETE_ACTUAL_PAIR" in flags


# -----------------------------------------------------------------------------
# 4. UTC timestamps normalized consistently
# -----------------------------------------------------------------------------
def test_utc_timestamps_normalized_consistently():
    delivery_hour = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    cutoff_utc = calculate_decision_cutoff(delivery_hour, cutoff_time_str="11:00", tz_name="UTC")

    assert cutoff_utc.tzinfo == timezone.utc
    assert cutoff_utc.year == 2026
    assert cutoff_utc.month == 1
    assert cutoff_utc.day == 14  # Day-ahead: Jan 14 for Jan 15 delivery
    assert cutoff_utc.hour == 11
    assert cutoff_utc.minute == 0


# -----------------------------------------------------------------------------
# 5. Latest eligible forecast is selected
# -----------------------------------------------------------------------------
def test_latest_eligible_forecast_selected():
    config = PipelineConfig(delivery_start_date="2026-01-02", delivery_end_date="2026-01-02")
    pipeline = ElexonDataPipeline(config)

    delivery_target = "2026-01-02T12:00:00+00:00"
    # Cutoff is 2026-01-01T11:00:00Z
    forecasts = [
        {"publishTime": "2026-01-01T04:30:00Z", "startTime": "2026-01-02T12:00:00Z", "generation": 12000.0,
         "_pub_dt": datetime(2026, 1, 1, 4, 30, tzinfo=timezone.utc), "_start_dt": datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)},
        {"publishTime": "2026-01-01T09:30:00Z", "startTime": "2026-01-02T12:00:00Z", "generation": 12500.0,
         "_pub_dt": datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc), "_start_dt": datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)},
    ]

    hourly_actuals = {
        delivery_target: {"actual_generation_mw": 12400.0, "actual_available": True, "quality_flags": []}
    }

    canonical_rows, _ = pipeline.build_canonical_evaluation_dataset(hourly_actuals, forecasts)
    row = [r for r in canonical_rows if r["delivery_time_utc"] == delivery_target][0]

    assert row["forecast_available"] is True
    # 09:30 is the latest published before 11:00 cutoff
    assert row["forecast_generation_mw"] == 12500.0
    assert row["forecast_publish_time_utc"] == "2026-01-01T09:30:00Z"
    # Cutoff is 11:00, pub was 09:30 -> age is 1.5 hours
    assert row["forecast_age_hours"] == 1.5


# -----------------------------------------------------------------------------
# 6. Forecast published after cutoff is excluded (No look-ahead leakage)
# -----------------------------------------------------------------------------
def test_forecast_published_after_cutoff_excluded():
    config = PipelineConfig(delivery_start_date="2026-01-02", delivery_end_date="2026-01-02")
    pipeline = ElexonDataPipeline(config)

    delivery_target = "2026-01-02T12:00:00+00:00"
    forecasts = [
        {"publishTime": "2026-01-01T09:30:00Z", "startTime": "2026-01-02T12:00:00Z", "generation": 12500.0,
         "_pub_dt": datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc), "_start_dt": datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)},
        # Newest forecast overall, but published AFTER 11:00 cutoff:
        {"publishTime": "2026-01-01T16:30:00Z", "startTime": "2026-01-02T12:00:00Z", "generation": 14000.0,
         "_pub_dt": datetime(2026, 1, 1, 16, 30, tzinfo=timezone.utc), "_start_dt": datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)},
    ]

    hourly_actuals = {
        delivery_target: {"actual_generation_mw": 12400.0, "actual_available": True, "quality_flags": []}
    }

    canonical_rows, _ = pipeline.build_canonical_evaluation_dataset(hourly_actuals, forecasts)
    row = [r for r in canonical_rows if r["delivery_time_utc"] == delivery_target][0]

    # Must NOT select 14000.0 MW
    assert row["forecast_generation_mw"] != 14000.0
    assert row["forecast_generation_mw"] == 12500.0
    assert row["forecast_publish_time_utc"] == "2026-01-01T09:30:00Z"


# -----------------------------------------------------------------------------
# 7. Forecasts from prior calendar day considered for early January delivery
# -----------------------------------------------------------------------------
def test_forecasts_from_prior_calendar_day_considered_for_early_january():
    config = PipelineConfig(delivery_start_date="2026-01-01", delivery_end_date="2026-01-01")
    pipeline = ElexonDataPipeline(config)

    delivery_target = "2026-01-01T04:00:00+00:00"
    # Day-ahead cutoff for Jan 1 delivery is 2025-12-31 at 11:00 UTC
    forecasts = [
        {"publishTime": "2025-12-31T09:30:00Z", "startTime": "2026-01-01T04:00:00Z", "generation": 9800.0,
         "_pub_dt": datetime(2025, 12, 31, 9, 30, tzinfo=timezone.utc), "_start_dt": datetime(2026, 1, 1, 4, 0, tzinfo=timezone.utc)},
    ]

    hourly_actuals = {
        delivery_target: {"actual_generation_mw": 9750.0, "actual_available": True, "quality_flags": []}
    }

    canonical_rows, _ = pipeline.build_canonical_evaluation_dataset(hourly_actuals, forecasts)
    row = [r for r in canonical_rows if r["delivery_time_utc"] == delivery_target][0]

    assert row["forecast_available"] is True
    assert row["forecast_generation_mw"] == 9800.0
    assert row["decision_cutoff_utc"] == "2025-12-31T11:00:00+00:00"


# -----------------------------------------------------------------------------
# 8. Missing forecast explicitly recorded
# -----------------------------------------------------------------------------
def test_missing_forecast_explicitly_recorded():
    config = PipelineConfig(delivery_start_date="2026-01-01", delivery_end_date="2026-01-01")
    pipeline = ElexonDataPipeline(config)

    delivery_target = "2026-01-01T20:00:00+00:00"
    # No forecasts available
    forecasts = []
    hourly_actuals = {
        delivery_target: {"actual_generation_mw": 11000.0, "actual_available": True, "quality_flags": []}
    }

    canonical_rows, summary = pipeline.build_canonical_evaluation_dataset(hourly_actuals, forecasts)
    row = [r for r in canonical_rows if r["delivery_time_utc"] == delivery_target][0]

    assert row["forecast_available"] is False
    assert row["forecast_generation_mw"] is None
    assert "NO_ELIGIBLE_FORECAST_BEFORE_CUTOFF" in row["data_quality_flags"]
    assert summary["intervals_missing_forecast"] >= 1


# -----------------------------------------------------------------------------
# 9. Duplicate records detected
# -----------------------------------------------------------------------------
def test_duplicate_records_detected():
    config = PipelineConfig()
    pipeline = ElexonDataPipeline(config)

    raw_wind = [
        {"publishTime": "2026-01-01T04:30:00Z", "startTime": "2026-01-02T12:00:00Z", "generation": 15000.0},
        {"publishTime": "2026-01-01T04:30:00Z", "startTime": "2026-01-02T12:00:00Z", "generation": 15000.0},  # duplicate
    ]

    clean_fcs, summary = pipeline.process_windfor_forecasts(raw_wind)
    assert len(clean_fcs) == 1
    assert summary["duplicate_count"] == 1
    assert summary["conflicts_detected"] == 0


# -----------------------------------------------------------------------------
# 10. Conflicting forecast values at same publication timestamp are flagged
# -----------------------------------------------------------------------------
def test_conflicting_forecast_values_flagged():
    config = PipelineConfig()
    pipeline = ElexonDataPipeline(config)

    raw_wind = [
        {"publishTime": "2026-01-01T04:30:00Z", "startTime": "2026-01-02T12:00:00Z", "generation": 15000.0},
        {"publishTime": "2026-01-01T04:30:00Z", "startTime": "2026-01-02T12:00:00Z", "generation": 16500.0},  # conflicting MW
    ]

    clean_fcs, summary = pipeline.process_windfor_forecasts(raw_wind)
    assert len(clean_fcs) == 1
    assert summary["conflicts_detected"] == 1
    assert summary["conflicts"][0]["existing_mw"] == 15000.0
    assert summary["conflicts"][0]["new_mw"] == 16500.0


# -----------------------------------------------------------------------------
# 11. API timeouts and non-200 responses handled with retry
# -----------------------------------------------------------------------------
def test_api_timeouts_and_non_200_handled_with_retry():
    config = PipelineConfig(max_retries=2, retry_backoff=0.01)
    pipeline = ElexonDataPipeline(config)

    # Subtest A: Transient ReadTimeout recovered on attempt 2
    mock_client_a = MagicMock(spec=httpx.Client)
    mock_resp_success = MagicMock(status_code=200)
    mock_resp_success.json.return_value = [{"test": 1}]
    mock_client_a.get.side_effect = [httpx.ReadTimeout("Timeout"), mock_resp_success]

    data, err = pipeline.fetch_with_retry(mock_client_a, "/test", {})
    assert err is None
    assert data == [{"test": 1}]
    assert mock_client_a.get.call_count == 2

    # Subtest B: Persistent 500 error exhausted
    mock_client_b = MagicMock(spec=httpx.Client)
    mock_resp_500 = MagicMock(status_code=500, text="Internal Server Error")
    mock_client_b.get.side_effect = [mock_resp_500, mock_resp_500]

    data, err = pipeline.fetch_with_retry(mock_client_b, "/test", {})
    assert data is None
    assert "HTTP 500" in err
    assert mock_client_b.get.call_count == 2

    # Subtest C: Non-transient 400 Bad Request immediately fails without retry
    mock_client_c = MagicMock(spec=httpx.Client)
    mock_resp_400 = MagicMock(status_code=400, text="Bad Request")
    mock_client_c.get.side_effect = [mock_resp_400]

    data, err = pipeline.fetch_with_retry(mock_client_c, "/test", {})
    assert data is None
    assert "HTTP 400" in err
    assert mock_client_c.get.call_count == 1  # No wasteful retry


# -----------------------------------------------------------------------------
# 12. Incomplete API coverage cannot be labelled complete
# -----------------------------------------------------------------------------
def test_incomplete_coverage_cannot_be_labelled_complete():
    config = PipelineConfig(delivery_start_date="2026-01-01", delivery_end_date="2026-01-02")
    pipeline = ElexonDataPipeline(config)

    # 48 expected hours across 2 days, but only 1 hour provided
    hourly_actuals = {
        "2026-01-01T00:00:00+00:00": {"actual_generation_mw": 5000.0, "actual_available": True, "quality_flags": []}
    }
    forecasts = [
        {"publishTime": "2025-12-31T09:30:00Z", "startTime": "2026-01-01T00:00:00Z", "generation": 5100.0,
         "_pub_dt": datetime(2025, 12, 31, 9, 30, tzinfo=timezone.utc), "_start_dt": datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)}
    ]

    _, summary = pipeline.build_canonical_evaluation_dataset(hourly_actuals, forecasts)
    assert summary["total_intervals"] == 48
    assert summary["complete_evaluation_pairs"] == 1
    # Strict rule: cannot be labelled complete
    assert summary["is_fully_complete"] is False


# -----------------------------------------------------------------------------
# 13. Date-range boundaries are handled correctly
# -----------------------------------------------------------------------------
def test_date_range_boundaries_handled_correctly():
    hours = generate_expected_delivery_hours("2026-01-01", "2026-01-02")
    assert len(hours) == 48
    assert hours[0] == datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert hours[-1] == datetime(2026, 1, 2, 23, 0, tzinfo=timezone.utc)
