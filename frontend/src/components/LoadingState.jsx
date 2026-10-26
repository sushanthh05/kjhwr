import React from 'react'
import { Loader2 } from 'lucide-react'

export default function LoadingState({
  message = 'Loading intelligence metrics...',
  subMessage = null,
  height = '200px',
}) {
  return (
    <div className="state-container loading-state" style={{ minHeight: height, flexDirection: 'column', textAlign: 'center', padding: '2rem' }}>
      <Loader2 size={28} className="spin-icon" style={{ color: 'var(--accent-blue)', marginBottom: '0.75rem' }} />
      <span className="state-message" style={{ fontWeight: 600 }}>{message}</span>
      {subMessage && (
        <span
          className="state-submessage"
          style={{
            marginTop: '0.5rem',
            fontSize: '0.85rem',
            color: 'var(--text-muted)',
            maxWidth: '520px',
            lineHeight: '1.45',
          }}
        >
          {subMessage}
        </span>
      )}
    </div>
  )
}
