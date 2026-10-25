"""
elexon_data.py
Phase 2 Data Ingestion, Temporal Normalization, and Canonical Dataset Builder
for Elexon BMRS Datasets:
- FUELHH (Half-hourly actual wind generation outturn)
- WINDFOR (Wind generation forecasts with historical publication vintages)

Handles:
- Bounded chunked retrieval with exponential backoff retry.
- Half-hourly actuals to hourly average aggregation:
  hourly_actual_MW = (first_half_hour_MW + second_half_hour_MW) / 2
- Strict day-ahead decision cutoff forecast selection (publishTime <= decision_cutoff).
- Canonical dataset assembly with audit metadata and data quality flags.
- Atomic persistence to CSV/JSON and local cache reuse.
"""

import csv
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

import httpx

# Ensure local imports from backend
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from elexon_validator import (
    parse_iso_timestamp,
    validate_fuelhh_records,
    validate_windfor_records,
)

logger = logging.getLogger("elexon_data")


@dataclass
class PipelineConfig:
    delivery_start_date: str = "2026-01-01"
    delivery_end_date: str = "2026-01-31"
    decision_cutoff_time: str = "11:00"
    decision_timezone: str = "UTC"
    base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    chunk_days: int = 7
    max_retries: int = 3
    retry_backoff: float = 1.0
    timeout_sec: float = 30.0
    data_dir: Path = field(default_factory=lambda: BACKEND_DIR / "data")
    refresh: bool = False


def calculate_decision_cutoff(
    delivery_hour_utc: datetime,
    cutoff_time_str: str = "11:00",
    tz_name: str = "UTC"
) -> datetime:
    """
    Computes the day-ahead decision cutoff UTC datetime for a delivery interval.

    Rule:
    1. Delivery hour is converted to the configured decision timezone.
    2. The day-ahead decision is made on the previous calendar day (D - 1).
    3. The decision cutoff time is applied on (D - 1) at `cutoff_time_str`.
    4. The result is converted to UTC.
    """
    if delivery_hour_utc.tzinfo is None:
        delivery_hour_utc = delivery_hour_utc.replace(tzinfo=timezone.utc)
    else:
        delivery_hour_utc = delivery_hour_utc.astimezone(timezone.utc)

    try:
        decision_tz = ZoneInfo(tz_name)
    except Exception:
        decision_tz = timezone.utc

    # Delivery time in decision timezone
    local_delivery_dt = delivery_hour_utc.astimezone(decision_tz)
    local_delivery_date = local_delivery_dt.date()
    decision_date = local_delivery_date - timedelta(days=1)

    parts = cutoff_time_str.strip().split(":")
    cutoff_hour = int(parts[0])
    cutoff_minute = int(parts[1]) if len(parts) > 1 else 0

    local_cutoff_dt = datetime.combine(
        decision_date,
        dt_time(cutoff_hour, cutoff_minute),
        tzinfo=decision_tz
    )
    return local_cutoff_dt.astimezone(timezone.utc)


