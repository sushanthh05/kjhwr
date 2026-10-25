# Wind Forecast Intelligence

An energy-market intelligence portal built for a UK electricity utility day-ahead trading and purchasing desk. The application analyzes wind generation forecast accuracy, systematic bias, and volumetric discrepancies between National Grid ESO day-ahead forecasts (`WINDFOR`) and actual metered wind outturn (`FUELHH`) from the Elexon BMRS market data system.

---

## Deployment Status

**Live Application URL**: `[Pending Deployment — Staging Target: http://localhost:8081]`

*Note: In accordance with deployment phase specifications, live external cloud deployment has not been published. The multi-container stack is fully configured, tested, and containerized for deployment via Docker Compose.*

---

## Current Project Status: Phase 6 Complete

- **Phase 0 (Environment Scaffold)**: FastAPI backend, Vite React frontend, baseline tests, and project hygiene established.
- **Phase 1 (Elexon API Investigation & Validation)**:
  - Official Elexon Insights Solution (BMRS) APIs investigated for `FUELHH` (actuals) and `WINDFOR` (forecasts).
  - Domain discovery: 30-minute actuals resolution vs 60-minute forecast resolution.
  - Reusable validation utilities created in `backend/elexon_validator.py`.
- **Phase 2 (Historical Data Ingestion & Normalization Pipeline)**:
  - Complete January 2026 actuals (`FUELHH`, 1,488 records) and multi-vintage forecasts (`WINDFOR`, 19,272 records) ingested from the live Elexon API.
  - Temporal resolution reconciliation: hourly actual power is calculated as the average of two valid half-hour intervals (`(:00 + :30) / 2`).
  - Configurable day-ahead decision cutoff enforced (default: `11:00 UTC` day-ahead). Forecasts published after cutoff are strictly excluded (0 look-ahead leakage).
  - Canonical evaluation dataset built for all 744 hours of January 2026 with **100% complete coverage** (744 complete matched pairs).
  - Atomic persistence to CSV and JSON under `backend/data/processed/`.
- **Phase 3 (Forecast Accuracy Analytics Engine & Backend API)**:
  - Core analytics module created in `backend/analytics.py` computing MAE, RMSE, MBE, MAPE, quantiles, and exact-sum histograms.
  - Signed error definition enforced: $\text{error\_mw} = \text{forecast\_mw} - \text{actual\_mw}$ (positive = overforecast, negative = underforecast).
  - Safe MAPE computation with explicit zero-actual exclusions.
  - Production FastAPI endpoints exposed under `/api/analytics/*` with date filtering, limit validation, and Europe/London diurnal profiling.
  - Automated Python test suite passing 43 tests.
- **Phase 4 (Complete React Wind Forecast Intelligence Dashboard)**:
  - Full single-page enterprise dashboard built in React 19 + Vite 8 with Vanilla CSS design tokens.
  - Clean API service layer in `frontend/src/services/api.js` consuming real backend endpoints with `AbortSignal` cancellation and zero synthetic fallback metrics.
  - Verified live connectivity status indicator in `Header.jsx`.
  - Visible day-ahead cutoff policy (`11:00 UTC D-1`) and GB national market scope boundary in `DecisionContext.jsx`.
  - 6 Core KPI cards (MAE, RMSE, MBE with overforecast bias styling, MAPE, Mean Actual, Mean Forecast) with loading skeletons.
  - Interactive Recharts time series with delivery date-range picker and preset buttons (`Full Month`, `Wk 1-4`, `29-31 Jan`).
  - Forecast error distribution histogram (10 partitions), quantiles, and signed error convention explanations.
  - Daily accuracy MAE chart with dynamic best/worst day identifiers.
  - Top 10 worst misses table with operational trading context.
  - Diurnal accuracy profile by UK local hour in `Europe/London` with section-level fault isolation.
  - Expandable data lineage and quality audit drawer in `MethodologyPanel.jsx`.
  - Complete unit test suite (39 passing Vitest tests) and clean production bundle (`npm run build`).
- **Phase 5 (Docker & Docker Compose Containerization)**:
  - Multi-container architecture orchestrating Python 3.13-slim FastAPI backend and Nginx-served React frontend.
  - Root `.dockerignore`, `backend/.dockerignore`, and `frontend/.dockerignore` excluding `.venv`, `node_modules`, and raw API caches while preserving the canonical processed evaluation dataset.
  - Production `backend/Dockerfile` running as a non-root user (`appuser`) with internal health checks.
  - Multi-stage `frontend/Dockerfile` using Node 20 Alpine for reproducible builds and lightweight Nginx 1.27 Alpine for static asset delivery.
  - Same-origin reverse proxy configuration in `frontend/nginx.conf` routing `/api/`, `/health`, and `/docs` to `http://backend:8000` with client-side SPA routing fallback.
  - `docker-compose.yml` declaring `backend` and `frontend` services with bridge network, internal port exposure, and container health checks on host port `8081:80`.
