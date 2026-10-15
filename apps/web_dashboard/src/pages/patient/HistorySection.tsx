import { useState } from 'react'
import { listActivities, listResults, listSessions } from '../../api/activities'
import type { Activity, Session } from '../../api/types'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState, ErrorState, Loading } from '../../components/ui/States'
import { Table } from '../../components/ui/Table'
import { useAsync } from '../../hooks/useAsync'
import { formatDateTime, formatDuration } from '../../lib/dates'
import { usePatient } from '../../state/patient'

const END_LABELS: Record<string, string> = {
  completed: 'Finished',
  user_stopped: 'Stopped by choice',
  fatigue_detected: 'Ended early to rest',
  timeout: 'Timed out',
}

export function HistorySection() {
  const { patient } = usePatient()
  const sessions = useAsync((signal) => listSessions(patient.id, 100, signal), [patient.id])
  const catalog = useAsync((signal) => listActivities(signal), [])
  const activities = new Map((catalog.data ?? []).map((a) => [a.id, a]))

  return (
    <Card title="Activity history">
      <p className="field__hint">Sessions recorded on the phone appear here after it syncs.</p>
      {sessions.status === 'error' && <ErrorState error={sessions.error} onRetry={sessions.reload} />}
      {sessions.status === 'loading' && !sessions.data && <Loading />}
      {sessions.data?.length === 0 && <EmptyState title="No activity sessions yet" />}
      <ul className="plain-list">
        {sessions.data?.map((s) => (
          <li key={s.id}>
            <SessionRow session={s} activities={activities} timezone={patient.timezone} />
          </li>
        ))}
      </ul>
    </Card>
  )
}

function SessionRow({
  session,
  activities,
  timezone,
}: {
  session: Session
  activities: Map<string, Activity>
  timezone: string
}) {
  const { patient } = usePatient()
  const [open, setOpen] = useState(false)
  const status =
    session.status === 'in_progress'
      ? 'In progress'
      : END_LABELS[session.end_reason ?? 'completed'] ?? 'Ended'
  return (
    <div className="session-row">
      <div className="session-row__summary">
        <span>
          <strong>{formatDateTime(session.started_at, timezone)}</strong> · {status}
        </span>
        <Button variant="secondary" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          {open ? 'Hide activities' : 'Show activities'}
        </Button>
      </div>
      {open && <SessionResults patientId={patient.id} sessionId={session.id} activities={activities} />}
    </div>
  )
}

function SessionResults({
  patientId,
  sessionId,
  activities,
}: {
  patientId: string
  sessionId: string
  activities: Map<string, Activity>
}) {
  const results = useAsync((signal) => listResults(patientId, sessionId, signal), [patientId, sessionId])
  if (results.status === 'error') return <ErrorState error={results.error} onRetry={results.reload} />
  if (!results.data) return <Loading />
  if (results.data.length === 0) return <p className="field__hint">No activities recorded in this session.</p>
  return (
    <Table
      caption="Activities in this session"
      rowKey={(r) => r.id}
      rows={results.data}
      columns={[
        { header: 'Activity', cell: (r) => activities.get(r.activity_id)?.title ?? 'Activity' },
        { header: 'Level', cell: (r) => r.difficulty_level, numeric: true },
        { header: 'Correct', cell: (r) => `${r.correct_count} of ${r.attempt_count}`, numeric: true },
        { header: 'Hints', cell: (r) => r.hint_count, numeric: true },
        { header: 'Time', cell: (r) => formatDuration(r.duration_ms), numeric: true },
        { header: 'Finished', cell: (r) => (r.abandoned ? 'Stopped early' : 'Yes') },
      ]}
    />
  )
}
