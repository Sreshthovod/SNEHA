import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { ALLOWED_PHOTO_TYPES, uploadMedia } from '../../api/files'
import {
  approveMemory,
  correctMemory,
  createMemory,
  createMemoryLink,
  deleteMemory,
  deleteMemoryLink,
  getMemory,
  listMemories,
  listMemoryLinks,
  rejectMemory,
} from '../../api/memories'
import type { Memory, MemoryKind, MemoryLink, MemoryLinkType, MemoryStatus } from '../../api/types'
import { ProtectedImage } from '../../components/ProtectedImage'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Dialog } from '../../components/ui/Dialog'
import { SelectField, TextArea, TextField } from '../../components/ui/Field'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { ActionError, EmptyState, ErrorState, Loading, Notice } from '../../components/ui/States'
import { Tabs } from '../../components/ui/Tabs'
import { useAsync } from '../../hooks/useAsync'
import { MEMORY_KIND_LABELS, MEMORY_STATUS_LABELS, options } from '../../lib/labels'
import { activityUses, phoneStatus } from '../../lib/memoryUse'
import { usePatient } from '../../state/patient'

const FILTERS: Array<{ id: MemoryStatus | 'all'; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'pending_approval', label: 'Waiting for approval' },
  { id: 'approved', label: 'Approved' },
  { id: 'rejected', label: 'Not approved' },
]

function conflictMessage(error: unknown): string {
  if (error instanceof ApiError && error.code === 'version_conflict')
    return 'Someone else changed this memory while you were working on it. The latest version has been loaded; please check it and try again.'
  return error instanceof Error ? error.message : 'Something went wrong.'
}

export function MemoriesSection() {
  const { patient, isManager } = usePatient()
  const [params, setParams] = useSearchParams()
  const initial = (params.get('status') as MemoryStatus | null) ?? 'all'
  const [filter, setFilter] = useState<MemoryStatus | 'all'>(isManager ? initial : 'approved')
  const memories = useAsync(
    (signal) => listMemories(patient.id, filter === 'all' ? undefined : filter, signal),
    [patient.id, filter],
  )
  // Every approved memory and every link, for the "How SNEHA uses this" panel.
  const context = useAsync(
    async (signal) => {
      const [approved, links] = await Promise.all([
        listMemories(patient.id, 'approved', signal),
        listMemoryLinks(patient.id, signal),
      ])
      return { approved, links }
    },
    [patient.id, memories.data],
  )
  const [creating, setCreating] = useState(false)
  const [message, setMessage] = useState<{ tone: 'success' | 'warning'; text: string } | null>(null)

  const onFilter = (id: string) => {
    setFilter(id as MemoryStatus | 'all')
    setParams(id === 'all' ? {} : { status: id }, { replace: true })
  }

  const list = (
    <>
      {memories.status === 'error' && <ErrorState error={memories.error} onRetry={memories.reload} />}
      {memories.status === 'loading' && !memories.data && <Loading />}
      {memories.data?.length === 0 && (
        <EmptyState title="No memories here yet">
          <p>Add familiar people, places and stories with a photo if you have one.</p>
        </EmptyState>
      )}
      <ul className="memory-grid">
        {memories.data?.map((m) => (
          <li key={m.id}>
            <MemoryCard
              memory={m}
              approved={context.data?.approved ?? []}
              links={context.data?.links ?? []}
              canManage={isManager}
              onChanged={(text, tone = 'success') => {
                setMessage({ text, tone })
                memories.reload()
              }}
            />
          </li>
        ))}
      </ul>
    </>
  )

  return (
    <Card
      title="Memory Bank"
      actions={<Button onClick={() => setCreating(true)}>Add a memory</Button>}
    >
      <p className="field__hint">
        Only approved memories are shown on the phone.{' '}
        {isManager
          ? 'Memories you add are approved straight away.'
          : 'Memories you add wait for a managing family member to approve them.'}
      </p>
      {message && <Notice tone={message.tone}>{message.text}</Notice>}
      {isManager ? (
        <Tabs
          label="Filter memories"
          selected={filter}
          onSelect={onFilter}
          items={FILTERS.map((f) => ({ id: f.id, label: f.label, content: list }))}
        />
      ) : (
        list
      )}
      {creating && (
      <MemoryFormDialog
        open
        onClose={() => setCreating(false)}
        onSaved={(m) => {
          setCreating(false)
          setMessage({
            tone: 'success',
            text: m.status === 'approved' ? 'Memory added.' : 'Memory added and waiting for approval.',
          })
          memories.reload()
        }}
      />
      )}
    </Card>
  )
}

