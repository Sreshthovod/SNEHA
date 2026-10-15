import { useState } from 'react'
import type { AnalyticsSummary, DailyMetrics } from '../../api/types'
import { BASELINE_METRIC_LABELS, formatChange, formatMetric, num, pct, seconds } from '../../lib/analytics'
import { formatDate, formatDateTime } from '../../lib/dates'
import { Notice } from '../ui/States'
import { Table } from '../ui/Table'
import { Tabs } from '../ui/Tabs'
import { CompletenessWarning } from './CompletenessWarning'
import { ReviewFlagsPanel } from './ReviewFlagsPanel'

/** Accessible, neutral bar chart: one hue, values labelled, a table alternative alongside. */
function DailyChart({ title, data, value, format, max }: {
  title: string
  data: DailyMetrics[]
  value: (d: DailyMetrics) => number | null
  format: (v: number) => string
  max: number
}) {
  return (
    <figure className="chart" aria-label={title}>
      <figcaption className="chart__title">{title}</figcaption>
      <div className="chart__bars" role="list">
        {data.map((d) => {
          const v = d.has_data ? value(d) : null
          const pctHeight = v === null || max === 0 ? 0 : Math.max(2, (v / max) * 100)
          return (
            <div key={d.day} className="chart__bar" role="listitem" aria-label={`${formatDate(d.day)}: ${v === null ? 'no data' : format(v)}`}>
              <div className="chart__track" aria-hidden="true">
                <div className={v === null ? 'chart__fill chart__fill--empty' : 'chart__fill'} style={{ height: `${pctHeight}%` }} />
              </div>
              <span className="chart__value" aria-hidden="true">{v === null ? '–' : format(v)}</span>
              <span className="chart__label" aria-hidden="true">{d.day.slice(5)}</span>
            </div>
          )
        })}
      </div>
    </figure>
  )
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="metric">
      <p className="metric__label">{label}</p>
      <p className="metric__value">{value}</p>
      {hint && <p className="field__hint">{hint}</p>}
    </div>
  )
}

