import React from 'react'
import { Info, Clock, CheckCircle2, AlertTriangle, Layers, Scale } from 'lucide-react'

export default function DecisionContext({
  scope = null,
  coverage = null,
  warnings = [],
  filterActive = false,
  filteredDateRange = null,
}) {
  const cutoffTime = scope?.decision_cutoff || '11:00 UTC (Day-Ahead D-1)'
  const matchedCount = coverage?.matched_pairs_count ?? '—'
  const expectedCount = coverage?.expected_intervals_count ?? '—'
  const coveragePct = coverage?.matched_coverage_pct !== undefined ? `${coverage.matched_coverage_pct}%` : '—'
  const excludedCount = coverage?.excluded_records_count ?? 0

  return (
    <div className="decision-context-card" id="decision-context-strip">
      <div className="decision-context-grid">
        {/* Core Trading Policy Banner */}
        <div className="decision-item">
          <div className="decision-icon-box">
            <Clock size={16} style={{ color: 'var(--accent-blue)' }} />
          </div>
          <div className="decision-content">
            <span className="decision-label">Day-Ahead Decision Cutoff</span>
            <div className="decision-value-row">
              <strong className="decision-highlight">{cutoffTime}</strong>
              <span className="decision-badge">Strict Pre-Cutoff</span>
            </div>
            <span className="decision-note">
              Forecasts published after 11:00 UTC on D-1 are excluded to prevent look-ahead bias.
            </span>
          </div>
        </div>

        {/* Temporal & Power Resolution */}
        <div className="decision-item">
          <div className="decision-icon-box">
            <Layers size={16} style={{ color: 'var(--accent-emerald)' }} />
          </div>
          <div className="decision-content">
            <span className="decision-label">Resolution &amp; Normalization</span>
            <div className="decision-value-row">
              <strong className="decision-value">Hourly Average (MW)</strong>
            </div>
            <span className="decision-note">
              Actuals: two-period settlement average (:00 &amp; :30). Forecasts: hourly step.
            </span>
          </div>
        </div>

        {/* Dataset Coverage & Completeness */}
        <div className="decision-item">
          <div className="decision-icon-box">
            <CheckCircle2 size={16} style={{ color: 'var(--accent-emerald)' }} />
          </div>
          <div className="decision-content">
            <span className="decision-label">Dataset Coverage</span>
            <div className="decision-value-row">
              <strong className="decision-value">
                {matchedCount} / {expectedCount} hrs
              </strong>
              <span className="coverage-pill">{coveragePct} complete</span>
            </div>
            <span className="decision-note">
              {excludedCount > 0
                ? `${excludedCount} record(s) excluded for data quality`
                : 'Zero missing intervals; 100% matched validation'}
            </span>
          </div>
        </div>

        {/* Operational Boundary Disclaimer */}
        <div className="decision-item">
          <div className="decision-icon-box">
            <Scale size={16} style={{ color: 'var(--accent-amber)' }} />
          </div>
          <div className="decision-content">
            <span className="decision-label">Market Scope Boundary</span>
            <div className="decision-value-row">
              <strong className="decision-value">GB National Generation</strong>
            </div>
            <span className="decision-note">
              Measures GB wind outturn forecast error; does not calculate individual utility positions.
            </span>
          </div>
        </div>
      </div>

      {/* Dynamic Data Quality or Date Filter Notice */}
      {filterActive && filteredDateRange && (
        <div className="filter-active-alert">
          <Info size={14} />
          <span>
            Active Date Scope: <strong>{filteredDateRange.start}</strong> to <strong>{filteredDateRange.end}</strong>.
            Time series and aggregated metrics reflect the selected delivery window.
          </span>
        </div>
      )}

      {warnings && warnings.length > 0 && (
        <div className="context-warnings-banner">
          <AlertTriangle size={14} className="warning-icon" />
          <div className="warning-text">
            {warnings.map((w, idx) => (
              <span key={idx} className="warning-item">{w}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
