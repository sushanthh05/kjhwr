# Phase 3: Forecast Accuracy Analytics Engine Documentation

This report presents the mathematical formulations, empirical results, daily and hourly patterns, and API specifications for the Phase 3 Wind Forecast Intelligence analytics engine. All metrics are calculated directly from the verified Phase 2 canonical dataset covering January 2026.

---

## 1. Metric Formulations & Mathematical Definitions

All power generation and error values are measured in **Megawatts (MW)**.

### Error Sign Convention
$$\text{error\_mw}_i = \text{forecast\_generation\_mw}_i - \text{actual\_generation\_mw}_i$$
- **Positive Error ($> 0$)**: **Overforecast** (forecast exceeded actual outturn; long position).
- **Negative Error ($< 0$)**: **Underforecast** (forecast fell short of actual outturn; short position).

### A. Mean Absolute Error (MAE)
$$\text{MAE} = \frac{1}{n} \sum_{i=1}^{n} |\text{forecast}_i - \text{actual}_i|$$
Measures overall magnitude of error without regard to direction.

### B. Root Mean Squared Error (RMSE)
$$\text{RMSE} = \sqrt{\frac{1}{n} \sum_{i=1}^{n} (\text{forecast}_i - \text{actual}_i)^2}$$
Penalizes large forecast misses more severely than small deviations.

### C. Mean Bias Error (MBE)
$$\text{MBE} = \frac{1}{n} \sum_{i=1}^{n} (\text{forecast}_i - \text{actual}_i)$$
Measures systematic directional bias. A positive MBE indicates systematic overforecasting; negative MBE indicates systematic underforecasting.

### D. Mean Absolute Percentage Error (MAPE)
$$\text{MAPE} = \frac{1}{n_{\text{nonzero}}} \sum_{i \in \{j \mid \text{actual}_j > 0\}} \frac{|\text{forecast}_i - \text{actual}_i|}{\text{actual}_i} \times 100\%$$
- Observations where $\text{actual} = 0$ are explicitly excluded to prevent division by zero.
- The number of included and excluded observations is explicitly tracked and reported.

---

## 2. Empirical Results on the Real January 2026 Dataset

The metrics were computed across all **744 hourly delivery intervals** of January 2026 (100% complete coverage):

| Metric | Empirical Value | Units | Interpretation |
| :--- | :--- | :--- | :--- |
| **Total Intervals Expected** | 744 | Hours | 31 calendar days $\times$ 24 hours |
| **Matched Pairs Evaluated** | 744 | Hours | 100% matched coverage ($n = 744$) |
| **Mean Actual Generation** | **11,580.74** | MW | Average actual wind generation across GB |
| **Mean Forecast Generation** | **13,421.03** | MW | Average day-ahead forecast generation |
| **Mean Absolute Error (MAE)** | **2,122.81** | MW | Average magnitude of forecast miss |
| **Root Mean Squared Error (RMSE)** | **2,616.69** | MW | Volatility-weighted miss metric |
| **Mean Bias Error (MBE)** | **+1,840.30** | MW | **Severe systematic overforecasting bias** |
| **Mean Absolute Percentage Error (MAPE)** | **22.06%** | % | 744 observations included (0 zero-actual exclusions) |
| **Median Absolute Error** | **1,714.00** | MW | 50% of intervals had error $\le 1,714$ MW |
| **Maximum Absolute Error** | **6,833.00** | MW | Largest single-hour miss (Jan 12, 01:00 UTC) |
| **Overforecast Count ($> 0$)** | **628** | Hours | **84.41%** of all January intervals |
| **Underforecast Count ($< 0$)** | **116** | Hours | **15.59%** of all January intervals |
| **Exact Zero Errors ($= 0$)** | **0** | Hours | 0.00% |

---

## 3. Systematic Overforecast Bias Analysis

The empirical analysis reveals a **pronounced systematic overforecasting bias** in NGESO's day-ahead wind forecasts for January 2026:
- **84.4% of all hours (628 out of 744)** had forecasts higher than actuals.
- The mean bias error (+1,840.30 MW) constitutes **86.7% of the total MAE** (2,122.81 MW).
- **Physical/Market Context**: Day-ahead wind generation forecasts are unconstrained by transmission boundaries. If actual outturn is lower due to network congestion (transmission constraint curtailment in Scotland/North of England), metered generation outturn will fall short of the unconstrained day-ahead meteorological forecast.

