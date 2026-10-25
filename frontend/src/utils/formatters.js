/**
 * formatters.js
 * Utility helpers for formatting numbers, power values, errors, and timestamps.
 */

/**
 * Format a number with thousands separators and optional decimals.
 * Returns fallback placeholder if null, undefined, or NaN.
 */
export function formatNumber(val, decimals = 0, fallback = '—') {
  if (val === null || val === undefined || isNaN(val)) {
    return fallback
  }
  return Number(val).toLocaleString('en-GB', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

/**
 * Format power value in MW.
 */
export function formatMw(val, decimals = 1, fallback = '—') {
  if (val === null || val === undefined || isNaN(val)) {
    return fallback
  }
  return `${formatNumber(val, decimals)} MW`
}

/**
 * Format percentage value.
 */
export function formatPct(val, decimals = 2, fallback = '—') {
  if (val === null || val === undefined || isNaN(val)) {
    return fallback
  }
  return `${formatNumber(val, decimals)}%`
}

/**
 * Format signed error (e.g. +1,840.30 MW or -420.50 MW)
 */
export function formatSignedMw(val, decimals = 1, fallback = '—') {
  if (val === null || val === undefined || isNaN(val)) {
    return fallback
  }
  const num = Number(val)
  const sign = num > 0 ? '+' : ''
  return `${sign}${formatNumber(num, decimals)} MW`
}

/**
 * Format an ISO UTC timestamp (e.g. "2026-01-12T04:00:00Z" -> "12 Jan 04:00 UTC")
 */
export function formatTimestamp(isoString, includeYear = false) {
  if (!isoString) return '—'
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return isoString

    const day = d.getUTCDate().toString().padStart(2, '0')
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    const month = months[d.getUTCMonth()]
    const year = d.getUTCFullYear()
    const hours = d.getUTCHours().toString().padStart(2, '0')
    const mins = d.getUTCMinutes().toString().padStart(2, '0')

    if (includeYear) {
      return `${day} ${month} ${year} ${hours}:${mins} UTC`
    }
    return `${day} ${month} ${hours}:${mins} UTC`
  } catch {
    return isoString
  }
}

/**
 * Format date only (e.g. "2026-01-12" -> "12 Jan 2026")
 */
export function formatDate(dateString) {
  if (!dateString) return '—'
  try {
    const parts = dateString.split('-')
    if (parts.length === 3) {
      const year = parts[0]
      const monthIdx = parseInt(parts[1], 10) - 1
      const day = parseInt(parts[2], 10)
      const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
      return `${day} ${months[monthIdx]} ${year}`
    }
    return dateString
  } catch {
    return dateString
  }
}

/**
 * Format compact date for chart axis (e.g. "2026-01-12T00:00:00Z" -> "12 Jan")
 */
export function formatAxisDate(isoString) {
  if (!isoString) return ''
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return isoString.slice(5, 10)
    const day = d.getUTCDate().toString().padStart(2, '0')
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    return `${day} ${months[d.getUTCMonth()]}`
  } catch {
    return isoString
  }
}

/**
 * Format compact time for chart axis (e.g. "04:00")
 */
export function formatAxisTime(isoString) {
  if (!isoString) return ''
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return ''
    const hours = d.getUTCHours().toString().padStart(2, '0')
    const mins = d.getUTCMinutes().toString().padStart(2, '0')
    return `${hours}:${mins}`
  } catch {
    return ''
  }
}
