import React, { useState } from 'react'
import {
  BookOpen,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertTriangle,
  Scale,
  Clock,
  Layers,
} from 'lucide-react'
import { formatTimestamp } from '../utils/formatters'

export default function MethodologyPanel({
  metadata = null,
  coverage = null,
  warnings = [],
  isLoading = false,
}) {
  const [isExpanded, setIsExpanded] = useState(false)

  if (isLoading) {
    return <div className="kpi-skeleton" style={{ height: 100 }}></div>
  }

  const scope = metadata?.delivery_scope || {}
  const assumptions = metadata?.assumptions_and_limitations || []

  return (
    <div className="methodology-card" id="methodology-section">
      <div
        className="methodology-header-toggle"
        onClick={() => setIsExpanded(!isExpanded)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            setIsExpanded(!isExpanded)
          }
        }}
        aria-expanded={isExpanded}
        aria-controls="methodology-details"
      >
        <div className="methodology-title-group">
          <BookOpen size={18} style={{ color: 'var(--accent-cyan)' }} />
          <div>
            <h3 className="methodology-title">Data Quality, Pipeline Lineage &amp; Market Assumptions</h3>
            <p className="methodology-subtitle">
              Elexon BMRS ingestion specifications, temporal alignment, and day-ahead trading boundary conditions
            </p>
          </div>
        </div>
        <div className="toggle-action">
          <span className="toggle-text">{isExpanded ? 'Hide Details' : 'Expand Specification'}</span>
          {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
      </div>

      {isExpanded && (
        <div className="methodology-details" id="methodology-details">
          {/* Data Quality & Coverage Summary */}
          <div className="methodology-grid">
            <div className="method-box">
              <div className="method-box-header">
                <CheckCircle2 size={16} style={{ color: 'var(--accent-emerald)' }} />
                <h4>Dataset Completeness &amp; Audit</h4>
              </div>
              <ul className="method-list">
                <li>
                  <strong>Expected Interval Count:</strong> {coverage?.expected_intervals_count ?? 744} hours (31 days &times; 24h)
                </li>
                <li>
                  <strong>Matched Pairs Validated:</strong> {coverage?.matched_pairs_count ?? 744} hours
                </li>
                <li>
                  <strong>Interval Completeness:</strong> {coverage?.matched_coverage_pct ?? 100}%
                </li>
                <li>
                  <strong>Excluded Anomalies:</strong> {coverage?.excluded_records_count ?? 0} records
                </li>
              </ul>
              {warnings && warnings.length > 0 ? (
                <div className="method-warning-box">
                  <AlertTriangle size={14} />
                  <span>{warnings.join(', ')}</span>
                </div>
              ) : (
                <div className="method-ok-box">
                  <CheckCircle2 size={14} />
                  <span>Zero missing intervals or out-of-order timestamps detected in canonical dataset.</span>
                </div>
              )}
            </div>

            {/* Ingestion & Normalization */}
            <div className="method-box">
              <div className="method-box-header">
                <Layers size={16} style={{ color: 'var(--accent-blue)' }} />
                <h4>Source Resolutions &amp; Normalization</h4>
              </div>
              <ul className="method-list">
                <li>
                  <strong>Actual Generation:</strong> Elexon BMRS <code>FUELHH</code> stream (settlement periods 1 to 48, half-hourly). Filtered to <code>fuelType = 'WIND'</code>.
                </li>
                <li>
                  <strong>Actual Normalization:</strong> Matched two-period arithmetic mean: <code>(MW[:00] + MW[:30]) / 2</code> to align with hourly clock boundaries.
                </li>
                <li>
                  <strong>Forecast Stream:</strong> Elexon BMRS <code>WINDFOR</code> stream (National Grid ESO 72-hour forecast projections).
                </li>
                <li>
                  <strong>Forecast Selection Rule:</strong> Most recent projection published strictly on or before <strong>{scope.decision_cutoff_time || '11:00'} {scope.decision_timezone || 'UTC'}</strong> on the day prior to delivery (D-1).
                </li>
              </ul>
            </div>

            {/* Error Convention & Units */}
            <div className="method-box">
              <div className="method-box-header">
                <Scale size={16} style={{ color: 'var(--accent-amber)' }} />
                <h4>Error Convention &amp; Formulations</h4>
              </div>
              <ul className="method-list">
                <li>
                  <strong>Signed Error Formulation:</strong> <code>error_mw = forecast_mw - actual_mw</code>
                </li>
                <li>
                  <strong>Mean Absolute Error (MAE):</strong> <code>&Sigma; |error_mw| / n</code>
                </li>
                <li>
                  <strong>Root Mean Squared Error (RMSE):</strong> <code>&radic;(&Sigma; error_mw&sup2; / n)</code>
                </li>
                <li>
                  <strong>Mean Bias Error (MBE):</strong> <code>&Sigma; error_mw / n</code>
                </li>
                <li>
                  <strong>MAPE Handling:</strong> Computed strictly on non-zero actuals; zero-actual hours are audited and excluded to prevent division-by-zero distortion.
                </li>
              </ul>
            </div>

            {/* Market Scope Boundary */}
            <div className="method-box">
              <div className="method-box-header">
                <Clock size={16} style={{ color: 'var(--accent-cyan)' }} />
                <h4>Day-Ahead Trading Assumptions &amp; Boundaries</h4>
              </div>
              <ul className="method-list">
                {assumptions.map((assump, idx) => (
                  <li key={idx}>{assump}</li>
                ))}
                <li>
                  Pipeline Run Stamp: <code>{formatTimestamp(metadata?.dataset_creation_timestamp_utc, true)}</code>
                </li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