---

## 4. Error Distribution & Quantiles

### Quantile Summary
| Quantile | Signed Error (MW) | Absolute Error (MW) |
| :--- | :--- | :--- |
| **Min** | -4,128.00 | 5.00 |
| **10th Percentile (p10)** | -488.85 | 488.85 |
| **25th Percentile (p25)** | +714.38 | 1,006.38 |
| **Median (p50)** | **+1,640.50** | **1,714.00** |
| **75th Percentile (p75)** | +2,990.88 | 3,018.00 |
| **90th Percentile (p90)** | +4,312.40 | 4,312.40 |
| **95th Percentile (p95)** | +5,418.53 | 5,418.53 |
| **Max** | +6,833.00 | 6,833.00 |

### 10-Bin Exact-Sum Histogram
Total observations accounted for: $\sum \text{count} = 744$ (100.0%).

| Bin | Range (MW) | Count | Percentage | Cumulative % |
| :---: | :---: | :---: | :---: | :---: |
| 0 | -4,128.00 to -3,031.90 | 3 | 0.40% | 0.40% |
| 1 | -3,031.90 to -1,935.80 | 6 | 0.81% | 1.21% |
| 2 | -1,935.80 to -839.70 | 47 | 6.32% | 7.53% |
| 3 | -839.70 to +256.40 | 80 | 10.75% | 18.28% |
| 4 | +256.40 to +1,352.50 | 179 | 24.06% | 42.34% |
| 5 | +1,352.50 to +2,448.60 | 184 | 24.73% | 67.07% |
| 6 | +2,448.60 to +3,544.70 | 104 | 13.98% | 81.05% |
| 7 | +3,544.70 to +4,640.80 | 79 | 10.62% | 91.67% |
| 8 | +4,640.80 to +5,736.90 | 45 | 6.05% | 97.72% |
| 9 | +5,736.90 to +6,833.00 | 17 | 2.28% | 100.00% |

---

## 5. Worst Forecast Misses (Top 5 Incidents)

Sorted deterministically by `absolute_error_mw` descending, with `delivery_time_utc` ascending as tie-breaker:

| Rank | Delivery Time (UTC) | Forecast (MW) | Actual (MW) | Error (MW) | Abs Miss (MW) | Miss % |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | `2026-01-12T01:00:00+00:00` | 20,905.0 | 14,072.0 | **+6,833.0** | 6,833.0 | 48.56% |
| **2** | `2026-01-12T02:00:00+00:00` | 20,886.0 | 14,120.5 | **+6,765.5** | 6,765.5 | 47.91% |
| **3** | `2026-01-12T00:00:00+00:00` | 20,707.0 | 14,032.0 | **+6,675.0** | 6,675.0 | 47.57% |
| **4** | `2026-01-12T05:00:00+00:00` | 20,679.0 | 14,022.0 | **+6,657.0** | 6,657.0 | 47.48% |
| **5** | `2026-01-12T03:00:00+00:00` | 20,808.0 | 14,163.0 | **+6,645.0** | 6,645.0 | 46.92% |

*Incident Note*: The entire early-morning block of January 12th experienced massive overforecasting (>6.6 GW overforecast), where NGESO anticipated near-record generation of ~20.9 GW, but actual generation capped at ~14.1 GW.

---

## 6. Daily and Diurnal (Hour of Day) Patterns

### 6.1 Daily Accuracy Extremes
- **Worst Accuracy Day**: **2026-01-28** (MAE: **5,374.79 MW**, MBE: **+5,374.79 MW**). Forecast persistently overpredicted generation by more than 5.3 GW throughout the day.
- **Best Accuracy Day**: **2026-01-09** (MAE: **797.06 MW**, MBE: **+221.73 MW**). Highly accurate forecasting with balanced errors.

### 6.2 Diurnal Patterns (Europe/London Local Hour)
- **Peak Error Period**: Overnight hours (01:00 to 04:00 GMT), peaking at **03:00 GMT** with MAE of **2,486.16 MW** and MBE of **+2,467.58 MW**.
- **Minimum Error Period**: Afternoon peak hours (14:00 to 17:00 GMT), reaching lowest MAE at **15:00 GMT** with MAE of **1,926.69 MW** and MBE of **+1,659.87 MW**.

