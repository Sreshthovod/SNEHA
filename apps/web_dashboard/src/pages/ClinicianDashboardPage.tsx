import { Link } from 'react-router-dom'
import { getAnalytics } from '../api/analytics'
import { listPatients } from '../api/patients'
import { listReports, reportPdfAvailable } from '../api/reports'
import { listReviewItems } from '../api/review'
import type { Patient } from '../api/types'
import { CompletenessWarning } from '../components/analytics/CompletenessWarning'
import { PdfDownloadButton } from '../components/PdfDownloadButton'
import { PageHeader } from '../components/ui/PageHeader'
import { EmptyState, ErrorState, Loading } from '../components/ui/States'
import { useAsync } from '../hooks/useAsync'
import { pct, seconds } from '../lib/analytics'
import { addDays, formatDate, todayInZone } from '../lib/dates'
import { initials } from '../lib/people'
import { reportDates } from '../lib/reports'

const WINDOW_DAYS = 9

function ClinicianPatientCard({ patient }: { patient: Patient }) {
  const today = todayInZone(patient.timezone)
  const data = useAsync(
    async (signal) => {
      const [analytics, reports, confirmed] = await Promise.all([
        getAnalytics(patient.id, addDays(today, -(WINDOW_DAYS - 1)), today, signal),
        listReports(patient.id, signal),
        listReviewItems(patient.id, 'confirmed', signal),
      ])
      return { analytics, confirmed, latestReady: reports.find(reportPdfAvailable) ?? null }
    },
    [patient.id, today],
  )
  const base = `/app/patients/${patient.id}`
  const a = data.data?.analytics
  const latest = data.data?.latestReady
  const latestDates = latest ? reportDates(latest.period_start, latest.period_end, patient.timezone) : null
  return (
    <section className="card person-summary" aria-labelledby={`clinician-person-${patient.id}`}>
      <div className="person-summary__header">
        <div className="person-summary__identity">
          <span className="app-user__avatar" aria-hidden="true">
            {initials(patient.display_name)}
          </span>
          <div>
            <h2 id={`clinician-person-${patient.id}`}>
              <Link to={base}>{patient.display_name}</Link>
            </h2>
            <p className="person-card__meta">Last {WINDOW_DAYS} days · descriptive only</p>
          </div>
        </div>
      </div>
      {data.status === 'error' && <ErrorState error={data.error} onRetry={data.reload} />}
      {!data.data && data.status === 'loading' && <Loading />}
      {a && (
        <>
          <div className="person-summary__grid">
            <div className="metric">
              <p className="metric__label">Activities recorded</p>
              <p className="metric__value">{a.totals.results}</p>
              <p className="field__hint">
                on {a.completeness.days_with_activity} of {a.completeness.days_elapsed} days
              </p>
            </div>
            <div className="metric">
              <p className="metric__label">Sessions completed</p>
              <p className="metric__value">
                {a.totals.sessions_completed} of {a.totals.sessions_ended}
              </p>
            </div>
            <div className="metric">
              <p className="metric__label">Sessions ended early for tiredness</p>
              <p className="metric__value">{a.totals.sessions_ended_for_fatigue}</p>
            </div>
          </div>
          <CompletenessWarning completeness={a.completeness} />
          <dl className="definition-list">
            <dt>Answers correct</dt>
            <dd>{pct(a.totals.accuracy_mean)} <span className="field__hint">(across all activities in the period; see Activity trends for their usual pattern)</span></dd>
            <dt>Typical time to answer</dt>
            <dd>{seconds(a.totals.median_response_ms)}</dd>
            <dt>Confirmed by the family for discussion</dt>
            <dd>
              {data.data?.confirmed.length ? (
                <ul className="attention-list">
                  {data.data.confirmed.map((i) => (
                    <li key={i.id}>{i.title}</li>
                  ))}
                </ul>
              ) : (
                'Nothing confirmed. Automated prompts are shared only after a caregiver confirms them.'
              )}
            </dd>
          </dl>
          <div className="report-row">
            {latest && latestDates ? (
              <>
                <p>
                  Latest report: {formatDate(latestDates.from)} – {formatDate(latestDates.to)}
                </p>
                <PdfDownloadButton report={latest} fileName={`sneha-report-${latestDates.from}-to-${latestDates.to}.pdf`} />
              </>
            ) : (
              <p className="field__hint">No ready report yet.</p>
            )}
          </div>
          <nav className="link-row link-row--buttons" aria-label={`Open ${patient.display_name}'s record`}>
            <Link className="button button--secondary" to={`${base}/analytics`}>Activity trends</Link>
            <Link className="button button--secondary" to={`${base}/reports`}>Reports</Link>
            <Link className="button button--secondary" to={`${base}/observations`}>Observations</Link>
            <Link className="button button--secondary" to={`${base}/progress`}>Progress</Link>
          </nav>
        </>
      )}
    </section>
  )
}

export function ClinicianDashboardPage() {
  const patients = useAsync((signal) => listPatients(signal), [])
  return (
    <>
      <PageHeader
        title="My patients"
        lede="Only patients whose families have granted you access, with consent in place, appear here."
      />
      {patients.status === 'error' && <ErrorState error={patients.error} onRetry={patients.reload} />}
      {patients.status === 'loading' && !patients.data && <Loading />}
      {patients.data?.length === 0 && (
        <EmptyState title="No shared patients">
          <p>
            A family member can share a record with you from their SNEHA dashboard. New clinician
            accounts must be verified first.
          </p>
        </EmptyState>
      )}
      {patients.data?.map((p) => <ClinicianPatientCard key={p.id} patient={p} />)}
    </>
  )
}
