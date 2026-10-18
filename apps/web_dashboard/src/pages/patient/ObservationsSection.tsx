import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  correctObservation,
  createObservation,
  deleteObservation,
  getFatigueDelivery,
  listObservations,
  listRevisions,
  resolveObservation,
  reviewObservation,
} from '../../api/observations'
import type { FatigueDeliveryItem, FatigueLevel, Observation, ObservationCategory, ObservationStatus } from '../../api/types'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Dialog } from '../../components/ui/Dialog'
import { SelectField, TextArea, TextField } from '../../components/ui/Field'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { ActionError, EmptyState, ErrorState, Loading, Notice } from '../../components/ui/States'
import { useAction, useAsync } from '../../hooks/useAsync'
import { formatDateTime, isoToLocalInput, localInputToIso, nowLocalInput } from '../../lib/dates'
import {
  FATIGUE_LEVEL_LABELS,
  OBSERVATION_LABELS,
  OBSERVATION_STATUS_LABELS,
  SOURCE_LABELS,
  options,
} from '../../lib/labels'
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

const DELIVERY_TEXT: Record<FatigueDeliveryItem['status'], string> = {
  sent: 'On the phone',
  waiting: 'Waiting for the phone to sync. Until then the phone does not know about this note.',
  no_phone: 'No phone is paired, so this note only affects suggestions made online.',
  from_phone: 'Reported on the phone, where it applied straight away.',
}

/** Honest status of a tiredness note on the patient's phone. */
function DeliveryLine({ item, timezone }: { item?: FatigueDeliveryItem; timezone: string }) {
  if (!item) return null
  const text =
    item.status === 'sent' && item.sent_at
      ? `${DELIVERY_TEXT.sent} (the phone last synced ${formatDateTime(item.sent_at, timezone)}).`
      : DELIVERY_TEXT[item.status]
  return (
    <p className="field__hint" data-testid={`delivery-${item.observation_id}`}>
      <StatusBadge tone={item.status === 'waiting' ? 'warning' : 'neutral'} label={item.status === 'waiting' ? 'Not on the phone yet' : 'Phone'} />{' '}
      {text}
    </p>
  )
}

function ObservationItem({
  observation: o,
  delivery,
  onChanged,
}: {
  observation: Observation
  delivery?: FatigueDeliveryItem
  onChanged: (msg?: string) => void
}) {
  const { patient, me, isClinician, isManager } = usePatient()
  const [mode, setMode] = useState<Mode | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
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
      {o.fatigue_level && <p className="field__hint">Level: {FATIGUE_LEVEL_LABELS[o.fatigue_level]}</p>}
      {o.category === 'fatigue' && <DeliveryLine item={delivery} timezone={tz} />}
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
          <>
            <span className="observation-actions__spacer" aria-hidden="true" />
            <Button
              variant="danger-outline"
              onClick={() => setConfirmDelete(true)}
              disabled={remove.pending}
              aria-label={`Delete: ${label}`}
            >
              Delete
            </Button>
          </>
        )}
      </div>
      <Dialog
        open={confirmDelete}
        title="Delete this note?"
        onClose={() => setConfirmDelete(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmDelete(false)}>Cancel</Button>
            <Button
              variant="danger"
              pending={remove.pending}
              onClick={async () => {
                await remove.run(o.id)
                setConfirmDelete(false)
                onChanged()
              }}
            >
              Delete note
            </Button>
          </>
        }
      >
        <p>{label} will be removed. This cannot be undone.</p>
      </Dialog>
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
  const [params] = useSearchParams()
  const [statusFilter, setStatusFilter] = useState<'' | ObservationStatus>(() => {
    const s = params.get('status')
    return s && s in OBSERVATION_STATUS_LABELS ? (s as ObservationStatus) : ''
  })
  const observations = useAsync(
    (signal) => listObservations(patient.id, { limit: 100, status: statusFilter || undefined }, signal),
    [patient.id, statusFilter],
  )
  // Delivery to the phone is fetched alongside; a failure only hides the status line.
  const delivery = useAsync(
    (signal) => getFatigueDelivery(patient.id, signal).catch(() => null),
    [patient.id, observations.data],
  )
  const deliveryById = new Map((delivery.data?.items ?? []).map((i) => [i.observation_id, i]))
  const [form, setForm] = useState({
    category: 'fatigue' as ObservationCategory,
    note: '',
    observed_at: nowLocalInput(),
    fatigue_level: 'mild' as FatigueLevel,
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState<string | null>(null)
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
    setSaved(null)
    if (Object.keys(next).length) return
    const result = await create.run({
      category: form.category,
      note: form.note.trim(),
      observed_at: localInputToIso(form.observed_at),
      fatigue_level: form.category === 'fatigue' ? form.fatigue_level : null,
    })
    if (result) {
      setForm((f) => ({ ...f, note: '' }))
      setSaved(
        form.category === 'fatigue'
          ? 'Observation saved. The phone applies it at its next sync; each note below shows whether the phone has it yet.'
          : 'Observation saved.',
      )
      observations.reload()
    }
  }

  return (
    <>
      {!isClinician && (
        <Card title="Add an observation">
          <p className="field__hint">
            Describe what you noticed in everyday words, such as tiredness after lunch or a good
            mood after a visit. Observations are notes, not medical assessments.
          </p>
          <details className="details">
            <summary>How tiredness notes reach the phone</summary>
            <p className="field__hint">
              A tiredness note reaches the person's phone when it next syncs: "a little tired" makes
              activities easier and shorter for a few hours; "very tired" means the next suggestion is
              a rest and a running activity stops. Only the level and time go to the phone, never your
              note.
            </p>
          </details>
          <form onSubmit={onSubmit} noValidate>
            <SelectField label="About" value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value as ObservationCategory }))} options={options(OBSERVATION_LABELS)} />
            {form.category === 'fatigue' && (
              <SelectField
                label="How tired"
                value={form.fatigue_level}
                onChange={(e) => setForm((f) => ({ ...f, fatigue_level: e.target.value as FatigueLevel }))}
                options={options(FATIGUE_LEVEL_LABELS)}
              />
            )}
            <TextField label="When" type="datetime-local" value={form.observed_at} onChange={(e) => setForm((f) => ({ ...f, observed_at: e.target.value }))} error={errors.observed_at} required />
            <TextArea label="Note" value={form.note} maxLength={2000} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} error={errors.note} required />
            <ActionError error={create.error} />
            {saved && <Notice tone="success">{saved}</Notice>}
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
              delivery={deliveryById.get(o.id)}
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
