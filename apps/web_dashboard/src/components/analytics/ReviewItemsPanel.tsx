import { useState, type ReactNode } from 'react'
import { addReviewContext, decideReviewItem } from '../../api/review'
import type { ReviewItem } from '../../api/types'
import { useAction } from '../../hooks/useAsync'
import { describeFlagNumbers } from '../../lib/analytics'
import { formatDate, formatDateTime } from '../../lib/dates'
import { REVIEW_STATUS_LABELS } from '../../lib/labels'
import { usePatient } from '../../state/patient'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { DisabledWithReason } from '../ui/DisabledReason'
import { TextArea } from '../ui/Field'
import { ActionError, ErrorState, Loading, Notice } from '../ui/States'
import { StatusBadge } from '../ui/StatusBadge'
import { FlagNumbers } from './FlagNumbers'
import type { ReviewItemsState } from '../../hooks/useReviewItems'

function DecisionDialog({ item, decision, onClose, onSaved }: {
  item: ReviewItem
  decision: 'confirmed' | 'dismissed'
  onClose: () => void
  onSaved: () => void
}) {
  const { patient } = usePatient()
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const save = useAction(() => decideReviewItem(patient.id, item.id, { decision, reason: reason.trim() }))
  const confirm = decision === 'confirmed'
  return (
    <Dialog
      open
      title={confirm ? 'Confirm: worth discussing with a clinician' : 'Dismiss this prompt'}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            pending={save.pending}
            onClick={async () => {
              if (reason.trim().length < 3) {
                setError('Please write a short reason. It is kept with your decision.')
                return
              }
              if (await save.run()) onSaved()
            }}
          >
            {confirm ? 'Confirm' : 'Dismiss'}
          </Button>
        </>
      }
    >
      <p>
        <strong>{item.title}</strong>
      </p>
      <p>{item.explanation}</p>
      <TextArea
        label={confirm ? 'What have you noticed at home?' : 'What explains it?'}
        hint={
          confirm
            ? 'For example: also forgetting names this week. A clinician will see this reason.'
            : 'For example: relatives were visiting, a cold, new glasses, a new phone.'
        }
        value={reason}
        maxLength={1000}
        onChange={(e) => setReason(e.target.value)}
        error={error ?? undefined}
        required
      />
      <p className="field__hint">Your decision is final and is recorded with your name and the time.</p>
      <ActionError error={save.error} />
    </Dialog>
  )
}

function ReviewItemCard({ item, onChanged, compact = false, children }: {
  item: ReviewItem
  onChanged: () => void
  compact?: boolean
  children?: ReactNode
}) {
  const { patient, isClinician, isManager } = usePatient()
  const [decision, setDecision] = useState<'confirmed' | 'dismissed' | null>(null)
  const awaiting = item.status === 'awaiting_review'
  const tone = awaiting ? 'warning' : 'neutral'
  const rows = describeFlagNumbers(item.rule_id, item.numbers)
  const period = `${formatDate(item.period_start)} – ${formatDate(item.period_end)}`
  return (
    <li className={awaiting ? 'review-flag' : 'review-flag review-flag--decided'}>
      <p className="review-flag__title">
        {compact ? <strong>{period}</strong> : <strong>{item.title}</strong>}{' '}
        <StatusBadge tone={tone} label={REVIEW_STATUS_LABELS[item.status]} />
      </p>
      {!compact && <p className="review-flag__meta">Period: {period}</p>}
      <p>{item.explanation}</p>
      <FlagNumbers
        main={rows.main}
        technical={rows.technical}
        ruleId={item.rule_id}
        footer={
          <p className="field__hint">
            Method {item.method_version}, settings {item.config_version}.
            {item.observation_ids.length > 0 && ` ${item.observation_ids.length} caregiver note(s) from this period are attached as context.`}
          </p>
        }
      />
      {item.decided_at && (
        <p className="field__hint">
          Decided {formatDateTime(item.decided_at, patient.timezone)}: {item.decision_reason}
        </p>
      )}
      <EvidenceLine item={item} />
      {(item.context_notes ?? []).length > 0 && (
        <ul className="plain-list review-context">
          {(item.context_notes ?? []).map((n) => (
            <li key={`${n.by}-${n.at}`} className="field__hint">
              Context added {formatDateTime(n.at, patient.timezone)}: {n.note}
            </li>
          ))}
        </ul>
      )}
      {!isClinician && <AddContext item={item} onChanged={onChanged} />}
      {!isClinician && awaiting && (
        <div className="observation-actions">
          {isManager ? (
            <>
              <Button variant="secondary" onClick={() => setDecision('confirmed')} aria-label={`Confirm: ${item.title}${compact ? ` (${period})` : ''}`}>
                Confirm
              </Button>
              <Button variant="secondary" onClick={() => setDecision('dismissed')} aria-label={`Dismiss: ${item.title}${compact ? ` (${period})` : ''}`}>
                Dismiss
              </Button>
            </>
          ) : (
            <DisabledWithReason label="Confirm or dismiss" reason="A managing family member decides on review items." />
          )}
        </div>
      )}
      {children}
      {decision && (
        <DecisionDialog
          item={item}
          decision={decision}
          onClose={() => setDecision(null)}
          onSaved={() => {
            setDecision(null)
            onChanged()
          }}
        />
      )}
    </li>
  )
}

/** Overlapping date ranges can raise the same prompt more than once: show one card per rule. */
function groupByRule(items: ReviewItem[]): ReviewItem[][] {
  const groups = new Map<string, ReviewItem[]>()
  for (const item of items) {
    const list = groups.get(item.rule_id) ?? []
    list.push(item)
    groups.set(item.rule_id, list)
  }
  return Array.from(groups.values()).map((list) =>
    [...list].sort((a, b) => b.period_end.localeCompare(a.period_end) || b.created_at.localeCompare(a.created_at)),
  )
}

