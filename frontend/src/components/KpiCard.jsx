import React from 'react'

export default function KpiCard({
  id,
  title,
  value,
  unit,
  subtitle,
  icon: Icon,
  variant = 'default', // 'default' | 'bias' | 'forecast' | 'actual' | 'warning'
  biasSign = null, // '+' | '-' | '0'
  isLoading = false,
  isUnavailable = false,
  badgeText = null,
}) {
  return (
    <div
      id={id}
      className={`kpi-card ${variant} ${isLoading ? 'loading' : ''} ${isUnavailable ? 'unavailable' : ''}`}
    >
      <div className="kpi-header">
        <span className="kpi-title">{title}</span>
        {Icon && (
          <div className="kpi-icon-wrapper">
            <Icon size={16} />
          </div>
        )}
      </div>

      <div className="kpi-value-container">
        {isLoading ? (
          <div className="kpi-skeleton"></div>
        ) : isUnavailable || value === null || value === undefined ? (
          <div className="kpi-unavailable">
            <span className="kpi-value-empty">Unavailable</span>
          </div>
        ) : (
          <div className="kpi-value-row">
            <span className={`kpi-value ${variant === 'bias' && biasSign === '+' ? 'bias-positive' : variant === 'bias' && biasSign === '-' ? 'bias-negative' : ''}`}>
              {value}
            </span>
            {unit && <span className="kpi-unit">{unit}</span>}
          </div>
        )}
      </div>

      <div className="kpi-footer">
        {badgeText && !isLoading && !isUnavailable && (
          <span className={`kpi-badge ${variant === 'bias' && biasSign === '+' ? 'badge-amber' : variant === 'bias' && biasSign === '-' ? 'badge-blue' : 'badge-neutral'}`}>
            {badgeText}
          </span>
        )}
        <p className="kpi-subtitle">{isLoading ? 'Fetching metric...' : subtitle}</p>
      </div>
    </div>
  )
}
