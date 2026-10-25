import React from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import KpiCard from '../components/KpiCard'
import DecisionContext from '../components/DecisionContext'
import WorstMissesTable from '../components/WorstMissesTable'
import Header from '../components/Header'

describe('Component Render Tests', () => {
  describe('KpiCard', () => {
    it('renders title, value, and unit correctly', () => {
      render(
        <KpiCard
          id="test-card"
          title="Mean Absolute Error (MAE)"
          value="2,122.8"
          unit="MW"
          subtitle="Average deviation magnitude"
        />
      )

      expect(screen.getByText('Mean Absolute Error (MAE)')).toBeTruthy()
      expect(screen.getByText('2,122.8')).toBeTruthy()
      expect(screen.getByText('MW')).toBeTruthy()
      expect(screen.getByText('Average deviation magnitude')).toBeTruthy()
    })

    it('renders skeleton during loading state and no hardcoded values', () => {
      const { container } = render(
        <KpiCard
          id="loading-card"
          title="Root Mean Squared Error (RMSE)"
          value={null}
          isLoading={true}
        />
      )

      expect(container.querySelector('.kpi-skeleton')).toBeTruthy()
      expect(screen.queryByText('2,616.7')).toBeNull()
    })

    it('displays explicit unavailable state when metric is null and not loading', () => {
      render(
        <KpiCard
          id="empty-card"
          title="Mean Absolute Error (MAE)"
          value={null}
          isLoading={false}
        />
      )

      expect(screen.getByText('Unavailable')).toBeTruthy()
    })

    it('distinguishes positive bias styling', () => {
      const { container } = render(
        <KpiCard
          id="bias-card"
          title="Mean Bias Error (MBE)"
          value="+1,840.3"
          unit="MW"
          variant="bias"
          biasSign="+"
          badgeText="Overforecast Bias"
        />
      )

      expect(container.querySelector('.bias-positive')).toBeTruthy()
      expect(screen.getByText('Overforecast Bias')).toBeTruthy()
    })
  })

  describe('DecisionContext', () => {
    it('displays visible 11:00 UTC day-ahead cutoff assumption', () => {
      render(
        <DecisionContext
          scope={{ decision_cutoff: '11:00 UTC (Day-Ahead D-1)' }}
          coverage={{ matched_pairs_count: 744, expected_intervals_count: 744, matched_coverage_pct: 100 }}
        />
      )

      expect(screen.getByText('11:00 UTC (Day-Ahead D-1)')).toBeTruthy()
      expect(screen.getByText('Strict Pre-Cutoff')).toBeTruthy()
      expect(screen.getByText('Hourly Average (MW)')).toBeTruthy()
    })

    it('communicates market boundary disclaimer', () => {
      render(
        <DecisionContext
          scope={{}}
          coverage={{ matched_pairs_count: 744, expected_intervals_count: 744 }}
        />
      )

      expect(screen.getByText(/GB National Generation/i)).toBeTruthy()
      expect(screen.getByText(/does not calculate individual utility positions/i)).toBeTruthy()
    })
  })

  describe('WorstMissesTable', () => {
    const mockMisses = [
      {
        rank: 1,
        delivery_time_utc: '2026-01-12T04:00:00Z',
        forecast_generation_mw: 14500.0,
        actual_generation_mw: 7667.0,
        error_mw: 6833.0,
        absolute_error_mw: 6833.0,
        forecast_publish_time_utc: '2026-01-11T09:30:00Z',
        decision_cutoff_utc: '2026-01-11T11:00:00Z',
      },
      {
        rank: 2,
        delivery_time_utc: '2026-01-16T18:00:00Z',
        forecast_generation_mw: 5000.0,
        actual_generation_mw: 9500.0,
        error_mw: -4500.0,
        absolute_error_mw: 4500.0,
        forecast_publish_time_utc: '2026-01-15T09:30:00Z',
        decision_cutoff_utc: '2026-01-15T11:00:00Z',
      },
    ]

    it('renders ranks, errors, and distinguishes overforecast from underforecast', () => {
      const { container } = render(<WorstMissesTable worstMisses={mockMisses} />)

      expect(screen.getByText('#1')).toBeTruthy()
      expect(screen.getByText('#2')).toBeTruthy()
      expect(container.querySelector('.row-overforecast')).toBeTruthy()
      expect(container.querySelector('.row-underforecast')).toBeTruthy()
    })

    it('includes operational disclaimer without claiming financial loss', () => {
      render(<WorstMissesTable worstMisses={mockMisses} />)
      expect(
        screen.getByText(/Forecast error represents volume discrepancy in MW, not direct financial loss/i)
      ).toBeTruthy()
    })

    it('renders clean empty state when list is empty', () => {
      render(<WorstMissesTable worstMisses={[]} />)
      expect(screen.getByText('No forecast misses recorded.')).toBeTruthy()
    })
  })

  describe('Header', () => {
    it('displays brand, period, and verified connection status', () => {
      const { rerender } = render(<Header connectionStatus="connected" />)
      expect(screen.getByText('Wind Forecast Intelligence')).toBeTruthy()
      expect(screen.getByText('January 2026')).toBeTruthy()
      expect(screen.getByText('Backend Connected')).toBeTruthy()

      rerender(<Header connectionStatus="error" />)
      expect(screen.getByText('API Offline')).toBeTruthy()

      rerender(<Header connectionStatus="checking" />)
      expect(screen.getByText('Verifying API...')).toBeTruthy()
    })
  })
})
