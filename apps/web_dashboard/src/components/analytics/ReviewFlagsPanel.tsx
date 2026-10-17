import { Link } from 'react-router-dom'
import type { ReviewFlag, RuleNotEvaluated } from '../../api/types'
import { describeFlagNumbers } from '../../lib/analytics'
import { Notice } from '../ui/States'
import { FlagNumbers } from './FlagNumbers'

const KIND_LABELS: Record<ReviewFlag['kind'], string> = {
  change: 'Change from their usual pattern',
  data: 'About the data',
  context: 'Context',
}

/** "May be worth reviewing" prompts. Every item explains the rule; the numbers are one click away. */
export function ReviewFlagsPanel({
  flags,
  notEvaluated,
  disclaimer,
  observationsHref,
  withheld = false,
  coveredRuleIds,
}: {
  /** True for clinicians: automated prompts are not shared until a caregiver confirms them. */
  withheld?: boolean
  flags: ReviewFlag[]
  notEvaluated: RuleNotEvaluated[]
  /** Shown only when the panel is used on its own (the analytics view already shows it). */
  disclaimer?: string
  observationsHref: string
  /** Prompts already listed for a decision elsewhere on the page (shown once, not twice). */
  coveredRuleIds?: ReadonlySet<string>
}) {
  const covered = flags.filter((f) => coveredRuleIds?.has(f.rule_id))
  const shown = flags.filter((f) => !coveredRuleIds?.has(f.rule_id))
  return (
    <section aria-labelledby="review-flags-heading" className="review-flags">
      <h3 id="review-flags-heading" className="analytics-section__title">
        May be worth reviewing
      </h3>
      {withheld ? (
        <p>
          Automated prompts are shared with clinicians only after a family caregiver confirms them.
          Confirmed items are listed below.
        </p>
      ) : flags.length === 0 ? (
        <p>Nothing stands out in this period.</p>
      ) : (
        <>
          {covered.length > 0 && (
            <div className="surface-muted">
              <p className="review-note">
                {covered.length === flags.length ? 'All ' : ''}
                {covered.length} prompt{covered.length === 1 ? '' : 's'} for this period {covered.length === 1 ? 'is' : 'are'}{' '}
                listed once, with {covered.length === 1 ? 'its' : 'their'} numbers, under <a href="#your-review">Your review</a> above.
              </p>
            </div>
          )}
          {shown.length > 0 && (
            <ul className="plain-list review-flags__list">
              {shown.map((f) => {
                const rows = describeFlagNumbers(f.rule_id, f.numbers)
                return (
                  <li key={f.rule_id} className="review-flag">
                    <p className="review-flag__title">
                      <strong>{f.title}</strong>{' '}
                      <span className="badge badge--neutral">{KIND_LABELS[f.kind]}</span>
                    </p>
                    <p>{f.explanation}</p>
                    {(rows.main.length > 0 || rows.technical.length > 0) && (
                      <FlagNumbers main={rows.main} technical={rows.technical} ruleId={f.rule_id} />
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
                )
              })}
            </ul>
          )}
        </>
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
