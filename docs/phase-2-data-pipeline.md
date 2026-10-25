# Phase 2: Historical Data Ingestion & Normalization Pipeline Documentation

This document describes the architecture, implementation, and verified results of the Phase 2 data ingestion and normalization pipeline for the Wind Forecast Intelligence platform.

---

## 1. Pipeline Architecture

The pipeline retrieves, validates, reconciles, and matches UK wind generation actuals and day-ahead forecasts from the official Elexon Insights Solution (BMRS) APIs.

```text
[Elexon BMRS API]
      │
      ├──> GET /datasets/FUELHH/stream (settlementDateFrom/To, fuelType=WIND)
      │         │
      │         ▼
      │    [Raw Actuals Cache: backend/data/raw/actuals/fuelhh_raw_*.json]
      │         │
      │         ▼
      │    [Temporal Normalizer: (H:00 MW + H:30 MW) / 2.0]
      │         │
      │         ▼
      │    [Hourly Actuals Map: 744 intervals]
      │         │
      ├──> GET /datasets/WINDFOR/stream (publishDateTimeFrom/To in 7-day chunks)
      │         │
      │         ▼
      │    [Raw Forecasts Cache: backend/data/raw/forecasts/windfor_raw_*.json]
      │         │
      │         ▼
      │    [Deduplication & Conflict Detection: (publishTime, startTime)]
      │         │
      │         ▼
      │    [Decision Cutoff Selector: publishTime <= decision_cutoff]
      │         │
      └─────────┴───────────────────────┐
                                        ▼
                  [Canonical Evaluation Dataset (744 Hours)]
                      ├── canonical_evaluation_dataset.csv
                      ├── canonical_evaluation_dataset.json
                      └── ingestion_summary.json
```

---

## 2. Data Source Endpoints & Ingestion Parameters

| Dataset | Endpoint | Verified Query Parameters | Ingestion Strategy |
| :--- | :--- | :--- | :--- |
| **FUELHH** (Actuals) | `GET /datasets/FUELHH/stream` | `settlementDateFrom=2026-01-01`<br>`settlementDateTo=2026-01-31`<br>`fuelType=WIND` | Single bounded monthly call (1,488 records). Server-side wind filtering verified. |
| **WINDFOR** (Forecasts) | `GET /datasets/WINDFOR/stream` | `publishDateTimeFrom`<br>`publishDateTimeTo` | Bounded 7-day publication-time chunks starting 2 days prior to start date (`2025-12-30T00:00:00Z` to `2026-01-31T23:59:59Z`). |

---

## 3. Configuration & Date/Timezone Semantics

### 3.1 Scope & Cutoff Defaults
- **Delivery Scope**: `2026-01-01` to `2026-01-31` (744 total hours).
- **Day-Ahead Decision Cutoff Time**: `11:00` (configurable via `--cutoff-time`).
- **Decision Timezone**: `UTC` (configurable via `--timezone`).

### 3.2 Cutoff Calculation Logic
For any hourly delivery interval $T_{\text{delivery}}$ on calendar day $D$ in the decision timezone:
1. $T_{\text{delivery}}$ is converted to the decision timezone.
2. The purchasing decision date is established as the previous calendar day: $D_{\text{decision}} = D - 1\text{ day}$.
3. The cutoff time is applied at the configured clock time on $D_{\text{decision}}$:
   $$\text{Cutoff}_{\text{local}} = \text{combine}(D_{\text{decision}}, \text{cutoff\_time})$$
4. The local cutoff is converted to UTC: $\text{Cutoff}_{\text{UTC}} = \text{to\_utc}(\text{Cutoff}_{\text{local}})$.

*Example*: For delivery on `2026-01-01T04:00:00Z`, the decision cutoff is `2025-12-31T11:00:00Z`.

---

## 4. Half-Hourly to Hourly Actuals Aggregation

In the Elexon `FUELHH` dataset, `startTime` indicates the start of a 30-minute settlement period:
- Period 1 (`:00`): First half-hour.
- Period 2 (`:30`): Second half-hour.

Because generation is reported as **average power in MW** (not energy totals in MWh):
$$\text{hourly\_actual\_MW} = \frac{\text{half\_hour}_{00\text{m}}\text{ (MW)} + \text{half\_hour}_{30\text{m}}\text{ (MW)}}{2.0}$$

### Quality Rules
- Both half-hour intervals (`:00` and `:30`) must be present and valid.
- If either half-hour interval is missing or invalid, `hourly_actual_MW` is set to `None`, `actual_available` is `False`, and quality flags (`MISSING_FIRST_HALF_HOUR`, `MISSING_SECOND_HALF_HOUR`, `INCOMPLETE_ACTUAL_PAIR`) are recorded.
- Power values are never summed.

---

## 5. Forecast Cutoff Selection & Look-Ahead Prevention

To avoid look-ahead bias and simulate real trading conditions:
1. **Target Matching**: Match forecasts targeting delivery interval `startTime == delivery_time_utc`.
2. **Strict Eligibility Filter**:
   $$\text{Eligible Forecasts} = \{ fc \mid fc.\text{publishTime} \le \text{decision\_cutoff\_utc} \}$$
3. **Latest Selection**:
   $$fc_{\text{selected}} = \arg\max_{fc \in \text{Eligible Forecasts}} (fc.\text{publishTime})$$
