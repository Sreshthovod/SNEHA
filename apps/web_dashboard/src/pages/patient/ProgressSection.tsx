import { getProgress } from '../../api/personalization'
import type { Recommendation } from '../../api/types'
import { Card } from '../../components/ui/Card'
import { EmptyState, ErrorState, Loading, Notice } from '../../components/ui/States'
import { Table } from '../../components/ui/Table'
import { useAsync } from '../../hooks/useAsync'
import { formatDateTime } from '../../lib/dates'
import { FALLBACK_LABELS, SUPPORT_KIND_LABELS, actionLabel, reasonLabel } from '../../lib/personalization'
import { usePatient } from '../../state/patient'

function RecommendationItem({ rec, timezone }: { rec: Recommendation; timezone: string }) {
  return (
    <li className="timeline__item">
      <p className="timeline__meta">{formatDateTime(rec.created_at, timezone)}</p>
      <p>
        <strong>{actionLabel(rec)}</strong>
        {rec.difficulty !== null && rec.action !== 'stop' && ` · level ${rec.difficulty}`}
        {rec.hints_enabled && ' · with hints'}
        {rec.break_minutes !== null && ` · rest for about ${rec.break_minutes} minutes`}
      </p>
      <p className="field__hint">Why:</p>
      <ul className="reason-list">
        {rec.reason_codes.map((code) => (
          <li key={code}>{reasonLabel(code)}</li>
        ))}
      </ul>
      {rec.supporting.length > 0 && (
        <details className="details">
          <summary>Based on {rec.supporting.length} stored record{rec.supporting.length === 1 ? '' : 's'}</summary>
          <ul>
            {rec.supporting.map((s) => (
              <li key={`${s.kind}-${s.id}`}>
                {SUPPORT_KIND_LABELS[s.kind] ?? s.kind}: {s.detail}
              </li>
            ))}
          </ul>
        </details>
      )}
      <p className="field__hint">
        {rec.fallback.used ? `Default choice: ${FALLBACK_LABELS[rec.fallback.reason ?? ''] ?? rec.fallback.reason}` : 'Chosen from their own history'} · rules{' '}
        {rec.algorithm_version}, settings {rec.config_version}
      </p>
    </li>
  )
}

export function ProgressSection() {
  const { patient, isClinician } = usePatient()
  const progress = useAsync((signal) => getProgress(patient.id, signal), [patient.id])
  if (progress.status === 'error' && !progress.data) return <ErrorState error={progress.error} onRetry={progress.reload} />
  if (!progress.data) return <Loading />
  const p = progress.data
  const played = p.activities.filter((a) => a.results > 0)

  return (
    <>
      <Card title="Progress & suggestions">
        <Notice tone="info">{p.disclaimer}</Notice>
        {isClinician && <p className="field__hint">Read only.</p>}
        {played.length === 0 ? (
          <EmptyState title="No activities recorded yet">
            <p>Levels and suggestions appear here once activities are played on the phone.</p>
          </EmptyState>
        ) : (
          <Table
            caption="Activity levels and participation"
            rowKey={(r) => r.activity_id}
            rows={played}
            columns={[
              { header: 'Activity', cell: (r) => r.title },
              { header: 'Level', cell: (r) => `Level ${r.current_difficulty} of ${r.max_difficulty}` },
              { header: 'Times played', cell: (r) => r.results, numeric: true },
              { header: 'Finished', cell: (r) => r.completed, numeric: true },
              { header: 'Stopped part-way', cell: (r) => r.interrupted, numeric: true },
              { header: 'Enjoyed / OK / not really', cell: (r) => `${r.enjoyed} / ${r.neutral} / ${r.not_enjoyed}` },
              { header: 'Said they were tired', cell: (r) => r.fatigue_reports, numeric: true },
              { header: 'Last played', cell: (r) => (r.last_played_at ? formatDateTime(r.last_played_at, patient.timezone) : '—') },
              { header: 'About the level', cell: (r) => reasonLabel(r.difficulty_reason) },
            ]}
          />
        )}
        <p className="field__hint">
          Rules version {p.algorithm_version} · settings {p.config_version}
        </p>
      </Card>
      <Card title="Recent suggestions">
        {p.recent_recommendations.length === 0 ? (
          <EmptyState title="No suggestions yet" />
        ) : (
          <ul className="timeline">
            {p.recent_recommendations.map((r) => (
              <RecommendationItem key={r.id} rec={r} timezone={patient.timezone} />
            ))}
          </ul>
        )}
      </Card>
    </>
  )
}
