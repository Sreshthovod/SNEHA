import { Link } from 'react-router-dom'
import { getAnalytics } from '../api/analytics'
import { listPatients } from '../api/patients'
import { listReports, reportPdfAvailable } from '../api/reports'
import type { Patient } from '../api/types'
import { CompletenessWarning } from '../components/analytics/CompletenessWarning'
import { PdfDownloadButton } from '../components/PdfDownloadButton'
import { Card } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { EmptyState, ErrorState, Loading } from '../components/ui/States'
import { useAsync } from '../hooks/useAsync'
import { pct, seconds } from '../lib/analytics'
import { addDays, formatDate, todayInZone } from '../lib/dates'
import { reportDates } from '../lib/reports'

const WINDOW_DAYS = 9

function ClinicianPatientCard({ patient }: { patient: Patient }) {
  const today = todayInZone(patient.timezone)
  const data = useAsync(
    async (signal) => {
      const [analytics, reports] = await Promise.all([
        getAnalytics(patient.id, addDays(today, -(WINDOW_DAYS - 1)), today, signal),
        listReports(patient.id, signal),
      ])
      return { analytics, latestReady: reports.find(reportPdfAvailable) ?? null }
    },
    [patient.id, today],
  )
  const base = `/app/patients/${patient.id}`
  const a = data.data?.analytics
  const latest = data.data?.latestReady
  const latestDates = latest ? reportDates(latest.period_start, latest.period_end, patient.timezone) : null
  return (
    <Card title={patient.display_name}>
      {data.status === 'error' && <ErrorState error={data.error} onRetry={data.reload} />}
      {!data.data && data.status === 'loading' && <Loading />}
      {a && (
        <>
          <p className="field__hint">Last {WINDOW_DAYS} days, descriptive only.</p>
          <dl className="definition-list">
            <dt>Activities recorded</dt>
            <dd>{a.totals.results}</dd>
            <dt>Days with activity</dt>
            <dd>
              {a.completeness.days_with_activity} of {a.completeness.days_elapsed}
            </dd>
            <dt>Sessions completed</dt>
            <dd>
              {a.totals.sessions_completed} of {a.totals.sessions_ended}
            </dd>
            <dt>Sessions ended early for tiredness</dt>
            <dd>{a.totals.sessions_ended_for_fatigue}</dd>
            <dt>Answers correct</dt>
            <dd>{pct(a.totals.accuracy_mean)}</dd>
            <dt>Typical time to answer</dt>
            <dd>{seconds(a.totals.median_response_ms)}</dd>
            <dt>May be worth reviewing</dt>
            <dd>
              {a.review_flags.length === 0 ? 'Nothing stands out' : a.review_flags.map((f) => f.title).join('; ')}
            </dd>
          </dl>
          <CompletenessWarning completeness={a.completeness} />
          {latest && latestDates ? (
            <div>
              <p>
                Latest report: {formatDate(latestDates.from)} – {formatDate(latestDates.to)}
              </p>
              <PdfDownloadButton report={latest} fileName={`sneha-report-${latestDates.from}-to-${latestDates.to}.pdf`} />
            </div>
          ) : (
            <p className="field__hint">No ready report yet.</p>
          )}
          <p className="link-row">
            <Link to={`${base}/analytics`}>Activity trends</Link>
            <Link to={`${base}/reports`}>Reports</Link>
            <Link to={`${base}/observations`}>Observations</Link>
            <Link to={`${base}/progress`}>Progress</Link>
          </p>
        </>
      )}
    </Card>
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