4. **Strict Look-Ahead Exclusion**: Any forecast published after cutoff ($\text{publishTime} > \text{decision\_cutoff\_utc}$) is disregarded, even if it is newer.
5. **Forecast Age**:
   $$\text{forecast\_age\_hours} = \frac{(\text{decision\_cutoff\_utc} - fc_{\text{selected}}.\text{publishTime}).\text{total\_seconds}()}{3600}$$

---

## 6. Output Artifacts & File Schema

### 6.1 Artifact Locations
- Raw Actuals: [backend/data/raw/actuals/fuelhh_raw_2026-01-01_2026-01-31.json](file:///e:/windX/kjhwr/backend/data/raw/actuals)
- Raw Forecasts: [backend/data/raw/forecasts/windfor_raw_2026-01-01_2026-01-31.json](file:///e:/windX/kjhwr/backend/data/raw/forecasts)
- Canonical Dataset (CSV): [backend/data/processed/canonical_evaluation_dataset.csv](file:///e:/windX/kjhwr/backend/data/processed/canonical_evaluation_dataset.csv)
- Canonical Dataset (JSON): [backend/data/processed/canonical_evaluation_dataset.json](file:///e:/windX/kjhwr/backend/data/processed/canonical_evaluation_dataset.json)
- Ingestion Summary: [backend/data/processed/ingestion_summary.json](file:///e:/windX/kjhwr/backend/data/processed/ingestion_summary.json)

### 6.2 Canonical Dataset Fields
| Field | Type | Description |
| :--- | :--- | :--- |
| `delivery_time_utc` | String (ISO 8601 UTC) | Target hourly delivery interval (e.g., `2026-01-01T00:00:00+00:00`) |
| `decision_cutoff_utc` | String (ISO 8601 UTC) | Day-ahead decision cutoff deadline (e.g., `2025-12-31T11:00:00+00:00`) |
| `forecast_publish_time_utc` | String / None | Publication timestamp of selected forecast vintage |
| `forecast_generation_mw` | Float / None | Forecast wind generation in MW |
| `actual_generation_mw` | Float / None | Two-period average actual wind generation in MW |
| `forecast_age_hours` | Float / None | Time delta between forecast publication and cutoff deadline |
| `forecast_available` | Boolean | True if an eligible forecast existed before cutoff |
| `actual_available` | Boolean | True if both half-hourly actual intervals were valid |
| `data_quality_flags` | String | `"OK"` or pipe-separated flags (e.g., `"DUPLICATE_ACTUAL_H0"`) |

---

## 7. Real January 2026 Retrieval Results

Executed against the live Elexon BMRS API with `--refresh`:

```text
--- INGESTION & NORMALIZATION SUMMARY ---
  Actuals Retrieved (FUELHH):      1,488 records (Source: live_api)
  Forecasts Retrieved (WINDFOR):   19,272 records (Source: live_api)
  Failed API Requests:             0
  Hourly Actuals Produced:         744 complete / 744 expected
  Deduplicated Forecasts:          19,272 (Duplicates removed: 0)
  Forecast Value Conflicts:        0
  Distinct Publication Vintages:   264
  Total Hourly Delivery Intervals: 744
  Complete Matched Pairs (FC+ACT): 744 (100% COMPLETE)
  Intervals Missing Forecast:      0
  Intervals Missing Actual:        0
```

---

## 8. Automated Test Suite Results

Offline test suite executed via `python -m pytest -q` in [backend/](file:///e:/windX/kjhwr/backend):

```text
.......................                                                  [100%]
23 passed, 1 warning in 0.73s
```
- **Total Tests Passed**: **23** (0 failed).
- **Phase 2 Pipeline Tests** ([backend/tests/test_elexon_pipeline.py](file:///e:/windX/kjhwr/backend/tests/test_elexon_pipeline.py)):
  1. `test_half_hourly_actuals_aggregate_to_hourly_average`: PASS
  2. `test_two_100mw_half_hours_yield_100mw_not_200mw`: PASS
  3. `test_missing_one_half_hour_makes_hour_unavailable_with_quality_flag`: PASS
  4. `test_utc_timestamps_normalized_consistently`: PASS
  5. `test_latest_eligible_forecast_selected`: PASS
  6. `test_forecast_published_after_cutoff_excluded`: PASS
  7. `test_forecasts_from_prior_calendar_day_considered_for_early_january`: PASS
  8. `test_missing_forecast_explicitly_recorded`: PASS
  9. `test_duplicate_records_detected`: PASS
  10. `test_conflicting_forecast_values_flagged`: PASS
  11. `test_api_timeouts_and_non_200_handled_with_retry`: PASS
  12. `test_incomplete_coverage_cannot_be_labelled_complete`: PASS
  13. `test_date_range_boundaries_handled_correctly`: PASS

---

## 9. Commands for Execution & Verification

### Run the Pipeline (CLI)
```powershell
cd E:\windX\kjhwr\backend

# Run with local cache reuse:
.\.venv\Scripts\python.exe scripts\build_evaluation_dataset.py

# Or force refresh from live API:
.\.venv\Scripts\python.exe scripts\build_evaluation_dataset.py --refresh
```

### Run Offline Automated Tests
```powershell
cd E:\windX\kjhwr\backend
.\.venv\Scripts\python.exe -m pytest -q
```