function periodText(i: ReviewItem): string {
  return `${formatDate(i.period_start)} – ${formatDate(i.period_end)}`
}

/**
 * Automated prompts kept for a caregiver's decision. Caregivers: the prompts for the period
 * shown (created on load) plus anything still waiting, one card per rule. Clinicians: confirmed
 * items only.
 */
export function ReviewItemsPanel({ items, canScan }: ReviewItemsState) {
  const { isClinician } = usePatient()
  const awaiting = items.data?.filter((i) => i.status === 'awaiting_review') ?? []
  const decided = items.data?.filter((i) => i.status !== 'awaiting_review') ?? []
  const groups = groupByRule(awaiting)
  return (
    <section aria-labelledby="review-items-heading" className="review-flags" id="your-review">
      <h3 id="review-items-heading" className="analytics-section__title">
        {isClinician ? 'Confirmed by the family' : 'Your review'}
      </h3>
      <p className="analytics-lede">
        {isClinician
          ? 'Automated prompts reach you only after a family caregiver has looked at the numbers and confirmed them. They are not diagnoses.'
          : 'Each prompt below was raised by fixed rules from recorded activity. Nothing is shared with a clinician unless you confirm it. Dismiss it if you know an everyday reason.'}
      </p>
      {items.status === 'error' && <ErrorState error={items.error} onRetry={items.reload} />}
      {items.status === 'loading' && !items.data && <Loading />}
      {items.data && items.data.length === 0 && (
        <p>{isClinician ? 'Nothing has been confirmed for discussion.' : 'Nothing is waiting for your review.'}</p>
      )}
      {groups.length > 0 && (
        <>
          <p className="review-count">
            <span aria-hidden="true">▲</span>
            <strong>
              {groups.length} prompt{groups.length === 1 ? '' : 's'} to look at
            </strong>
          </p>
          <ul className="plain-list review-flags__list">
            {groups.map(([latest, ...older]) => (
              <ReviewItemCard key={`${latest.id}-${latest.status}`} item={latest} onChanged={items.reload}>
                {older.length > 0 && (
                  <details className="details review-flag__more">
                    <summary>
                      Also raised for {older.map(periodText).join(', ')} ({older.length} more)
                    </summary>
                    <p className="field__hint">
                      The same rule was checked again for an overlapping date range. You can decide on each one separately.
                    </p>
                    <ul className="plain-list review-flags__list">
                      {older.map((i) => (
                        <ReviewItemCard key={`${i.id}-${i.status}`} item={i} onChanged={items.reload} compact />
                      ))}
                    </ul>
                  </details>
                )}
              </ReviewItemCard>
            ))}
          </ul>
        </>
      )}
      {decided.length > 0 && (
        <details className="details" open={isClinician}>
          <summary>{isClinician ? `Confirmed items (${decided.length})` : `Already decided (${decided.length})`}</summary>
          <ul className="plain-list review-flags__list">
            {decided.map((i) => <ReviewItemCard key={`${i.id}-${i.status}`} item={i} onChanged={items.reload} />)}
          </ul>
        </details>
      )}
      {!isClinician && !canScan && <Notice tone="info">Choose 3 to 31 days to check for new review prompts.</Notice>}
    </section>
  )
}

/** The stored records the prompt is based on, and what could not be checked. */
function EvidenceLine({ item }: { item: ReviewItem }) {
  const raw = item.evidence
  if (!raw || !raw.results_considered) return null
  const ev = {
    results_considered: raw.results_considered,
    activities: raw.activities ?? [],
    missing_days: raw.missing_days ?? [],
    limitations: raw.limitations ?? [],
  }
  return (
    <details className="details">
      <summary>What this is based on</summary>
      <p className="field__hint">
        {ev.results_considered} recorded {ev.results_considered === 1 ? 'activity' : 'activities'}
        {ev.activities.length > 0 && ` (${ev.activities.join(', ')})`}.
        {ev.missing_days.length > 0 && ` No activity on ${ev.missing_days.length} ${ev.missing_days.length === 1 ? 'day' : 'days'}; missing days are not counted as low results.`}
      </p>
      {ev.limitations.length > 0 && (
        <ul className="field__hint">
          {ev.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}
    </details>
  )
}

/** Any caregiver can add context; it is kept and never changes the decision. */
function AddContext({ item, onChanged }: { item: ReviewItem; onChanged: () => void }) {
  const { patient } = usePatient()
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const save = useAction(() => addReviewContext(patient.id, item.id, note.trim()))
  if (!open)
    return (
      <Button variant="ghost" onClick={() => setOpen(true)} aria-label={`Add context: ${item.title}`}>
        Add context
      </Button>
    )
  return (
    <div className="review-context-form">
      <TextArea
        label="Context"
        hint="Something you know that helps explain this, e.g. a visit, an illness, a new phone. It is kept and does not decide anything."
        value={note}
        maxLength={1000}
        onChange={(e) => setNote(e.target.value)}
        error={error ?? undefined}
      />
      <div className="form-actions">
        <Button
          pending={save.pending}
          onClick={async () => {
            if (note.trim().length < 3) {
              setError('Please write a few words.')
              return
            }
            if (await save.run()) {
              setOpen(false)
              setNote('')
              onChanged()
            }
          }}
        >
          Save context
        </Button>
        <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
      <ActionError error={save.error} />
    </div>
  )
}
