# syntax=docker/dockerfile:1
# Wind Forecast Intelligence — Frontend Dockerfile
# Stage 1: Reproducible Build Stage using Node 20 Alpine
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency manifests for reproducible dependency resolution
COPY package.json package-lock.json ./

# Install dependencies using package-lock.json (--legacy-peer-deps handles React 19 / Recharts peer resolution)
RUN npm ci --legacy-peer-deps

# Copy application sources (excluding node_modules & local .env via .dockerignore)
COPY index.html vite.config.js ./
COPY public/ ./public/
COPY src/ ./src/

# Build argument for same-origin API routing (defaults to empty string for reverse-proxied production)
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build production bundle into /app/dist
RUN npm run build

# Stage 2: High-Performance Lightweight Nginx Serving Container
FROM nginx:1.27-alpine

# Remove default Nginx welcome site
RUN rm -rf /usr/share/nginx/html/*

# Copy Nginx template and dynamic runtime entrypoint script
COPY nginx.conf.template /etc/nginx/nginx.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Copy compiled static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose internal HTTP port
EXPOSE 80

# Lightweight container health check respecting dynamic PORT
HEALTHCHECK --interval=20s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null "http://127.0.0.1:${PORT:-80}/" || exit 1

# Start container via dynamic entrypoint script
ENTRYPOINT ["/docker-entrypoint.sh"]