- **Phase 6 (Production Readiness & Deployment Preparation)**:
  - **Backend Hardening**: Sanitized all 500 and 503 error responses to prevent local filesystem paths and raw stack traces from leaking to clients. Added query parameter validation (`start_date <= end_date`, limit bounds `1 <= limit <= 100`).
  - **Lightweight Health Check**: Kept `/health` lightweight, returning service status and timestamp without disk I/O, ideal for Docker container health checks.
  - **Frontend Hardening & Responsiveness**: Mobile and tablet responsive styling down to 360px viewport widths in `index.css`. Tested loading, empty, and malformed data error handling. Verified zero hardcoded benchmark numbers or development URLs in production bundle.
  - **Data Integrity & Methodology Verification**: 8 automated verification tests created in `backend/tests/test_production_readiness.py` validating 744 hourly intervals, half-hourly averaging, cutoff filtering, signed error conventions, and metrics mathematics.
  - **Clean Hygiene**: Updated `.gitignore` to protect raw data caches while preserving the canonical processed dataset for container builds.
  - **Full Test Suite**: 53 backend tests passing (100%), 41 frontend tests passing (100%), zero lint errors, and successful production build.

---

## Key Features

1. **Executive KPI Header**: Instant visibility into Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), Mean Bias Error (MBE), Mean Absolute Percentage Error (MAPE), Mean Actual Generation, and Mean Forecast Generation.
2. **Interactive Delivery Time Series**: High-resolution chart comparing hourly day-ahead forecasts against metered outturn with brush zooming, custom tooltips, and delivery date filtering (Full Month, Wk 1–4, and custom ranges).
3. **Error Distribution & Quantile Breakdown**: 10-bin exact-sum error distribution histogram alongside P10, P25, Median (P50), P75, and P90 error quantiles, highlighting asymmetric long/short exposure.
4. **Daily Accuracy Heatmap/Bars**: Daily MAE bar chart with dynamic badges highlighting the most accurate day (lowest MAE) and most challenging forecast day (highest MAE).
5. **Top 10 Worst Forecast Misses**: Operational table ranking the largest volumetric forecast deviations with delivery timestamp, forecast vs actual generation, absolute error, and imbalance trading context.
6. **Diurnal (24-Hour) Accuracy Profile**: Hourly breakdown in UK local time (`Europe/London`), identifying intraday periods with peak volatility and systematic morning/evening ramp errors.
7. **Transparent Methodology & Lineage Panel**: Collapsible audit panel disclosing dataset provenance, Elexon BMRS endpoint lineage, half-hourly aggregation formulas, and day-ahead cutoff rules.

---

## Architecture & Technology Stack

```text
               +-------------------------------------------------------+
               |                    Browser Client                     |
               +-------------------------------------------------------+
                                           |
                                  HTTP (Host Port 8081)
                                           v
+------------------------------------------------------------------------------------+
| Docker Compose Environment (wind-forecast-network)                                 |
|                                                                                    |
|  +------------------------------------------------------------------------------+  |
|  | Frontend Service (Nginx 1.27 Alpine)                                         |  |
|  |  - Serves React 19 SPA (Vite 8 production build)                             |  |
|  |  - Gzip compression & security headers (nosniff, SAMEORIGIN)                 |  |
|  |  - Reverse Proxies:                                                          |  |
|  |      /api/*        ---> http://backend:8000/api/*                            |  |
|  |      /health       ---> http://backend:8000/health                           |  |
|  |      /docs         ---> http://backend:8000/docs                             |  |
|  +------------------------------------------------------------------------------+  |
|                                          |                                         |
|                                 Internal HTTP (Bridge)                             |
|                                          v                                         |
|  +------------------------------------------------------------------------------+  |
|  | Backend Service (Python 3.13-slim / FastAPI / Uvicorn)                       |  |
|  |  - Runs as unprivileged non-root user (appuser)                              |  |
|  |  - Sanitized error handling (zero path / stack trace leaks)                  |  |
|  |  - Analytics engine (Pandas, NumPy)                                          |  |
|  |  - Pre-packaged canonical evaluation dataset (January 2026, 744 hours)      |  |
|  +------------------------------------------------------------------------------+  |
+------------------------------------------------------------------------------------+
```

