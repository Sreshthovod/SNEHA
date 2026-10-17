import type { ReactNode } from 'react'
import type { FlagNumberRow } from '../../lib/analytics'

/**
 * "The numbers behind this" for a review prompt: plain-language values first; rule settings
 * and the internal rule reference sit one level deeper so they never read like a test result.
 */
export function FlagNumbers({
  main,
  technical,
  ruleId,
  footer,
}: {
  main: FlagNumberRow[]
  technical: FlagNumberRow[]
  ruleId: string
  footer?: ReactNode
}) {
  return (
    <details className="details">
      <summary>The numbers behind this</summary>
      {main.length > 0 && (
        <dl className="definition-list definition-list--compact">
          {main.map((r) => (
            <div key={r.key}>
              <dt>{r.label}</dt>
              <dd>{r.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {footer}
      <details className="details">
        <summary>Technical details</summary>
        <dl className="definition-list definition-list--compact">
          {technical.map((r) => (
            <div key={r.key}>
              <dt>{r.label}</dt>
              <dd>{r.value}</dd>
            </div>
          ))}
          <div>
            <dt>Rule reference</dt>
            <dd>
              <code>{ruleId}</code>
            </dd>
          </div>
        </dl>
      </details>
    </details>
  )
}
