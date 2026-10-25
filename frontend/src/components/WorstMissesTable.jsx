import React from 'react'
import { TrendingUp, TrendingDown, Info } from 'lucide-react'
import { formatNumber, formatSignedMw, formatTimestamp } from '../utils/formatters'

export default function WorstMissesTable({
  worstMisses = [],
  isLoading = false,
}) {
  if (isLoading) {
    return <div className="kpi-skeleton" style={{ height: 350 }}></div>
  }

  if (!worstMisses || worstMisses.length === 0) {
    return (
      <div className="empty-state-box">
        <p>No forecast misses recorded.</p>
      </div>
    )
  }

  return (
    <div className="worst-misses-container">
      {/* Operational Relevance Context */}
      <div className="operational-impact-box">
        <Info size={16} className="impact-icon" />
        <div className="impact-text">
          <strong>Trading &amp; Procurement Operational Significance:</strong>
          <p>
            Large day-ahead forecast errors require utility desks to reconcile unhedged generation volume in within-day (intraday) auctions or absorb Balancing Mechanism cashout exposure (system buy/sell prices).
            Overforecasts leave short positions in market delivery, while underforecasts leave uncommitted energy.
            <em> Note: Forecast error represents volume discrepancy in MW, not direct financial loss.</em>
          </p>
        </div>
      </div>

      {/* Table */}
      <div className="table-responsive">
        <table className="intelligence-table">
          <thead>
            <tr>
              <th scope="col" className="col-rank">Rank</th>
              <th scope="col">Delivery Interval (UTC)</th>
              <th scope="col" className="text-right">Forecast (MW)</th>
              <th scope="col" className="text-right">Actual (MW)</th>
              <th scope="col" className="text-right">Signed Error</th>
              <th scope="col" className="text-right">Abs. Error</th>
              <th scope="col">Forecast Published</th>
              <th scope="col">Decision Cutoff</th>
            </tr>
          </thead>
          <tbody>
            {worstMisses.map((row) => {
              const isOver = row.error_mw > 0
              const isUnder = row.error_mw < 0

              return (
                <tr
                  key={row.rank}
                  className={`miss-row ${isOver ? 'row-overforecast' : isUnder ? 'row-underforecast' : ''}`}
                >
                  <td className="col-rank">
                    <span className="rank-badge">#{row.rank}</span>
                  </td>
                  <td className="delivery-time-cell">
                    <strong>{formatTimestamp(row.delivery_time_utc, true)}</strong>
                  </td>
                  <td className="text-right text-mono text-blue">
                    {formatNumber(row.forecast_generation_mw, 1)}
                  </td>
                  <td className="text-right text-mono text-emerald">
                    {formatNumber(row.actual_generation_mw, 1)}
                  </td>
                  <td className="text-right text-mono">
                    <span className={`direction-badge ${isOver ? 'badge-amber' : isUnder ? 'badge-blue' : ''}`}>
                      {isOver ? <TrendingUp size={12} /> : isUnder ? <TrendingDown size={12} /> : null}
                      {formatSignedMw(row.error_mw, 1)}
                    </span>
                  </td>
                  <td className="text-right text-mono font-bold">
                    {formatNumber(row.absolute_error_mw, 1)} MW
                  </td>
                  <td className="meta-time-cell">
                    {formatTimestamp(row.forecast_publish_time_utc)}
                  </td>
                  <td className="meta-time-cell">
                    {formatTimestamp(row.decision_cutoff_utc)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
