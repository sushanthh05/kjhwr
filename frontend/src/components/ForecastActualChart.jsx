import React, { useMemo } from 'react'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import { Calendar, RotateCcw } from 'lucide-react'
import { formatNumber, formatTimestamp, formatAxisDate, formatAxisTime, formatSignedMw } from '../utils/formatters'

/**
 * Custom chart tooltip showing full operational telemetry
 */
function CustomTimeSeriesTooltip({ active, payload }) {
  if (!active || !payload || payload.length === 0) return null

  const item = payload[0]?.payload
  if (!item) return null

  const isOverforecast = item.error_mw > 0
  const isUnderforecast = item.error_mw < 0

  return (
    <div className="chart-tooltip">
      <div className="tooltip-header">
        <span className="tooltip-title">Delivery Interval (UTC)</span>
        <strong className="tooltip-time">{formatTimestamp(item.delivery_time_utc, true)}</strong>
      </div>

      <div className="tooltip-body">
        <div className="tooltip-row">
          <span className="tooltip-label">
            <span className="color-dot actual-dot"></span>
            Actual Generation:
          </span>
          <span className="tooltip-val actual-val">{formatNumber(item.actual_generation_mw, 1)} MW</span>
        </div>

        <div className="tooltip-row">
          <span className="tooltip-label">
            <span className="color-dot forecast-dot"></span>
            Day-Ahead Forecast:
          </span>
          <span className="tooltip-val forecast-val">{formatNumber(item.forecast_generation_mw, 1)} MW</span>
        </div>

        <div className="tooltip-divider"></div>

        <div className="tooltip-row">
          <span className="tooltip-label">Signed Error (F - A):</span>
          <span className={`tooltip-val error-val ${isOverforecast ? 'text-amber' : isUnderforecast ? 'text-blue' : ''}`}>
            {formatSignedMw(item.error_mw, 1)}
            <span className="error-tag">{isOverforecast ? 'Overforecast' : isUnderforecast ? 'Underforecast' : 'Exact'}</span>
          </span>
        </div>

        <div className="tooltip-row">
          <span className="tooltip-label">Absolute Error:</span>
          <span className="tooltip-val">{formatNumber(item.absolute_error_mw, 1)} MW</span>
        </div>

        {item.absolute_percentage_error !== null && (
          <div className="tooltip-row">
            <span className="tooltip-label">Absolute Error (%):</span>
            <span className="tooltip-val">{formatNumber(item.absolute_percentage_error, 2)}%</span>
          </div>
        )}

        <div className="tooltip-meta">
          <div className="tooltip-meta-line">
            <span>Forecast Published:</span>
            <span>{formatTimestamp(item.forecast_publish_time_utc)}</span>
          </div>
          <div className="tooltip-meta-line">
            <span>Decision Cutoff:</span>
            <span>{formatTimestamp(item.decision_cutoff_utc)}</span>
          </div>
          {item.forecast_age_hours !== undefined && (
            <div className="tooltip-meta-line">
              <span>Forecast Lead Time:</span>
              <span>{item.forecast_age_hours} hrs ahead of cutoff</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function ForecastActualChart({
  data = [],
  startDate = '2026-01-01',
  endDate = '2026-01-31',
  onDateChange,
}) {
  // Pre-calculate downsampled tick timestamps to avoid axis congestion
  const xTicks = useMemo(() => {
    if (!data || data.length === 0) return []

    // If more than 14 days, show every 2 or 3 days at 00:00
    if (data.length > 336) {
      return data
        .filter((d) => {
          const hour = d.delivery_time_utc?.slice(11, 13)
          const day = parseInt(d.delivery_time_utc?.slice(8, 10), 10)
          return hour === '00' && (day % 3 === 1 || day === 31)
        })
        .map((d) => d.delivery_time_utc)
    }

    // If 4-14 days, show every day at 00:00
    if (data.length > 72) {
      return data
        .filter((d) => d.delivery_time_utc?.slice(11, 13) === '00')
        .map((d) => d.delivery_time_utc)
    }

    // If 1-3 days, show every 6 hours
    return data
      .filter((d) => {
        const hour = parseInt(d.delivery_time_utc?.slice(11, 13), 10)
        return hour % 6 === 0
      })
      .map((d) => d.delivery_time_utc)
  }, [data])

  const handlePreset = (start, end) => {
    if (onDateChange) {
      onDateChange(start, end)
    }
  }

  const handleStartInput = (e) => {
    const val = e.target.value
    if (onDateChange && val) {
      onDateChange(val, endDate)
    }
  }

  const handleEndInput = (e) => {
    const val = e.target.value
    if (onDateChange && val) {
      onDateChange(startDate, val)
    }
  }

  const handleReset = () => {
    if (onDateChange) {
      onDateChange('2026-01-01', '2026-01-31')
    }
  }

  const isFullMonth = startDate === '2026-01-01' && endDate === '2026-01-31'

  return (
    <div className="timeseries-chart-wrapper">
      {/* Date Filter & Preset Controls */}
      <div className="chart-controls-bar">
        <div className="filter-group">
          <div className="filter-label-group">
            <Calendar size={14} style={{ color: 'var(--accent-blue)' }} />
            <span>Delivery Date Range (Jan 2026):</span>
          </div>

          <div className="date-input-group">
            <input
              type="date"
              id="start-date-input"
              className="date-input"
              value={startDate}
              min="2026-01-01"
              max="2026-01-31"
              onChange={handleStartInput}
              aria-label="Filter Start Date"
            />
            <span className="date-separator">to</span>
            <input
              type="date"
              id="end-date-input"
              className="date-input"
              value={endDate}
              min="2026-01-01"
              max="2026-01-31"
              onChange={handleEndInput}
              aria-label="Filter End Date"
            />
          </div>
        </div>

        <div className="preset-buttons-group">
          <button
            type="button"
            className={`btn-chip ${isFullMonth ? 'active' : ''}`}
            onClick={() => handlePreset('2026-01-01', '2026-01-31')}
          >
            Full Month
          </button>
          <button
            type="button"
            className={`btn-chip ${startDate === '2026-01-01' && endDate === '2026-01-07' ? 'active' : ''}`}
            onClick={() => handlePreset('2026-01-01', '2026-01-07')}
          >
            Wk 1 (1–7)
          </button>
          <button
            type="button"
            className={`btn-chip ${startDate === '2026-01-08' && endDate === '2026-01-14' ? 'active' : ''}`}
            onClick={() => handlePreset('2026-01-08', '2026-01-14')}
          >
            Wk 2 (8–14)
          </button>
          <button
            type="button"
            className={`btn-chip ${startDate === '2026-01-15' && endDate === '2026-01-21' ? 'active' : ''}`}
            onClick={() => handlePreset('2026-01-15', '2026-01-21')}
          >
            Wk 3 (15–21)
          </button>
          <button
            type="button"
            className={`btn-chip ${startDate === '2026-01-22' && endDate === '2026-01-28' ? 'active' : ''}`}
            onClick={() => handlePreset('2026-01-22', '2026-01-28')}
          >
            Wk 4 (22–28)
          </button>
          <button
            type="button"
            className={`btn-chip ${startDate === '2026-01-29' && endDate === '2026-01-31' ? 'active' : ''}`}
            onClick={() => handlePreset('2026-01-29', '2026-01-31')}
          >
            29–31 Jan
          </button>

          {!isFullMonth && (
            <button
              type="button"
              className="btn-chip reset"
              onClick={handleReset}
              title="Reset to full month"
            >
              <RotateCcw size={12} />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      {/* Chart Canvas */}
      {data && data.length > 0 ? (
        <div className="chart-canvas-container" style={{ width: '100%', height: 420 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={data}
              margin={{ top: 15, right: 25, left: 15, bottom: 25 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255, 255, 255, 0.07)"
                vertical={false}
              />
              <XAxis
                dataKey="delivery_time_utc"
                ticks={xTicks.length > 0 ? xTicks : undefined}
                tickFormatter={(val) => {
                  if (data.length <= 48) {
                    return `${formatAxisDate(val)} ${formatAxisTime(val)}`
                  }
                  return formatAxisDate(val)
                }}
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                tickLine={{ stroke: 'rgba(255, 255, 255, 0.15)' }}
                axisLine={{ stroke: 'rgba(255, 255, 255, 0.15)' }}
              />
              <YAxis
                unit=" MW"
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                tickFormatter={(val) => (val >= 1000 ? `${(val / 1000).toFixed(0)}k` : val)}
                tickLine={{ stroke: 'rgba(255, 255, 255, 0.15)' }}
                axisLine={{ stroke: 'rgba(255, 255, 255, 0.15)' }}
                domain={[0, 'auto']}
              />
              <Tooltip content={<CustomTimeSeriesTooltip />} />
              <Legend
                verticalAlign="top"
                align="right"
                wrapperStyle={{ paddingBottom: 15, fontSize: 12 }}
                iconType="circle"
                formatter={(value) => {
                  if (value === 'actual_generation_mw') return 'Actual Outturn Generation (Elexon FUELHH)'
                  if (value === 'forecast_generation_mw') return 'Day-Ahead Wind Forecast (Elexon WINDFOR)'
                  return value
                }}
              />
              <Line
                type="monotone"
                dataKey="actual_generation_mw"
                name="actual_generation_mw"
                stroke="var(--accent-emerald)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 5, fill: 'var(--accent-emerald)', stroke: '#ffffff', strokeWidth: 1.5 }}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="forecast_generation_mw"
                name="forecast_generation_mw"
                stroke="var(--accent-blue)"
                strokeWidth={2}
                strokeDasharray={undefined}
                dot={false}
                activeDot={{ r: 5, fill: 'var(--accent-blue)', stroke: '#ffffff', strokeWidth: 1.5 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="empty-chart-state">
          <p>No delivery intervals found for selected date window ({startDate} to {endDate}).</p>
          <button type="button" className="btn-secondary btn-sm" onClick={handleReset}>
            Reset to Full January Scope
          </button>
        </div>
      )}
    </div>
  )
}
