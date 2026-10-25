# Phase 4 — Wind Forecast Intelligence Dashboard

## 1. Executive Summary

Phase 4 delivers the complete, production-grade React analytics dashboard for **Wind Forecast Intelligence**, an energy-market portal built for a UK utility day-ahead electricity trading and procurement desk.

The application connects directly to the FastAPI backend API service (`http://127.0.0.1:8000`), consuming the canonical January 2026 dataset (744 matched hourly delivery intervals derived from Elexon BMRS `FUELHH` wind generation actuals and `WINDFOR` day-ahead forecasts).

All calculations are executed server-side via the Phase 3 analytics engine. The frontend serves as a high-fidelity visual and analytical exploration interface adhering to modern trading terminal standards, accessibility guidelines, and robust fault-isolation principles.

---

## 2. Dashboard Architecture & Component Hierarchy

The dashboard is structured into modular presentation and container components under `frontend/src/`:

```
frontend/src/
├── services/
│   └── api.js                     # Unified API service layer with AbortSignal & error parsing
├── utils/
│   └── formatters.js              # Formatting helpers for MW, signed errors, %, and UTC timestamps
├── components/
│   ├── Header.jsx                 # Brand identity, period pill, and live backend connection badge
│   ├── DecisionContext.jsx        # Day-ahead decision cutoff (11:00 UTC D-1), resolution, and market scope
│   ├── KpiCard.jsx                # Metric card with loading skeletons, unavailable states & bias styles
│   ├── SectionCard.jsx            # Reusable card container with headers, icons, and action slots
│   ├── ForecastActualChart.jsx    # Large Recharts time-series with date range filter & presets
│   ├── ErrorAnalysis.jsx          # Signed convention banner, 10-bin histogram & over/under breakdown
│   ├── DailyAccuracyChart.jsx     # Daily MAE bar chart highlighting best/worst performance days
│   ├── WorstMissesTable.jsx       # Ranked top 10 forecast deviations with operational trading context
│   ├── HourOfDayChart.jsx         # Diurnal accuracy profile grouped by UK local hour (Europe/London)
│   ├── MethodologyPanel.jsx       # Expandable data lineage, quality audit, and mathematical formulations
│   ├── LoadingState.jsx           # Unified loading spinner and status feedback
│   └── ErrorState.jsx             # Error boundary feedback with retry actions
├── App.jsx                        # Orchestrator managing data fetch, date filtering, and state resilience
├── index.css                      # Utility-grade energy terminal design system (Vanilla CSS)
└── main.jsx                       # Application mount entrypoint
```

---

## 3. Dashboard Sections & Domain Capabilities

### A. Portal Header & Live Status
- **Product Identity**: `Wind Forecast Intelligence` (UK Market Portal).
- **Reporting Period**: January 2026 (`2026-01-01` to `2026-01-31`).
- **Data Source**: Elexon BMRS (`FUELHH` actuals & `WINDFOR` forecasts).
- **Verified Connectivity Indicator**: Does not assume "live" on render; performs an active `GET /health` ping. Renders `Backend Connected` (green glow), `Verifying API...` (blue spinner), or `API Offline` (rose badge).

### B. Decision Context Strip
- **Assumed Decision Policy**: Day-ahead cutoff at **11:00 UTC on the day before delivery ($D-1$)**. Forecasts published after cutoff are strictly excluded to eliminate look-ahead bias.
- **Temporal Resolution**: Hourly averages. Actual generation normalized from two half-hourly settlement periods (`(:00 + :30) / 2`).
- **Dataset Coverage**: Displays `744 / 744 hrs` (`100% complete`, 0 excluded records).
- **Market Scope Boundary**: Clearly states that the application measures GB national wind generation forecast discrepancy and does not calculate specific utility procurement obligations or imbalance penalty settlement.

### C. Core KPI Cards
Driven by `GET /api/analytics/overview`:
1. **Mean Absolute Error (MAE)**: `2,122.8 MW` (1 decimal precision).
2. **Root Mean Squared Error (RMSE)**: `2,616.7 MW` (Volatility penalty).
3. **Mean Bias Error (MBE)**: `+1,840.3 MW` with prominent **Overforecast Bias** badge (positive bias indicates forecasts systematically exceeded actual generation).
4. **Mean Absolute Percentage Error (MAPE)**: `22.06%` across non-zero generation hours (744 / 744 hrs).
5. **Mean Actual Generation (Outturn)**: `11,580.7 MW`.
6. **Mean Day-Ahead Forecast**: `13,421.0 MW`.

