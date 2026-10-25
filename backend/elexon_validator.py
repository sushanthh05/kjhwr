"""
elexon_validator.py
Validation and parsing utilities for Elexon BMRS datasets:
- FUELHH (Half-hourly generation outturn by fuel type)
- WINDFOR (Wind generation forecast)

Also provides deterministic decision-cutoff forecast selection logic.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def parse_iso_timestamp(ts: Any) -> Optional[datetime]:
    """
    Safely parses an ISO 8601 timestamp string into a timezone-aware UTC datetime.
    Returns None if missing, malformed, or not a string.
    """
    if not isinstance(ts, str) or not ts.strip():
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def validate_fuelhh_records(records: Any) -> Dict[str, Any]:
    """
    Validates a list of FUELHH actual generation records.
    Required fields: 'startTime', 'generation', 'fuelType'.
    Returns a comprehensive validation summary and clean records.
    """
    summary: Dict[str, Any] = {
        "dataset": "FUELHH",
        "total_records": 0,
        "valid_records_count": 0,
        "invalid_records_count": 0,
        "missing_fields_records": 0,
        "malformed_timestamps_records": 0,
        "fuel_types": set(),
        "distinct_start_times": 0,
        "min_start_time": None,
        "max_start_time": None,
        "duplicates": [],
        "conflicts": [],
        "valid_records": [],
        "errors": []
    }

    if not isinstance(records, list):
        summary["errors"].append(f"Expected records list, got {type(records).__name__}")
        return summary

    summary["total_records"] = len(records)
    observed_keys: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    valid_start_dts: List[datetime] = []

    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            summary["invalid_records_count"] += 1
            summary["errors"].append(f"Record #{idx} is not a dictionary.")
            continue

        # Check required fields
        has_start = "startTime" in rec and rec["startTime"] is not None
        has_gen = "generation" in rec and rec["generation"] is not None
        has_fuel = "fuelType" in rec and rec["fuelType"] is not None

        if not (has_start and has_gen and has_fuel):
            summary["invalid_records_count"] += 1
            summary["missing_fields_records"] += 1
            missing = [f for f, exists in [("startTime", has_start), ("generation", has_gen), ("fuelType", has_fuel)] if not exists]
            summary["errors"].append(f"Record #{idx} missing required fields: {', '.join(missing)}")
            continue

        # Parse timestamp
        start_dt = parse_iso_timestamp(rec["startTime"])
        if start_dt is None:
            summary["invalid_records_count"] += 1
            summary["malformed_timestamps_records"] += 1
            summary["errors"].append(f"Record #{idx} has invalid startTime: {rec.get('startTime')}")
            continue

        # Check generation is numeric
        gen = rec["generation"]
        if not isinstance(gen, (int, float)) or isinstance(gen, bool):
            summary["invalid_records_count"] += 1
            summary["errors"].append(f"Record #{idx} generation is not numeric: {gen}")
            continue

        fuel_type = str(rec["fuelType"]).strip().upper()
        summary["fuel_types"].add(fuel_type)
        valid_start_dts.append(start_dt)

        cleaned_rec = {
            "dataset": rec.get("dataset", "FUELHH"),
            "startTime": start_dt.isoformat(),
            "publishTime": rec.get("publishTime"),
            "settlementDate": rec.get("settlementDate"),
            "settlementPeriod": rec.get("settlementPeriod"),
            "fuelType": fuel_type,
            "generation": float(gen),
            "_dt": start_dt
        }
        summary["valid_records"].append(cleaned_rec)
        summary["valid_records_count"] += 1

        # Track duplicates by delivery interval and fuel type
        key = (start_dt.isoformat(), fuel_type)
        if key in observed_keys:
            existing = observed_keys[key]
            summary["duplicates"].append({
                "key": key,
                "first_index": existing[0]["_idx"],
                "duplicate_index": idx
            })
            if any(prev["generation"] != float(gen) for prev in existing):
                summary["conflicts"].append({
                    "key": key,
                    "previous_generations": [prev["generation"] for prev in existing],
                    "new_generation": float(gen),
                    "duplicate_index": idx
                })
            existing.append({"_idx": idx, "generation": float(gen)})
        else:
            observed_keys[key] = [{"_idx": idx, "generation": float(gen)}]

    summary["distinct_start_times"] = len(set(dt.isoformat() for dt in valid_start_dts))
    if valid_start_dts:
        summary["min_start_time"] = min(valid_start_dts).isoformat()
        summary["max_start_time"] = max(valid_start_dts).isoformat()

    summary["fuel_types"] = sorted(list(summary["fuel_types"]))
    return summary


def validate_windfor_records(records: Any) -> Dict[str, Any]:
    """
    Validates a list of WINDFOR wind forecast records.
    Required fields: 'startTime', 'publishTime', 'generation'.
    Returns a comprehensive validation summary and clean records.
    """
    summary: Dict[str, Any] = {
        "dataset": "WINDFOR",
        "total_records": 0,
        "valid_records_count": 0,
        "invalid_records_count": 0,
        "missing_fields_records": 0,
        "malformed_timestamps_records": 0,
        "distinct_publish_times": 0,
        "distinct_start_times": 0,
        "min_publish_time": None,
        "max_publish_time": None,
        "min_start_time": None,
        "max_start_time": None,
        "duplicates": [],
        "conflicts": [],
        "valid_records": [],
        "errors": []
    }

    if not isinstance(records, list):
        summary["errors"].append(f"Expected records list, got {type(records).__name__}")
        return summary

    summary["total_records"] = len(records)
    observed_keys: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    valid_pub_dts: List[datetime] = []
    valid_start_dts: List[datetime] = []

    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            summary["invalid_records_count"] += 1
            summary["errors"].append(f"Record #{idx} is not a dictionary.")
            continue

        # Check required fields
        has_start = "startTime" in rec and rec["startTime"] is not None
        has_pub = "publishTime" in rec and rec["publishTime"] is not None
        has_gen = "generation" in rec and rec["generation"] is not None

        if not (has_start and has_pub and has_gen):
            summary["invalid_records_count"] += 1
            summary["missing_fields_records"] += 1
            missing = [f for f, exists in [("startTime", has_start), ("publishTime", has_pub), ("generation", has_gen)] if not exists]
            summary["errors"].append(f"Record #{idx} missing required fields: {', '.join(missing)}")
            continue

        # Parse timestamps
        start_dt = parse_iso_timestamp(rec["startTime"])
        pub_dt = parse_iso_timestamp(rec["publishTime"])

        if start_dt is None or pub_dt is None:
            summary["invalid_records_count"] += 1
            summary["malformed_timestamps_records"] += 1
            invalid_fields = []
            if start_dt is None:
                invalid_fields.append(f"startTime='{rec.get('startTime')}'")
            if pub_dt is None:
                invalid_fields.append(f"publishTime='{rec.get('publishTime')}'")
            summary["errors"].append(f"Record #{idx} has invalid timestamp: {', '.join(invalid_fields)}")
            continue

        # Check generation is numeric
        gen = rec["generation"]
        if not isinstance(gen, (int, float)) or isinstance(gen, bool):
            summary["invalid_records_count"] += 1
            summary["errors"].append(f"Record #{idx} generation is not numeric: {gen}")
            continue

        valid_pub_dts.append(pub_dt)
        valid_start_dts.append(start_dt)

        cleaned_rec = {
            "dataset": rec.get("dataset", "WINDFOR"),
            "publishTime": pub_dt.isoformat(),
            "startTime": start_dt.isoformat(),
            "generation": float(gen),
            "_pub_dt": pub_dt,
            "_start_dt": start_dt
        }
        summary["valid_records"].append(cleaned_rec)
        summary["valid_records_count"] += 1

        # Check duplicate vintage key: (publishTime, startTime)
        key = (pub_dt.isoformat(), start_dt.isoformat())
        if key in observed_keys:
            existing = observed_keys[key]
            summary["duplicates"].append({
                "key": key,
                "first_index": existing[0]["_idx"],
                "duplicate_index": idx
            })
            if any(prev["generation"] != float(gen) for prev in existing):
                summary["conflicts"].append({
                    "key": key,
                    "previous_generations": [prev["generation"] for prev in existing],
                    "new_generation": float(gen),
                    "duplicate_index": idx
                })
            existing.append({"_idx": idx, "generation": float(gen)})
        else:
            observed_keys[key] = [{"_idx": idx, "generation": float(gen)}]

    summary["distinct_publish_times"] = len(set(dt.isoformat() for dt in valid_pub_dts))
    summary["distinct_start_times"] = len(set(dt.isoformat() for dt in valid_start_dts))

    if valid_pub_dts:
        summary["min_publish_time"] = min(valid_pub_dts).isoformat()
        summary["max_publish_time"] = max(valid_pub_dts).isoformat()

    if valid_start_dts:
        summary["min_start_time"] = min(valid_start_dts).isoformat()
        summary["max_start_time"] = max(valid_start_dts).isoformat()

    return summary


def select_decision_forecast(
    forecast_records: List[Dict[str, Any]],
    delivery_time: Any,
    decision_cutoff: Any
) -> Optional[Dict[str, Any]]:
    """
    Selects the latest forecast published at or before the decision cutoff
    for a specified delivery interval (startTime).

    Constraints:
    1. The forecast's target delivery interval must match `delivery_time`.
    2. Eligibility condition: `publishTime <= decision_cutoff`.
    3. Any forecast published after `decision_cutoff` (`publishTime > decision_cutoff`)
       MUST BE STRICTLY EXCLUDED, even if it is the newest forecast overall.
    4. Among all eligible forecasts, the one with the latest `publishTime` is selected.

    Returns:
        The selected forecast record, or None if no eligible forecast exists.
    """
    target_start_dt = delivery_time if isinstance(delivery_time, datetime) else parse_iso_timestamp(delivery_time)
    cutoff_dt = decision_cutoff if isinstance(decision_cutoff, datetime) else parse_iso_timestamp(decision_cutoff)

    if target_start_dt is None or cutoff_dt is None:
        return None

    # Ensure timezone awareness
    if target_start_dt.tzinfo is None:
        target_start_dt = target_start_dt.replace(tzinfo=timezone.utc)
    if cutoff_dt.tzinfo is None:
        cutoff_dt = cutoff_dt.replace(tzinfo=timezone.utc)

    eligible_forecasts: List[Tuple[datetime, Dict[str, Any]]] = []

    for rec in forecast_records:
        rec_start_dt = rec.get("_start_dt") or parse_iso_timestamp(rec.get("startTime"))
        rec_pub_dt = rec.get("_pub_dt") or parse_iso_timestamp(rec.get("publishTime"))

        if rec_start_dt is None or rec_pub_dt is None:
            continue

        # Match delivery interval
        if rec_start_dt != target_start_dt:
            continue

        # Check cutoff constraint: publishTime <= decision_cutoff
        if rec_pub_dt <= cutoff_dt:
            eligible_forecasts.append((rec_pub_dt, rec))
        # If rec_pub_dt > cutoff_dt: strictly ineligible (disregarded)

    if not eligible_forecasts:
        return None

    # Select latest published before cutoff
    eligible_forecasts.sort(key=lambda item: item[0], reverse=True)
    return eligible_forecasts[0][1]
