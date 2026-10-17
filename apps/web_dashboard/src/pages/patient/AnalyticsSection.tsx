import { useMemo, useState } from 'react'
import { getAnalytics } from '../../api/analytics'
import { AnalyticsView } from '../../components/analytics/AnalyticsView'
import { ReviewItemsPanel } from '../../components/analytics/ReviewItemsPanel'
import { useReviewItems } from '../../hooks/useReviewItems'
import { Card } from '../../components/ui/Card'
import { TextField } from '../../components/ui/Field'
import { ErrorState, Loading } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { addDays, formatDate, todayInZone } from '../../lib/dates'
import { usePatient } from '../../state/patient'

export function AnalyticsSection() {
  const { patient } = usePatient()
  const today = todayInZone(patient.timezone)
  const [range, setRange] = useState({ from: addDays(today, -8), to: today })
  const valid = Boolean(range.from && range.to && range.from <= range.to)
  const analytics = useAsync(
    (signal) =>
      valid
        ? getAnalytics(patient.id, range.from, range.to, signal)
        : Promise.reject(new Error('Choose a start date before the end date.')),
    [patient.id, range.from, range.to],
  )
  const review = useReviewItems(range.from, range.to, valid)
  // Rules that already have a card waiting for a decision: shown once, under "Your review".
  const covered = useMemo(
    () => new Set((review.items.data ?? []).filter((i) => i.status === 'awaiting_review').map((i) => i.rule_id)),
    [review.items.data],
  )
  const updating = analytics.status === 'loading' && Boolean(analytics.data)
  const panel = valid ? <ReviewItemsPanel {...review} /> : null

  return (
    <Card title="Activity trends">
      <div className="analytics-toolbar">
        <div className="inline-fields">
          <TextField label="From" type="date" value={range.from} max={range.to} onChange={(e) => setRange((r) => ({ ...r, from: e.target.value }))} />
          <TextField label="To" type="date" value={range.to} min={range.from} onChange={(e) => setRange((r) => ({ ...r, to: e.target.value }))} />
        </div>
      </div>
      <p className="analytics-status" role="status">
        {updating && valid ? `Updating for ${formatDate(range.from)} – ${formatDate(range.to)}…` : ''}
      </p>
      {analytics.status === 'error' && <ErrorState error={analytics.error} onRetry={analytics.reload} />}
      {analytics.status === 'loading' && !analytics.data && <Loading />}
      {analytics.data ? (
        <div className={updating ? 'is-updating' : undefined} aria-busy={updating || undefined}>
          <AnalyticsView
            analytics={analytics.data}
            observationsHref={`/app/patients/${patient.id}/observations`}
            reviewSlot={panel}
            coveredRuleIds={covered}
          />
        </div>
      ) : (
        panel
      )}
    </Card>
  )
}
