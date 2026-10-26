/**
 * api.js
 * API service layer for Wind Forecast Intelligence.
 * Communicates with FastAPI backend endpoints under /api/analytics/*.
 */

/**
 * Resolves API Base URL from Vite environment variables or defaults:
 * - If VITE_API_BASE_URL is set (including "" for same-origin production), use it.
 * - If VITE_BACKEND_URL is set, use it.
 * - In production builds without explicit override, default to same-origin relative URLs ("").
 * - In local development mode, default to http://127.0.0.1:8000.
 */
export function getApiBaseUrl(env = (typeof import.meta !== 'undefined' ? import.meta.env : {})) {
  if (env && env.VITE_API_BASE_URL !== undefined) {
    return String(env.VITE_API_BASE_URL).trim().replace(/\/+$/, '')
  }
  if (env && env.VITE_BACKEND_URL !== undefined) {
    return String(env.VITE_BACKEND_URL).trim().replace(/\/+$/, '')
  }
  if (env && env.PROD) {
    return ''
  }
  return 'http://127.0.0.1:8000'
}

export const API_BASE_URL = getApiBaseUrl()

/**
 * Custom API Error class with HTTP status code and parsed details
 */
export class ApiError extends Error {
  constructor(message, status, details = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

/**
 * Internal generic fetch helper with error handling and AbortSignal support
 */
async function request(endpoint, options = {}) {
  const { params, signal, ...customConfig } = options
  let url = `${API_BASE_URL}${endpoint}`

  if (params && Object.keys(params).length > 0) {
    const searchParams = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, String(value))
      }
    }
    const queryString = searchParams.toString()
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString
    }
  }

  const defaultHeaders = {
    'Accept': 'application/json',
  }

  const config = {
    method: 'GET',
    headers: { ...defaultHeaders, ...customConfig.headers },
    signal,
    ...customConfig,
  }

  let response
  try {
    response = await fetch(url, config)
  } catch (err) {
    if (err.name === 'AbortError') {
      throw err
    }
    throw new ApiError(
      `Network connection failed: ${err.message || 'Unable to reach backend service'}. Ensure backend is running at ${API_BASE_URL || 'the server origin'}.`,
      0,
      err
    )
  }

  let data
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    try {
      data = await response.json()
    } catch (parseErr) {
      throw new ApiError(
        `Failed to parse server JSON response: ${parseErr.message}`,
        response.status
      )
    }
  } else {
    data = await response.text()
  }

  if (!response.ok) {
    // Auto-retry on Render Free Tier cold start errors (502 / 504) for up to ~40 seconds
    const retryCount = options._retryCount || 0
    if ((response.status === 502 || response.status === 504) && retryCount < 10 && !signal?.aborted) {
      await new Promise(resolve => setTimeout(resolve, 3500))
      return request(endpoint, { ...options, _retryCount: retryCount + 1 })
    }

    let errorMessage
    if (data && typeof data === 'object' && (data.detail || data.message)) {
      errorMessage = data.detail || data.message
    } else if (typeof data === 'string' && data.length > 0 && !data.includes('<!DOCTYPE') && !data.includes('<html')) {
      errorMessage = data
    } else if (response.status === 502 || response.status === 504) {
      errorMessage = 'Backend service is warming up from inactivity (Render Free Tier cold start). Retrying automatically...'
    } else {
      errorMessage = `HTTP ${response.status}: ${response.statusText || 'Server Error'}`
    }
    throw new ApiError(errorMessage, response.status, data)
  }


  return data
}

/**
 * Check backend service health
 */
export async function fetchHealth(signal) {
  return request('/health', { signal })
}

/**
 * Fetch root metadata
 */
export async function fetchRoot(signal) {
  return request('/', { signal })
}

/**
 * Fetch overall metrics (MAE, RMSE, MBE, MAPE, mean power, coverage, sign counts)
 * Supports optional date range filtering (start_date, end_date)
 */
export async function fetchOverview(options = {}) {
  const { startDate, endDate, signal } = options
  return request('/api/analytics/overview', {
    params: {
      start_date: startDate,
      end_date: endDate,
    },
    signal,
  })
}

/**
 * Fetch hourly timeseries of forecasts versus actuals
 */
export async function fetchTimeseries(options = {}) {
  const { startDate, endDate, signal } = options
  return request('/api/analytics/timeseries', {
    params: {
      start_date: startDate,
      end_date: endDate,
    },
    signal,
  })
}

/**
 * Fetch daily accuracy aggregates
 */
export async function fetchDaily(options = {}) {
  const { startDate, endDate, signal } = options
  return request('/api/analytics/daily', {
    params: {
      start_date: startDate,
      end_date: endDate,
    },
    signal,
  })
}

/**
 * Fetch forecast error distribution, quantiles, and histogram bins
 */
export async function fetchErrors(options = {}) {
  const { signal } = options
  return request('/api/analytics/errors', { signal })
}

/**
 * Fetch worst forecast misses sorted by absolute error descending
 */
export async function fetchWorstMisses(options = {}) {
  const { limit = 10, signal } = options
  return request('/api/analytics/worst-misses', {
    params: { limit },
    signal,
  })
}

/**
 * Fetch hour-of-day accuracy profile in Europe/London timezone
 */
export async function fetchHourOfDay(options = {}) {
  const { signal } = options
  return request('/api/analytics/hour-of-day', { signal })
}

/**
 * Fetch analytical methodology, dataset lineage, assumptions, and quality audit
 */
export async function fetchMetadata(options = {}) {
  const { signal } = options
  return request('/api/analytics/metadata', { signal })
}
