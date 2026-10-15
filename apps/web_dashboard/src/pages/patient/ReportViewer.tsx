import { Link, useParams } from 'react-router-dom'
import { getAnalytics } from '../../api/analytics'
import { getReport } from '../../api/reports'
import { AnalyticsView } from '../../components/analytics/AnalyticsView'
import { PdfDownloadButton } from '../../components/PdfDownloadButton'
import { RetryReportButton } from '../../components/RetryReportButton'
import { Card } from '../../components/ui/Card'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { ErrorState, Loading, Notice } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { formatDate, formatDateTime } from '../../lib/dates'
import { REPORT_STATUS_LABELS } from '../../lib/labels'
import { reportDates } from '../../lib/reports'
import { usePatient } from '../../state/patient'

/** Longitudinal report viewer: report metadata, PDF download and the analytics for its period. */
export function ReportViewer() {
  const { reportId = '' } = useParams()
  const { patient } = usePatient()
  const data = useAsync(
    async (signal) => {
      const report = await getReport(patient.id, reportId, signal)
      const dates = reportDates(report.period_start, report.period_end, patient.timezone)
      const analytics = await getAnalytics(patient.id, dates.from, dates.to, signal)
      return { report, dates, analytics }
    },
    [patient.id, reportId],
  )
  if (data.status === 'error' && !data.data) return <ErrorState error={data.error} onRetry={data.reload} />
  if (!data.data) return <Loading />
  const { report, dates, analytics } = data.data
  return (
    <Card title={`Report: ${formatDate(dates.from)} – ${formatDate(dates.to)}`}>
      <p>
        <Link to="..">← All reports</Link>
      </p>
      <dl className="definition-list">
        <dt>Status</dt>
        <dd>
          <StatusBadge tone={report.status === 'ready' ? 'success' : report.status === 'failed' ? 'warning' : 'neutral'} label={REPORT_STATUS_LABELS[report.status]} />
        </dd>
        <dt>Requested</dt>
        <dd>{formatDateTime(report.created_at, patient.timezone)}</dd>
        {report.generated_at && (
          <>
            <dt>Prepared</dt>
            <dd>{formatDateTime(report.generated_at, patient.timezone)}</dd>
          </>
        )}
        {report.method_version && (
          <>
            <dt>Method</dt>
            <dd>{report.method_version}</dd>
          </>
        )}
      </dl>
      {report.status === 'failed' && (
        <Notice tone="warning" title="This report could not be prepared">
          {report.error_message ?? 'Please try again.'}
        </Notice>
      )}
      <div className="link-row">
        <PdfDownloadButton report={report} fileName={`sneha-report-${dates.from}-to-${dates.to}.pdf`} />
        <RetryReportButton report={report} onDone={() => data.reload()} />
      </div>
      <h3>Activity summary for this period</h3>
      <AnalyticsView analytics={analytics} observationsHref={`/app/patients/${patient.id}/observations`} />
    </Card>
  )
}