function MemoryCard({
  memory,
  approved,
  links,
  canManage,
  onChanged,
}: {
  memory: Memory
  approved: Memory[]
  links: MemoryLink[]
  canManage: boolean
  onChanged: (text: string, tone?: 'success' | 'warning') => void
}) {
  const { patient } = usePatient()
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const tone = memory.status === 'approved' ? 'success' : memory.status === 'pending_approval' ? 'warning' : 'neutral'

  async function review(kind: 'approve' | 'reject') {
    setBusy(true)
    setError(null)
    try {
      const fn = kind === 'approve' ? approveMemory : rejectMemory
      await fn(patient.id, memory.id, { expected_version: memory.version })
      onChanged(kind === 'approve' ? `“${memory.title}” approved.` : `“${memory.title}” not approved.`)
    } catch (e) {
      setError(conflictMessage(e))
      if (e instanceof ApiError && (e.code === 'version_conflict' || e.code === 'not_pending'))
        onChanged(conflictMessage(e), 'warning')
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    setBusy(true)
    try {
      await deleteMemory(patient.id, memory.id)
      setConfirmDelete(false)
      onChanged(`“${memory.title}” deleted permanently.`)
    } catch (e) {
      setError(conflictMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="memory-card" aria-labelledby={`memory-${memory.id}`}>
      {memory.media_file_id && <ProtectedImage fileId={memory.media_file_id} alt={memory.title} />}
      <h3 id={`memory-${memory.id}`} className="memory-card__title">
        {memory.title}
      </h3>
      <p>
        <StatusBadge tone={tone} label={MEMORY_STATUS_LABELS[memory.status]} />{' '}
        <span className="field__hint">
          {MEMORY_KIND_LABELS[memory.kind]}
          {memory.relationship ? ` · ${memory.relationship}` : ''}
          {memory.approx_year ? ` · around ${memory.approx_year}` : ''}
        </span>
      </p>
      {memory.description && <p>{memory.description}</p>}
      <MemoryUsePanel memory={memory} approved={approved} links={links} canManage={canManage} onChanged={onChanged} />
      {memory.tags.length > 0 && <p className="field__hint">Tags: {memory.tags.join(', ')}</p>}
      {memory.review_note && <p className="field__hint">Note: {memory.review_note}</p>}
      {error && (
        <p className="field__error" role="alert">
          {error}
        </p>
      )}
      {canManage && (
        <div className="form-actions">
          {memory.status === 'pending_approval' && (
            <>
              <Button onClick={() => review('approve')} pending={busy}>
                Approve
              </Button>
              <Button variant="secondary" onClick={() => review('reject')} disabled={busy}>
                Do not approve
              </Button>
            </>
          )}
          <Button variant="secondary" onClick={() => setEditing(true)} disabled={busy}>
            Correct
          </Button>
          <span className="observation-actions__spacer" aria-hidden="true" />
          <Button variant="danger-outline" onClick={() => setConfirmDelete(true)} disabled={busy}>
            Delete
          </Button>
        </div>
      )}
      {editing && (
      <MemoryFormDialog
        open
        memory={memory}
        onClose={() => setEditing(false)}
        onSaved={() => {
          setEditing(false)
          onChanged(`“${memory.title}” updated.`)
        }}
        onConflict={(text) => {
          setEditing(false)
          onChanged(text, 'warning')
        }}
      />
      )}
      <Dialog
        open={confirmDelete}
        title="Delete this memory?"
        onClose={() => setConfirmDelete(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={remove} pending={busy}>
              Delete permanently
            </Button>
          </>
        }
      >
        <p>
          “{memory.title}” and its photo will be removed from SNEHA and from the phone at its next
          sync. This cannot be undone.
        </p>
      </Dialog>
    </article>
  )
}

function MemoryFormDialog({
  open,
  memory,
  onClose,
  onSaved,
  onConflict,
}: {
  open: boolean
  memory?: Memory
  onClose: () => void
  onSaved: (m: Memory) => void
  onConflict?: (message: string) => void
}) {
  const { patient } = usePatient()
  const [form, setForm] = useState({
    kind: memory?.kind ?? ('person' as MemoryKind),
    title: memory?.title ?? '',
    description: memory?.description ?? '',
    approx_year: memory?.approx_year?.toString() ?? '',
    relationship: memory?.relationship ?? '',
    tags: memory?.tags.join(', ') ?? '',
    note: '',
  })
  // One client ID per new memory: a double click or a retry after a lost response
  // cannot create the memory twice (the server answers 409 id_conflict).
  const [clientId] = useState(() => crypto.randomUUID())
  const [photo, setPhoto] = useState<File | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState<ApiError | null>(null)
  const [pending, setPending] = useState(false)
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }))

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const next: Record<string, string> = {}
    if (!form.title.trim()) next.title = 'Give the memory a short title.'
    const year = form.approx_year ? Number(form.approx_year) : null
    if (year !== null && (!Number.isInteger(year) || year < 1900 || year > 2100))
      next.approx_year = 'Enter a year between 1900 and 2100, or leave it empty.'
    const tags = form.tags.split(',').map((t) => t.trim()).filter(Boolean)
    if (tags.length > 20) next.tags = 'Use at most 20 tags.'
    if (photo && !ALLOWED_PHOTO_TYPES.includes(photo.type))
      next.photo = 'Choose a JPEG, PNG or WebP photo.'
    setErrors(next)
    setError(null)
    if (Object.keys(next).length) return
    setPending(true)
    try {
      const media = photo ? await uploadMedia(patient.id, photo) : null
      const fields = {
        kind: form.kind,
        title: form.title.trim(),
        description: form.description.trim() || null,
        approx_year: year,
        relationship: form.kind === 'person' ? form.relationship.trim() || null : null,
        tags,
        ...(media ? { media_file_id: media.id } : {}),
      }
      const saved = memory
        ? await correctMemory(patient.id, memory.id, {
            ...fields,
            expected_version: memory.version,
            correction_note: form.note.trim() || null,
          })
        : await createMemory(patient.id, { ...fields, id: clientId })
      onSaved(saved)
    } catch (e) {
      if (!memory && e instanceof ApiError && e.code === 'id_conflict') {
        // Saved by an earlier attempt whose response was lost: show that one.
        onSaved(await getMemory(patient.id, clientId))
      } else if (e instanceof ApiError && e.code === 'version_conflict' && onConflict) {
        onConflict(conflictMessage(e))
      } else {
        setError(e instanceof ApiError ? e : new ApiError('Could not save.', { status: null, code: 'unknown' }))
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <Dialog open={open} title={memory ? 'Correct memory' : 'Add a memory'} onClose={onClose}>
      <form onSubmit={onSubmit} noValidate>
        <SelectField label="Type" value={form.kind} onChange={(e) => set('kind')(e.target.value)} options={options(MEMORY_KIND_LABELS)} />
        <TextField label="Title" hint="Short and familiar, e.g. “Aunt Rina at the tea garden”." value={form.title} onChange={(e) => set('title')(e.target.value)} error={errors.title} maxLength={120} required />
        <TextArea label="Description" hint="Optional. Up to 2000 characters." value={form.description} onChange={(e) => set('description')(e.target.value)} maxLength={2000} />
        {form.kind === 'person' && (
          <TextField
            label={`How is this person related to ${patient.preferred_name ?? patient.display_name}?`}
            hint="Optional, in your own words, e.g. “granddaughter”, “neighbour”. Used for gentle hints and story prompts. SNEHA never guesses this from a photo."
            value={form.relationship}
            onChange={(e) => set('relationship')(e.target.value)}
            maxLength={60}
          />
        )}
        <TextField label="Around which year?" inputMode="numeric" value={form.approx_year} onChange={(e) => set('approx_year')(e.target.value)} error={errors.approx_year} />
        <TextField label="Tags" hint="Separate with commas." value={form.tags} onChange={(e) => set('tags')(e.target.value)} error={errors.tags} />
        <TextField
          label={memory?.media_file_id ? 'Replace photo' : 'Photo'}
          type="file"
          accept={ALLOWED_PHOTO_TYPES.join(',')}
          hint="Optional. JPEG, PNG or WebP, up to 5 MB."
          onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
          error={errors.photo}
        />
        {memory && (
          <TextField label="What was corrected?" hint="Optional note for the family." value={form.note} onChange={(e) => set('note')(e.target.value)} maxLength={500} />
        )}
        <ActionError error={error} />
        <div className="form-actions">
          <Button type="submit" pending={pending}>Save</Button>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Dialog>
  )
}

const LINK_LABELS: Record<MemoryLinkType, string> = {
  person_in: 'is in',
  located_at: 'is at',
  part_of: 'is part of',
  related_to: 'is related to',
}

/** Phone availability, activities this memory feeds, and its links to other memories. */
function MemoryUsePanel({
  memory,
  approved,
  links,
  canManage,
  onChanged,
}: {
  memory: Memory
  approved: Memory[]
  links: MemoryLink[]
  canManage: boolean
  onChanged: (text: string, tone?: 'success' | 'warning') => void
}) {
  const { patient } = usePatient()
  const status = phoneStatus(memory, patient.has_paired_device)
  const uses = activityUses(memory, approved)
  const byId = new Map(approved.map((m) => [m.id, m]))
  const mine = links.filter((l) => l.from_memory_id === memory.id || l.to_memory_id === memory.id)
  const others = approved.filter((m) => m.id !== memory.id)
  const [target, setTarget] = useState('')
  const [type, setType] = useState<MemoryLinkType>('person_in')
  const [error, setError] = useState<string | null>(null)

  async function addLink() {
    if (!target) return
    setError(null)
    try {
      await createMemoryLink(patient.id, { from_memory_id: memory.id, to_memory_id: target, relation_type: type })
      onChanged('Link added. Story time can now mention them together.')
      setTarget('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not add the link.')
    }
  }

  return (
    <details className="details memory-use">
      <summary>
        <span>How SNEHA uses this</span>
        <span className="memory-use__state">{status.shared ? 'On the phone' : 'Not on the phone'}</span>
      </summary>
      <p className="field__hint">{status.text}</p>
      {uses.length > 0 && (
        <ul className="plain-list memory-use__list">
          {uses.map((u) => (
            <li key={u.title}>
              <StatusBadge tone={u.ready ? 'success' : 'neutral'} label={u.ready ? 'Ready' : 'Not yet'} />{' '}
              <strong>{u.title}</strong>
              <br />
              <span className="field__hint">{u.detail}</span>
            </li>
          ))}
        </ul>
      )}
      {memory.status === 'approved' && (
        <>
          <p className="memory-use__heading"><strong>Linked memories</strong></p>
          {mine.length === 0 ? (
            <p className="field__hint">None. Linking a person to an event or place lets story time ask about them together.</p>
          ) : (
            <ul className="plain-list">
              {mine.map((l) => {
                const from = l.from_memory_id === memory.id ? memory : byId.get(l.from_memory_id)
                const to = l.to_memory_id === memory.id ? memory : byId.get(l.to_memory_id)
                return (
                  <li key={l.id}>
                    {from?.title ?? 'A memory'} {LINK_LABELS[l.relation_type]} {to?.title ?? 'a memory'}
                    {canManage && (
                      <Button
                        variant="ghost"
                        aria-label={`Remove link: ${from?.title ?? 'memory'} ${LINK_LABELS[l.relation_type]} ${to?.title ?? 'memory'}`}
                        onClick={async () => {
                          await deleteMemoryLink(patient.id, l.id)
                          onChanged('Link removed.')
                        }}
                      >
                        Remove
                      </Button>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
          {canManage && others.length > 0 && (
            <div className="inline-fields">
              <SelectField
                label={`“${memory.title}”…`}
                value={type}
                onChange={(e) => setType(e.target.value as MemoryLinkType)}
                options={(Object.keys(LINK_LABELS) as MemoryLinkType[]).map((k) => ({ value: k, label: LINK_LABELS[k] }))}
              />
              <SelectField
                label="Other memory"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                options={[{ value: '', label: 'Choose…' }, ...others.map((m) => ({ value: m.id, label: m.title }))]}
              />
              <Button variant="secondary" onClick={addLink} disabled={!target}>Link</Button>
            </div>
          )}
          {error && <p className="field__error" role="alert">{error}</p>}
        </>
      )}
    </details>
  )
}
