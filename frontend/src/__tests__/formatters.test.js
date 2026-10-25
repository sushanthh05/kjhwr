import { describe, it, expect } from 'vitest'
import {
  formatNumber,
  formatMw,
  formatPct,
  formatSignedMw,
  formatTimestamp,
  formatDate,
  formatAxisDate,
  formatAxisTime,
} from '../utils/formatters'

describe('Formatters Utility', () => {
  describe('formatNumber', () => {
    it('formats numbers with thousands separators and requested decimals', () => {
      expect(formatNumber(11580.74, 2)).toBe('11,580.74')
      expect(formatNumber(13421.03, 1)).toBe('13,421.0')
      expect(formatNumber(2122.81, 0)).toBe('2,123')
    })

    it('handles null, undefined, and NaN by returning placeholder fallback', () => {
      expect(formatNumber(null)).toBe('—')
      expect(formatNumber(undefined)).toBe('—')
      expect(formatNumber(NaN)).toBe('—')
      expect(formatNumber(null, 2, 'N/A')).toBe('N/A')
    })
  })

  describe('formatMw', () => {
    it('appends MW unit correctly', () => {
      expect(formatMw(2122.81, 1)).toBe('2,122.8 MW')
      expect(formatMw(0, 0)).toBe('0 MW')
    })

    it('returns fallback for missing values without throwing', () => {
      expect(formatMw(null)).toBe('—')
      expect(formatMw(undefined)).toBe('—')
    })
  })

  describe('formatPct', () => {
    it('formats percentage with percent sign', () => {
      expect(formatPct(22.06, 2)).toBe('22.06%')
      expect(formatPct(100, 1)).toBe('100.0%')
    })

    it('handles null and undefined gracefully', () => {
      expect(formatPct(null)).toBe('—')
    })
  })

  describe('formatSignedMw', () => {
    it('adds plus sign to positive error values', () => {
      expect(formatSignedMw(1840.3, 1)).toBe('+1,840.3 MW')
      expect(formatSignedMw(25.55, 2)).toBe('+25.55 MW')
    })

    it('keeps minus sign for negative error values', () => {
      expect(formatSignedMw(-420.7, 1)).toBe('-420.7 MW')
    })

    it('handles zero without plus sign', () => {
      expect(formatSignedMw(0, 1)).toBe('0.0 MW')
    })

    it('returns fallback for null values', () => {
      expect(formatSignedMw(null)).toBe('—')
    })
  })

  describe('formatTimestamp and date helpers', () => {
    it('formats ISO UTC timestamp string correctly', () => {
      const formatted = formatTimestamp('2026-01-12T04:00:00Z', false)
      expect(formatted).toBe('12 Jan 04:00 UTC')
    })

    it('includes year when requested', () => {
      const formatted = formatTimestamp('2026-01-12T04:00:00Z', true)
      expect(formatted).toBe('12 Jan 2026 04:00 UTC')
    })

    it('formats date strings', () => {
      expect(formatDate('2026-01-12')).toBe('12 Jan 2026')
    })

    it('formats axis labels', () => {
      expect(formatAxisDate('2026-01-12T00:00:00Z')).toBe('12 Jan')
      expect(formatAxisTime('2026-01-12T04:30:00Z')).toBe('04:30')
    })

    it('handles malformed timestamp strings safely', () => {
      expect(formatTimestamp('')).toBe('—')
      expect(formatTimestamp(null)).toBe('—')
      expect(formatDate('')).toBe('—')
    })
  })
})
