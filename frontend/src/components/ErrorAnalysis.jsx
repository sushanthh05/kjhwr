import React from 'react'
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
import { ArrowUpRight, ArrowDownRight, Compass } from 'lucide-react'
import { formatSignedMw } from '../utils/formatters'

/**
 * Custom Tooltip for Error Distribution Histogram
 */
function CustomHistogramTooltip({ active, payload }) {
  if (!active || !payload || payload.length === 0) return null

  const bin = payload[0]?.payload
  if (!bin) return null

  const isUnderforecast = bin.bin_end_mw <= 0

  return (
    <div className="chart-tooltip">
      <div className="tooltip-header">
        <span className="tooltip-title">Error Interval (MW)</span>
        <strong className="tooltip-time">
          [{formatSignedMw(bin.bin_start_mw, 0)} to {formatSignedMw(bin.bin_end_mw, 0)}]
        </strong>
      </div>
      <div className="tooltip-body">
        <div className="tooltip-row">
          <span className="tooltip-label">Observation Count:</span>
          <strong className="tooltip-val">{bin.count} hours</strong>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Share of Dataset:</span>
          <span className="tooltip-val">{bin.percentage}%</span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Direction:</span>
          <span className={`tooltip-val ${isUnderforecast ? 'text-blue' : 'text-amber'}`}>
            {isUnderforecast ? 'Underforecast (Actual > Forecast)' : 'Overforecast (Forecast > Actual)'}
          </span>
        </div>
      </div>
    </div>
  )
}

