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

/** Generic display for a review-prompt number (unknown keys keep their raw value). */
export function formatFlagNumber(v: unknown): string {
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(2)
  if (Array.isArray(v)) return v.join(', ')
  if (v === null || v === undefined) return '—'
  return String(v)
}

export interface FlagNumberRow {
  key: string
  label: string
  value: string
}

/** Rule settings (thresholds) are technical detail: shown only on request. */
const TECHNICAL_KEYS = new Set(['threshold_drop', 'threshold_increase'])

/**
 * Plain-language rows for the numbers behind a review prompt, e.g. "Usual: 90%",
 * "This period: 67%". Rule settings are returned separately as `technical`.
 */
export function describeFlagNumbers(ruleId: string, numbers: Record<string, unknown>): {
  main: FlagNumberRow[]
  technical: FlagNumberRow[]
} {
  const rule = ruleId.toUpperCase()
  const asValue = (v: unknown): string => {
    if (typeof v !== 'number') return formatFlagNumber(v)
    if (rule.includes('ACCURACY')) return pct(v)
    if (rule.includes('HINT')) return `${num(v)} per activity`
    return formatFlagNumber(v)
  }
  const known: Record<string, (v: unknown) => [string, string]> = {
    baseline: (v) => ['Usual', asValue(v)],
    current: (v) => ['This period', asValue(v)],
    baseline_ms: (v) => ['Usual time to answer', typeof v === 'number' ? seconds(v) : formatFlagNumber(v)],
    current_ms: (v) => ['Time to answer this period', typeof v === 'number' ? seconds(v) : formatFlagNumber(v)],
    share_of_days: (v) => ['Share of days that matched', typeof v === 'number' ? pct(v) : formatFlagNumber(v)],
    days_considered: (v) => ['Days looked at', formatFlagNumber(v)],
    baseline_difficulty: (v) => ['Usual level', typeof v === 'number' ? num(v) : formatFlagNumber(v)],
    current_difficulty: (v) => ['Level this period', typeof v === 'number' ? num(v) : formatFlagNumber(v)],
    threshold_drop: (v) => ['Rule setting: smallest drop that raises a prompt', formatFlagNumber(v)],
    threshold_increase: (v) => ['Rule setting: smallest rise that raises a prompt', formatFlagNumber(v)],
  }
  const main: FlagNumberRow[] = []
  const technical: FlagNumberRow[] = []
  for (const [key, v] of Object.entries(numbers)) {
    const [label, value] = known[key]?.(v) ?? [flagNumberLabel(key), formatFlagNumber(v)]
    ;(TECHNICAL_KEYS.has(key) ? technical : main).push({ key, label, value })
  }
  return { main, technical }
}
