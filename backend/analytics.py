"""
analytics.py
Forecast Accuracy Analytics Engine for Wind Forecast Intelligence (Phase 3).

Core Analytics Capabilities:
- Pure metric calculation functions (MAE, RMSE, MBE, MAPE, quantiles).
- Strict error sign convention:
    error_mw = forecast_generation_mw - actual_generation_mw
    (positive = overforecast, negative = underforecast)
- Safe MAPE computation with explicit zero-actual exclusions.
- Complete hourly timeseries, daily aggregations, and hour-of-day profiling in Europe/London.
- Error distribution and exact-sum histogram binning.
- Deterministic worst forecast misses sorting.
- In-memory caching and custom dataset injection for testing.
"""

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import os

BACKEND_DIR = Path(__file__).resolve().parent
_env_canonical = os.getenv("CANONICAL_DATASET_PATH")
DEFAULT_CANONICAL_PATH = Path(_env_canonical).resolve() if _env_canonical else (BACKEND_DIR / "data" / "processed" / "canonical_evaluation_dataset.json")

_env_summary = os.getenv("INGESTION_SUMMARY_PATH")
DEFAULT_SUMMARY_PATH = Path(_env_summary).resolve() if _env_summary else (BACKEND_DIR / "data" / "processed" / "ingestion_summary.json")

_CACHED_DATASET: Optional[List[Dict[str, Any]]] = None
_CACHED_SUMMARY: Optional[Dict[str, Any]] = None


def load_canonical_dataset(
    data_path: Optional[Path] = None,
    force_reload: bool = False
) -> List[Dict[str, Any]]:
    """
    Loads the canonical evaluation dataset from disk with in-memory caching.
    Raises FileNotFoundError or ValueError with clear diagnostic messages if missing or invalid.
    """
    global _CACHED_DATASET
    if _CACHED_DATASET is not None and not force_reload and data_path is None:
        return _CACHED_DATASET

    path = data_path or DEFAULT_CANONICAL_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Canonical evaluation dataset not found at '{path}'. "
            f"Please run 'scripts/build_evaluation_dataset.py' to generate the Phase 2 dataset."
        )

    try:
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
    except Exception as exc:
        raise ValueError(f"Failed to read canonical dataset JSON from '{path}': {exc}")

    if not isinstance(records, list) or len(records) == 0:
        raise ValueError(f"Canonical dataset at '{path}' is empty or not a valid JSON array.")

    if data_path is None:
        _CACHED_DATASET = records
    return records


def load_ingestion_summary(summary_path: Optional[Path] = None) -> Dict[str, Any]:
    """Loads the Phase 2 ingestion and data-quality summary JSON."""
    global _CACHED_SUMMARY
    if _CACHED_SUMMARY is not None and summary_path is None:
        return _CACHED_SUMMARY

    path = summary_path or DEFAULT_SUMMARY_PATH
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if summary_path is None:
                _CACHED_SUMMARY = data
            return data
    except Exception:
        return {}


def parse_date_bound(d_str: Optional[str]) -> Optional[date]:
    """Parses an ISO format date string (YYYY-MM-DD), raising ValueError if invalid."""
    if not d_str:
        return None
    try:
        return date.fromisoformat(d_str.strip())
    except (ValueError, TypeError):
        raise ValueError(f"Invalid date parameter '{d_str}'. Must be in YYYY-MM-DD format.")


