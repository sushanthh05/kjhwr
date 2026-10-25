"""
test_elexon_validation.py
Offline unit tests for Elexon BMRS parsing, schema validation,
and day-ahead decision cutoff forecast selection.
Does NOT require live internet access or external API calls.
"""

import pytest
from elexon_validator import (
    validate_fuelhh_records,
    validate_windfor_records,
    select_decision_forecast,
    parse_iso_timestamp
)


# -----------------------------------------------------------------------------
# 1. Valid Actual Records (FUELHH)
# -----------------------------------------------------------------------------
def test_valid_actual_records():
    fixtures = [
        {
            "dataset": "FUELHH",
            "publishTime": "2026-01-01T01:00:00Z",
            "startTime": "2026-01-01T00:00:00Z",
            "settlementDate": "2026-01-01",
            "settlementPeriod": 1,
            "fuelType": "WIND",
            "generation": 12450.5
        },
        {
            "dataset": "FUELHH",
            "publishTime": "2026-01-01T01:30:00Z",
            "startTime": "2026-01-01T00:30:00Z",
            "settlementDate": "2026-01-01",
            "settlementPeriod": 2,
            "fuelType": "WIND",
            "generation": 12890.0
        }
    ]

    summary = validate_fuelhh_records(fixtures)
    assert summary["total_records"] == 2
    assert summary["valid_records_count"] == 2
    assert summary["invalid_records_count"] == 0
    assert summary["fuel_types"] == ["WIND"]
    assert summary["distinct_start_times"] == 2
    assert summary["min_start_time"] == "2026-01-01T00:00:00+00:00"
    assert summary["max_start_time"] == "2026-01-01T00:30:00+00:00"
    assert len(summary["duplicates"]) == 0
    assert len(summary["conflicts"]) == 0


# -----------------------------------------------------------------------------
# 2. Valid Forecast Records (WINDFOR)
# -----------------------------------------------------------------------------
def test_valid_forecast_records():
    fixtures = [
        {
            "dataset": "WINDFOR",
            "publishTime": "2026-01-01T04:30:00Z",
            "startTime": "2026-01-02T10:00:00Z",
            "generation": 15400.0
        },
        {
            "dataset": "WINDFOR",
            "publishTime": "2026-01-01T04:30:00Z",
            "startTime": "2026-01-02T11:00:00Z",
            "generation": 15850.0
        },
        {
            "dataset": "WINDFOR",
            "publishTime": "2026-01-01T09:30:00Z",
            "startTime": "2026-01-02T10:00:00Z",
            "generation": 16100.0
        }
    ]

    summary = validate_windfor_records(fixtures)
    assert summary["total_records"] == 3
    assert summary["valid_records_count"] == 3
    assert summary["invalid_records_count"] == 0
    assert summary["distinct_publish_times"] == 2
    assert summary["distinct_start_times"] == 2
    assert summary["min_publish_time"] == "2026-01-01T04:30:00+00:00"
    assert summary["max_publish_time"] == "2026-01-01T09:30:00+00:00"


# -----------------------------------------------------------------------------
# 3. Missing Required Fields
# -----------------------------------------------------------------------------
def test_missing_required_fields():
    # FUELHH missing required fields
    fuel_records = [
        {"generation": 1000.0, "fuelType": "WIND"},                     # missing startTime
        {"startTime": "2026-01-01T00:00:00Z", "fuelType": "WIND"},       # missing generation
        {"startTime": "2026-01-01T00:00:00Z", "generation": 1000.0},     # missing fuelType
    ]
    summary_fuel = validate_fuelhh_records(fuel_records)
    assert summary_fuel["total_records"] == 3
    assert summary_fuel["valid_records_count"] == 0
    assert summary_fuel["invalid_records_count"] == 3
    assert summary_fuel["missing_fields_records"] == 3

    # WINDFOR missing required fields
    wind_records = [
        {"startTime": "2026-01-02T00:00:00Z", "generation": 1000.0},     # missing publishTime
        {"publishTime": "2026-01-01T00:00:00Z", "generation": 1000.0},   # missing startTime
        {"publishTime": "2026-01-01T00:00:00Z", "startTime": "2026-01-02T00:00:00Z"}  # missing generation
    ]
    summary_wind = validate_windfor_records(wind_records)
    assert summary_wind["total_records"] == 3
    assert summary_wind["valid_records_count"] == 0
    assert summary_wind["invalid_records_count"] == 3
    assert summary_wind["missing_fields_records"] == 3


# -----------------------------------------------------------------------------
# 4. Invalid Timestamps
# -----------------------------------------------------------------------------
def test_invalid_timestamps():
    fuel_records = [
        {"startTime": "not-a-timestamp", "generation": 500.0, "fuelType": "WIND"},
        {"startTime": "", "generation": 600.0, "fuelType": "WIND"},
        {"startTime": 12345, "generation": 700.0, "fuelType": "WIND"}
    ]
    summary_fuel = validate_fuelhh_records(fuel_records)
    assert summary_fuel["invalid_records_count"] == 3
    assert summary_fuel["malformed_timestamps_records"] == 3

    wind_records = [
        {"publishTime": "2026-02-30T00:00:00Z", "startTime": "2026-01-01T00:00:00Z", "generation": 500.0},
        {"publishTime": "2026-01-01T00:00:00Z", "startTime": "bad-iso", "generation": 500.0}
    ]
    summary_wind = validate_windfor_records(wind_records)
    assert summary_wind["invalid_records_count"] == 2
    assert summary_wind["malformed_timestamps_records"] == 2


