export type StatusTone = 'success' | 'warning' | 'danger' | 'neutral' | 'info'

const SYMBOL: Record<StatusTone, string> = {
  success: '●',
  warning: '▲',
  danger: '■',
  neutral: '○',
  info: '◆',
}

interface StatusBadgeProps {
  tone: StatusTone
  label: string
}

/** Status is conveyed by text and shape, never colour alone (WCAG 1.4.1). */
export function StatusBadge({ tone, label }: StatusBadgeProps) {
  return (
    <span className={`badge badge--${tone}`}>
      <span aria-hidden="true">{SYMBOL[tone]}</span>
      {label}
    </span>
  )
}
