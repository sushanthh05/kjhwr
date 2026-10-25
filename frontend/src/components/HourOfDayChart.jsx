import React from 'react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import { Clock } from 'lucide-react'
import { formatNumber, formatSignedMw } from '../utils/formatters'
import ErrorState from './ErrorState'

/**
 * Custom Tooltip for Hour of Day Profile
 */
function CustomHourTooltip({ active, payload }) {
  if (!active || !payload || payload.length === 0) return null

  const item = payload[0]?.payload
  if (!item) return null

  const hourStr = String(item.hour_of_day_local).padStart(2, '0')

  return (
    <div className="chart-tooltip">
      <div className="tooltip-header">
        <span className="tooltip-title">UK Local Hour (Europe/London)</span>
        <strong className="tooltip-time">{hourStr}:00 &ndash; {hourStr}:59</strong>
      </div>

      <div className="tooltip-body">
        <div className="tooltip-row">
          <span className="tooltip-label">Mean Absolute Error (MAE):</span>
          <strong className="tooltip-val text-cyan">{formatNumber(item.mae_mw, 1)} MW</strong>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Root Mean Sq. Error (RMSE):</span>
          <span className="tooltip-val">{formatNumber(item.rmse_mw, 1)} MW</span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Mean Bias Error (MBE):</span>
          <span className={`tooltip-val ${item.mbe_mw > 0 ? 'text-amber' : item.mbe_mw < 0 ? 'text-blue' : ''}`}>
            {formatSignedMw(item.mbe_mw, 1)}
          </span>
        </div>
        {item.mape_pct !== null && (
          <div className="tooltip-row">
            <span className="tooltip-label">MAPE:</span>
            <span className="tooltip-val">{formatNumber(item.mape_pct, 2)}%</span>
          </div>
        )}
        <div className="tooltip-divider"></div>
        <div className="tooltip-row">
          <span className="tooltip-label">Mean Actual Generation:</span>
          <span className="tooltip-val text-emerald">{formatNumber(item.mean_actual_mw, 1)} MW</span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Mean Forecast:</span>
          <span className="tooltip-val text-blue">{formatNumber(item.mean_forecast_mw, 1)} MW</span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Sample Observations:</span>
          <span className="tooltip-val">{item.observation_count} hours ({item.timezone})</span>
        </div>
      </div>
    </div>
  )
}

export default function HourOfDayChart({
  hourData = null,
  isLoading = false,
  error = null,
  onRetry,
}) {
  if (isLoading) {
    return <div className="kpi-skeleton" style={{ height: 280 }}></div>
  }

  if (error) {
    return (
      <ErrorState
        title="Hour of Day Analytics Unavailable"
        message={error}
        onRetry={onRetry}
        height="220px"
      />
    )
  }

  const items = hourData?.data || []
  const timezone = hourData?.timezone || 'Europe/London'

  if (items.length === 0) {
    return (
      <div className="empty-state-box">
        <p>No diurnal hourly data available.</p>
      </div>
    )
  }

  const chartData = items.map((h) => ({
    ...h,
    label: `${String(h.hour_of_day_local).padStart(2, '0')}:00`,
  }))

  return (
    <div className="hour-chart-wrapper">
      <div className="chart-top-note">
        <Clock size={13} />
        <span>Diurnal forecast error profile grouped by UK local hour ({timezone}) across all January days</span>
      </div>

      <div style={{ width: '100%', height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 15, right: 15, left: 10, bottom: 20 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.07)" vertical={false} />
            <XAxis
              dataKey="label"
              stroke="var(--text-muted)"
              tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
              tickLine={{ stroke: 'rgba(255, 255, 255, 0.15)' }}
            />
            <YAxis
              unit=" MW"
              stroke="var(--text-muted)"
              tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
              tickFormatter={(val) => (val >= 1000 ? `${(val / 1000).toFixed(0)}k` : val)}
              tickLine={{ stroke: 'rgba(255, 255, 255, 0.15)' }}
            />
            <Tooltip content={<CustomHourTooltip />} />
            <Bar
              dataKey="mae_mw"
              name="Mean Absolute Error (MAE)"
              fill="var(--accent-blue)"
              fillOpacity={0.8}
              radius={[3, 3, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