export default function ErrorAnalysis({
  errorData = null,
  mbeMw = null,
  isLoading = false,
}) {
  if (isLoading) {
    return <div className="kpi-skeleton" style={{ height: 280 }}></div>
  }

  if (!errorData) {
    return (
      <div className="empty-state-box">
        <p>Error distribution data is currently unavailable.</p>
      </div>
    )
  }

  const {
    total_observations = 0,
    positive_error_count = 0,
    negative_error_count = 0,
    quantiles_signed_mw = {},
    histogram_bins = [],
  } = errorData

  const posPct = total_observations > 0 ? ((positive_error_count / total_observations) * 100).toFixed(1) : 0
  const negPct = total_observations > 0 ? ((negative_error_count / total_observations) * 100).toFixed(1) : 0

  // Formatted bins for Recharts
  const chartBins = histogram_bins.map((b) => ({
    ...b,
    rangeLabel: `${b.bin_start_mw >= 0 ? '+' : ''}${Math.round(b.bin_start_mw)} to ${b.bin_end_mw >= 0 ? '+' : ''}${Math.round(b.bin_end_mw)}`,
    isOverforecast: b.bin_start_mw >= 0 || (b.bin_start_mw + b.bin_end_mw) / 2 > 0,
  }))

  return (
    <div className="error-analysis-container">
      {/* Top Banner: Signed Convention & Bias Notice */}
      <div className="error-convention-banner">
        <div className="convention-info">
          <Compass size={18} className="convention-icon" />
          <div>
            <div className="convention-title">
              Signed Error Convention: <code>error_mw = forecast_generation_mw - actual_generation_mw</code>
            </div>
            <p className="convention-desc">
              <strong>Positive (&gt; 0 MW)</strong> denotes overforecasting (National Grid anticipated more wind than materialized).
              {' '}<strong>Negative (&lt; 0 MW)</strong> denotes underforecasting (outturn wind exceeded expectations).
            </p>
          </div>
        </div>

        {mbeMw !== null && (
          <div className={`bias-status-badge ${mbeMw > 0 ? 'bias-overforecast' : mbeMw < 0 ? 'bias-underforecast' : ''}`}>
            {mbeMw > 0 ? <ArrowUpRight size={18} /> : <ArrowDownRight size={18} />}
            <div className="bias-status-text">
              <span className="bias-label">Systemic Portfolio Bias (MBE)</span>
              <strong>{formatSignedMw(mbeMw, 2)}</strong>
              <span className="bias-subtext">
                {mbeMw > 0 ? 'Net Overforecast Bias' : 'Net Underforecast Bias'}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Overforecast vs Underforecast Count Cards */}
      <div className="error-counter-grid">
        <div className="counter-card overforecast-card">
          <div className="counter-header">
            <span className="counter-title">Overforecast Intervals</span>
            <span className="badge-amber">{posPct}% of period</span>
          </div>
          <div className="counter-value-row">
            <span className="counter-number text-amber">{positive_error_count}</span>
            <span className="counter-total">/ {total_observations} hours</span>
          </div>
          <p className="counter-explanation">
            Forecast exceeded actuals. In a long position, excess procurement leads to spill/curtailment or cashout imbalance risk.
          </p>
        </div>

        <div className="counter-card underforecast-card">
          <div className="counter-header">
            <span className="counter-title">Underforecast Intervals</span>
            <span className="badge-blue">{negPct}% of period</span>
          </div>
          <div className="counter-value-row">
            <span className="counter-number text-blue">{negative_error_count}</span>
            <span className="counter-total">/ {total_observations} hours</span>
          </div>
          <p className="counter-explanation">
            Outturn exceeded forecast. Under-hedged day-ahead volume requires relying on within-day markets or selling surplus.
          </p>
        </div>

        <div className="counter-card quantiles-card">
          <div className="counter-header">
            <span className="counter-title">Signed Error Quantiles</span>
            <span className="badge-neutral">Distribution</span>
          </div>
          <div className="quantiles-mini-grid">
            <div className="quantile-cell">
              <span className="q-label">Min Error</span>
              <strong className="q-val text-blue">{formatSignedMw(quantiles_signed_mw.min, 0)}</strong>
            </div>
            <div className="quantile-cell">
              <span className="q-label">10th Pct</span>
              <strong className="q-val text-blue">{formatSignedMw(quantiles_signed_mw.p10, 0)}</strong>
            </div>
            <div className="quantile-cell">
              <span className="q-label">Median (p50)</span>
              <strong className="q-val text-amber">{formatSignedMw(quantiles_signed_mw.p50_median, 0)}</strong>
            </div>
            <div className="quantile-cell">
              <span className="q-label">90th Pct</span>
              <strong className="q-val text-amber">{formatSignedMw(quantiles_signed_mw.p90, 0)}</strong>
            </div>
            <div className="quantile-cell">
              <span className="q-label">Max Error</span>
              <strong className="q-val text-amber">{formatSignedMw(quantiles_signed_mw.max, 0)}</strong>
            </div>
          </div>
        </div>
      </div>

      {/* Histogram of Error Bins from Backend */}
      <div className="histogram-wrapper">
        <div className="histogram-header">
          <h3 className="chart-inner-title">Forecast Error Distribution (10 Partitions)</h3>
          <span className="histogram-note">Exact observation counts across 744 matched hours</span>
        </div>

        <div style={{ width: '100%', height: 260 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartBins}
              margin={{ top: 10, right: 20, left: 0, bottom: 35 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.07)" vertical={false} />
              <XAxis
                dataKey="rangeLabel"
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                angle={-25}
                textAnchor="end"
                interval={0}
                tickLine={{ stroke: 'rgba(255, 255, 255, 0.15)' }}
              />
              <YAxis
                unit=" hrs"
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                tickLine={{ stroke: 'rgba(255, 255, 255, 0.15)' }}
              />
              <Tooltip content={<CustomHistogramTooltip />} />
              <Bar dataKey="count" name="Interval Count" radius={[4, 4, 0, 0]}>
                {chartBins.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.isOverforecast ? '#f59e0b' : '#3b82f6'}
                    fillOpacity={0.85}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="histogram-legend">
          <div className="legend-item">
            <span className="legend-color-box bg-blue"></span>
            <span>Underforecast Intervals (Actual &gt; Forecast)</span>
          </div>
          <div className="legend-item">
            <span className="legend-color-box bg-amber"></span>
            <span>Overforecast Intervals (Forecast &gt; Actual)</span>
          </div>
        </div>
      </div>
    </div>
  )
}
