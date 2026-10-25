import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  TrendingUp,
  BarChart3,
  Calendar,
  AlertOctagon,
  Clock,
  Zap,
  Gauge,
  Activity,
} from 'lucide-react'

// API Service Layer
import {
  fetchHealth,
  fetchOverview,
  fetchTimeseries,
  fetchDaily,
  fetchErrors,
  fetchWorstMisses,
  fetchHourOfDay,
  fetchMetadata,
} from './services/api'

// Formatting Utilities
import {
  formatNumber,
  formatSignedMw,
  formatPct,
} from './utils/formatters'

// Modular Components
import Header from './components/Header'
import DecisionContext from './components/DecisionContext'
import KpiCard from './components/KpiCard'
import SectionCard from './components/SectionCard'
import ForecastActualChart from './components/ForecastActualChart'
import ErrorAnalysis from './components/ErrorAnalysis'
import DailyAccuracyChart from './components/DailyAccuracyChart'
import WorstMissesTable from './components/WorstMissesTable'
import HourOfDayChart from './components/HourOfDayChart'
import MethodologyPanel from './components/MethodologyPanel'
import LoadingState from './components/LoadingState'
import ErrorState from './components/ErrorState'

export default function App() {
  // Backend Connectivity
  const [connectionStatus, setConnectionStatus] = useState('idle') // 'idle' | 'checking' | 'connected' | 'error'
  const [isInitialLoading, setIsInitialLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [globalError, setGlobalError] = useState(null)

  // Date Filtering (Default: Full January 2026 Scope)
  const [startDate, setStartDate] = useState('2026-01-01')
  const [endDate, setEndDate] = useState('2026-01-31')

  // API Datasets
  const [overviewData, setOverviewData] = useState(null)
  const [isOverviewLoading, setIsOverviewLoading] = useState(false)

  const [timeseriesData, setTimeseriesData] = useState([])
  const [isTimeseriesLoading, setIsTimeseriesLoading] = useState(false)

  const [dailyData, setDailyData] = useState([])
  const [isDailyLoading, setIsDailyLoading] = useState(false)

  const [errorsData, setErrorsData] = useState(null)
  const [isErrorsLoading, setIsErrorsLoading] = useState(false)

  const [worstMissesData, setWorstMissesData] = useState([])
  const [isWorstMissesLoading, setIsWorstMissesLoading] = useState(false)

  const [hourOfDayData, setHourOfDayData] = useState(null)
  const [isHourOfDayLoading, setIsHourOfDayLoading] = useState(false)
  const [hourOfDayError, setHourOfDayError] = useState(null)

  const [metadataData, setMetadataData] = useState(null)

  // Stale request tracking
  const activeRequestIdRef = useRef(0)

  /**
   * Load date-filtered endpoints (Overview, Timeseries, Daily)
   */
  const loadFilteredData = useCallback(async (start, end) => {
    const requestId = ++activeRequestIdRef.current
    setIsOverviewLoading(true)
    setIsTimeseriesLoading(true)
    setIsDailyLoading(true)

    try {
      const [overviewRes, timeseriesRes, dailyRes] = await Promise.all([
        fetchOverview({ startDate: start, endDate: end }),
        fetchTimeseries({ startDate: start, endDate: end }),
        fetchDaily({ startDate: start, endDate: end }),
      ])

      // Ignore if a newer filter request was issued
      if (requestId !== activeRequestIdRef.current) return

      setOverviewData(overviewRes)
      setTimeseriesData(timeseriesRes?.data || [])
      setDailyData(dailyRes?.data || [])
    } catch (err) {
      if (requestId !== activeRequestIdRef.current) return
      console.error('Failed to load filtered analytics:', err)
      // We do not crash the app, but leave states visible
    } finally {
      if (requestId === activeRequestIdRef.current) {
        setIsOverviewLoading(false)
        setIsTimeseriesLoading(false)
        setIsDailyLoading(false)
      }
    }
  }, [])

  /**
   * Initial full dashboard bootstrap
   */
  const loadAllDashboardData = useCallback(async () => {
    setIsRefreshing(true)
    setConnectionStatus('checking')
    setGlobalError(null)
    setIsErrorsLoading(true)
    setIsWorstMissesLoading(true)

    try {
      // 1. Health check to confirm real API connectivity
      await fetchHealth()
      setConnectionStatus('connected')

      // 2. Fetch all modules concurrently
      const [
        overviewRes,
        timeseriesRes,
        dailyRes,
        errorsRes,
        worstRes,
        metaRes,
      ] = await Promise.all([
        fetchOverview({ startDate, endDate }),
        fetchTimeseries({ startDate, endDate }),
        fetchDaily({ startDate, endDate }),
        fetchErrors(),
        fetchWorstMisses({ limit: 10 }),
        fetchMetadata(),
      ])

      setOverviewData(overviewRes)
      setTimeseriesData(timeseriesRes?.data || [])
      setDailyData(dailyRes?.data || [])
      setErrorsData(errorsRes)
      setWorstMissesData(worstRes?.data || [])
      setMetadataData(metaRes)
      setGlobalError(null)

      // Fetch Hour of Day separately for local fault isolation
      try {
        setIsHourOfDayLoading(true)
        setHourOfDayError(null)
        const hodRes = await fetchHourOfDay()
        setHourOfDayData(hodRes)
      } catch (hodErr) {
        console.warn('Hour of Day endpoint error:', hodErr)
        setHourOfDayError(hodErr.message || 'Failed to load diurnal hourly profile.')
      } finally {
        setIsHourOfDayLoading(false)
      }
    } catch (err) {
      console.error('Initial dashboard load failed:', err)
      setConnectionStatus('error')
      setGlobalError(
        err.message || 'Unable to connect to the backend analytics service. Ensure FastAPI server is running on http://127.0.0.1:8000.'
      )
    } finally {
      setIsInitialLoading(false)
      setIsRefreshing(false)
      setIsErrorsLoading(false)
      setIsWorstMissesLoading(false)
    }
  }, [startDate, endDate])

  // Mount effect
  useEffect(() => {
    loadAllDashboardData()
  }, [loadAllDashboardData])

  // Handle Date Filter Changes
  const handleDateChange = (newStart, newEnd) => {
    setStartDate(newStart)
    setEndDate(newEnd)
    loadFilteredData(newStart, newEnd)
  }

  // Individual section retry for Hour of Day
  const handleRetryHourOfDay = async () => {
    setIsHourOfDayLoading(true)
    setHourOfDayError(null)
    try {
      const res = await fetchHourOfDay()
      setHourOfDayData(res)
    } catch (err) {
      setHourOfDayError(err.message || 'Failed to load diurnal hourly profile.')
    } finally {
      setIsHourOfDayLoading(false)
    }
  }

  const metrics = overviewData?.metrics || {}
  const coverage = overviewData?.coverage || {}
  const warnings = overviewData?.data_quality_warnings || []
  const scope = overviewData?.delivery_scope || {}

  const isFullMonth = startDate === '2026-01-01' && endDate === '2026-01-31'
  const filterActive = !isFullMonth

  return (
    <div className="app-wrapper">
      {/* 1. Header with Live Status Indicator */}
      <Header
        connectionStatus={connectionStatus}
        onRefreshAll={loadAllDashboardData}
        isRefreshing={isRefreshing}
      />

      <main className="dashboard-main">
        {/* Global Connection Error Banner */}
        {globalError && (
          <ErrorState
            title="Backend Service Connection Error"
            message={globalError}
            onRetry={loadAllDashboardData}
            height="200px"
          />
        )}

        {/* Initial Loading Screen */}
        {isInitialLoading && !globalError ? (
          <LoadingState
            message="Connecting to Elexon BMRS Analytics API and compiling January 2026 telemetry..."
            height="400px"
          />
        ) : (
          <>
            {/* 2. Decision Context Strip */}
            <DecisionContext
              scope={scope}
              coverage={coverage}
              warnings={warnings}
              filterActive={filterActive}
              filteredDateRange={{ start: startDate, end: endDate }}
            />

            {/* 3. Core KPI Cards */}
            <div className="kpi-grid" id="kpi-cards-section">
              {/* Card 1: MAE */}
              <KpiCard
                id="kpi-mae"
                title="Mean Absolute Error (MAE)"
                value={formatNumber(metrics.mae_mw, 1)}
                unit="MW"
                subtitle="Average magnitude of hourly forecast deviation regardless of direction."
                icon={Gauge}
                isLoading={isOverviewLoading}
                badgeText="Accuracy"
              />

              {/* Card 2: RMSE */}
              <KpiCard
                id="kpi-rmse"
                title="Root Mean Squared Error (RMSE)"
                value={formatNumber(metrics.rmse_mw, 1)}
                unit="MW"
                subtitle="Penalizes large outlier forecast errors more heavily than MAE."
                icon={Zap}
                isLoading={isOverviewLoading}
                badgeText="Volatility"
              />

              {/* Card 3: MBE (Signed Bias) */}
              <KpiCard
                id="kpi-mbe"
                title="Mean Bias Error (MBE)"
                value={formatSignedMw(metrics.mbe_mw, 1)}
                unit="MW"
                subtitle={
                  metrics.mbe_mw > 0
                    ? 'Positive bias: Forecast systematically over-projected actual outturn.'
                    : metrics.mbe_mw < 0
                    ? 'Negative bias: Forecast systematically under-projected actual outturn.'
                    : 'Unbiased expectation.'
                }
                variant="bias"
                biasSign={metrics.mbe_mw > 0 ? '+' : metrics.mbe_mw < 0 ? '-' : '0'}
                isLoading={isOverviewLoading}
                badgeText={metrics.mbe_mw > 0 ? 'Overforecast Bias' : metrics.mbe_mw < 0 ? 'Underforecast Bias' : 'Neutral'}
              />

              {/* Card 4: MAPE */}
              <KpiCard
                id="kpi-mape"
                title="Mean Abs. Percentage Error (MAPE)"
                value={formatPct(metrics.mape_pct, 2)}
                subtitle={`Relative forecast error across non-zero generation hours (${coverage.mape_included_count ?? 744} hrs).`}
                icon={TrendingUp}
                isLoading={isOverviewLoading}
                badgeText="Relative"
              />

              {/* Card 5: Mean Actual Generation */}
              <KpiCard
                id="kpi-actual"
                title="Mean Actual Generation"
                value={formatNumber(metrics.mean_actual_mw, 1)}
                unit="MW"
                subtitle="National GB metered wind output (Elexon FUELHH settlement avg)."
                variant="actual"
                isLoading={isOverviewLoading}
                badgeText="Outturn"
              />

              {/* Card 6: Mean Day-Ahead Forecast */}
              <KpiCard
                id="kpi-forecast"
                title="Mean Day-Ahead Forecast"
                value={formatNumber(metrics.mean_forecast_mw, 1)}
                unit="MW"
                subtitle="National Grid ESO projection published before 11:00 UTC D-1 cutoff."
                variant="forecast"
                isLoading={isOverviewLoading}
                badgeText="Day-Ahead"
              />
            </div>

            {/* 4. Main Time Series Chart */}
            <SectionCard
              id="timeseries-section"
              title="Day-Ahead Wind Forecast vs Metered Outturn Generation"
              subtitle="Hourly synchronized telemetry across January 2026 delivery intervals (MW)"
              icon={Activity}
              badge={`${timeseriesData.length} intervals`}
            >
              {isTimeseriesLoading && timeseriesData.length === 0 ? (
                <LoadingState message="Loading time series data..." height="420px" />
              ) : (
                <ForecastActualChart
                  data={timeseriesData}
                  startDate={startDate}
                  endDate={endDate}
                  onDateChange={handleDateChange}
                  isLoading={isTimeseriesLoading}
                />
              )}
            </SectionCard>

            {/* 5. Error Analysis Section */}
            <SectionCard
              id="error-analysis-section"
              title="Forecast Error Distribution & Directional Bias Analysis"
              subtitle="Signed error profile, quantile partitions, and overforecast vs underforecast exposure"
              icon={BarChart3}
              badge="Quantiles & Bins"
            >
              <ErrorAnalysis
                errorData={errorsData}
                mbeMw={metrics.mbe_mw}
                isLoading={isErrorsLoading}
              />
            </SectionCard>

            {/* Two-Column Mid-Tier Grid: Daily Accuracy & Diurnal Profile */}
            <div className="two-column-grid">
              {/* 6. Daily Accuracy Chart */}
              <SectionCard
                id="daily-accuracy-section"
                title="Daily Forecast Accuracy (MAE in MW)"
                subtitle="Day-by-day mean absolute error with best and worst accuracy highlights"
                icon={Calendar}
                badge="31 Delivery Days"
              >
                <DailyAccuracyChart
                  dailyData={dailyData}
                  isLoading={isDailyLoading}
                />
              </SectionCard>

              {/* 7. Hour of Day Accuracy Profile */}
              <SectionCard
                id="hour-of-day-section"
                title="Diurnal Accuracy Profile (Hour of Day)"
                subtitle="Mean Absolute Error by UK local delivery hour in Europe/London"
                icon={Clock}
                badge="00:00 to 23:00 GMT"
              >
                <HourOfDayChart
                  hourData={hourOfDayData}
                  isLoading={isHourOfDayLoading}
                  error={hourOfDayError}
                  onRetry={handleRetryHourOfDay}
                />
              </SectionCard>
            </div>

            {/* 8. Worst Forecast Misses Table */}
            <SectionCard
              id="worst-misses-section"
              title="Top 10 Worst Forecast Misses"
              subtitle="Ranked by absolute forecast deviation with publication timestamps and operational risk context"
              icon={AlertOctagon}
              badge="Peak Discrepancies"
            >
              <WorstMissesTable
                worstMisses={worstMissesData}
                isLoading={isWorstMissesLoading}
              />
            </SectionCard>

            {/* 9. Methodology and Lineage Specification */}
            <MethodologyPanel
              metadata={metadataData}
              coverage={coverage}
              warnings={warnings}
              isLoading={isOverviewLoading && !overviewData}
            />
          </>
        )}
      </main>

      {/* 10. Footer */}
      <footer className="portal-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <strong>Wind Forecast Intelligence</strong> &middot; UK National Electricity Market Day-Ahead Forecast Analytics
          </div>
          <div className="footer-notes">
            <span>Data Source: Elexon BMRS (FUELHH &amp; WINDFOR)</span>
            <span>Target Market: GB Balancing Mechanism &amp; Power Auctions</span>
            <span>Evaluation Period: January 2026 (744 matched hours)</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