### Technology Matrix

| Layer | Component | Technologies |
| :--- | :--- | :--- |
| **Frontend** | Framework & Build | React 19, Vite 8, Vanilla CSS (custom design tokens) |
| | Visualizations | Recharts, Lucide React icons |
| | Quality & Testing | Vitest, Testing Library, Oxlint |
| **Backend** | API Framework | FastAPI, Starlette, Uvicorn |
| | Data & Analytics | Pandas, NumPy, Pydantic |
| | Quality & Testing | Pytest, TestClient |
| **Ingestion** | Data Source | Elexon BMRS Insights API (`FUELHH`, `WINDFOR`) |
| **Infrastructure** | Containerization | Docker, Docker Compose, Multi-stage builds |
| | Web Server & Proxy | Nginx 1.27 Alpine (gzip, security headers, reverse proxy) |

---

## Local Development Instructions (Non-Docker)

### 1. Prerequisites
- **Python**: 3.11+ (tested on Python 3.13)
- **Node.js**: 20+ (tested on Node v20.20)
- **npm**: 10+ (tested on npm 10.8)

### 2. Backend Setup & Startup

```powershell
# Navigate to backend directory
cd E:\windX\kjhwr\backend

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies (if not already installed)
pip install -r requirements.txt

# Start FastAPI development server with auto-reload
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

- API Base URL: `http://127.0.0.1:8000`
- Interactive OpenAPI Swagger UI: `http://127.0.0.1:8000/docs`
- Health Check: `http://127.0.0.1:8000/health`

### 3. Frontend Setup & Startup

```powershell
# Open a new terminal and navigate to frontend directory
cd E:\windX\kjhwr\frontend

# Install dependencies (if not already installed)
npm install --legacy-peer-deps

# Start Vite development server
npm run dev
```

- Frontend Dev URL: `http://localhost:5173`
- The development server automatically proxies API calls to `http://127.0.0.1:8000` via Vite configuration.

---

## Docker Startup & Shutdown Commands

### 1. Build and Start the Stack
From the project root (`E:\windX\kjhwr`), start both services in detached mode:

```powershell
# Build container images and launch services
docker compose up --build -d
```

### 2. Check Service Health & Status
```powershell
# View running container status and health
docker compose ps

# Follow live container logs
docker compose logs -f
```

### 3. Access Containerized Application
- **Frontend Dashboard**: `http://localhost:8081`
- **Backend Health Check**: `http://localhost:8081/health`
- **API Swagger Documentation**: `http://localhost:8081/docs`

*(Note: Default host port is configured to `8081` via `${PORT:-8081}` to avoid conflicts with common Windows host services bound to port `8080`).*

### 4. Stop Containers
```powershell
# Stop and remove containers and bridge network
docker compose down
```

---

## API Endpoints Reference

All analytics endpoints return deterministic results based on the canonical January 2026 evaluation dataset.

| Endpoint | Method | Query Parameters | Expected Response | Description |
| :--- | :---: | :--- | :---: | :--- |
| `/health` | `GET` | None | `200 OK` | Lightweight container health check (`status`, `timestamp`). No disk I/O. |
| `/docs` | `GET` | None | `200 OK` | Interactive Swagger UI API documentation. |
| `/openapi.json` | `GET` | None | `200 OK` | OpenAPI 3.1 schema specification. |
| `/api/analytics/overview` | `GET` | `start_date`, `end_date` (`YYYY-MM-DD`) | `200 OK` / `400` / `503` | Overall accuracy metrics (MAE, RMSE, MBE, MAPE), mean generation, bias counts, coverage. |
| `/api/analytics/timeseries` | `GET` | `start_date`, `end_date` (`YYYY-MM-DD`) | `200 OK` / `400` / `503` | Chronological hourly records: `delivery_start`, `actual_mw`, `forecast_mw`, `error_mw`, `abs_error_mw`, `pct_error`. |
| `/api/analytics/daily` | `GET` | `start_date`, `end_date` (`YYYY-MM-DD`) | `200 OK` / `400` / `503` | Daily aggregated accuracy metrics, interval counts, completeness indicator. |
| `/api/analytics/errors` | `GET` | None | `200 OK` / `503` | Quantiles (P10, P25, P50, P75, P90), over/under counts, and 10-bin exact-sum histogram. |
| `/api/analytics/worst-misses` | `GET` | `limit` (int, default: 10, range: 1–100) | `200 OK` / `422` / `503` | Largest forecast deviations sorted by absolute error descending with trading impact analysis. |
| `/api/analytics/hour-of-day` | `GET` | None | `200 OK` / `503` | 24-hour diurnal accuracy profile aggregated by local delivery hour in `Europe/London`. |
| `/api/analytics/metadata` | `GET` | None | `200 OK` / `503` | Data lineage, source endpoints, temporal resolution, cutoff rules, and operational boundaries. |

