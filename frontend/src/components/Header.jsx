import React from 'react'
import { Wind, Database, Calendar, RefreshCw } from 'lucide-react'

export default function Header({
  connectionStatus = 'idle', // 'idle' | 'checking' | 'connected' | 'error'
  onRefreshAll,
  isRefreshing = false,
}) {
  return (
    <header className="portal-header">
      <div className="header-inner">
        {/* Brand identity */}
        <div className="brand-group">
          <div className="brand-icon">
            <Wind size={22} />
          </div>
          <div className="brand-text">
            <div className="brand-title-row">
              <h1 className="brand-heading">Wind Forecast Intelligence</h1>
              <span className="environment-badge">UK Market Portal</span>
            </div>
            <p className="brand-subtitle">UK national wind generation &middot; Day-ahead forecast analysis</p>
          </div>
        </div>

        {/* Metadata Badges & Live Status */}
        <div className="header-meta">
          <div className="meta-pill" title="Reporting Period">
            <Calendar size={14} className="meta-icon" />
            <span className="meta-label">Period:</span>
            <strong className="meta-value">January 2026</strong>
          </div>

          <div className="meta-pill" title="Official Transmission & Market Settlement Data">
            <Database size={14} className="meta-icon" />
            <span className="meta-label">Source:</span>
            <strong className="meta-value">Elexon BMRS</strong>
          </div>

          {/* Real Backend Connectivity Indicator */}
          <div
            className={`connection-indicator ${connectionStatus}`}
            id="backend-connection-badge"
            title={`Backend API status: ${connectionStatus}`}
          >
            {connectionStatus === 'connected' && (
              <>
                <span className="status-dot connected"></span>
                <span className="status-text">Backend Connected</span>
              </>
            )}
            {connectionStatus === 'checking' && (
              <>
                <RefreshCw size={12} className="spin-icon" />
                <span className="status-text">Verifying API...</span>
              </>
            )}
            {connectionStatus === 'error' && (
              <>
                <span className="status-dot disconnected"></span>
                <span className="status-text">API Offline</span>
              </>
            )}
            {connectionStatus === 'idle' && (
              <>
                <span className="status-dot idle"></span>
                <span className="status-text">Connecting...</span>
              </>
            )}
          </div>

          {onRefreshAll && (
            <button
              type="button"
              id="refresh-dashboard-btn"
              className="btn-icon"
              onClick={onRefreshAll}
              disabled={isRefreshing}
              title="Refresh all intelligence data"
              aria-label="Refresh dashboard data"
            >
              <RefreshCw size={15} className={isRefreshing ? 'spin-icon' : ''} />
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
