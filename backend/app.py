import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from analytics import (
    calculate_core_metrics,
    calculate_daily_metrics,
    calculate_error_distribution,
    calculate_hour_of_day_metrics,
    calculate_worst_misses,
    filter_records_by_date,
    load_canonical_dataset,
    load_ingestion_summary,
    validate_and_extract_pairs,
)

logger = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="Wind Forecast Intelligence API",
    version="0.1.0",
    description="Backend service for UK electricity wind-generation forecast intelligence."
)

# Configurable CORS origins (supports Vite dev, local Nginx container, and host access)
raw_origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080,http://localhost:8081,http://127.0.0.1:8081"
)
allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

is_wildcard = allowed_origins == ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=not is_wildcard,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Global exception handler preventing raw stack traces or local paths from leaking in API responses
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)
    logger.error("Unhandled exception at %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred while processing the request."}
    )


# Dependency to load canonical dataset (can be overridden in tests via app.dependency_overrides)
def get_canonical_dataset() -> List[Dict[str, Any]]:
    try:
        return load_canonical_dataset()
    except FileNotFoundError as exc:
        logger.error("Canonical evaluation dataset missing: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canonical evaluation dataset is currently unavailable on the server."
        )
    except ValueError as exc:
        logger.error("Canonical evaluation dataset validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Canonical evaluation dataset failed validation or could not be loaded."
        )


