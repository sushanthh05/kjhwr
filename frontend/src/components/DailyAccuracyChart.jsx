import React, { useMemo } from 'react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from 'recharts'
import { Award, AlertTriangle } from 'lucide-react'
import { formatNumber, formatSignedMw, formatDate } from '../utils/formatters'

/**
 * Custom Tooltip for Daily Accuracy Chart
 */
function CustomDailyTooltip({ active, payload }) {
  if (!active || !payload || payload.length === 0) return null

  const item = payload[0]?.payload
  if (!item) return null

  return (
    <div className="chart-tooltip">
      <div className="tooltip-header">
        <span className="tooltip-title">Delivery Date</span>
        <strong className="tooltip-time">{formatDate(item.delivery_date)}</strong>
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
            <span className="tooltip-label">MAPE (%):</span>
            <span className="tooltip-val">{formatNumber(item.mape_pct, 2)}%</span>
          </div>
        )}
        <div className="tooltip-divider"></div>
        <div className="tooltip-row">
          <span className="tooltip-label">Mean Actual Generation:</span>
          <span className="tooltip-val">{formatNumber(item.mean_actual_mw, 1)} MW</span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Mean Day-Ahead Forecast:</span>
          <span className="tooltip-val">{formatNumber(item.mean_forecast_mw, 1)} MW</span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Matched Intervals:</span>
          <span className="tooltip-val">{item.matched_interval_count} / {item.expected_interval_count} hrs</span>
        </div>
      </div>
    </div>
  )
}

export default function DailyAccuracyChart({
  dailyData = [],
  isLoading = false,
}) {
  // Identify the best (lowest MAE) and worst (highest MAE) days from real API data
  const { bestDay, worstDay } = useMemo(() => {
    if (!dailyData || dailyData.length === 0) return { bestDay: null, worstDay: null }

    let best = dailyData[0]
    let worst = dailyData[0]

    for (const d of dailyData) {
      if (d.mae_mw !== null && (best.mae_mw === null || d.mae_mw < best.mae_mw)) {
        best = d
      }
      if (d.mae_mw !== null && (worst.mae_mw === null || d.mae_mw > worst.mae_mw)) {
        worst = d
      }
    }
    return { bestDay: best, worstDay: worst }
  }, [dailyData])

  if (isLoading) {
    return <div className="kpi-skeleton" style={{ height: 320 }}></div>
  }

  if (!dailyData || dailyData.length === 0) {
    return (
      <div className="empty-state-box">
        <p>No daily accuracy records returned for the current period.</p>
      </div>
    )
  }

  return (
    <div className="daily-chart-wrapper">
      {/* Best & Worst Day Identifiers */}
      <div className="daily-stats-row">
        {bestDay && (
          <div className="daily-badge-card best-day">
            <div className="badge-icon green">
              <Award size={16} />
            </div>
            <div>
              <span className="badge-label">Best Day-Ahead Accuracy</span>
              <div className="badge-value-line">
                <strong>{formatDate(bestDay.delivery_date)}</strong>
                <span className="badge-metric text-emerald">MAE: {formatNumber(bestDay.mae_mw, 1)} MW</span>
              </div>
            </div>
          </div>
        )}

        {worstDay && (
          <div className="daily-badge-card worst-day">
            <div className="badge-icon amber">
              <AlertTriangle size={16} />
            </div>
            <div>
              <span className="badge-label">Highest Error Day</span>
              <div className="badge-value-line">
                <strong>{formatDate(worstDay.delivery_date)}</strong>
                <span className="badge-metric text-amber">MAE: {formatNumber(worstDay.mae_mw, 1)} MW</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Recharts Daily Bar Chart */}
      <div style={{ width: '100%', height: 320 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={dailyData}
            margin={{ top: 15, right: 15, left: 10, bottom: 25 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.07)" vertical={false} />
            <XAxis
              dataKey="delivery_date"
              tickFormatter={(d) => d.slice(8, 10)}
              stroke="var(--text-muted)"
              tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
              tickLine={{ stroke: 'rgba(255, 255, 255, 0.15)' }}
            />
            <YAxis
              unit=" MW"
              stroke="var(--text-muted)"
              tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
              tickFormatter={(val) => (val >= 1000 ? `${(val / 1000).toFixed(0)}k` : val)}
              tickLine={{ stroke: 'rgba(255, 255, 255, 0.15)' }}
            />
            <Tooltip content={<CustomDailyTooltip />} />
            <Bar dataKey="mae_mw" name="Daily MAE" radius={[4, 4, 0, 0]}>
              {dailyData.map((entry, index) => {
                const isBest = bestDay && entry.delivery_date === bestDay.delivery_date
                const isWorst = worstDay && entry.delivery_date === worstDay.delivery_date
                const barColor = isBest
                  ? 'var(--accent-emerald)'
                  : isWorst
                  ? 'var(--accent-amber)'
                  : 'var(--accent-cyan)'

                return <Cell key={`daily-cell-${index}`} fill={barColor} fillOpacity={0.85} />
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="daily-chart-footer">
        <span className="footer-legend-item">
          <span className="color-box bg-emerald"></span> Best Day ({bestDay ? formatDate(bestDay.delivery_date) : ''})
        </span>
        <span className="footer-legend-item">
          <span className="color-box bg-amber"></span> Worst Day ({worstDay ? formatDate(worstDay.delivery_date) : ''})
        </span>
        <span className="footer-legend-item">
          <span className="color-box bg-cyan"></span> Daily Average Error (MW)
        </span>
      </div>
    </div>
  )
}