### Parameter Validation Rules
- **Date Format**: Must match `YYYY-MM-DD` ISO 8601 string.
- **Date Range**: If both `start_date` and `end_date` are supplied, `start_date <= end_date` is enforced. Otherwise, HTTP 400 Bad Request is returned.
- **Limit Bounds**: `/api/analytics/worst-misses` enforces `1 <= limit <= 100`. Out-of-bound values return HTTP 422 Unprocessable Entity.

---

## Dataset Provenance & Evaluation Methodology

### 1. Data Sources
- **Actual Generation**: Elexon BMRS `FUELHH` (Half-hourly generation by fuel type). Records where `fuelType == 'WIND'` are retained.
- **Forecast Generation**: Elexon BMRS `WINDFOR` (Wind generation forecasts by published vintage and delivery start time).
- **Time Horizon**: Complete calendar month of January 2026 (2026-01-01 00:00 UTC through 2026-01-31 23:00 UTC).

### 2. Temporal Resolution Reconciliation
- `FUELHH` actuals are published every 30 minutes (48 settlement periods per day).
- `WINDFOR` day-ahead forecasts are published on an hourly delivery schedule (24 intervals per day).
- **Mathematical Averaging**: To accurately represent average power in Megawatts (MW) over an hour, the two half-hourly actuals (`:00` and `:30`) are averaged, **not summed**:
  $$\text{actual\_generation\_mw} = \frac{\text{actual\_generation\_mw}_{:00} + \text{actual\_generation\_mw}_{:30}}{2}$$
  *(Summing power values would improperly double the true delivery rate).*

### 3. Day-Ahead Decision Cutoff & Vintage Selection
- Utility day-ahead procurement decisions must be finalized prior to market clearing deadlines.
- **Cutoff Policy**: `11:00 UTC` on the day prior to delivery ($D-1$).
- **Selection Rule**: For each delivery interval, the dataset selects the latest forecast vintage published on or before the cutoff timestamp:
  $$\text{publish\_time} \le \text{delivery\_date}_{D-1} \text{ 11:00:00 UTC}$$
- **Zero Look-Ahead Leakage**: Forecasts published after the cutoff are strictly excluded from the day-ahead evaluation.

### 4. Error Sign Convention
$$\text{error\_mw}_i = \text{forecast\_generation\_mw}_i - \text{actual\_generation\_mw}_i$$
- **Positive Error ($> 0$)**: **Overforecast**. Forecast exceeded actual outturn. A utility buying against this forecast would be long in day-ahead and forced to sell spill in the Balancing Mechanism.
- **Negative Error ($< 0$)**: **Underforecast**. Forecast fell short of actual outturn. A utility would be short and face cashout imbalance penalties.

### 5. Metric Calculations
- **Mean Absolute Error (MAE)**:
  $$\text{MAE} = \frac{1}{n} \sum_{i=1}^{n} |\text{forecast}_i - \text{actual}_i|$$
- **Root Mean Squared Error (RMSE)**:
  $$\text{RMSE} = \sqrt{\frac{1}{n} \sum_{i=1}^{n} (\text{forecast}_i - \text{actual}_i)^2}$$
- **Mean Bias Error (MBE)**:
  $$\text{MBE} = \frac{1}{n} \sum_{i=1}^{n} (\text{forecast}_i - \text{actual}_i)$$
- **Mean Absolute Percentage Error (MAPE)**:
  $$\text{MAPE} = \frac{1}{n_{\text{nonzero}}} \sum_{i \in \{j \mid \text{actual}_j > 0\}} \frac{|\text{forecast}_i - \text{actual}_i|}{\text{actual}_i} \times 100\%$$
  *(Observations where $\text{actual} = 0$ are explicitly excluded to prevent division by zero).*

