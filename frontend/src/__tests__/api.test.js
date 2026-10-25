import {
  API_BASE_URL,
  getApiBaseUrl,
  ApiError,
  fetchHealth,
  fetchOverview,
  fetchTimeseries,
  fetchDaily,
  fetchErrors,
  fetchWorstMisses,
  fetchHourOfDay,
  fetchMetadata,
} from '../services/api'

describe('API Service Layer', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  describe('getApiBaseUrl resolution', () => {
    it('returns empty string for same-origin production when VITE_API_BASE_URL is empty', () => {
      expect(getApiBaseUrl({ VITE_API_BASE_URL: '' })).toBe('')
      expect(getApiBaseUrl({ VITE_API_BASE_URL: '   ' })).toBe('')
    })

    it('returns trimmed URL without trailing slash when configured', () => {
      expect(getApiBaseUrl({ VITE_API_BASE_URL: 'http://127.0.0.1:8000/' })).toBe('http://127.0.0.1:8000')
      expect(getApiBaseUrl({ VITE_BACKEND_URL: 'http://backend:8000/' })).toBe('http://backend:8000')
    })

    it('defaults to empty string in production mode without explicit env setting', () => {
      expect(getApiBaseUrl({ PROD: true })).toBe('')
    })

    it('defaults to http://127.0.0.1:8000 in dev mode or default environment', () => {
      expect(getApiBaseUrl({ DEV: true })).toBe('http://127.0.0.1:8000')
      expect(getApiBaseUrl({})).toBe('http://127.0.0.1:8000')
    })
  })

  it('uses configured or default base URL', () => {
    expect(typeof API_BASE_URL).toBe('string')
  })

  it('fetchHealth queries /health and returns parsed JSON', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => ({ status: 'healthy' }),
    })

    const res = await fetchHealth()
    expect(global.fetch).toHaveBeenCalledWith(
      `${API_BASE_URL}/health`,
      expect.objectContaining({ method: 'GET' })
    )
    expect(res).toEqual({ status: 'healthy' })
  })

  it('fetchOverview correctly encodes start_date and end_date query parameters', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => ({
        metrics: { mae_mw: 2122.81, rmse_mw: 2616.69 },
      }),
    })

    await fetchOverview({ startDate: '2026-01-05', endDate: '2026-01-10' })
    expect(global.fetch).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/analytics/overview?start_date=2026-01-05&end_date=2026-01-10`,
      expect.anything()
    )
  })

  it('fetchTimeseries passes date filters', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => ({ count: 24, data: [] }),
    })

    const res = await fetchTimeseries({ startDate: '2026-01-01', endDate: '2026-01-01' })
    expect(global.fetch).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/analytics/timeseries?start_date=2026-01-01&end_date=2026-01-01`,
      expect.anything()
    )
    expect(res.count).toBe(24)
  })

  it('fetchWorstMisses properly sets limit parameter', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => ({ limit: 5, data: [] }),
    })

    await fetchWorstMisses({ limit: 5 })
    expect(global.fetch).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/analytics/worst-misses?limit=5`,
      expect.anything()
    )
  })

  it('fetchErrors calls /api/analytics/errors endpoint', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => ({ total_observations: 744, histogram_bins: [] }),
    })

    const res = await fetchErrors()
    expect(global.fetch).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/analytics/errors`,
      expect.anything()
    )
    expect(res.total_observations).toBe(744)
  })

  it('fetchHourOfDay calls /api/analytics/hour-of-day endpoint', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => ({ timezone: 'Europe/London', data: [] }),
    })

    const res = await fetchHourOfDay()
    expect(global.fetch).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/analytics/hour-of-day`,
      expect.anything()
    )
    expect(res.timezone).toBe('Europe/London')
  })

  it('throws ApiError with status and message when server returns HTTP 400', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: "start_date '2026-01-10' cannot be after end_date '2026-01-05'." }),
    })

    await expect(
      fetchOverview({ startDate: '2026-01-10', endDate: '2026-01-05' })
    ).rejects.toThrow(ApiError)

    try {
      await fetchOverview({ startDate: '2026-01-10', endDate: '2026-01-05' })
    } catch (err) {
      expect(err.status).toBe(400)
      expect(err.message).toContain('start_date')
    }
  })

  it('handles network connection failures gracefully', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'))

    await expect(fetchMetadata()).rejects.toThrow(ApiError)
    try {
      await fetchMetadata()
    } catch (err) {
      expect(err.status).toBe(0)
      expect(err.message).toContain('Network connection failed')
    }
  })

  it('handles invalid JSON responses', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => {
        throw new Error('Unexpected token < in JSON at position 0')
      },
    })

    await expect(fetchDaily()).rejects.toThrow(ApiError)
  })

  it('passes AbortSignal to fetch and propagates AbortError', async () => {
    const controller = new AbortController()
    global.fetch = vi.fn().mockImplementation((_, opts) => {
      if (opts?.signal?.aborted) {
        const err = new Error('The operation was aborted')
        err.name = 'AbortError'
        return Promise.reject(err)
      }
      return Promise.resolve({
        ok: true,
        headers: { get: () => 'application/json' },
        json: async () => ({}),
      })
    })

    controller.abort()
    await expect(fetchOverview({ signal: controller.signal })).rejects.toThrow('aborted')
  })

  it('ensures no hardcoded metrics are returned on failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'Canonical evaluation dataset not found' }),
    })

    // The API layer must reject, NEVER return fake 2,122.81 MW fallback values
    await expect(fetchOverview()).rejects.toThrow(ApiError)
  })
})
