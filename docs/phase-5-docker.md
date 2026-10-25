# Phase 5 — Docker Containerization & Reverse-Proxy Architecture

## 1. Overview & Architectural Design

Phase 5 introduces full multi-containerization for the **Wind Forecast Intelligence** platform using Docker and Docker Compose. The architecture decouples the computational analytics service from the presentation layer while enforcing a single-origin reverse proxy topology.

```
                                  [ Browser Client ]
                                           │
                                           │ HTTP: http://localhost:8080
                                           ▼
             ┌───────────────────────────────────────────────────────────┐
             │            Container: wind-forecast-frontend             │
             │                     (Nginx 1.27)                          │
             │                                                           │
             │  Static Routes:                                           │
             │    /               ──► Serves React 19 SPA (Vite dist)    │
             │    /* (fallback)   ──► try_files index.html (SPA routing) │
             │                                                           │
             │  Reverse Proxy Routes:                                    │
             │    /api/*          ──► http://backend:8000/api/*          │
             │    /health         ──► http://backend:8000/health         │
             │    /docs           ──► http://backend:8000/docs           │
             │    /openapi.json   ──► http://backend:8000/openapi.json   │
             └─────────────────────────────┬─────────────────────────────┘
                                           │
                                           │ Internal Bridge Network
                                           │ (wind-forecast-network:8000)
                                           ▼
             ┌───────────────────────────────────────────────────────────┐
             │             Container: wind-forecast-backend             │
             │               (FastAPI + Python 3.13-slim)               │
             │                                                           │
             │  Runtime Components:                                      │
             │    - Non-root user: appuser (uid/gid)                    │
             │    - Uvicorn serving on 0.0.0.0:8000                      │
             │    - In-memory cached Canonical January 2026 Dataset      │
             │      (/app/data/processed/canonical_evaluation_dataset)   │
             │    - Zero external Elexon API requests at startup         │
             └───────────────────────────────────────────────────────────┘
```

---

## 2. Container Specifications

### A. Backend Container (`backend/Dockerfile`)
- **Base Image**: `python:3.13-slim` (matches local Python 3.13 development environment).
- **Security & User**: Creates a dedicated non-root user `appuser` (`/sbin/nologin`) to prevent running processes as root.
- **Packaged Data Assets**:
  - `data/processed/canonical_evaluation_dataset.json` (Normalized hourly matched pairs for all 744 hours of January 2026).
  - `data/processed/canonical_evaluation_dataset.csv` (CSV representation).
  - `data/processed/ingestion_summary.json` (Pipeline execution and quality audit metadata).
- **Excluded Assets**: Local `.venv`, raw API caches (`backend/data/raw/`), Git metadata, and test caches (enforced via `.dockerignore`).
- **Networking**: Exposes port `8000` internally to the Compose network. It is **not** published directly on the host machine to enforce routing via Nginx.
- **Health Check**: Utilizes Python's standard library `urllib.request` to poll `http://127.0.0.1:8000/health` without requiring external binary dependencies (`curl` or `wget`).

### B. Frontend Container (`frontend/Dockerfile` & `frontend/nginx.conf`)
- **Multi-Stage Build**:
  1. **Builder Stage (`node:20-alpine`)**:
     - Reproducibly installs dependencies using `package-lock.json` via `npm ci --legacy-peer-deps`.
     - Injects build-time argument `VITE_API_BASE_URL=""` to ensure all API calls use same-origin relative URLs (`/api/...`).
     - Executes `npm run build` to generate optimized production assets under `/app/dist`.
  2. **Serving Stage (`nginx:1.27-alpine`)**:
     - Removes default Nginx pages.
     - Copies compiled static assets into `/usr/share/nginx/html`.
     - Deploys custom `frontend/nginx.conf` handling gzip compression, security headers (`X-Content-Type-Options`, `X-Frame-Options`), SPA client-side routing fallback (`try_files $uri $uri/ /index.html`), and reverse proxy upstreaming to `http://backend:8000`.
- **Networking**: Maps container port `80` to host port `8080`.
- **Health Check**: Polls `http://127.0.0.1/` using `wget` to verify Nginx availability.

---

## 3. Same-Origin Routing & Configuration

In production, client browsers load the application from `http://localhost:8080`. Rather than exposing the backend on a different port (which would require cross-origin CORS configuration and expose internal services), the frontend requests `/api/analytics/*` and `/health` directly on its own origin. Nginx transparently proxies these requests across the internal Docker bridge network (`wind-forecast-network`) to the `backend:8000` service.

### Environment Variable Matrix