### 6. Reference Empirical Results (January 2026 Canonical Dataset)
- **Matched Delivery Intervals**: 744 hours (100% complete coverage)
- **Mean Actual Generation**: 11,580.74 MW
- **Mean Forecast Generation**: 13,421.03 MW
- **Mean Absolute Error (MAE)**: 2,122.81 MW
- **Root Mean Squared Error (RMSE)**: 2,616.69 MW
- **Mean Bias Error (MBE)**: +1,840.30 MW (systematic overforecast bias)
- **Mean Absolute Percentage Error (MAPE)**: 22.06%
- **Overforecast Intervals**: 628 hours (84.41%)
- **Underforecast Intervals**: 116 hours (15.59%)
- **Maximum Absolute Miss**: 6,833.0 MW (observed at 01:00 UTC on 12 January 2026)

---

## Limitations & Operational Assumptions

1. **National Grid Scope**: This portal evaluates aggregate transmission-connected GB national wind generation outturn published by Elexon BMRS. It does not measure embedded distribution-connected generation or non-wind generation assets.
2. **No Utility-Specific Demand Modeling**: The analytics evaluate forecast accuracy against outturn. They do not model a specific utility's customer load profile, retail consumption, retail customer churn, or bilateral PPA contracts.
3. **No Fabricated Pricing or Financial Loss Claims**: Financial settlement in the UK electricity market depends on complex half-hourly System Buy Price (SBP), System Sell Price (SSP), cashout rates, and individual utility trading books. This application computes exact volumetric and percentage errors; it strictly avoids fabricating financial prices, cashout cash flows, or customer-specific savings.
4. **Time Zone Alignment**: All BMRS source data is timestamped in UTC. Diurnal analysis aligns intervals to `Europe/London` local time (which corresponds to GMT during January).

---

## How to Run Tests

### Backend Test Suite (Pytest)
The backend automated test suite contains 53 tests covering ingestion validation, cutoff filtering, temporal aggregation, pure analytics formulas, API endpoints, error sanitization, parameter validation, and methodology integrity.

```powershell
cd E:\windX\kjhwr\backend
.\.venv\Scripts\python.exe -m pytest -q
```
*Expected Result: `53 passed in < 1.5s`*

### Frontend Unit & Component Tests (Vitest)
The frontend test suite contains 41 tests covering formatting utilities, API service request/parameter encoding, error handling, component rendering (KPI cards, charts, worst misses table, methodology panel), and loading/error states.

```powershell
cd E:\windX\kjhwr\frontend
npm test
```
*Expected Result: `41 passed across 3 test files`*

### Frontend Linting
```powershell
cd E:\windX\kjhwr\frontend
npm run lint
```
*Expected Result: `0 errors`*

### Frontend Production Build
```powershell
cd E:\windX\kjhwr\frontend
npm run build
```
*Expected Result: Built cleanly into `dist/` with zero hardcoded development URLs.*

---

## Explicit AI Tools Disclosure

In accordance with project governance standards, AI tools were utilized during the development of this project:

- **AI Assistants Used**: Google Antigravity / Gemini 2.5 Coding Agent.
- **Specific Tasks Supported**:
  - **Phase 0**: Project layout initialization, directory structures, environment verification scripts, and baseline smoke tests.
  - **Phase 1**: Exploration and schema verification of the official Elexon BMRS Insights Solution REST endpoints (`FUELHH` and `WINDFOR`), identifying the half-hourly vs hourly temporal resolution mismatch.
  - **Phase 2**: Generation of the historical data ingestion and normalization pipeline, implementation of the half-hourly averaging reconciliation algorithm, enforcement of the `11:00 UTC D-1` decision cutoff, and creation of automated pipeline regression tests.
  - **Phase 3**: Statistical formula implementation for forecast accuracy metrics (MAE, RMSE, MBE, MAPE with safe division), quantile calculation, exact-sum error distribution binning, and FastAPI REST endpoint scaffolding.
  - **Phase 4**: Frontend component architecture in React 19, Vanilla CSS design token system implementation, Recharts integration, Vitest component test authoring, and browser-driven UI verification.
  - **Phase 5**: Containerization configuration including non-root backend Dockerfile, multi-stage frontend Dockerfile, Nginx reverse proxy configuration, `.dockerignore` filters, and Docker Compose orchestration.
  - **Phase 6**: Production readiness auditing, error response path sanitization, query parameter boundary validation, methodology integrity tests, and technical documentation authoring.
- **Human Oversight & Verification**: All calculations, formulas, test suites, API contracts, and container configurations were verified against actual execution outputs and live test runs. No synthetic metrics, fabricated prices, or hypothetical test results were generated.