analytics_router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@analytics_router.get("/overview")
def get_overview(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    records: List[Dict[str, Any]] = Depends(get_canonical_dataset)
):
    """
    Returns overall forecast accuracy metrics (MAE, RMSE, MBE, MAPE),
    coverage statistics, error sign counts, and dataset quality warnings.
    Supports optional date range filtering (start_date, end_date).
    """
    try:
        filtered = filter_records_by_date(records, start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    valid_pairs, audit = validate_and_extract_pairs(filtered)
    metrics = calculate_core_metrics(valid_pairs, total_expected_intervals=len(filtered))

    summary = load_ingestion_summary()
    config = summary.get("config", {})

    warnings = []
    if audit["excluded_records_count"] > 0:
        warnings.append(f"{audit['excluded_records_count']} record(s) excluded from accuracy metrics due to data quality flags.")
    if metrics["mape_excluded_zero_actual_count"] > 0:
        warnings.append(f"{metrics['mape_excluded_zero_actual_count']} observation(s) excluded from MAPE due to zero actual generation.")

    return {
        "delivery_scope": {
            "start_date": start_date or config.get("delivery_start_date", "2026-01-01"),
            "end_date": end_date or config.get("delivery_end_date", "2026-01-31"),
            "decision_cutoff": f"{config.get('decision_cutoff_time', '11:00')} {config.get('decision_timezone', 'UTC')} (Day-Ahead)"
        },
        "error_definition": "error_mw = forecast_generation_mw - actual_generation_mw (positive = overforecast, negative = underforecast)",
        "units": {
            "power": "Megawatts (MW)",
            "errors": "Megawatts (MW)",
            "percentage": "Percent (%)"
        },
        "metrics": {
            "mae_mw": metrics["mae_mw"],
            "rmse_mw": metrics["rmse_mw"],
            "mbe_mw": metrics["mbe_mw"],
            "mape_pct": metrics["mape_pct"],
            "max_absolute_error_mw": metrics["max_absolute_error_mw"],
            "median_absolute_error_mw": metrics["median_absolute_error_mw"],
            "mean_actual_mw": metrics["mean_actual_mw"],
            "mean_forecast_mw": metrics["mean_forecast_mw"]
        },
        "coverage": {
            "expected_intervals_count": metrics["expected_intervals_count"],
            "matched_pairs_count": metrics["matched_pairs_count"],
            "matched_coverage_pct": metrics["matched_coverage_pct"],
            "excluded_records_count": audit["excluded_records_count"],
            "mape_included_count": metrics["mape_included_count"],
            "mape_excluded_zero_actual_count": metrics["mape_excluded_zero_actual_count"]
        },
        "error_sign_counts": {
            "positive_overforecast_count": metrics["positive_error_count"],
            "negative_underforecast_count": metrics["negative_error_count"],
            "zero_error_count": metrics["zero_error_count"]
        },
        "data_quality_warnings": warnings
    }


@analytics_router.get("/timeseries")
def get_timeseries(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    records: List[Dict[str, Any]] = Depends(get_canonical_dataset)
):
    """
    Returns the hourly time series of forecasts versus actuals,
    signed error, absolute error, and percentage error.
    """
    try:
        filtered = filter_records_by_date(records, start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    valid_pairs, _ = validate_and_extract_pairs(filtered)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "count": len(valid_pairs),
        "data": valid_pairs
    }


@analytics_router.get("/daily")
def get_daily(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    records: List[Dict[str, Any]] = Depends(get_canonical_dataset)
):
    """
    Returns daily aggregated forecast accuracy summaries (MAE, RMSE, MBE, MAPE, mean power).
    """
    try:
        daily_metrics = calculate_daily_metrics(records, start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {
        "start_date": start_date,
        "end_date": end_date,
        "count": len(daily_metrics),
        "data": daily_metrics
    }


@analytics_router.get("/errors")
def get_errors(
    records: List[Dict[str, Any]] = Depends(get_canonical_dataset)
):
    """
    Returns the error distribution, signed/absolute quantiles, and a histogram suitable for frontend rendering.
    """
    valid_pairs, _ = validate_and_extract_pairs(records)
    dist = calculate_error_distribution(valid_pairs, num_bins=10)
    return dist


@analytics_router.get("/worst-misses")
def get_worst_misses_endpoint(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of worst misses to return (1-100)"),
    records: List[Dict[str, Any]] = Depends(get_canonical_dataset)
):
    """
    Returns the largest forecast misses sorted by absolute error descending with deterministic tie-breaking.
    """
    valid_pairs, _ = validate_and_extract_pairs(records)
    try:
        worst = calculate_worst_misses(valid_pairs, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {
        "limit": limit,
        "count": len(worst),
        "data": worst
    }


@analytics_router.get("/hour-of-day")
def get_hour_of_day(
    records: List[Dict[str, Any]] = Depends(get_canonical_dataset)
):
    """
    Returns forecast accuracy profile grouped by UK local delivery hour (0-23 in Europe/London).
    """
    valid_pairs, _ = validate_and_extract_pairs(records)
    hod = calculate_hour_of_day_metrics(valid_pairs, tz_name="Europe/London")
    return {
        "timezone": "Europe/London",
        "data": hod
    }


@analytics_router.get("/metadata")
def get_metadata(
    records: List[Dict[str, Any]] = Depends(get_canonical_dataset)
):
    """
    Returns metadata about datasets, sources, assumptions, and analytical boundaries.
    """
    summary = load_ingestion_summary()
    config = summary.get("config", {})
    eval_ds = summary.get("evaluation_dataset", {})

    valid_pairs, audit = validate_and_extract_pairs(records)
    metrics = calculate_core_metrics(valid_pairs, total_expected_intervals=len(records))

    return {
        "service_name": "Wind Forecast Intelligence Analytics API",
        "version": "0.1.0",
        "data_sources": [
            "Elexon BMRS FUELHH (Half-hourly generation by fuel type - WIND actuals)",
            "Elexon BMRS WINDFOR (National Grid ESO Wind generation forecasts)"
        ],
        "delivery_scope": {
            "start_date": config.get("delivery_start_date", "2026-01-01"),
            "end_date": config.get("delivery_end_date", "2026-01-31"),
            "decision_cutoff_time": config.get("decision_cutoff_time", "11:00"),
            "decision_timezone": config.get("decision_timezone", "UTC")
        },
        "generation_unit": "Megawatts (MW)",
        "temporal_resolutions": {
            "fuelhh_actuals_raw": "30 minutes (settlement periods 1 to 48)",
            "windfor_forecasts_raw": "60 minutes (hourly projections over 72h horizon)",
            "canonical_evaluation": "60 minutes (two-period half-hourly average actual matched to pre-cutoff forecast)"
        },
        "dataset_creation_timestamp_utc": summary.get("pipeline_run_timestamp_utc"),
        "coverage_summary": {
            "total_intervals": metrics["expected_intervals_count"],
            "complete_matched_pairs": metrics["matched_pairs_count"],
            "coverage_pct": metrics["matched_coverage_pct"],
            "is_fully_complete": eval_ds.get("is_fully_complete", metrics["matched_coverage_pct"] == 100.0)
        },
        "assumptions_and_limitations": [
            "The 11:00 UTC day-ahead cutoff is a documented working assumption based on European/UK day-ahead market auctions.",
            "All power values are in average MW per hour, not interval energy MWh.",
            "This analysis evaluates national GB wind generation forecast error; it does not calculate commercial balancing mechanism penalties or client-specific portfolio procurement needs.",
            "Forecasts published after the 11:00 UTC cutoff are strictly excluded to avoid look-ahead bias."
        ]
    }


app.include_router(analytics_router)


@app.get("/")
def get_root():
    return {
        "name": "Wind Forecast Intelligence API",
        "version": "0.1.0",
        "status": "ok",
        "description": "UK electricity wind-generation forecast intelligence"
    }


@app.get("/health")
def get_health():
    return {"status": "healthy"}