### D. Main Forecast-versus-Actual Time Series Chart
- Large Recharts line chart plotting Actual Generation (`#10b981` emerald) and Forecast Generation (`#3b82f6` blue).
- **Custom Tooltip**: Displays UTC delivery interval, actual MW, forecast MW, signed error (`error_mw`), forecast publication time, decision cutoff, and forecast lead time.
- **Tick Optimization**: Downsamples timestamps so axis labels never collide (e.g. 3-day intervals at 00:00 UTC for full-month view; 6-hour intervals for short ranges).
- **Interactive Date Filters**:
  - Direct date pickers (`start-date-input`, `end-date-input`) bounded to January 2026.
  - Quick-select chip buttons: `Full Month`, `Wk 1 (1–7)`, `Wk 2 (8–14)`, `Wk 3 (15–21)`, `Wk 4 (22–28)`, `29–31 Jan`.
  - Dynamic KPI synchronization: overview metrics dynamically update when the date filter changes.
  - Reset button to restore full-month view.

### E. Error Distribution & Bias Analysis
- **Signed Error Convention**:
  $$\text{error\_mw} = \text{forecast\_generation\_mw} - \text{actual\_generation\_mw}$$
  - $\text{error\_mw} > 0$: **Overforecast** (forecast exceeded actuals).
  - $\text{error\_mw} < 0$: **Underforecast** (actuals exceeded forecast).
- **Counter Cards**:
  - Overforecast: **628 hours (84.4%)**.
  - Underforecast: **116 hours (15.6%)**.
- **Histogram**: Exact 10-partition binning rendered directly from `GET /api/analytics/errors`, color-coded by error direction (amber for overforecast, blue for underforecast).
- **Quantile Summary**: Min (`-4,568 MW`), p10 (`-368 MW`), Median (`+1,821 MW`), p90 (`+4,210 MW`), Max (`+6,833 MW`).

### F. Daily Forecast Accuracy
- Grouped daily MAE bar chart across all 31 days in January 2026 (`GET /api/analytics/daily`).
- **Best Day Badge**: Identifies **9 Jan 2026** (MAE `797.1 MW`).
- **Highest Error Day Badge**: Identifies **28 Jan 2026** (MAE `5,374.8 MW`).
- Detailed tooltips with daily MAE, RMSE, MBE, MAPE, mean power, and interval completeness.

### G. Top 10 Worst Forecast Misses Table
- Consumes `GET /api/analytics/worst-misses?limit=10`.
- Ranks intervals by absolute error descending with deterministic tie-breaking.
- **Peak Outliers**: Validated that rank #1 to #5 are early-morning hours of **12 January 2026** (Rank #1 at `2026-01-12 01:00 UTC` with `+6,833.0 MW` overforecast).
- **Operational Trading Statement**: Explains why forecast errors require traders to rebalance positions in intraday power markets or face balancing mechanism cashout charges, without claiming forecast error equals direct financial loss.

### H. Diurnal Accuracy Profile (Hour of Day)
- Groups MAE by UK local delivery hour (0–23 in `Europe/London`) via `GET /api/analytics/hour-of-day`.
- Tooltip displays local hour range (`HH:00 - HH:59`), MAE, RMSE, MBE, mean outturn, and sample size.
- **Section-Level Resilience**: If this endpoint fails, a section-specific error box with retry appears without affecting the rest of the dashboard.

### I. Methodology, Lineage & Assumptions Panel
- Expandable accordion detailing:
  - Canonical dataset completeness (744 expected / 744 matched, 100% coverage, 0 excluded records).
  - Elexon BMRS streams (`FUELHH` and `WINDFOR`).
  - Strict pre-cutoff selection rule (11:00 UTC D-1).
  - Signed error formulation and non-zero MAPE calculation rule.
  - Pipeline lineage timestamp (`2026-10-25 05:51:30 UTC`).

