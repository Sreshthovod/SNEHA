import { useState, type FormEvent } from 'react'
import {
  correctObservation,
  createObservation,
  deleteObservation,
  listObservations,
  listRevisions,
  resolveObservation,
  reviewObservation,
} from '../../api/observations'
import type { Observation, ObservationCategory, ObservationStatus } from '../../api/types'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Dialog } from '../../components/ui/Dialog'
import { SelectField, TextArea, TextField } from '../../components/ui/Field'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { ActionError, EmptyState, ErrorState, Loading, Notice } from '../../components/ui/States'
import { useAction, useAsync } from '../../hooks/useAsync'
import { formatDateTime, isoToLocalInput, localInputToIso, nowLocalInput } from '../../lib/dates'
import { OBSERVATION_LABELS, OBSERVATION_STATUS_LABELS, SOURCE_LABELS, options } from '../../lib/labels'
import { usePatient } from '../../state/patient'

/** Server 409 codes that mean "someone else changed this": reload and explain. */
const STALE_CODES: Record<string, string> = {
  version_conflict:
    'Someone else changed this note while you were working on it. The latest version is shown now; please check it and try again.',
  observation_resolved: 'This note has been resolved, so it can no longer be changed.',
  not_open: 'This note has already been reviewed.',
  already_resolved: 'This note is already resolved.',
}

type Mode = 'review' | 'correct' | 'resolve'

function ObservationDialog({
  mode,
  observation,
  onClose,
  onSaved,
}: {
  mode: Mode
  observation: Observation
  onClose: () => void
  onSaved: (staleMessage?: string) => void
}) {
  const { patient } = usePatient()
  const [note, setNote] = useState(mode === 'correct' ? observation.note : '')
  const [category, setCategory] = useState<ObservationCategory>(observation.category)
  const [when, setWhen] = useState(isoToLocalInput(observation.observed_at))
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const action = useAction(async () => {
    const v = observation.version
    if (mode === 'review') return reviewObservation(patient.id, observation.id, { expected_version: v, note: note.trim() || null })
    if (mode === 'resolve') return resolveObservation(patient.id, observation.id, { expected_version: v, note: note.trim() })
    const body: Parameters<typeof correctObservation>[2] = { expected_version: v, reason: reason.trim() }
    if (note.trim() !== observation.note) body.note = note.trim()
    if (category !== observation.category) body.category = category
    const iso = localInputToIso(when)
    if (new Date(iso).getTime() !== new Date(observation.observed_at).getTime()) body.observed_at = iso
    return correctObservation(patient.id, observation.id, body)
  })

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (mode === 'resolve' && !note.trim()) return setError('Write a short note about how this was resolved.')
    if (mode === 'correct') {
      if (!reason.trim()) return setError('Say briefly why this note is being corrected.')
      if (!note.trim()) return setError('The note cannot be empty.')
      if (note.trim() === observation.note && category === observation.category && when === isoToLocalInput(observation.observed_at))
        return setError('Nothing has been changed yet.')
    }
    const result = await action.run()
    if (result) onSaved()
  }

  const stale = action.error && action.error.status === 409 ? STALE_CODES[action.error.code] : undefined
  const titles: Record<Mode, string> = { review: 'Mark as reviewed', correct: 'Correct this note', resolve: 'Resolve this note' }

  return (
    <Dialog
      open
      title={titles[mode]}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="observation-dialog-form" pending={action.pending}>
            {titles[mode]}
          </Button>
        </>
      }
    >
      <form id="observation-dialog-form" onSubmit={onSubmit} noValidate>
        {mode === 'correct' ? (
          <>
            <SelectField label="About" value={category} onChange={(e) => setCategory(e.target.value as ObservationCategory)} options={options(OBSERVATION_LABELS)} />
            <TextField label="When" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
            <TextArea label="Note" value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} required />
            <TextField label="Reason for the correction" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} required hint="Kept in the note's history." />
          </>
        ) : (
          <TextArea
            label={mode === 'resolve' ? 'How was this resolved?' : 'Review note (optional)'}
            value={note}
            maxLength={1000}
            onChange={(e) => setNote(e.target.value)}
            required={mode === 'resolve'}
          />
        )}
        {error && <p className="field__error" role="alert">{error}</p>}
        {stale ? (
          <Notice tone="warning">
            <p>{stale}</p>
            <Button variant="secondary" onClick={() => onSaved(stale)}>Show the latest version</Button>
          </Notice>
        ) : (
          <ActionError error={action.error} />
        )}
      </form>
    </Dialog>
  )
}