| Variable | Scope | Default Value | Description |
| :--- | :---: | :--- | :--- |
| `VITE_API_BASE_URL` | Frontend Build | `""` (in Docker) / `http://127.0.0.1:8000` (Local Dev) | Base URL for API requests. Empty string produces same-origin relative URLs. |
| `VITE_BACKEND_URL` | Frontend Build | Optional fallback | Backward-compatible URL definition. |
| `CORS_ALLOWED_ORIGINS` | Backend Runtime | `http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173` | Allowed CORS origins for browser access. |
| `CANONICAL_DATASET_PATH` | Backend Runtime | `/app/data/processed/canonical_evaluation_dataset.json` | Optional override for canonical dataset location. |
| `INGESTION_SUMMARY_PATH` | Backend Runtime | `/app/data/processed/ingestion_summary.json` | Optional override for ingestion summary location. |

---

## 4. Operational Instructions (Docker Compose)

### Prerequisites
1. Download and install **Docker Desktop for Windows** from the official site:
   [https://docs.docker.com/desktop/setup/install/windows-install/](https://docs.docker.com/desktop/setup/install/windows-install/)
2. Start Docker Desktop and wait until the status displays **Docker Engine running**.

### Starting the Stack
Open PowerShell and navigate to the project root:

```powershell
cd E:\windX\kjhwr

# Validate Compose configuration syntax
docker compose config

# Build and start both containers in detached mode
docker compose up --build -d
```

### Inspecting Service Status & Logs
```powershell
# Inspect container health and port bindings
docker compose ps

# Follow real-time logs from both services
docker compose logs -f

# View last 100 log lines from the backend service
docker compose logs --tail=100 backend

# View last 100 log lines from the frontend Nginx service
docker compose logs --tail=100 frontend
```

### Accessing the Portal
Once running, open your web browser to:
- **Main Portal UI**: `http://localhost:8080`
- **Backend Health Check**: `http://localhost:8080/health`
- **Interactive Swagger Documentation**: `http://localhost:8080/docs`
- **OpenAPI JSON Schema**: `http://localhost:8080/openapi.json`

### Rebuilding After Source Code Changes
```powershell
# Rebuild containers reflecting code updates
docker compose up --build -d
```

### Stopping the Stack
```powershell
# Stop and remove containers and networks
docker compose down

# Stop and remove containers, networks, and named volumes
docker compose down -v
```

---

## 5. Preservation of Local Development Workflow

The containerization configuration is strictly additive. Local development workflows remain completely intact and independent of Docker:

```powershell
# Local Backend Execution (Terminal 1)
cd E:\windX\kjhwr\backend
.\.venv\Scripts\Activate.ps1
uvicorn app:app --host 127.0.0.1 --port 8000 --reload

# Local Frontend Execution (Terminal 2)
cd E:\windX\kjhwr\frontend
npm run dev
# Accessible at http://localhost:5173
```

---

## 6. Verification Status: Performed vs Pending Checks

### Checks Actually Performed (Offline / Pre-Docker)
- [x] **Backend Test Suite**: 43/43 tests passed (`pytest` in Python 3.13 virtual environment).
- [x] **Frontend Unit & Component Tests**: 39/39 tests passed (`vitest run` verifying API service, formatters, and component renders).
- [x] **Frontend Production Build**: `npm run build` compiled cleanly into `/dist` in 722ms.
- [x] **API Base URL Resolution**: Tested and verified that `getApiBaseUrl({ VITE_API_BASE_URL: '' }) === ''` produces same-origin requests in production while defaulting to `http://127.0.0.1:8000` in dev mode.
- [x] **Compose File & Dockerfile Path Audits**: Verified that `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, `.dockerignore`, and all processed canonical data files exist and have valid paths and syntax.
- [x] **Context Exclusion Audit**: Confirmed that `.dockerignore` correctly excludes `.venv`, `node_modules`, `.env`, and raw API caches (`backend/data/raw/`) while explicitly preserving `backend/data/processed/`.
- [x] **Local Non-Docker Flow**: Verified that local FastAPI and Vite dev servers continue to run with zero regressions.

### Checks Pending Docker Installation
- [ ] Execution of `docker --version`, `docker compose version`, and `docker info`.
- [ ] Building images via `docker compose build`.
- [ ] Running containers via `docker compose up -d` and validating live browser interaction on `http://localhost:8080`.

---

## 7. Common Windows Docker Desktop Troubleshooting

1. **WSL 2 Backend Not Initialized**:
   - Ensure WSL 2 is installed: `wsl --install` or `wsl --update`.
   - In Docker Desktop Settings > General, ensure "Use the WSL 2 based engine" is enabled.
2. **Port 8080 Conflict**:
   - If port 8080 is already bound by another local service, edit `docker-compose.yml` to map to an alternative port (e.g. `"8081:80"`).
3. **File Permission / Volume Mount Warning**:
   - The production containers package code directly into the images (`COPY`), meaning no Windows-to-Linux host filesystem volume mounting is required at runtime, preventing file lock and permission issues.
