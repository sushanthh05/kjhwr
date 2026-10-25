# Technical Documentation

This directory contains technical architecture documentation and phase reports for the UK Wind Generation Forecast Intelligence platform.

## Documentation Index

- **[phase-1-elexon-investigation.md](file:///E:/windX/kjhwr/docs/phase-1-elexon-investigation.md)**: Elexon BMRS API investigation findings, endpoint exploration (`FUELHH`, `WINDFOR`), temporal resolution mismatch discovery (30-min actuals vs 60-min forecasts), and validation utilities.
- **[phase-2-data-pipeline.md](file:///E:/windX/kjhwr/docs/phase-2-data-pipeline.md)**: Historical ingestion engine, half-hourly averaging reconciliation (`(:00 + :30)/2`), `11:00 UTC D-1` decision cutoff enforcement, and canonical January 2026 dataset construction (744 matched hours).
- **[phase-3-analytics.md](file:///E:/windX/kjhwr/docs/phase-3-analytics.md)**: Mathematical formulations for forecast accuracy metrics (MAE, RMSE, MBE, MAPE with safe division), 10-bin exact-sum error distribution, quantile calculation, and FastAPI REST endpoints reference.
- **[phase-4-frontend.md](file:///E:/windX/kjhwr/docs/phase-4-frontend.md)**: React 19 + Vite 8 frontend architecture, Vanilla CSS design token system, Recharts visualizations, component contracts, error boundaries, and Vitest test suite.
- **[phase-5-docker.md](file:///E:/windX/kjhwr/docs/phase-5-docker.md)**: Containerization architecture, non-root Python 3.13 backend Dockerfile, multi-stage Node 20 / Nginx 1.27 frontend Dockerfile, reverse proxy routing, and Docker Compose orchestration.

## Operational Boundaries & Data Lineage

- **Scope**: Evaluates GB national aggregate transmission-metered wind generation from Elexon BMRS.
- **Decision Cutoff**: Day-ahead 11:00 UTC cutoff enforced on forecast publication timestamps to guarantee 0 look-ahead leakage.
- **Exclusions**: Does not model utility customer demand portfolios, retail supply contracts, or financial imbalance settlement losses. No prices or financial savings are fabricated.