function RevisionHistory({ observation }: { observation: Observation }) {
  const { patient } = usePatient()
  const revisions = useAsync((signal) => listRevisions(patient.id, observation.id, signal), [patient.id, observation.id, observation.version])
  if (revisions.status === 'error') return <ErrorState error={revisions.error} onRetry={revisions.reload} />
  if (!revisions.data) return <Loading label="Loading history…" />
  if (revisions.data.length === 0) return <p className="field__hint">No corrections have been made.</p>
  return (
    <ol className="plain-list" aria-label="Earlier versions">
      {revisions.data.map((r) => (
        <li key={r.id} className="timeline__item">
          <p className="timeline__meta">
            Version {r.version} · {OBSERVATION_LABELS[r.category]} · {formatDateTime(r.observed_at, patient.timezone)} · replaced{' '}
            {formatDateTime(r.created_at, patient.timezone)}
          </p>
          <p>{r.note}</p>
          {r.correction_reason && <p className="field__hint">Reason for correction: {r.correction_reason}</p>}
        </li>
      ))}
    </ol>
  )
}

function ObservationItem({ observation: o, onChanged }: { observation: Observation; onChanged: (msg?: string) => void }) {
  const { patient, me, isClinician, isManager } = usePatient()
  const [mode, setMode] = useState<Mode | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const remove = useAction((id: string) => deleteObservation(patient.id, id))
  const mine = o.author_id === me.id
  const tz = patient.timezone
  const label = `${OBSERVATION_LABELS[o.category]} note from ${formatDateTime(o.observed_at, tz)}`

  return (
    <li className="timeline__item">
      <p className="timeline__meta">
        <strong>{OBSERVATION_LABELS[o.category]}</strong>
        <StatusBadge tone={o.status === 'open' ? 'warning' : o.status === 'resolved' ? 'success' : 'neutral'} label={OBSERVATION_STATUS_LABELS[o.status]} />
        {' '}· noticed {formatDateTime(o.observed_at, tz)} · {mine ? 'by you' : 'by another caregiver'}
      </p>
      <p>{o.note}</p>
      <p className="field__hint">
        {SOURCE_LABELS[o.source]} · recorded {formatDateTime(o.created_at, tz)}
        {o.updated_at && o.version > 1 && ` · corrected ${formatDateTime(o.updated_at, tz)} (version ${o.version})`}
        {o.reviewed_at && ` · reviewed ${formatDateTime(o.reviewed_at, tz)}${o.reviewed_by_id === me.id ? ' by you' : ''}`}
        {o.resolved_at && ` · resolved ${formatDateTime(o.resolved_at, tz)}${o.resolved_by_id === me.id ? ' by you' : ''}`}
      </p>
      {o.review_note && <p className="field__hint">Review note: {o.review_note}</p>}
      {o.resolution_note && <p className="field__hint">Resolution: {o.resolution_note}</p>}
      <div className="observation-actions">
        {!isClinician && isManager && o.status === 'open' && (
          <Button variant="secondary" onClick={() => setMode('review')} aria-label={`Mark as reviewed: ${label}`}>Mark reviewed</Button>
        )}
        {!isClinician && (mine || isManager) && o.status !== 'resolved' && (
          <Button variant="secondary" onClick={() => setMode('correct')} aria-label={`Correct: ${label}`}>Correct</Button>
        )}
        {!isClinician && isManager && o.status !== 'resolved' && (
          <Button variant="secondary" onClick={() => setMode('resolve')} aria-label={`Resolve: ${label}`}>Resolve</Button>
        )}
        <Button variant="ghost" aria-expanded={showHistory} onClick={() => setShowHistory((v) => !v)} aria-label={`History: ${label}`}>
          {showHistory ? 'Hide history' : 'History'}
        </Button>
        {!isClinician && (mine || isManager) && (
          <Button
            variant="ghost"
            onClick={async () => {
              await remove.run(o.id)
              onChanged()
            }}
            disabled={remove.pending}
            aria-label={`Delete: ${label}`}
          >
            Delete
          </Button>
        )}
      </div>
      <ActionError error={remove.error} />
      {showHistory && <RevisionHistory observation={o} />}
      {mode && (
        <ObservationDialog
          mode={mode}
          observation={o}
          onClose={() => setMode(null)}
          onSaved={(stale) => {
            setMode(null)
            onChanged(stale)
          }}
        />
      )}
    </li>
  )
}

