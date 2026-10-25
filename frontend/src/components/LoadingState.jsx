import React from 'react'
import { Loader2 } from 'lucide-react'

export default function LoadingState({ message = 'Loading intelligence metrics...', height = '200px' }) {
  return (
    <div className="state-container loading-state" style={{ minHeight: height }}>
      <Loader2 size={24} className="spin-icon" style={{ color: 'var(--accent-blue)' }} />
      <span className="state-message">{message}</span>
    </div>
  )
}
