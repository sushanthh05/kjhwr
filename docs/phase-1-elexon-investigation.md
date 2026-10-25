# Phase 1: Elexon BMRS API Investigation & Historical Data Validation Report

This report documents the verified technical and domain findings from investigating official Elexon Insights Solution (BMRS) APIs for UK wind generation forecasts and actuals relevant to January 2026.

---

## 1. Official Documentation & Endpoint Architecture

| Dataset | Purpose | Official Documentation Link | Verified Endpoint |
| :--- | :--- | :--- | :--- |
| **FUELHH** | Half-hourly actual generation outturn by fuel type | [Elexon FUELHH Stream Docs](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream) | `GET /datasets/FUELHH/stream` |
| **WINDFOR** | Wind generation forecasts (ESO national forecast) | [Elexon WINDFOR Stream Docs](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream) | `GET /datasets/WINDFOR/stream` |
| **Swagger/OpenAPI** | Machine-readable API contract specification | [Elexon Swagger v1](https://data.elexon.co.uk/swagger/v1/swagger.json) | `GET /swagger/v1/swagger.json` |

- **Official Base URL**: `https://data.elexon.co.uk/bmrs/api/v1`
- **Authentication**: No API key or HTTP Bearer token is required. Publicly queryable.
- **Payload Format**: The `/stream` endpoints deliver an optimized flat JSON array (`list[dict]`). The non-stream endpoints (`/datasets/{dataset}`) return a wrapper object containing `{"data": [...]}`.

---

## 2. API Contracts & Verified Query Shapes

### 2.1 FUELHH (Actual Generation)
- **Verified URL Format**:
  `GET https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream?settlementDateFrom=2026-01-01&settlementDateTo=2026-01-02&fuelType=WIND`
- **Supported Query Parameters**:
  - `settlementDateFrom` (format: `yyyy-MM-dd`, e.g., `2026-01-01`)
  - `settlementDateTo` (format: `yyyy-MM-dd`, e.g., `2026-01-02`)
  - `settlementPeriod` (integer list, e.g., `[1, 2]`)
  - `fuelType` (string list, e.g., `WIND` or `['WIND', 'NUCLEAR']`)
  - `publishDateTimeFrom` / `publishDateTimeTo` (ISO 8601 date-time)
  > [!NOTE]
  > According to the official OpenAPI contract, settlement date parameters (`settlementDateFrom/To`) and publish date parameters (`publishDateTimeFrom/To`) are mutually exclusive.
- **Server-Side Fuel Filtering**: Verified. Supplying `fuelType=WIND` successfully restricts the payload to wind generation only, avoiding wasteful transfer of other fuel types.
- **Observed Fields**:
  - `dataset` (`string`, `"FUELHH"`)
  - `startTime` (`string`, ISO 8601 UTC timestamp, e.g., `"2026-01-01T00:00:00Z"`)
  - `publishTime` (`string`, ISO 8601 UTC timestamp)
  - `settlementDate` (`string`, `yyyy-MM-dd`)
  - `settlementPeriod` (`int`, `1` to `48`)
  - `fuelType` (`string`, `"WIND"`)
  - `generation` (`number`, average MW over the 30-minute period)

### 2.2 WINDFOR (Wind Forecast)
- **Verified URL Format**:
  `GET https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream?publishDateTimeFrom=2026-01-01T00:00:00Z&publishDateTimeTo=2026-01-01T12:00:00Z`
- **Supported Query Parameters**:
  - `publishDateTimeFrom` (ISO 8601 date-time, e.g., `"2026-01-01T00:00:00Z"`)
  - `publishDateTimeTo` (ISO 8601 date-time, e.g., `"2026-01-01T12:00:00Z"`)
- **Behavior Without Parameters**: Returns only the single latest published forecast curve (74 points).
- **Behavior With Date Range**: Returns all forecast vintages published within that publication window.
- **Observed Fields**:
  - `dataset` (`string`, `"WINDFOR"`)
  - `publishTime` (`string`, ISO 8601 UTC timestamp when the forecast was issued)
  - `startTime` (`string`, ISO 8601 UTC timestamp for target delivery interval)
  - `generation` (`number`, forecast wind generation in MW)

---

## 3. Verified Telemetry and Sample Observations

Telemetry recorded using [backend/scripts/inspect_elexon.py](file:///e:/windX/kjhwr/backend/scripts/inspect_elexon.py):

| Metric | FUELHH Sample (`2026-01-01` to `2026-01-02`) | WINDFOR Sample (`2026-01-01 00:00` to `12:00`) |
| :--- | :--- | :--- |
| **HTTP Status** | `200 OK` | `200 OK` |
| **Response Time** | 0.653 seconds | 0.165 seconds |
| **Payload Content-Type** | `application/json; charset=utf-8` | `application/json; charset=utf-8` |
| **Total Records** | 96 | 365 |
| **Valid Records** | 96 (100%) | 365 (100%) |
| **Invalid / Missing Fields** | 0 | 0 |
| **Duplicates / Conflicts** | 0 duplicates, 0 conflicts | 0 duplicates, 0 conflicts |
| **Distinct Delivery Intervals (`startTime`)** | 96 half-hourly intervals | 73 hourly intervals |
| **Distinct Publications (`publishTime`)** | N/A (Actuals) | 5 publication runs |
| **Observed Timestamp Range** | `2026-01-01T00:00:00Z` – `2026-01-02T23:30:00Z` | `2025-12-31T21:00:00Z` – `2026-01-03T21:00:00Z` |
| **Confirmed Units** | Megawatts (MW), 30-min average | Megawatts (MW), 60-min forecast |

### Genuine Sample Records (Live API Outturn)

**FUELHH Record:**
```json
{
  "dataset": "FUELHH",
  "publishTime": "2026-01-03T00:00:00Z",
  "startTime": "2026-01-02T23:30:00Z",
  "settlementDate": "2026-01-02",
  "settlementPeriod": 48,
  "fuelType": "WIND",
  "generation": 14202.0
}
```

**WINDFOR Record:**
```json
{
  "dataset": "WINDFOR",
  "publishTime": "2026-01-01T11:30:00Z",
  "startTime": "2026-01-02T12:00:00Z",
  "generation": 17739.0
}
```

---

## 4. January 2026 Historical Data Availability Findings

1. **Actual Generation (FUELHH)**:
   - Full January 2026 actual generation is **fully available** in the Elexon API.
   - Half-hourly resolution, 48 settlement periods per day, cleanly categorized under `fuelType: "WIND"`.

2. **Forecast Vintages (WINDFOR Stream)**:
   - Historical forecast vintages published in January 2026 **are retrievable** using `publishDateTimeFrom` and `publishDateTimeTo`.
   - In the inspected 12-hour window on `2026-01-01`, 5 distinct publication runs were returned (`02:30`, `04:30`, `07:30`, `09:30`, `11:30`).
   - Each publication run projects an hourly generation curve spanning a 72-hour horizon (~3 days ahead).

3. **Alternative Historical Endpoint Finding**:
   - The OpenAPI spec defines `/forecast/generation/wind/history`, which accepts a required parameter `publishTime` (single point in time) and returns 73 points for that single run.
   - For batch backtesting, the prescribed `/datasets/WINDFOR/stream` endpoint is significantly more suitable because it accepts a date range (`publishDateTimeFrom/To`) and returns multiple vintages in a single request.

---

## 5. Critical Domain Insights & Backtest Implications

### 5.1 Temporal Resolution Mismatch (30-Minute vs 60-Minute)
- **FUELHH Actuals**: Reported in **30-minute settlement periods** (48 periods per calendar day).
- **WINDFOR Forecasts**: Reported in **60-minute delivery intervals** (hourly time steps, 24 periods per calendar day).
- **Implication**: Forecast and actual timestamps cannot be directly joined 1-to-1 on `startTime` without a reconciliation strategy. In Phase 2, the pipeline must either:
  1. Average consecutive 30-minute actuals to hourly intervals: $\text{Actual}_{\text{hour}} = \frac{\text{Period}_{2k-1} + \text{Period}_{2k}}{2}$.
  2. Map hourly forecasts to both constituent 30-minute settlement periods.

### 5.2 Querying by Publish Time vs Delivery Time
- `WINDFOR/stream` queries by **forecast publication time** (`publishDateTimeFrom/To`), NOT target delivery time (`startTime`).
- **Implication**: To obtain the day-ahead forecast for a delivery interval in early January (e.g., `2026-01-01`), the ingestion pipeline must query publications starting in late December 2025 (e.g., `2025-12-31`).

### 5.3 Forecast Horizon & Intraday Revisions
- NGESO publishes up to 8 forecast updates per day (e.g., `03:30`, `05:30`, `08:30`, `10:30`, `12:30`, `16:30`, `19:30`, `23:30`).
- Because multiple vintages exist for every delivery interval, a strict decision cutoff must be enforced to avoid look-ahead bias:
  $$\text{Selected Forecast} = \arg\max_{rec} \{ rec.\text{publishTime} \mid rec.\text{publishTime} \le \text{decision\_cutoff} \land rec.\text{startTime} = \text{delivery\_interval} \}$$

---

## 6. Unresolved Business Assumptions

### 6.1 Unspecified Day-Ahead Decision Cutoff Clock Time
- The brief does not prescribe an exact clock time for the day-ahead purchasing decision.
- In UK / European electricity trading:
  - **EPEX SPOT / Nord Pool Day-Ahead Auction**: Gate closure is **11:00 UTC** (or 12:00 CET).
  - **Physical Balancing Mechanism Gate Closure**: 1 hour before the start of each half-hour settlement period.
- **Recommendation**: Document this as an open assumption and make the cutoff time an explicit configurable parameter in Phase 2 (defaulting to `11:00 UTC day-ahead`).

### 6.2 January 2026 Scope Ambiguity
- The prompt specifies "decisions to be made in January 2026":
  - **Interpretation A (Decision-Date Scope)**: Decisions made from `2026-01-01` to `2026-01-31` (which govern delivery intervals from `2026-01-02` through `2026-02-01`).
  - **Interpretation B (Delivery-Date Scope)**: Delivery intervals occurring from `2026-01-01` to `2026-01-31` (which require decisions made between `2025-12-31` and `2026-01-30`).
- **Recommendation**: Support both interpretations by allowing configurable evaluation windows in the ingestion engine.

---

## 7. Automated Test Suite Verification

The parsing, schema validation, and cutoff selection logic are tested offline in [backend/tests/test_elexon_validation.py](file:///e:/windX/kjhwr/backend/tests/test_elexon_validation.py):

| Test Case | Description | Result |
| :--- | :--- | :--- |
| `test_valid_actual_records` | Verifies clean FUELHH records, settlement periods, and MW parsing | **PASS** |
| `test_valid_forecast_records` | Verifies WINDFOR records with multiple vintages and delivery points | **PASS** |
| `test_missing_required_fields` | Verifies rejection of records missing `startTime`, `generation`, or `fuelType` | **PASS** |
| `test_invalid_timestamps` | Verifies rejection of non-ISO or malformed datetime strings | **PASS** |
| `test_duplicate_delivery_timestamps` | Verifies detection of duplicate keys and value conflicts | **PASS** |
| `test_multiple_forecast_publications...` | Verifies grouping of multiple publication vintages for the same delivery interval | **PASS** |
| `test_selection_of_latest_forecast...` | Verifies selection of latest forecast published prior to cutoff | **PASS** |
| `test_exclusion_of_forecasts...` | **Strict no-leakage check**: Confirms forecasts published after cutoff are never selected, even if newest | **PASS** |

**Pytest Execution Command**: `python -m pytest -q`
**Result**: `10 passed, 1 warning in 0.57s` (including 2 baseline tests in [test_app.py](file:///e:/windX/kjhwr/backend/tests/test_app.py)).

---

## 8. Next Recommended Engineering Step (Phase 2 Preview)

Design and implement a structured historical data ingestion module:
1. **Windowed Extractor**: Chunked query routine for `WINDFOR/stream` and `FUELHH/stream` across January 2026 with rate-limiting safety buffers.
2. **Temporal Reconciler**: Normalizer aligning 30-minute actuals with 60-minute forecast intervals.
3. **Cutoff Selector**: Deterministic filter selecting the latest pre-cutoff forecast vintage for each target settlement interval.
