import { Link } from 'react-router-dom'
import type { ReviewFlag, RuleNotEvaluated } from '../../api/types'
import { flagNumberLabel } from '../../lib/analytics'
import { Notice } from '../ui/States'

const KIND_LABELS: Record<ReviewFlag['kind'], string> = {
  change: 'Change from their usual pattern',
  data: 'About the data',
  context: 'Context',
}

function formatNumber(v: unknown): string {
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(2)
  if (Array.isArray(v)) return v.join(', ')
  if (v === null || v === undefined) return '—'
  return String(v)
}

/** "May be worth reviewing" prompts. Every item explains the rule and the numbers it used. */
export function ReviewFlagsPanel({
  flags,
  notEvaluated,
  disclaimer,
  observationsHref,
}: {
  flags: ReviewFlag[]
  notEvaluated: RuleNotEvaluated[]
  /** Shown only when the panel is used on its own (the analytics view already shows it). */
  disclaimer?: string
  observationsHref: string
}) {
  return (
    <section aria-labelledby="review-flags-heading" className="review-flags">
      <h3 id="review-flags-heading">May be worth reviewing</h3>
      {flags.length === 0 ? (
        <p>Nothing stands out in this period.</p>
      ) : (
        <ul className="plain-list review-flags__list">
          {flags.map((f) => (
            <li key={f.rule_id} className="review-flag">
              <p className="review-flag__title">
                <strong>{f.title}</strong> <span className="badge badge--neutral">{KIND_LABELS[f.kind]}</span>
              </p>
              <p>{f.explanation}</p>
              {Object.keys(f.numbers).length > 0 && (
                <dl className="definition-list definition-list--compact">
                  {Object.entries(f.numbers).map(([k, v]) => (
                    <div key={k}>
                      <dt>{flagNumberLabel(k)}</dt>
                      <dd>{formatNumber(v)}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {f.observation_ids.length > 0 && (
                <p>
                  <Link to={observationsHref}>
                    {f.observation_ids.length} related caregiver note{f.observation_ids.length === 1 ? '' : 's'}
                  </Link>
                </p>
              )}
              {f.wording && <p className="field__hint">{f.wording}</p>}
            </li>
          ))}
        </ul>
      )}
      {disclaimer && <Notice tone="info">{disclaimer}</Notice>}
      {notEvaluated.length > 0 && (
        <details className="details">
          <summary>Checks that could not be made ({notEvaluated.length})</summary>
          <ul>
            {notEvaluated.map((r) => (
              <li key={r.rule_id}>{r.reason}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}