export function ObservationsSection() {
  const { patient, isClinician } = usePatient()
  const [statusFilter, setStatusFilter] = useState<'' | ObservationStatus>('')
  const observations = useAsync(
    (signal) => listObservations(patient.id, { limit: 100, status: statusFilter || undefined }, signal),
    [patient.id, statusFilter],
  )
  const [form, setForm] = useState({ category: 'fatigue' as ObservationCategory, note: '', observed_at: nowLocalInput() })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const create = useAction((body: Parameters<typeof createObservation>[1]) => createObservation(patient.id, body))

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const next: Record<string, string> = {}
    if (!form.note.trim()) next.note = 'Write a short note about what you noticed.'
    if (!form.observed_at) next.observed_at = 'Choose when you noticed this.'
    else if (new Date(form.observed_at).getTime() > Date.now() + 5 * 60_000)
      next.observed_at = 'This time is in the future.'
    setErrors(next)
    setSaved(false)
    if (Object.keys(next).length) return
    const result = await create.run({
      category: form.category,
      note: form.note.trim(),
      observed_at: localInputToIso(form.observed_at),
    })
    if (result) {
      setForm((f) => ({ ...f, note: '' }))
      setSaved(true)
      observations.reload()
    }
  }

  return (
    <>
      {!isClinician && (
        <Card title="Add an observation">
          <p className="field__hint">
            Describe what you noticed in everyday words, such as tiredness after lunch or a good
            mood after a visit. Observations are notes, not medical assessments. Tiredness notes
            also make activity suggestions gentler for a few hours.
          </p>
          <form onSubmit={onSubmit} noValidate>
            <SelectField label="About" value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value as ObservationCategory }))} options={options(OBSERVATION_LABELS)} />
            <TextField label="When" type="datetime-local" value={form.observed_at} onChange={(e) => setForm((f) => ({ ...f, observed_at: e.target.value }))} error={errors.observed_at} required />
            <TextArea label="Note" value={form.note} maxLength={2000} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} error={errors.note} required />
            <ActionError error={create.error} />
            {saved && <Notice tone="success">Observation saved.</Notice>}
            <Button type="submit" pending={create.pending}>Save observation</Button>
          </form>
        </Card>
      )}
      <Card title="Observations">
        <SelectField
          label="Show"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as '' | ObservationStatus)}
          options={[{ value: '', label: 'All notes' }, ...options(OBSERVATION_STATUS_LABELS).map((o) => ({ ...o, label: `${o.label} only` }))]}
        />
        {isClinician && <p className="field__hint">You can read these notes. Only the family can change them.</p>}
        {notice && <Notice tone="warning">{notice}</Notice>}
        {observations.status === 'error' && <ErrorState error={observations.error} onRetry={observations.reload} />}
        {observations.status === 'loading' && !observations.data && <Loading />}
        {observations.data?.length === 0 && <EmptyState title={statusFilter ? 'No notes with this status' : 'No observations yet'} />}
        <ul className="timeline">
          {observations.data?.map((o) => (
            <ObservationItem
              key={`${o.id}-${o.version}-${o.status}`}
              observation={o}
              onChanged={(msg) => {
                setNotice(msg ?? null)
                observations.reload()
              }}
            />
          ))}
        </ul>
      </Card>
    </>
  )
}
