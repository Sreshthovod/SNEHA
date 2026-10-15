/** Labels and formatting for descriptive analytics. Neutral wording only. */

export const BASELINE_METRIC_LABELS: Record<string, string> = {
  accuracy_mean: 'Share of answers correct',
  median_response_ms: 'Typical time to answer',
  interruption_rate: 'Activities stopped part-way',
  hints_per_result: 'Hints per activity',
  mean_difficulty: 'Average level',
}

export function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`
}

export function seconds(ms: number | null | undefined): string {
  return ms === null || ms === undefined ? '—' : `${(ms / 1000).toFixed(1)} s`
}

export function num(v: number | null | undefined, digits = 1): string {
  return v === null || v === undefined ? '—' : v.toFixed(digits)
}

export function formatMetric(metric: string, v: number | null | undefined): string {
  switch (metric) {
    case 'accuracy_mean':
    case 'interruption_rate':
      return pct(v)
    case 'median_response_ms':
      return seconds(v)
    case 'mean_difficulty':
      return num(v, 1)
    default:
      return num(v, 2)
  }
}

export function formatChange(metric: string, v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  const sign = v > 0 ? '+' : v < 0 ? '−' : '±'
  const abs = Math.abs(v)
  switch (metric) {
    case 'accuracy_mean':
    case 'interruption_rate':
      return `${sign}${Math.round(abs * 100)} points`
    case 'median_response_ms':
      return `${sign}${(abs / 1000).toFixed(1)} s`
    default:
      return `${sign}${abs.toFixed(metric === 'mean_difficulty' ? 1 : 2)}`
  }
}

/** Plain value for a review-flag number (keys are snake_case). */
export function flagNumberLabel(key: string): string {
  const text = key.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}