---

## 4. API Service Layer Design (`frontend/src/services/api.js`)

- **Environment Configuration**: Configured with `VITE_API_BASE_URL` (falling back to `VITE_BACKEND_URL` and `http://127.0.0.1:8000`).
- **Error Handling**: Custom `ApiError` class encapsulating HTTP status codes, server error messages, and network failure diagnostics.
- **Cancellation & Stale Request Protection**: All request functions accept an optional `signal` (`AbortSignal`) or request token.
- **Safe Parameter Serialization**: Query parameters (`start_date`, `end_date`, `limit`) are encoded using `URLSearchParams`.
- **Zero Fallback Distortion**: Real errors reject promises; the frontend never manufactures hardcoded January metrics on network failure.

---

## 5. Design System & Aesthetics (`frontend/src/index.css`)

- **Aesthetic**: Deep charcoal/navy background (`#080C14`, `#0D131F`, `#0F1726`) tailored for utility control rooms.
- **Palette**:
  - Green accent (`#10B981`): Wind generation outturn and high accuracy.
  - Blue accent (`#3B82F6`): Day-ahead forecast projections.
  - Amber accent (`#F59E0B`): Overforecast bias and operational warnings.
  - Rose accent (`#F43F5E`): Extreme forecast misses and connection errors.
- **Typography**: Inter for UI chrome, monospace font stack (`ui-monospace, Consolas`) for telemetry values.
- **Accessibility**: Visible high-contrast focus rings (`:focus-visible` with `#06B6D4` outline) on all interactive controls.
- **Responsive Layout**: Fluid CSS Grid and Flexbox adapting smoothly across desktop, tablet, and mobile viewports.

---

## 6. Verification & Test Results

### A. Frontend Unit Tests (Vitest)
Installed Vitest, JSDOM, and Testing Library (`npm test`):
- **3 test suites, 35 unit tests passed (100% passing)**:
  - `src/__tests__/formatters.test.js`: 15 passed (MW, signed formatting, null handling, UTC timestamps).
  - `src/__tests__/api.test.js`: 10 passed (HTTP error handling, parameter encoding, abort signals, zero fallback metrics).
  - `src/__tests__/components.test.jsx`: 10 passed (KpiCard skeletons, DecisionContext visible cutoff, WorstMissesTable over/under badges, Header status).

### B. Frontend Production Build
`npm run build`:
```
vite v8.3.5 building client environment for production...
✓ 2522 modules transformed.
dist/index.html                   1.08 kB │ gzip:   0.55 kB
dist/assets/index-DHL1xkZ7.css   23.57 kB │ gzip:   4.76 kB
dist/assets/index-DMYcPSWv.js   666.85 kB │ gzip: 193.80 kB
✓ built in 626ms (Exit code 0)
```

### C. Backend Test Suite (Pytest)
`.\.venv\Scripts\python.exe -m pytest -q` in `backend/`:
```
...........................................                              [100%]
43 passed, 1 warning in 0.90s (Exit code 0)
```

### D. Live Browser Integration Verification
Performed via automated browser subagent on `http://localhost:5173`:
- Verified backend connectivity indicator transitions to **Backend Connected**.
- Verified all 6 KPI card figures match real backend API values.
- Verified interactive date filter presets (`Wk 1 (1–7)` filtered to 168 hours; `Full Month` restored to 744 hours).
- Verified signed error distribution (628 overforecast vs 116 underforecast).
- Verified top 10 worst misses table displays 12 Jan early morning errors (Rank #1 at `2026-01-12 01:00 UTC` with `6,833.0 MW` deviation).
- Verified expandable methodology drawer.
- Verified zero console errors.

---

## 7. Operational Guidelines & Remaining Considerations

1. **Development Server Execution**:
   - Backend: `uvicorn app:app --host 127.0.0.1 --port 8000` from `backend/`.
   - Frontend: `npm run dev` from `frontend/` (accessible at `http://localhost:5173`).
2. **Operational Scope Limitation**:
   - The dataset evaluates national GB wind forecast accuracy for January 2026. Commercial balancing cashout calculations or portfolio-specific imbalance settlement require utility-specific contracted position data.