export function AnalyticsView({ analytics, observationsHref }: { analytics: AnalyticsSummary; observationsHref: string }) {
  const [view, setView] = useState('charts')
  const t = analytics.totals
  const maxResults = Math.max(1, ...analytics.daily.map((d) => d.results))
  const baseline = analytics.baseline
  const e = analytics.engagement

  const charts = (
    <div className="chart-grid">
      <DailyChart title="Activities per day" data={analytics.daily} value={(d) => d.results} format={(v) => String(v)} max={maxResults} />
      <DailyChart title="Share of answers correct, per day" data={analytics.daily} value={(d) => d.accuracy_mean} format={(v) => `${Math.round(v * 100)}%`} max={1} />
    </div>
  )
  const dailyTable = (
    <Table
      caption="Activity by day"
      rowKey={(r) => r.day}
      rows={analytics.daily}
      columns={[
        { header: 'Day', cell: (r) => formatDate(r.day) },
        { header: 'Activities', cell: (r) => (r.has_data ? r.results : 'No data'), numeric: true },
        { header: 'Stopped part-way', cell: (r) => (r.has_data ? r.interrupted : '—'), numeric: true },
        { header: 'Answers correct', cell: (r) => pct(r.accuracy_mean), numeric: true },
        { header: 'Typical time to answer', cell: (r) => seconds(r.median_response_ms), numeric: true },
        { header: 'Hints per activity', cell: (r) => num(r.hints_per_result), numeric: true },
      ]}
    />
  )

  return (
    <>
      <Notice tone="info" title="About these numbers">
        {analytics.disclaimer}
      </Notice>
      <CompletenessWarning completeness={analytics.completeness} />

      <h3>Summary</h3>
      <div className="summary-grid">
        <Metric label="Activities recorded" value={String(t.results)} hint={`on ${analytics.completeness.days_with_activity} of ${analytics.completeness.days_elapsed} days`} />
        <Metric label="Sessions completed" value={`${t.sessions_completed} of ${t.sessions_ended}`} hint={t.completion_rate === null ? 'No finished sessions' : `${pct(t.completion_rate)} completed`} />
        <Metric label="Stopped part-way" value={pct(t.interruption_rate)} hint={`${t.interrupted_results} activities; ${t.sessions_ended_for_fatigue} sessions ended to rest`} />
        <Metric label="Answers correct" value={pct(t.accuracy_mean)} hint={`from ${t.scored_results} scored activities`} />
        <Metric label="Typical time to answer" value={seconds(t.median_response_ms)} />
        <Metric label="Hints per activity" value={num(t.hints_per_result)} hint={t.share_results_with_hints === null ? undefined : `${pct(t.share_results_with_hints)} of activities used a hint`} />
        <Metric label="Typical session length" value={t.median_session_minutes === null ? '—' : `${num(t.median_session_minutes)} min`} />
        <Metric label="Enjoyment answers" value={`${e.enjoyed} enjoyed`} hint={`${e.neutral} it was OK · ${e.not_enjoyed} not really · ${e.unanswered} not answered`} />
      </div>

      {analytics.daily.some((d) => d.has_data) && (
        <Tabs
          label="Show daily activity as"
          selected={view}
          onSelect={setView}
          items={[
            { id: 'charts', label: 'Charts', content: charts },
            { id: 'table', label: 'Table', content: dailyTable },
          ]}
        />
      )}

      <h3>By activity</h3>
      {analytics.activities.length === 0 ? (
        <p>No activities in this period.</p>
      ) : (
        <Table
          caption="Activities in this period"
          rowKey={(r) => r.activity_id}
          rows={analytics.activities}
          columns={[
            { header: 'Activity', cell: (r) => r.title },
            { header: 'Times played', cell: (r) => r.results, numeric: true },
            { header: 'Finished', cell: (r) => r.completed, numeric: true },
            { header: 'Stopped part-way', cell: (r) => r.interrupted, numeric: true },
            { header: 'Answers correct', cell: (r) => pct(r.accuracy_mean), numeric: true },
            { header: 'Typical time', cell: (r) => seconds(r.median_response_ms), numeric: true },
            { header: 'Hints per activity', cell: (r) => num(r.hints_per_result), numeric: true },
            { header: 'Enjoyed', cell: (r) => r.enjoyed, numeric: true },
          ]}
        />
      )}

      <h3>Compared with their usual pattern</h3>
      {baseline.status === 'compared' ? (
        <>
          <p className="field__hint">
            Usual pattern: {formatDate(baseline.from_date)} – {formatDate(baseline.to_date)} ({baseline.results} activities over {baseline.days} days).
          </p>
          <Table
            caption="This period compared with their usual pattern"
            rowKey={(r) => r.metric}
            rows={baseline.comparisons}
            columns={[
              { header: 'Measure', cell: (r) => BASELINE_METRIC_LABELS[r.metric] ?? r.metric },
              { header: 'Usual', cell: (r) => formatMetric(r.metric, r.baseline), numeric: true },
              { header: 'This period', cell: (r) => formatMetric(r.metric, r.current), numeric: true },
              { header: 'Difference', cell: (r) => formatChange(r.metric, r.change), numeric: true },
            ]}
          />
        </>
      ) : (
        <p>
          Not enough earlier activity to compare yet. A comparison needs at least {baseline.required_results} activities
          over {baseline.required_days} days before this period; so far there are {baseline.results} over {baseline.days} days.
        </p>
      )}

      <ReviewFlagsPanel
        flags={analytics.review_flags}
        notEvaluated={analytics.rules_not_evaluated}
        observationsHref={observationsHref}
      />

      {analytics.context_observations.length > 0 && (
        <>
          <h3>Caregiver notes in this period</h3>
          <p className="field__hint">{analytics.context_observations.length} notes, shown for context.</p>
        </>
      )}

      <details className="details">
        <summary>How these numbers are worked out</summary>
        <ul>
          {analytics.methodology.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
        <p className="field__hint">
          Method {analytics.method_version} · settings {analytics.config_version} · prepared{' '}
          {formatDateTime(analytics.generated_at, analytics.timezone)}
        </p>
      </details>
    </>
  )
}