# -----------------------------------------------------------------------------
# 5. Duplicate Delivery Timestamps & Conflict Detection
# -----------------------------------------------------------------------------
def test_duplicate_delivery_timestamps():
    fuel_records = [
        {"startTime": "2026-01-01T12:00:00Z", "generation": 10000.0, "fuelType": "WIND"},
        {"startTime": "2026-01-01T12:00:00Z", "generation": 10000.0, "fuelType": "WIND"},  # exact duplicate
        {"startTime": "2026-01-01T12:00:00Z", "generation": 12000.0, "fuelType": "WIND"},  # duplicate with conflicting generation
    ]
    summary = validate_fuelhh_records(fuel_records)
    assert summary["total_records"] == 3
    assert summary["valid_records_count"] == 3
    assert len(summary["duplicates"]) == 2
    assert len(summary["conflicts"]) == 1
    assert summary["conflicts"][0]["new_generation"] == 12000.0


# -----------------------------------------------------------------------------
# 6. Multiple Forecast Publications for the Same Delivery Interval
# -----------------------------------------------------------------------------
def test_multiple_forecast_publications_for_same_delivery_interval():
    delivery_interval = "2026-01-02T14:00:00Z"
    forecast_fixtures = [
        {"publishTime": "2026-01-01T04:30:00Z", "startTime": delivery_interval, "generation": 11000.0},
        {"publishTime": "2026-01-01T09:30:00Z", "startTime": delivery_interval, "generation": 11500.0},
        {"publishTime": "2026-01-01T16:30:00Z", "startTime": delivery_interval, "generation": 12200.0},
        {"publishTime": "2026-01-02T04:30:00Z", "startTime": delivery_interval, "generation": 13000.0},
    ]

    summary = validate_windfor_records(forecast_fixtures)
    assert summary["total_records"] == 4
    assert summary["valid_records_count"] == 4
    assert summary["distinct_publish_times"] == 4
    assert summary["distinct_start_times"] == 1
    assert len(summary["duplicates"]) == 0  # Different publishTimes mean distinct vintages, not duplicates


# -----------------------------------------------------------------------------
# 7. Selection of the Latest Forecast Published Before a Cutoff
# -----------------------------------------------------------------------------
def test_selection_of_latest_forecast_published_before_cutoff():
    delivery_interval = "2026-01-02T14:00:00Z"
    forecast_fixtures = [
        {"publishTime": "2026-01-01T04:30:00Z", "startTime": delivery_interval, "generation": 11000.0},
        {"publishTime": "2026-01-01T09:30:00Z", "startTime": delivery_interval, "generation": 11500.0},
        {"publishTime": "2026-01-01T16:30:00Z", "startTime": delivery_interval, "generation": 12200.0},
    ]

    # Day-ahead cutoff set to 12:00 on 2026-01-01
    decision_cutoff = "2026-01-01T12:00:00Z"

    selected = select_decision_forecast(forecast_fixtures, delivery_interval, decision_cutoff)
    assert selected is not None
    # 09:30 is the latest eligible publication before 12:00 (04:30 is also eligible but older)
    assert parse_iso_timestamp(selected["publishTime"]) == parse_iso_timestamp("2026-01-01T09:30:00Z")
    assert selected["generation"] == 11500.0


# -----------------------------------------------------------------------------
# 8. Exclusion of Forecasts Published After the Cutoff (No Look-Ahead Leakage)
# -----------------------------------------------------------------------------
def test_exclusion_of_forecasts_published_after_cutoff():
    delivery_interval = "2026-01-02T14:00:00Z"
    forecast_fixtures = [
        {"publishTime": "2026-01-01T04:30:00Z", "startTime": delivery_interval, "generation": 11000.0},
        {"publishTime": "2026-01-01T09:30:00Z", "startTime": delivery_interval, "generation": 11500.0},
        {"publishTime": "2026-01-01T16:30:00Z", "startTime": delivery_interval, "generation": 12200.0},  # Published AFTER 12:00
        {"publishTime": "2026-01-02T04:30:00Z", "startTime": delivery_interval, "generation": 14000.0},  # Published on delivery day
    ]

    # Case A: Decision cutoff at 12:00 on 2026-01-01
    decision_cutoff = "2026-01-01T12:00:00Z"
    selected = select_decision_forecast(forecast_fixtures, delivery_interval, decision_cutoff)

    assert selected is not None
    # The newest overall forecast (14000 MW at 2026-01-02T04:30) MUST NOT be selected
    assert selected["generation"] != 14000.0
    # The afternoon forecast (12200 MW at 2026-01-01T16:30) MUST NOT be selected
    assert selected["generation"] != 12200.0
    assert parse_iso_timestamp(selected["publishTime"]) == parse_iso_timestamp("2026-01-01T09:30:00Z")

    # Case B: When ALL forecasts were published AFTER the decision cutoff
    early_cutoff = "2026-01-01T03:00:00Z"
    selected_none = select_decision_forecast(forecast_fixtures, delivery_interval, early_cutoff)
    # Must return None because no eligible forecast existed prior to 03:00
    assert selected_none is None