def generate_expected_delivery_hours(start_date_str: str, end_date_str: str) -> List[datetime]:
    """
    Generates a continuous sequence of hourly UTC timestamps from start_date 00:00 to end_date 23:00.
    """
    start_d = date.fromisoformat(start_date_str)
    end_d = date.fromisoformat(end_date_str)

    current_dt = datetime(start_d.year, start_d.month, start_d.day, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(end_d.year, end_d.month, end_d.day, 23, 0, tzinfo=timezone.utc)

    hours = []
    while current_dt <= end_dt:
        hours.append(current_dt)
        current_dt += timedelta(hours=1)
    return hours


def write_atomic_json(filepath: Path, data: Any) -> None:
    """Writes data to a temporary file in the same directory, then renames it atomically."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    temp_file = filepath.with_suffix(filepath.suffix + ".tmp")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    temp_file.replace(filepath)


def write_atomic_csv(filepath: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    """Writes tabular data to a temporary file in the same directory, then renames it atomically."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    temp_file = filepath.with_suffix(filepath.suffix + ".tmp")
    with open(temp_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        f.flush()
        os.fsync(f.fileno())
    temp_file.replace(filepath)


class ElexonDataPipeline:
    """
    Elexon BMRS Historical Data Ingestion and Normalization Engine.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.client_timeout = httpx.Timeout(
            connect=10.0,
            read=self.config.timeout_sec,
            write=10.0,
            pool=10.0
        )

    def fetch_with_retry(
        self,
        client: httpx.Client,
        endpoint_path: str,
        params: Dict[str, Any]
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Executes a GET request against Elexon API with bounded exponential backoff.
        Retries on transient errors (timeouts, connection drops, HTTP 429/5xx).
        """
        url = f"{self.config.base_url.rstrip('/')}{endpoint_path}"
        last_error = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data, None
                    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                        return data["data"], None
                    return None, f"Unexpected response schema: {type(data).__name__}"

                # Handle transient server errors or rate limiting
                if response.status_code in (429, 500, 502, 503, 504):
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    if attempt < self.config.max_retries:
                        sleep_time = self.config.retry_backoff * (2 ** (attempt - 1))
                        time.sleep(sleep_time)
                        continue
                else:
                    # Non-transient client error (e.g. 400 Bad Request)
                    return None, f"HTTP {response.status_code}: {response.text[:200]}"

            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
                last_error = f"Network error ({type(exc).__name__}): {exc}"
                if attempt < self.config.max_retries:
                    sleep_time = self.config.retry_backoff * (2 ** (attempt - 1))
                    time.sleep(sleep_time)
                    continue
            except Exception as exc:
                return None, f"Fatal exception ({type(exc).__name__}): {exc}"

        return None, last_error or "Max retries exceeded"

    def fetch_fuelhh_actuals(
        self,
        client: Optional[httpx.Client] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Retrieves FUELHH actual generation for the configured delivery date range.
        Filters server-side to fuelType == 'WIND'.
        """
        telemetry = {
            "dataset": "FUELHH",
            "settlementDateFrom": self.config.delivery_start_date,
            "settlementDateTo": self.config.delivery_end_date,
            "fuelType": "WIND",
            "request_count": 1,
            "failed_requests": [],
            "raw_records_count": 0,
            "elapsed_seconds": 0.0
        }

        raw_dir = self.config.data_dir / "raw" / "actuals"
        cache_file = raw_dir / f"fuelhh_raw_{self.config.delivery_start_date}_{self.config.delivery_end_date}.json"

        # Check local cache if refresh is not forced
        if not self.config.refresh and cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    telemetry["raw_records_count"] = len(cached_data)
                    telemetry["source"] = "local_cache"
                    return cached_data, telemetry
            except Exception as exc:
                logger.warning(f"Could not load cached FUELHH data: {exc}. Re-downloading.")

        params = {
            "settlementDateFrom": self.config.delivery_start_date,
            "settlementDateTo": self.config.delivery_end_date,
            "fuelType": "WIND"
        }

        t0 = time.perf_counter()
        owns_client = False
        if client is None:
            client = httpx.Client(timeout=self.client_timeout, follow_redirects=True)
            owns_client = True

        try:
            records, error = self.fetch_with_retry(client, "/datasets/FUELHH/stream", params)
            elapsed = time.perf_counter() - t0
            telemetry["elapsed_seconds"] = round(elapsed, 3)

            if error or records is None:
                telemetry["failed_requests"].append({"params": params, "error": error})
                return [], telemetry

            telemetry["raw_records_count"] = len(records)
            telemetry["source"] = "live_api"

            # Cache raw actuals atomically
            write_atomic_json(cache_file, records)
            return records, telemetry

        finally:
            if owns_client:
                client.close()

    def fetch_windfor_forecasts(
        self,
        client: Optional[httpx.Client] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Retrieves WINDFOR wind forecasts in bounded publication-date chunks.
        Ensures coverage begins prior to start_date (starting D - 2 days) so day-ahead
        forecasts published for early January deliveries are captured.
        """
        delivery_start = date.fromisoformat(self.config.delivery_start_date)
        delivery_end = date.fromisoformat(self.config.delivery_end_date)

        # Publication window starts 2 days prior to first delivery date to capture day-ahead vintages
        publish_start = datetime.combine(delivery_start - timedelta(days=2), dt_time(0, 0), tzinfo=timezone.utc)
        publish_end = datetime.combine(delivery_end, dt_time(23, 59, 59), tzinfo=timezone.utc)

        telemetry = {
            "dataset": "WINDFOR",
            "publishDateTimeFrom": publish_start.isoformat(),
            "publishDateTimeTo": publish_end.isoformat(),
            "chunk_days": self.config.chunk_days,
            "total_chunks": 0,
            "successful_chunks": 0,
            "failed_chunks": [],
            "raw_records_count": 0,
            "elapsed_seconds": 0.0
        }

        raw_dir = self.config.data_dir / "raw" / "forecasts"
        cache_file = raw_dir / f"windfor_raw_{self.config.delivery_start_date}_{self.config.delivery_end_date}.json"

        # Check local cache if refresh is not forced
        if not self.config.refresh and cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    telemetry["raw_records_count"] = len(cached_data)
                    telemetry["source"] = "local_cache"
                    return cached_data, telemetry
            except Exception as exc:
                logger.warning(f"Could not load cached WINDFOR data: {exc}. Re-downloading.")

        t0 = time.perf_counter()
        owns_client = False
        if client is None:
            client = httpx.Client(timeout=self.client_timeout, follow_redirects=True)
            owns_client = True

        all_records: List[Dict[str, Any]] = []
        current_chunk_start = publish_start

        try:
            while current_chunk_start < publish_end:
                current_chunk_end = min(current_chunk_start + timedelta(days=self.config.chunk_days), publish_end)
                telemetry["total_chunks"] += 1

                chunk_params = {
                    "publishDateTimeFrom": current_chunk_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "publishDateTimeTo": current_chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ")
                }

                records, error = self.fetch_with_retry(client, "/datasets/WINDFOR/stream", chunk_params)
                if error or records is None:
                    telemetry["failed_chunks"].append({"params": chunk_params, "error": error})
                else:
                    telemetry["successful_chunks"] += 1
                    all_records.extend(records)

                current_chunk_start = current_chunk_end

            elapsed = time.perf_counter() - t0
            telemetry["elapsed_seconds"] = round(elapsed, 3)
            telemetry["raw_records_count"] = len(all_records)
            telemetry["source"] = "live_api"

            # Cache raw forecasts atomically
            if all_records:
                write_atomic_json(cache_file, all_records)

            return all_records, telemetry

        finally:
            if owns_client:
                client.close()

    def aggregate_fuelhh_to_hourly(
        self,
        raw_fuel_records: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
        """
        Normalizes and aggregates half-hourly FUELHH actual records to hourly delivery intervals.

        Formula:
            hourly_actual_MW = (first_half_hour_MW + second_half_hour_MW) / 2.0

        Strict Quality Rules:
        - Exactly two valid half-hour intervals (:00 and :30) are required for a complete hour.
        - If either half-hour interval is missing or invalid, hourly_actual_MW is set to None
          and flagged as incomplete.
        - Power (MW) values are averaged, NOT summed.
        """
        validation_summary = validate_fuelhh_records(raw_fuel_records)
        valid_records = validation_summary.get("valid_records", [])

        # Group valid half-hours by their containing UTC hour
        # Elexon startTime represents interval start time:
        # e.g., 14:00:00Z is period 1 (14:00-14:30), 14:30:00Z is period 2 (14:30-15:00)
        grouped_by_hour: Dict[str, Dict[int, List[Dict[str, Any]]]] = {}

        for rec in valid_records:
            dt = rec["_dt"]
            hour_key = dt.replace(minute=0, second=0, microsecond=0).isoformat()
            minute = dt.minute

            if hour_key not in grouped_by_hour:
                grouped_by_hour[hour_key] = {0: [], 30: []}

            if minute in (0, 30):
                grouped_by_hour[hour_key][minute].append(rec)
            else:
                # Unexpected half-hour alignment
                grouped_by_hour[hour_key].setdefault(minute, []).append(rec)

        expected_hours = generate_expected_delivery_hours(
            self.config.delivery_start_date,
            self.config.delivery_end_date
        )

        hourly_actuals: Dict[str, Dict[str, Any]] = {}
        complete_count = 0
        incomplete_count = 0
        missing_count = 0
        conflicts_count = 0

        for h_dt in expected_hours:
            h_key = h_dt.isoformat()
            hour_data = grouped_by_hour.get(h_key)

            if not hour_data:
                hourly_actuals[h_key] = {
                    "delivery_time_utc": h_key,
                    "actual_generation_mw": None,
                    "actual_available": False,
                    "quality_flags": ["MISSING_FULL_HOUR_ACTUAL"],
                    "h0_mw": None,
                    "h30_mw": None
                }
                missing_count += 1
                continue

            h0_list = hour_data.get(0, [])
            h30_list = hour_data.get(30, [])
            flags: List[str] = []

            # Check duplicate / conflicting entries for minute 0
            if len(h0_list) > 1:
                flags.append("DUPLICATE_ACTUAL_H0")
                if any(x["generation"] != h0_list[0]["generation"] for x in h0_list):
                    flags.append("CONFLICTING_ACTUAL_H0")
                    conflicts_count += 1

            # Check duplicate / conflicting entries for minute 30
            if len(h30_list) > 1:
                flags.append("DUPLICATE_ACTUAL_H30")
                if any(x["generation"] != h30_list[0]["generation"] for x in h30_list):
                    flags.append("CONFLICTING_ACTUAL_H30")
                    conflicts_count += 1

            h0_val = h0_list[0]["generation"] if h0_list else None
            h30_val = h30_list[0]["generation"] if h30_list else None

            if h0_val is None:
                flags.append("MISSING_FIRST_HALF_HOUR")
            if h30_val is None:
                flags.append("MISSING_SECOND_HALF_HOUR")

            if h0_val is not None and h30_val is not None:
                # Correct hourly power average (MW)
                hourly_mw = round((h0_val + h30_val) / 2.0, 3)
                hourly_actuals[h_key] = {
                    "delivery_time_utc": h_key,
                    "actual_generation_mw": hourly_mw,
                    "actual_available": True,
                    "quality_flags": flags,
                    "h0_mw": h0_val,
                    "h30_mw": h30_val
                }
                complete_count += 1
            else:
                flags.append("INCOMPLETE_ACTUAL_PAIR")
                hourly_actuals[h_key] = {
                    "delivery_time_utc": h_key,
                    "actual_generation_mw": None,
                    "actual_available": False,
                    "quality_flags": flags,
                    "h0_mw": h0_val,
                    "h30_mw": h30_val
                }
                incomplete_count += 1

        summary = {
            "total_expected_hours": len(expected_hours),
            "complete_hours": complete_count,
            "incomplete_hours": incomplete_count,
            "missing_hours": missing_count,
            "conflicts_count": conflicts_count,
            "validation": validation_summary
        }
        return hourly_actuals, summary

    def process_windfor_forecasts(
        self,
        raw_wind_records: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Validates, deduplicates, and indexes WINDFOR forecast records.
        Deduplicates by composite key (publishTime, startTime).
        Flags conflicting generation values if observed for the same key.
        """
        validation_summary = validate_windfor_records(raw_wind_records)
        valid_records = validation_summary.get("valid_records", [])

        deduped_records: Dict[Tuple[str, str], Dict[str, Any]] = {}
        conflicts: List[Dict[str, Any]] = []

        for rec in valid_records:
            key = (rec["publishTime"], rec["startTime"])
            if key in deduped_records:
                existing = deduped_records[key]
                if existing["generation"] != rec["generation"]:
                    conflicts.append({
                        "key": key,
                        "existing_mw": existing["generation"],
                        "new_mw": rec["generation"]
                    })
                    # Deterministic tie-break: retain existing, flag conflict
            else:
                deduped_records[key] = rec

        clean_forecasts = list(deduped_records.values())
        summary = {
            "total_raw_valid": len(valid_records),
            "deduplicated_count": len(clean_forecasts),
            "duplicate_count": len(valid_records) - len(clean_forecasts),
            "conflicts_detected": len(conflicts),
            "distinct_publish_times": validation_summary.get("distinct_publish_times", 0),
            "distinct_start_times": validation_summary.get("distinct_start_times", 0),
            "min_publish_time": validation_summary.get("min_publish_time"),
            "max_publish_time": validation_summary.get("max_publish_time"),
            "min_start_time": validation_summary.get("min_start_time"),
            "max_start_time": validation_summary.get("max_start_time"),
            "conflicts": conflicts
        }
        return clean_forecasts, summary

    def build_canonical_evaluation_dataset(
        self,
        hourly_actuals: Dict[str, Dict[str, Any]],
        clean_forecasts: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Matches normalized hourly actuals with the latest eligible forecast published
        at or before the day-ahead decision cutoff.

        Constraints:
        1. Forecast publishTime <= decision_cutoff_utc.
        2. Any forecast published after cutoff is strictly excluded.
        3. Forecast age is computed as (decision_cutoff_utc - publish_time).
        4. One record per hourly delivery interval across the requested scope.
        """
        expected_hours = generate_expected_delivery_hours(
            self.config.delivery_start_date,
            self.config.delivery_end_date
        )

        # Index forecasts by delivery interval startTime as normalized UTC datetime
        forecasts_by_delivery: Dict[datetime, List[Dict[str, Any]]] = {}
        for fc in clean_forecasts:
            st_dt = fc.get("_start_dt") or parse_iso_timestamp(fc.get("startTime"))
            if st_dt is not None:
                if st_dt.tzinfo is None:
                    st_dt = st_dt.replace(tzinfo=timezone.utc)
                else:
                    st_dt = st_dt.astimezone(timezone.utc)
                forecasts_by_delivery.setdefault(st_dt, []).append(fc)

        canonical_rows: List[Dict[str, Any]] = []
        matched_count = 0
        missing_forecast_count = 0
        missing_actual_count = 0
        complete_pair_count = 0

        for h_dt in expected_hours:
            h_key = h_dt.isoformat()
            cutoff_dt = calculate_decision_cutoff(
                h_dt,
                self.config.decision_cutoff_time,
                self.config.decision_timezone
            )
            cutoff_key = cutoff_dt.isoformat()

            # Retrieve available forecasts for this delivery interval
            available_fcs = forecasts_by_delivery.get(h_dt, [])

            # Filter to eligible forecasts: publishTime <= decision_cutoff
            eligible_fcs = []
            for fc in available_fcs:
                pub_dt = fc.get("_pub_dt") or parse_iso_timestamp(fc.get("publishTime"))
                if pub_dt is not None:
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                    else:
                        pub_dt = pub_dt.astimezone(timezone.utc)
                    if pub_dt <= cutoff_dt:
                        eligible_fcs.append((pub_dt, fc))

            flags: List[str] = []

            # Retrieve actual generation details (support +00:00, Z, and datetime keying)
            actual_info = (
                hourly_actuals.get(h_key)
                or hourly_actuals.get(h_key.replace("+00:00", "Z"))
                or hourly_actuals.get(h_dt)
                or {
                    "actual_generation_mw": None,
                    "actual_available": False,
                    "quality_flags": ["MISSING_ACTUAL_RECORD"]
                }
            )
            flags.extend(actual_info.get("quality_flags", []))

            selected_fc = None
            if eligible_fcs:
                # Sort by publishTime descending to select the latest published before cutoff
                eligible_fcs.sort(key=lambda item: item[0], reverse=True)
                selected_fc = eligible_fcs[0][1]

                # Check if multiple forecasts exist with the exact same latest publishTime and conflicting MW
                latest_pub_dt = eligible_fcs[0][0]
                same_pub = [fc for dt, fc in eligible_fcs if dt == latest_pub_dt]
                if len(same_pub) > 1 and any(fc["generation"] != selected_fc["generation"] for fc in same_pub):
                    flags.append("CONFLICTING_FORECAST_AT_CUTOFF")

                matched_count += 1
            else:
                flags.append("NO_ELIGIBLE_FORECAST_BEFORE_CUTOFF")
                missing_forecast_count += 1

            actual_mw = actual_info.get("actual_generation_mw")
            actual_avail = actual_info.get("actual_available", False)

            if not actual_avail:
                missing_actual_count += 1

            if selected_fc is not None:
                fc_mw = selected_fc["generation"]
                fc_pub_time = selected_fc["publishTime"]
                pub_dt = selected_fc.get("_pub_dt") or parse_iso_timestamp(selected_fc["publishTime"])
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                fc_age = round((cutoff_dt - pub_dt).total_seconds() / 3600.0, 2)
                fc_avail = True
            else:
                fc_mw = None
                fc_pub_time = None
                fc_age = None
                fc_avail = False

            if fc_avail and actual_avail:
                complete_pair_count += 1

            # Clean and deduplicate flags
            flags = sorted(list(set(f for f in flags if f and f != "OK")))
            flags_str = "|".join(flags) if flags else "OK"

            row = {
                "delivery_time_utc": h_key,
                "decision_cutoff_utc": cutoff_key,
                "forecast_publish_time_utc": fc_pub_time,
                "forecast_generation_mw": fc_mw,
                "actual_generation_mw": actual_mw,
                "forecast_age_hours": fc_age,
                "forecast_available": fc_avail,
                "actual_available": actual_avail,
                "data_quality_flags": flags_str
            }
            canonical_rows.append(row)

        summary = {
            "total_intervals": len(expected_hours),
            "complete_evaluation_pairs": complete_pair_count,
            "intervals_with_forecast": matched_count,
            "intervals_missing_forecast": missing_forecast_count,
            "intervals_with_actual": len(expected_hours) - missing_actual_count,
            "intervals_missing_actual": missing_actual_count,
            "is_fully_complete": complete_pair_count == len(expected_hours),
            "earliest_delivery": expected_hours[0].isoformat() if expected_hours else None,
            "latest_delivery": expected_hours[-1].isoformat() if expected_hours else None
        }
        return canonical_rows, summary

    def run(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Executes the complete Phase 2 Ingestion, Normalization, and Dataset Generation pipeline.
        Saves raw data, canonical dataset (CSV/JSON), and ingestion summary atomically.
        """
        run_start_time = datetime.now(timezone.utc).isoformat()
        logger.info(f"Starting Elexon Ingestion Pipeline for {self.config.delivery_start_date} to {self.config.delivery_end_date}")

        # 1. Ingest FUELHH Actuals
        raw_actuals, actuals_telemetry = self.fetch_fuelhh_actuals()

        # 2. Ingest WINDFOR Forecasts
        raw_forecasts, forecasts_telemetry = self.fetch_windfor_forecasts()

        # 3. Aggregate Actuals to Hourly
        hourly_actuals, actuals_agg_summary = self.aggregate_fuelhh_to_hourly(raw_actuals)

        # 4. Deduplicate and Index Forecasts
        clean_forecasts, forecast_proc_summary = self.process_windfor_forecasts(raw_forecasts)

        # 5. Build Canonical Evaluation Dataset
        canonical_rows, eval_summary = self.build_canonical_evaluation_dataset(
            hourly_actuals,
            clean_forecasts
        )

        # 6. Persist Processed Artifacts Atomically
        proc_dir = self.config.data_dir / "processed"
        csv_file = proc_dir / "canonical_evaluation_dataset.csv"
        json_file = proc_dir / "canonical_evaluation_dataset.json"
        summary_file = proc_dir / "ingestion_summary.json"

        fieldnames = [
            "delivery_time_utc",
            "decision_cutoff_utc",
            "forecast_publish_time_utc",
            "forecast_generation_mw",
            "actual_generation_mw",
            "forecast_age_hours",
            "forecast_available",
            "actual_available",
            "data_quality_flags"
        ]
        write_atomic_csv(csv_file, canonical_rows, fieldnames)
        write_atomic_json(json_file, canonical_rows)

        full_summary = {
            "pipeline_run_timestamp_utc": run_start_time,
            "config": {
                "delivery_start_date": self.config.delivery_start_date,
                "delivery_end_date": self.config.delivery_end_date,
                "decision_cutoff_time": self.config.decision_cutoff_time,
                "decision_timezone": self.config.decision_timezone,
                "base_url": self.config.base_url
            },
            "actuals_ingestion": actuals_telemetry,
            "forecasts_ingestion": forecasts_telemetry,
            "actuals_normalization": {
                "total_expected_hours": actuals_agg_summary["total_expected_hours"],
                "complete_hours": actuals_agg_summary["complete_hours"],
                "incomplete_hours": actuals_agg_summary["incomplete_hours"],
                "missing_hours": actuals_agg_summary["missing_hours"],
                "conflicts_count": actuals_agg_summary["conflicts_count"]
            },
            "forecasts_normalization": {
                "deduplicated_count": forecast_proc_summary["deduplicated_count"],
                "duplicate_count": forecast_proc_summary["duplicate_count"],
                "conflicts_detected": forecast_proc_summary["conflicts_detected"],
                "distinct_publish_times": forecast_proc_summary["distinct_publish_times"],
                "distinct_start_times": forecast_proc_summary["distinct_start_times"]
            },
            "evaluation_dataset": eval_summary,
            "output_files": {
                "canonical_csv": str(csv_file),
                "canonical_json": str(json_file),
                "summary_json": str(summary_file)
            }
        }
        write_atomic_json(summary_file, full_summary)

        return canonical_rows, full_summary
