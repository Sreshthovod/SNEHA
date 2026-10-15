import { useState } from 'react'
import { getAnalytics } from '../../api/analytics'
import { AnalyticsView } from '../../components/analytics/AnalyticsView'
import { Card } from '../../components/ui/Card'
import { TextField } from '../../components/ui/Field'
import { ErrorState, Loading } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { addDays, todayInZone } from '../../lib/dates'
import { usePatient } from '../../state/patient'

export function AnalyticsSection() {
  const { patient } = usePatient()
  const today = todayInZone(patient.timezone)
  const [range, setRange] = useState({ from: addDays(today, -8), to: today })
  const valid = range.from && range.to && range.from <= range.to
  const analytics = useAsync(
    (signal) =>
      valid
        ? getAnalytics(patient.id, range.from, range.to, signal)
        : Promise.reject(new Error('Choose a start date before the end date.')),
    [patient.id, range.from, range.to],
  )
  return (
    <Card title="Activity trends">
      <div className="inline-fields">
        <TextField label="From" type="date" value={range.from} max={range.to} onChange={(e) => setRange((r) => ({ ...r, from: e.target.value }))} />
        <TextField label="To" type="date" value={range.to} min={range.from} onChange={(e) => setRange((r) => ({ ...r, to: e.target.value }))} />
      </div>
      {analytics.status === 'error' && <ErrorState error={analytics.error} onRetry={analytics.reload} />}
      {analytics.status === 'loading' && !analytics.data && <Loading />}
      {analytics.data && (
        <AnalyticsView analytics={analytics.data} observationsHref={`/app/patients/${patient.id}/observations`} />
      )}
    </Card>
  )
}
