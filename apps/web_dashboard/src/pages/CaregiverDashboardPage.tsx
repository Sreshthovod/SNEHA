import { Link } from 'react-router-dom'
import { getAnalytics } from '../api/analytics'
import { listMemories } from '../api/memories'
import { listObservations } from '../api/observations'
import { listCaregivers, listPatients } from '../api/patients'
import type { Patient } from '../api/types'
import { Card } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { EmptyState, ErrorState, Loading } from '../components/ui/States'
import { useAsync } from '../hooks/useAsync'
import { addDays, formatDateTime, todayInZone } from '../lib/dates'
import { useAuth } from '../state/auth'

function PatientSummaryCard({ patient }: { patient: Patient }) {
  const { user } = useAuth()
  const today = todayInZone(patient.timezone)
  const summary = useAsync(
    async (signal) => {
      const caregivers = await listCaregivers(patient.id, signal)
      const isManager = Boolean(caregivers.find((c) => c.caregiver_id === user?.id)?.can_manage)
      const [pending, open, recent, analytics] = await Promise.all([
        isManager ? listMemories(patient.id, 'pending_approval', signal) : Promise.resolve(null),
        isManager ? listObservations(patient.id, { status: 'open', limit: 100 }, signal) : Promise.resolve(null),
        listObservations(patient.id, { limit: 50 }, signal),
        getAnalytics(patient.id, addDays(today, -6), today, signal),
      ])
      return {
        isManager,
        pending,
        open,
        fatigue: recent.filter((o) => o.category === 'fatigue').slice(0, 3),
        analytics,
      }
    },
    [patient.id, today, user?.id],
  )
  const base = `/app/patients/${patient.id}`

  return (
    <Card title={patient.display_name} headingLevel={2}>
      {summary.status === 'error' && <ErrorState error={summary.error} onRetry={summary.reload} />}
      {!summary.data && summary.status === 'loading' && <Loading />}
      {summary.data && (
        <div className="summary-grid">
          <div className="metric">
            <p className="metric__label">Memories waiting for approval</p>
            {summary.data.pending ? (
              <>
                <p className="metric__value">{summary.data.pending.length}</p>
                {summary.data.pending.length > 0 && <Link to={`${base}/memories?status=pending_approval`}>Review memories</Link>}
              </>
            ) : (
              <p className="field__hint">A managing family member approves memories.</p>
            )}
          </div>
          <div className="metric">
            <p className="metric__label">Notes waiting for review</p>
            {summary.data.open ? (
              <>
                <p className="metric__value">{summary.data.open.length}</p>
                {summary.data.open.length > 0 && <Link to={`${base}/observations`}>Review notes</Link>}
              </>
            ) : (
              <p className="field__hint">A managing family member reviews notes.</p>
            )}
          </div>
          <div className="metric">
            <p className="metric__label">Activities in the last 7 days</p>
            <p className="metric__value">{summary.data.analytics.totals.results}</p>
            <p className="field__hint">
              on {summary.data.analytics.completeness.days_with_activity} of {summary.data.analytics.completeness.days_elapsed} days
            </p>
            <Link to={`${base}/history`}>Activity history</Link>
          </div>
          <div className="metric">
            <p className="metric__label">May be worth reviewing</p>
            <p className="metric__value">{summary.data.analytics.review_flags.length}</p>
            {summary.data.analytics.review_flags.length > 0 ? (
              <ul className="plain-list">
                {summary.data.analytics.review_flags.slice(0, 3).map((f) => (
                  <li key={f.rule_id}>{f.title}</li>
                ))}
              </ul>
            ) : (
              <p className="field__hint">Nothing stands out this week.</p>
            )}
            <Link to={`${base}/analytics`}>Activity trends</Link>
          </div>
          <div className="metric">
            <p className="metric__label">Recent tiredness notes</p>
            {summary.data.fatigue.length === 0 ? (
              <p className="field__hint">None recorded.</p>
            ) : (
              <ul className="plain-list">
                {summary.data.fatigue.map((o) => (
                  <li key={o.id}>
                    <span className="field__hint">{formatDateTime(o.observed_at, patient.timezone)}</span>
                    <br />
                    {o.note}
                  </li>
                ))}
              </ul>
            )}
            <Link to={`${base}/observations`}>All observations</Link>
          </div>
        </div>
      )}
    </Card>
  )
}

export function CaregiverDashboardPage() {
  const patients = useAsync((signal) => listPatients(signal), [])
  return (
    <>
      <PageHeader title="Dashboard" lede="A calm overview of the people you care for." />
      {patients.status === 'error' && <ErrorState error={patients.error} onRetry={patients.reload} />}
      {patients.status === 'loading' && !patients.data && <Loading />}
      {patients.data?.length === 0 && (
        <EmptyState title="No one added yet">
          <p>Add the person you care for to start building their Memory Bank.</p>
          <Link to="/app/patients" className="button">
            Add a person
          </Link>
        </EmptyState>
      )}
      {patients.data?.map((p) => <PatientSummaryCard key={p.id} patient={p} />)}
    </>
  )
}
