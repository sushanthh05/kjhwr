# Wind Forecast Intelligence — Frontend Dashboard

A high-performance energy-market intelligence dashboard built with React 19, Vite 8, Recharts, and custom Vanilla CSS design tokens.

## Architecture

- **Framework**: React 19 SPA bundled with Vite 8.
- **Styling**: Vanilla CSS design system with CSS custom properties (`frontend/src/index.css`) supporting modern dark themes, responsive layouts down to 360px viewports, and custom focus rings.
- **Visualization**: Recharts for high-resolution forecast vs outturn time series, error distribution histograms, and diurnal 24-hour profiles.
- **Icons**: Lucide React.
- **Testing**: Vitest + React Testing Library (41 passing unit & component tests).
- **Linter**: Oxlint.

## Available Scripts

- `npm run dev`: Launch Vite local development server on `http://localhost:5173`. Proxies `/api/` to `http://127.0.0.1:8000`.
- `npm test`: Run automated Vitest test suite (`vitest run`).
- `npm run lint`: Run Oxlint code analysis.
- `npm run build`: Build production SPA bundle into `frontend/dist/`.
- `npm run preview`: Preview the production build locally.

## Production Routing & Nginx Integration

In production mode, the dashboard relies on an empty API base URL (`VITE_API_BASE_URL=""`), routing all `/api/...` and `/health` requests to same-origin URLs reverse-proxied by Nginx (`frontend/nginx.conf`) to the FastAPI backend container.