def filter_records_by_date(
    records: List[Dict[str, Any]],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Filters records by delivery date range (inclusive).
    Validates range order and formats.
    """
    start_d = parse_date_bound(start_date)
    end_d = parse_date_bound(end_date)

    if start_d and end_d and start_d > end_d:
        raise ValueError(f"start_date '{start_date}' cannot be after end_date '{end_date}'.")

    if not start_d and not end_d:
        return records

    filtered = []
    for rec in records:
        delivery_str = rec.get("delivery_time_utc", "")
        try:
            rec_date = date.fromisoformat(delivery_str[:10])
        except Exception:
            continue

        if start_d and rec_date < start_d:
            continue
        if end_d and rec_date > end_d:
            continue
        filtered.append(rec)

    return filtered


def validate_and_extract_pairs(
    records: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Audits input records and extracts valid matched forecast-actual pairs.
    Checks:
    - Non-finite numbers (NaN, Inf).
    - Missing actual or forecast values.
    - Duplicate delivery timestamps.
    - Publication timestamp not later than decision cutoff.
    """
    valid_pairs: List[Dict[str, Any]] = []
    observed_delivery_times: set = set()
    exclusions: List[Dict[str, Any]] = []

    for idx, rec in enumerate(records):
        delivery_time = rec.get("delivery_time_utc")
        if not delivery_time:
            exclusions.append({"index": idx, "reason": "MISSING_DELIVERY_TIME"})
            continue

        if delivery_time in observed_delivery_times:
            exclusions.append({
                "index": idx,
                "delivery_time": delivery_time,
                "reason": "DUPLICATE_DELIVERY_TIMESTAMP"
            })
            continue
        observed_delivery_times.add(delivery_time)

        fc_avail = rec.get("forecast_available", False)
        act_avail = rec.get("actual_available", False)
        fc_val = rec.get("forecast_generation_mw")
        act_val = rec.get("actual_generation_mw")

        if not fc_avail or fc_val is None:
            exclusions.append({"index": idx, "delivery_time": delivery_time, "reason": "MISSING_FORECAST"})
            continue

        if not act_avail or act_val is None:
            exclusions.append({"index": idx, "delivery_time": delivery_time, "reason": "MISSING_ACTUAL"})
            continue

        try:
            fc_float = float(fc_val)
            act_float = float(act_val)
        except (ValueError, TypeError):
            exclusions.append({"index": idx, "delivery_time": delivery_time, "reason": "NON_NUMERIC_VALUE"})
            continue

        if not math.isfinite(fc_float) or not math.isfinite(act_float):
            exclusions.append({"index": idx, "delivery_time": delivery_time, "reason": "NON_FINITE_NUMERIC_VALUE"})
            continue

        # Invariant check: selected forecast publication must not be after decision cutoff
        pub_str = rec.get("forecast_publish_time_utc")
        cut_str = rec.get("decision_cutoff_utc")
        if pub_str and cut_str:
            try:
                pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                cut_dt = datetime.fromisoformat(cut_str.replace("Z", "+00:00"))
                if pub_dt > cut_dt:
                    exclusions.append({
                        "index": idx,
                        "delivery_time": delivery_time,
                        "reason": "FORECAST_PUBLISHED_AFTER_CUTOFF",
                        "publishTime": pub_str,
                        "decision_cutoff": cut_str
                    })
                    continue
            except Exception:
                pass

        error_mw = fc_float - act_float
        abs_error_mw = abs(error_mw)

        abs_pct_err = None
        if act_float > 0:
            abs_pct_err = (abs_error_mw / act_float) * 100.0

        valid_pairs.append({
            "delivery_time_utc": delivery_time,
            "decision_cutoff_utc": cut_str,
            "forecast_publish_time_utc": pub_str,
            "forecast_generation_mw": fc_float,
            "actual_generation_mw": act_float,
            "error_mw": round(error_mw, 3),
            "absolute_error_mw": round(abs_error_mw, 3),
            "absolute_percentage_error": round(abs_pct_err, 3) if abs_pct_err is not None else None,
            "forecast_age_hours": rec.get("forecast_age_hours"),
            "data_quality_flags": rec.get("data_quality_flags", "OK")
        })

    audit_summary = {
        "total_records_inspected": len(records),
        "valid_matched_pairs_count": len(valid_pairs),
        "excluded_records_count": len(exclusions),
        "exclusions": exclusions
    }
    return valid_pairs, audit_summary


def calculate_core_metrics(
    valid_pairs: List[Dict[str, Any]],
    total_expected_intervals: Optional[int] = None
) -> Dict[str, Any]:
    """
    Computes overall statistical and forecast accuracy metrics on valid matched pairs.
    Definitions:
        error_mw = forecast_mw - actual_mw
        MAE = mean(abs(error_mw))
        RMSE = sqrt(mean(error_mw^2))
        MBE = mean(error_mw)
        MAPE = mean(abs(error_mw) / actual_mw * 100) for actual_mw > 0
    """
    n = len(valid_pairs)
    if n == 0:
        return {
            "matched_pairs_count": 0,
            "expected_intervals_count": total_expected_intervals or 0,
            "matched_coverage_pct": 0.0,
            "mae_mw": None,
            "rmse_mw": None,
            "mbe_mw": None,
            "mape_pct": None,
            "mape_included_count": 0,
            "mape_excluded_zero_actual_count": 0,
            "max_absolute_error_mw": None,
            "median_absolute_error_mw": None,
            "mean_actual_mw": None,
            "mean_forecast_mw": None,
            "positive_error_count": 0,
            "negative_error_count": 0,
            "zero_error_count": 0
        }

    errors = [p["error_mw"] for p in valid_pairs]
    abs_errors = [p["absolute_error_mw"] for p in valid_pairs]
    forecasts = [p["forecast_generation_mw"] for p in valid_pairs]
    actuals = [p["actual_generation_mw"] for p in valid_pairs]

    mae = sum(abs_errors) / n
    rmse = math.sqrt(sum(e * e for e in errors) / n)
    mbe = sum(errors) / n

    # MAPE calculation strictly for observations where actual > 0
    eligible_pcts = [p["absolute_percentage_error"] for p in valid_pairs if p["actual_generation_mw"] > 0 and p["absolute_percentage_error"] is not None]
    zero_actual_count = sum(1 for p in valid_pairs if p["actual_generation_mw"] <= 0)
    mape = (sum(eligible_pcts) / len(eligible_pcts)) if eligible_pcts else None

    sorted_abs = sorted(abs_errors)
    median_abs = (
        sorted_abs[n // 2]
        if n % 2 != 0
        else (sorted_abs[(n // 2) - 1] + sorted_abs[n // 2]) / 2.0
    )

    pos_count = sum(1 for e in errors if e > 0)
    neg_count = sum(1 for e in errors if e < 0)
    zero_count = sum(1 for e in errors if e == 0)

    expected = total_expected_intervals or n
    coverage_pct = round((n / expected) * 100.0, 2) if expected > 0 else 0.0

    return {
        "matched_pairs_count": n,
        "expected_intervals_count": expected,
        "matched_coverage_pct": coverage_pct,
        "mae_mw": round(mae, 2),
        "rmse_mw": round(rmse, 2),
        "mbe_mw": round(mbe, 2),
        "mape_pct": round(mape, 2) if mape is not None else None,
        "mape_included_count": len(eligible_pcts),
        "mape_excluded_zero_actual_count": zero_actual_count,
        "max_absolute_error_mw": round(max(abs_errors), 2),
        "median_absolute_error_mw": round(median_abs, 2),
        "mean_actual_mw": round(sum(actuals) / n, 2),
        "mean_forecast_mw": round(sum(forecasts) / n, 2),
        "positive_error_count": pos_count,
        "negative_error_count": neg_count,
        "zero_error_count": zero_count
    }


def calculate_daily_metrics(
    records: List[Dict[str, Any]],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Groups valid matched pairs by delivery date and calculates daily MAE, RMSE, MBE, MAPE.
    Handles incomplete days by marking is_complete=False and providing actual interval count.
    """
    filtered = filter_records_by_date(records, start_date, end_date)
    valid_pairs, _ = validate_and_extract_pairs(filtered)

    by_date: Dict[str, List[Dict[str, Any]]] = {}
    for p in valid_pairs:
        d_str = p["delivery_time_utc"][:10]
        by_date.setdefault(d_str, []).append(p)

    daily_results = []
    for d_str in sorted(by_date.keys()):
        day_pairs = by_date[d_str]
        m = calculate_core_metrics(day_pairs, total_expected_intervals=24)
        daily_results.append({
            "delivery_date": d_str,
            "matched_interval_count": len(day_pairs),
            "expected_interval_count": 24,
            "is_complete": len(day_pairs) == 24,
            "mae_mw": m["mae_mw"],
            "rmse_mw": m["rmse_mw"],
            "mbe_mw": m["mbe_mw"],
            "mape_pct": m["mape_pct"],
            "mean_actual_mw": m["mean_actual_mw"],
            "mean_forecast_mw": m["mean_forecast_mw"]
        })
    return daily_results


def calculate_error_distribution(
    valid_pairs: List[Dict[str, Any]],
    num_bins: int = 10
) -> Dict[str, Any]:
    """
    Calculates error quantiles and constructs an exact-sum histogram binning structure.
    Every valid observation is accounted for exactly once in the histogram bins.
    """
    n = len(valid_pairs)
    if n == 0:
        return {
            "total_observations": 0,
            "positive_error_count": 0,
            "negative_error_count": 0,
            "zero_error_count": 0,
            "quantiles_signed_mw": {},
            "quantiles_absolute_mw": {},
            "histogram_bins": []
        }

    errors = sorted([p["error_mw"] for p in valid_pairs])
    abs_errors = sorted([p["absolute_error_mw"] for p in valid_pairs])

    def quantile(sorted_list: List[float], q: float) -> float:
        idx = q * (len(sorted_list) - 1)
        lower = int(math.floor(idx))
        upper = int(math.ceil(idx))
        weight = idx - lower
        return sorted_list[lower] * (1 - weight) + sorted_list[upper] * weight

    quantiles_signed = {
        "min": round(errors[0], 2),
        "p05": round(quantile(errors, 0.05), 2),
        "p10": round(quantile(errors, 0.10), 2),
        "p25": round(quantile(errors, 0.25), 2),
        "p50_median": round(quantile(errors, 0.50), 2),
        "p75": round(quantile(errors, 0.75), 2),
        "p90": round(quantile(errors, 0.90), 2),
        "p95": round(quantile(errors, 0.95), 2),
        "max": round(errors[-1], 2)
    }

    quantiles_abs = {
        "min": round(abs_errors[0], 2),
        "p25": round(quantile(abs_errors, 0.25), 2),
        "p50_median": round(quantile(abs_errors, 0.50), 2),
        "p75": round(quantile(abs_errors, 0.75), 2),
        "p90": round(quantile(abs_errors, 0.90), 2),
        "p95": round(quantile(abs_errors, 0.95), 2),
        "max": round(abs_errors[-1], 2)
    }

    # Build histogram: num_bins partitions from min to max error
    min_val = errors[0]
    max_val = errors[-1]
    span = max_val - min_val

    if span == 0:
        histogram_bins = [{
            "bin_index": 0,
            "bin_start_mw": min_val,
            "bin_end_mw": max_val,
            "count": n,
            "percentage": 100.0
        }]
    else:
        bin_width = span / num_bins
        counts = [0] * num_bins
        for val in errors:
            b_idx = int((val - min_val) / bin_width)
            if b_idx >= num_bins:
                b_idx = num_bins - 1
            counts[b_idx] += 1

        histogram_bins = []
        for i in range(num_bins):
            b_start = min_val + i * bin_width
            b_end = min_val + (i + 1) * bin_width
            histogram_bins.append({
                "bin_index": i,
                "bin_start_mw": round(b_start, 2),
                "bin_end_mw": round(b_end, 2),
                "count": counts[i],
                "percentage": round((counts[i] / n) * 100.0, 2)
            })

    return {
        "total_observations": n,
        "positive_error_count": sum(1 for e in errors if e > 0),
        "negative_error_count": sum(1 for e in errors if e < 0),
        "zero_error_count": sum(1 for e in errors if e == 0),
        "quantiles_signed_mw": quantiles_signed,
        "quantiles_absolute_mw": quantiles_abs,
        "histogram_bins": histogram_bins
    }


def calculate_worst_misses(
    valid_pairs: List[Dict[str, Any]],
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Returns the largest absolute errors in descending order.
    Uses deterministic tie-breaking: absolute_error_mw DESC, then delivery_time_utc ASC.
    """
    if limit < 1 or limit > 100:
        raise ValueError(f"Parameter 'limit' must be between 1 and 100 (got {limit}).")

    sorted_pairs = sorted(
        valid_pairs,
        key=lambda p: (-p["absolute_error_mw"], p["delivery_time_utc"])
    )

    top_n = sorted_pairs[:limit]
    return [
        {
            "rank": idx + 1,
            "delivery_time_utc": p["delivery_time_utc"],
            "decision_cutoff_utc": p["decision_cutoff_utc"],
            "forecast_publish_time_utc": p["forecast_publish_time_utc"],
            "forecast_generation_mw": p["forecast_generation_mw"],
            "actual_generation_mw": p["actual_generation_mw"],
            "error_mw": p["error_mw"],
            "absolute_error_mw": p["absolute_error_mw"],
            "absolute_percentage_error": p["absolute_percentage_error"],
            "forecast_age_hours": p["forecast_age_hours"]
        }
        for idx, p in enumerate(top_n)
    ]


def calculate_hour_of_day_metrics(
    valid_pairs: List[Dict[str, Any]],
    tz_name: str = "Europe/London"
) -> List[Dict[str, Any]]:
    """
    Groups observations by local delivery hour (0 to 23), explicitly using Europe/London.
    In January the UK is on GMT (UTC+0), but using explicit ZoneInfo guarantees future correctness.
    """
    try:
        local_tz = ZoneInfo(tz_name)
    except Exception:
        local_tz = timezone.utc

    by_hour: Dict[int, List[Dict[str, Any]]] = {h: [] for h in range(24)}

    for p in valid_pairs:
        d_str = p["delivery_time_utc"]
        dt = datetime.fromisoformat(d_str.replace("Z", "+00:00"))
        local_dt = dt.astimezone(local_tz)
        by_hour[local_dt.hour].append(p)

    results = []
    for h in range(24):
        pairs = by_hour[h]
        if pairs:
            m = calculate_core_metrics(pairs)
            results.append({
                "hour_of_day_local": h,
                "timezone": tz_name,
                "observation_count": len(pairs),
                "mae_mw": m["mae_mw"],
                "rmse_mw": m["rmse_mw"],
                "mbe_mw": m["mbe_mw"],
                "mape_pct": m["mape_pct"],
                "mean_actual_mw": m["mean_actual_mw"],
                "mean_forecast_mw": m["mean_forecast_mw"]
            })
        else:
            results.append({
                "hour_of_day_local": h,
                "timezone": tz_name,
                "observation_count": 0,
                "mae_mw": None,
                "rmse_mw": None,
                "mbe_mw": None,
                "mape_pct": None,
                "mean_actual_mw": None,
                "mean_forecast_mw": None
            })
    return results
