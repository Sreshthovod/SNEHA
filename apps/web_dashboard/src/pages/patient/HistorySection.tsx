import { useState } from 'react'
import { listActivities, listResults, listSessionEvents, listSessions } from '../../api/activities'
import type { Activity, Session } from '../../api/types'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { EmptyState, ErrorState, Loading } from '../../components/ui/States'
import { Table } from '../../components/ui/Table'
import { useAsync } from '../../hooks/useAsync'
import { addDays, dateInZone, formatDate, formatDateTime, formatDuration } from '../../lib/dates'
import { listMemories } from '../../api/memories'
import { describeEvent } from '../../lib/labels'
import { usePatient } from '../../state/patient'

const INITIAL_COUNT = 20

/** Monday of the week that contains `day` (YYYY-MM-DD). */
function weekStart(day: string): string {
  const d = new Date(`${day}T00:00:00Z`)
  const offset = (d.getUTCDay() + 6) % 7
  return addDays(day, -offset)
}

function groupByWeek(sessions: Session[], timezone: string): Array<{ start: string; sessions: Session[] }> {
  const groups: Array<{ start: string; sessions: Session[] }> = []
  for (const s of sessions) {
    const start = weekStart(dateInZone(new Date(s.started_at), timezone))
    const last = groups[groups.length - 1]
    if (last && last.start === start) last.sessions.push(s)
    else groups.push({ start, sessions: [s] })
  }
  return groups
}

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
  const [showAll, setShowAll] = useState(false)
  const all = sessions.data ?? []
  const visible = showAll ? all : all.slice(0, INITIAL_COUNT)
  const weeks = groupByWeek(visible, patient.timezone)

  return (
    <Card title="Activity history">
      <p className="field__hint">Sessions recorded on the phone appear here after it syncs. Newest first, grouped by week.</p>
      {sessions.status === 'error' && <ErrorState error={sessions.error} onRetry={sessions.reload} />}
      {sessions.status === 'loading' && !sessions.data && <Loading />}
      {sessions.data?.length === 0 && (
        <EmptyState title="No activity sessions yet">
          <p>Sessions appear here after the phone app has been used and has synced.</p>
        </EmptyState>
      )}
      {weeks.map((w) => (
        <section key={w.start} className="history-week" aria-labelledby={`week-${w.start}`}>
          <h3 id={`week-${w.start}`} className="history-week__title">
            Week of {formatDate(w.start)} · {w.sessions.length} {w.sessions.length === 1 ? 'session' : 'sessions'}
          </h3>
          <ul className="plain-list">
            {w.sessions.map((s) => (
              <li key={s.id}>
                <SessionRow session={s} activities={activities} timezone={patient.timezone} />
              </li>
            ))}
          </ul>
        </section>
      ))}
      {all.length > INITIAL_COUNT && (
        <div className="form-actions">
          <Button variant="secondary" aria-expanded={showAll} onClick={() => setShowAll((v) => !v)}>
            {showAll ? 'Show fewer sessions' : `Show earlier sessions (${all.length - INITIAL_COUNT} more)`}
          </Button>
        </div>
      )}
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
  const [timeline, setTimeline] = useState(false)
  const status =
    session.status === 'in_progress'
      ? 'In progress'
      : END_LABELS[session.end_reason ?? 'completed'] ?? 'Ended'
  return (
    <div className="session-row">
      <div className="session-row__summary">
        <span className="session-row__when">
          <strong>{formatDateTime(session.started_at, timezone)}</strong>
          <StatusBadge tone={session.status === 'in_progress' ? 'info' : 'neutral'} label={status} />
        </span>
        <Button variant="secondary" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          {open ? 'Hide activities' : 'Show activities'}
        </Button>
        <Button variant="ghost" aria-expanded={timeline} onClick={() => setTimeline((v) => !v)}>
          {timeline ? 'Hide what happened' : 'What happened'}
        </Button>
      </div>
      {(open || timeline) && (
        <div className="session-row__detail">
          {open && <SessionResults patientId={patient.id} sessionId={session.id} activities={activities} />}
          {timeline && <SessionTimeline patientId={patient.id} sessionId={session.id} timezone={timezone} />}
        </div>
      )}
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

/** Every recorded step of the session, including what the app changed and why. */
function SessionTimeline({ patientId, sessionId, timezone }: { patientId: string; sessionId: string; timezone: string }) {
  const { isClinician } = usePatient()
  // Titles for memory references; clinicians have no Memory Bank access, so they see
  // "a family memory" instead.
  const titles = useAsync(
    (signal) => (isClinician ? Promise.resolve([]) : listMemories(patientId, 'approved', signal)),
    [patientId, isClinician],
  )
  const titleOf = (id: string) => titles.data?.find((m) => m.id === id)?.title
  const events = useAsync((signal) => listSessionEvents(patientId, sessionId, signal), [patientId, sessionId])
  if (events.status === 'error') return <ErrorState error={events.error} onRetry={events.reload} />
  if (!events.data) return <Loading />
  if (events.data.length === 0)
    return <p className="field__hint">No step-by-step record for this session (recorded by an older app version, or not synced yet).</p>
  return (
    <ol className="timeline" aria-label="What happened in this session">
      {events.data.map((e) => (
        <li key={e.id} className={e.event_type === 'adaptation' || e.event_type === 'fatigue_reported' ? 'timeline__item timeline__item--notable' : 'timeline__item'}>
          <span className="field__hint">{formatDateTime(e.occurred_at, timezone)}{e.round_index !== null ? ` · round ${e.round_index + 1}` : ''}</span>
          <br />
          {describeEvent(e, titleOf)}
        </li>
      ))}
    </ol>
  )
}
