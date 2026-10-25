# syntax=docker/dockerfile:1
# Wind Forecast Intelligence — Backend Dockerfile
# Base image: Official Python 3.13 slim (matching local development runtime)
FROM python:3.13-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Set container working directory
WORKDIR /app

# Create a non-root system user and group for runtime security
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Install pinned Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend application modules
COPY app.py analytics.py elexon_validator.py elexon_data.py ./

# Package the canonical January 2026 processed evaluation dataset and metadata
COPY data/processed/ ./data/processed/

# Ensure application files are owned by non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose internal FastAPI service port
EXPOSE 8000

# Health check using Python's standard library (no curl/wget dependency required)
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

# Start FastAPI application using Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