---

## 7. Verification of Forecast Age and Publication Schedule

In Phase 2, every selected forecast vintage was reported with `publishTime` at 09:30 UTC and `forecast_age_hours` of 1.5 hours relative to an 11:00 UTC cutoff.
- **Verification Result**: Verified as **empirically correct**.
- **Explanation**: In the Elexon `WINDFOR` system, NGESO publishes forecast runs on a schedule (e.g. 02:30, 04:30, 07:30, 09:30, 11:30, 16:30, etc.).
- With an 11:00 UTC day-ahead cutoff on day $D - 1$, the 09:30 UTC vintage is consistently the latest published run before 11:00 UTC. The next run (11:30 UTC) is after gate closure and was strictly excluded.
- Across all 31 days in January 2026, 31 distinct 09:30 UTC runs were selected, each covering the 24 delivery hours of the following calendar day, with an age of $11:00 - 09:30 = 1.5\text{ hours}$.

---

## 8. API Specification & Route Reference

Base URL: `http://127.0.0.1:8000`

| Route | Method | Query Parameters | Description |
| :--- | :---: | :--- | :--- |
| `/api/analytics/overview` | `GET` | None | Overall metrics, error bias counts, coverage summary, and quality warnings |
| `/api/analytics/timeseries` | `GET` | `start_date`, `end_date` | Hourly forecasts vs actuals, signed error, and percentage error |
| `/api/analytics/daily` | `GET` | `start_date`, `end_date` | Daily aggregated MAE, RMSE, MBE, MAPE, and completeness status |
| `/api/analytics/errors` | `GET` | None | Signed/absolute quantiles, sign counts, and 10-bin exact-sum histogram |
| `/api/analytics/worst-misses` | `GET` | `limit` (default: 10, range: 1–100) | Largest absolute forecast misses sorted descending |
| `/api/analytics/hour-of-day` | `GET` | None | Diurnal profile (0–23) in `Europe/London` timezone |
| `/api/analytics/metadata` | `GET` | None | Service information, units, resolutions, assumptions, and limitations |

### Sample Response (`GET /api/analytics/overview`)
```json
{
  "delivery_scope": {
    "start_date": "2026-01-01",
    "end_date": "2026-01-31",
    "decision_cutoff": "11:00 UTC (Day-Ahead)"
  },
  "error_definition": "error_mw = forecast_generation_mw - actual_generation_mw (positive = overforecast, negative = underforecast)",
  "metrics": {
    "mae_mw": 2122.81,
    "rmse_mw": 2616.69,
    "mbe_mw": 1840.3,
    "mape_pct": 22.06,
    "max_absolute_error_mw": 6833.0,
    "median_absolute_error_mw": 1714.0,
    "mean_actual_mw": 11580.74,
    "mean_forecast_mw": 13421.03
  },
  "coverage": {
    "expected_intervals_count": 744,
    "matched_pairs_count": 744,
    "matched_coverage_pct": 100.0,
    "excluded_records_count": 0,
    "mape_included_count": 744,
    "mape_excluded_zero_actual_count": 0
  },
  "error_sign_counts": {
    "positive_overforecast_count": 628,
    "negative_underforecast_count": 116,
    "zero_error_count": 0
  },
  "data_quality_warnings": []
}
```

---

## 9. Automated Test Suite Results

Offline test suite executed via `.\.venv\Scripts\python.exe -m pytest -q` in [backend/](file:///e:/windX/kjhwr/backend):

```text
...........................................                              [100%]
43 passed, 1 warning in 0.88s
```
- **Total Tests**: **43 passed, 0 failed**.
  - Phase 0 (FastAPI Core): 2 passed.
  - Phase 1 (Schema & Cutoff Validation): 8 passed.
  - Phase 2 (Ingestion & Aggregation Pipeline): 13 passed.
  - Phase 3 (Analytics Engine & Endpoints): 20 passed.
- **Offline Guarantee**: All 43 tests execute in under 1 second without external network dependencies.
