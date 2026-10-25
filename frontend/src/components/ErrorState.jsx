import React from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

export default function ErrorState({
  title = 'Failed to load data',
  message = 'An error occurred while fetching information from the backend service.',
  onRetry,
  height = '200px',
}) {
  return (
    <div className="state-container error-state" style={{ minHeight: height }}>
      <div className="error-icon-wrapper">
        <AlertTriangle size={24} style={{ color: 'var(--accent-rose)' }} />
      </div>
      <h3 className="state-title">{title}</h3>
      <p className="state-message">{message}</p>
      {onRetry && (
        <button type="button" className="btn-secondary btn-sm" onClick={onRetry}>
          <RefreshCw size={14} />
          <span>Retry Request</span>
        </button>
      )}
    </div>
  )
}
