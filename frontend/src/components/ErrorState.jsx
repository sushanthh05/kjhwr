import React, { useState, useEffect } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

export default function ErrorState({
  title = 'Failed to load data',
  message = 'An error occurred while fetching information from the backend service.',
  onRetry,
  height = '200px',
  autoRetry = true,
  autoRetrySeconds = 8,
}) {
  const [countdown, setCountdown] = useState(autoRetrySeconds)

  useEffect(() => {
    if (!onRetry || !autoRetry || autoRetrySeconds <= 0) return
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer)
          onRetry()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [onRetry, autoRetry, autoRetrySeconds])

  return (
    <div className="state-container error-state" style={{ minHeight: height }}>
      <div className="error-icon-wrapper">
        <AlertTriangle size={24} style={{ color: 'var(--accent-rose)' }} />
      </div>
      <h3 className="state-title">{title}</h3>
      <p className="state-message">{message}</p>
      {onRetry && (
        <button
          type="button"
          className="btn-secondary btn-sm"
          onClick={() => {
            setCountdown(0)
            onRetry()
          }}
        >
          <RefreshCw size={14} className={countdown === 0 ? 'spin-icon' : ''} />
          <span>
            {autoRetry && countdown > 0
              ? `Auto-retrying in ${countdown}s... (click to retry now)`
              : 'Retry Request'}
          </span>
        </button>
      )}
    </div>
  )
}
