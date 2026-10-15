import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { listReports, requestReport } from '../../api/reports'
import type { Report } from '../../api/types'
import { PdfDownloadButton } from '../../components/PdfDownloadButton'
import { RetryReportButton } from '../../components/RetryReportButton'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { SelectField, TextField } from '../../components/ui/Field'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { ActionError, EmptyState, ErrorState, Loading, Notice } from '../../components/ui/States'
import { Table } from '../../components/ui/Table'
import { useAction, useAsync } from '../../hooks/useAsync'
import { addDays, formatDate, todayInZone } from '../../lib/dates'
import { REPORT_STATUS_LABELS } from '../../lib/labels'
import { reportDates } from '../../lib/reports'
import { usePatient } from '../../state/patient'

function fileName(report: Report, timezone: string): string {
  const d = reportDates(report.period_start, report.period_end, timezone)
  return `sneha-report-${d.from}-to-${d.to}.pdf`
}

export function ReportsSection() {
  const { patient } = usePatient()
  const today = todayInZone(patient.timezone)
  const reports = useAsync((signal) => listReports(patient.id, signal), [patient.id])
  const [length, setLength] = useState('9')
  const [start, setStart] = useState(addDays(today, -8))
  const [latest, setLatest] = useState<Report | null>(null)
  const action = useAction((body: { period_start: string; period_end: string }) => requestReport(patient.id, body))
  const end = start ? addDays(start, Number(length) - 1) : ''

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setLatest(null)
    const result = await action.run({ period_start: start, period_end: end })
    if (result) {
      setLatest(result)
      reports.reload()
    }
  }

  return (
    <>
      <Card title="Request a summary report">
        <p className="field__hint">
          Reports cover 8 or 9 days and describe activity; they do not assess health. The PDF is prepared straight away.
        </p>
        <form onSubmit={onSubmit} noValidate className="inline-fields">
          <TextField label="First day" type="date" value={start} max={today} onChange={(e) => setStart(e.target.value)} required />
          <SelectField label="Length" value={length} onChange={(e) => setLength(e.target.value)} options={[{ value: '8', label: '8 days' }, { value: '9', label: '9 days' }]} />
          <p className="field__hint">Last day: {end ? formatDate(end) : '—'}</p>
          <Button type="submit" pending={action.pending} disabled={!start}>Request report</Button>
        </form>
        <ActionError error={action.error} />
        {latest?.status === 'ready' && (
          <Notice tone="success" title="Report ready">
            <p>The PDF has been prepared. <Link to={latest.id}>View the report</Link></p>
            <PdfDownloadButton report={latest} fileName={fileName(latest, patient.timezone)} />
          </Notice>
        )}
        {latest && latest.status !== 'ready' && (
          <Notice tone="warning" title="The report could not be prepared">
            <p>{latest.error_message ?? 'Please try again.'}</p>
            <RetryReportButton
              report={latest}
              onDone={(r) => {
                setLatest(r)
                reports.reload()
              }}
            />
          </Notice>
        )}
      </Card>
      <Card title="Reports">
        {reports.status === 'error' && <ErrorState error={reports.error} onRetry={reports.reload} />}
        {reports.status === 'loading' && !reports.data && <Loading />}
        {reports.data?.length === 0 && <EmptyState title="No reports yet" />}
        {reports.data && reports.data.length > 0 && (
          <Table
            caption="Reports"
            captionHidden
            rowKey={(r) => r.id}
            rows={reports.data}
            columns={[
              {
                header: 'Period',
                cell: (r) => {
                  const d = reportDates(r.period_start, r.period_end, patient.timezone)
                  return `${formatDate(d.from)} – ${formatDate(d.to)}`
                },
              },
              {
                header: 'Status',
                cell: (r) => (
                  <StatusBadge
                    tone={r.status === 'ready' ? 'success' : r.status === 'failed' ? 'warning' : 'neutral'}
                    label={REPORT_STATUS_LABELS[r.status]}
                  />
                ),
              },
              { header: 'Prepared by', cell: (r) => (r.automated ? 'Automatic' : 'On request') },
              { header: 'Open', cell: (r) => <Link to={r.id}>View report</Link> },
            ]}
          />
        )}
      </Card>
    </>
  )
}
