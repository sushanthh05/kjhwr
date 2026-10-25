# Wind Forecast Intelligence

An energy-market intelligence portal that evaluates Great Britain's national wind generation forecasts against actual metered outturn to support day-ahead trading and purchasing decisions.

The application ingests transmission-level data from the Elexon BMRS market system, normalizes differing temporal resolutions, and calculates key forecast accuracy, systematic bias, and volumetric miss metrics.

- **Live Application**: [https://wind-forecast-frontend.onrender.com/](https://wind-forecast-frontend.onrender.com/)
- **GitHub Repository**: [https://github.com/sushanthh05/kjhwr](https://github.com/sushanthh05/kjhwr)

---

## Key Capabilities

- **Forecast vs. Actual Time Series**: Interactive delivery-hour charts comparing day-ahead forecasts against metered outturn, with date range filters and preset windows.
- **Accuracy & Bias Metrics**: Executive KPIs including Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), Mean Bias Error (MBE), and Mean Absolute Percentage Error (MAPE).
- **Error Distribution & Quantiles**: 10-bin exact-sum error distribution histogram alongside P10, P25, Median, P75, and P90 error quantiles.
- **Daily Accuracy Breakdown**: Day-by-day MAE comparisons with automated best and worst forecast day identification.
- **Worst Forecast Misses**: Ranked table of the largest absolute volumetric deviations with operational trading context.
- **Diurnal (24-Hour) Profile**: Hourly accuracy breakdown in UK local time (`Europe/London`) to identify recurring intraday pattern errors.
- **Methodology & Data Lineage**: Collapsible audit panel disclosing data sources, aggregation formulas, and decision cutoff rules.

---

## Example Findings (January 2026)

Evaluating Great Britain's national wind generation for all 744 hourly delivery intervals of January 2026 yields the following reference metrics:

| Metric | Value | Units | Note |
| :--- | :---: | :---: | :--- |
| **Evaluated Intervals** | 744 | Hours | 100% matched hourly delivery coverage (31 days × 24 hours) |
| **Mean Actual Generation** | 11,580.74 | MW | Average transmission-metered outturn |
| **Mean Forecast Generation** | 13,421.03 | MW | Average day-ahead forecast generation |
| **Mean Absolute Error (MAE)** | 2,122.81 | MW | Average magnitude of forecast deviation |
| **Root Mean Squared Error (RMSE)** | 2,616.69 | MW | Volatility-penalized deviation metric |
| **Mean Bias Error (MBE)** | +1,840.30 | MW | Systematic overforecasting bias (84.4% of hours overforecast) |
| **Mean Absolute Percentage Error (MAPE)** | 22.06% | % | Evaluated across non-zero generation hours |

*Under the project's forecast-minus-actual sign convention, a positive MBE indicates systematic overforecasting. These figures describe evaluated national GB wind outturn and do not represent customer-specific demand, utility supply positions, or financial profit/loss.*

---

## Technology Stack

- **Frontend**: React 19, Vite, Recharts, Lucide React, Vanilla CSS (custom design tokens).
- **Backend**: Python 3.13, FastAPI, Uvicorn, Pandas, NumPy, Pydantic.
- **Containerization & Web**: Docker, Docker Compose, Nginx 1.27 Alpine (reverse proxy, SPA fallback, gzip compression).
- **Testing & Quality**: Pytest (backend), Vitest, Testing Library, Oxlint (frontend).

---

## Run Locally with Docker

The application runs via Docker Compose with a pre-packaged canonical January 2026 dataset.

```powershell
# 1. Clone repository
git clone https://github.com/sushanthh05/kjhwr.git
cd kjhwr

# 2. Start services in background
docker compose up --build -d

# 3. Verify service status
docker compose ps

# 4. Stop services when finished
docker compose down
```

### URLs and Access Ports
- **Dashboard**: `http://localhost:8081`
- **Health Check**: `http://localhost:8081/health`
- **Interactive API Docs (Swagger UI)**: `http://localhost:8081/docs`

*The host port defaults to `8081` via `${PORT:-8081}` to prevent collisions with common host services. To change the port, set `PORT` in your shell (e.g., `$env:PORT=8080`) or create a `.env` file from `.env.example`.*

---

## Run Locally without Docker

### Backend Setup (FastAPI)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```
*Backend runs on `http://127.0.0.1:8000` (`/health`, `/docs`).*

### Frontend Setup (React + Vite)
```powershell
cd frontend
npm install --legacy-peer-deps
npm run dev
```
*Frontend runs on `http://localhost:5173` and proxies API requests to `http://127.0.0.1:8000`.*

---

## Data and Evaluation Methodology

- **Data Sources**: Elexon BMRS Insights Solution REST API.
  - Actual generation: `FUELHH` filtered to `fuelType = 'WIND'`.
  - Day-ahead forecasts: `WINDFOR` published multi-vintage forecast streams.
- **Evaluation Period**: January 1, 2026 00:00 UTC through January 31, 2026 23:00 UTC (744 delivery hours).
- **Temporal Resolution Reconciliation**: `FUELHH` actuals are reported at 30-minute intervals. To match hourly `WINDFOR` forecasts, the two half-hourly actual power values are averaged: `(:00 + :30) / 2`. Averaging power (MW) preserves the true hourly delivery rate (summing would erroneously double it).
- **Decision Cutoff Assumption**: Day-ahead procurement decisions require forecasts fixed before market clearing. As a project evaluation assumption, the system selects the latest forecast published on or before **11:00 UTC on the day prior to delivery (D - 1)**. Forecasts published after cutoff are excluded to ensure zero look-ahead bias.
- **Error Sign Convention**:
  $$\text{Error (MW)} = \text{Forecast (MW)} - \text{Actual (MW)}$$
  - **Positive (> 0 MW)**: Overforecast (forecast exceeded actual generation).
  - **Negative (< 0 MW)**: Underforecast (forecast fell short of actual generation).

---

## Limitations

- **National Aggregate Scope**: The system evaluates aggregate GB transmission-metered wind generation only. It does not measure embedded distribution generation or other fuel types.
- **No Utility-Specific Portfolio Modeling**: The application does not model an individual utility's retail customer demand, supply commitments, bilateral contracts, or hedging positions.
- **No Financial Loss or Cashout Calculations**: UK imbalance settlement involves dynamic System Buy Price (SBP) and System Sell Price (SSP) cashout mechanisms. Forecast volumetric error cannot be equated directly to financial loss or savings without utility contract positions and cashout data.

---

## API Reference

| Endpoint | Method | Query Parameters | Description |
| :--- | :---: | :--- | :--- |
| `/health` | `GET` | None | Lightweight service health probe (`status`, `timestamp`). |
| `/api/analytics/overview` | `GET` | `start_date`, `end_date` | Summary KPIs (MAE, RMSE, MBE, MAPE), mean generation, bias breakdown. |
| `/api/analytics/timeseries` | `GET` | `start_date`, `end_date` | Chronological hourly forecasts, actuals, signed errors, and percentage errors. |
| `/api/analytics/daily` | `GET` | `start_date`, `end_date` | Daily aggregated accuracy metrics and interval completeness counts. |
| `/api/analytics/errors` | `GET` | None | Error quantiles (P10–P90), bias counts, and 10-bin exact-sum histogram. |
| `/api/analytics/worst-misses` | `GET` | `limit` (default: 10, max: 100) | Largest forecast deviations sorted by absolute error descending. |
| `/api/analytics/hour-of-day` | `GET` | None | Diurnal 24-hour error profile aggregated by local UK delivery hour. |
| `/api/analytics/metadata` | `GET` | None | Dataset provenance, lineage, units, cutoff parameters, and assumptions. |

---

## Testing

```powershell
# Run backend tests
cd backend
.\.venv\Scripts\python.exe -m pytest -q

# Run frontend tests and production build
cd frontend
npm test
npm run build
```

---

## AI Assistance Disclosure

In accordance with project governance standards, AI tools (Google Antigravity / Gemini) were used during implementation for code scaffolding, unit test authoring, configuration, and documentation assistance. All analytical formulations, data ingestion pipelines, test assertions, and container configurations were verified through execution against the canonical dataset.

---

## Deployment

The application is deployed on Render using a Blueprint configuration (`render.yaml`), orchestrating the FastAPI backend and Nginx-served React frontend as containerized Docker Web Services:

- **Live Application**: [https://wind-forecast-frontend.onrender.com/](https://wind-forecast-frontend.onrender.com/)
- **Backend Service**: [https://wind-forecast-backend-yb3v.onrender.com/](https://wind-forecast-backend-yb3v.onrender.com/) (`/health`, `/docs`)
- **GitHub Repository**: [https://github.com/sushanthh05/kjhwr](https://github.com/sushanthh05/kjhwr)

### Deployment Architecture
- **Backend Web Service**: FastAPI analytics service running on Python 3.13-slim with pre-packaged canonical January 2026 data.
- **Frontend Web Service**: React 19 production build served via Nginx 1.27 Alpine, reverse-proxying `/api/` and `/health` requests to the live backend service with full TLS SNI support.
