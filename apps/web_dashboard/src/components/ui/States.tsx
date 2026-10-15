import type { ReactNode } from 'react'
import type { ApiError } from '../../api/client'
import { Button } from './Button'

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <p className="state state--loading" role="status">
      {label}
    </p>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state state--empty">
      <p className="state__title">{title}</p>
      {children && <div className="state__body">{children}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: ApiError | Error; onRetry?: () => void }) {
  return (
    <div className="state state--error" role="alert">
      <p className="state__title">Something went wrong</p>
      <p>{error.message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

export function Notice({
  tone = 'info',
  title,
  children,
}: {
  tone?: 'info' | 'warning' | 'success' | 'danger'
  title?: string
  children: ReactNode
}) {
  return (
    <div className={`notice notice--${tone}`} role={tone === 'danger' ? 'alert' : 'status'}>
      {title && <p className="notice__title">{title}</p>}
      <div>{children}</div>
    </div>
  )
}

/** Inline error from a failed action, e.g. under a form. */
export function ActionError({ error }: { error: ApiError | null }) {
  if (!error) return null
  return (
    <p className="field__error" role="alert">
      {error.message}
    </p>
  )
}
