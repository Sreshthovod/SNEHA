import { useState, type FormEvent } from 'react'
import { getCatalog, getPreferences, putPreferences } from '../../api/personalization'
import type { Preferences } from '../../api/types'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { CheckboxField, TextField } from '../../components/ui/Field'
import { ActionError, ErrorState, Loading, Notice } from '../../components/ui/States'
import { useAction, useAsync } from '../../hooks/useAsync'
import { formatDateTime } from '../../lib/dates'
import { LANGUAGE_LABELS } from '../../lib/labels'
import { usePatient } from '../../state/patient'

const TAG_PATTERN = /^[\p{L}\p{N} _-]{1,40}$/u

function normaliseTag(raw: string): string {
  return raw.trim().toLowerCase().replace(/\s+/g, ' ')
}

function TagList({ tags, onRemove }: { tags: string[]; onRemove?: (t: string) => void }) {
  if (tags.length === 0) return <p className="field__hint">None yet.</p>
  return (
    <ul className="chip-list" aria-label="Interests">
      {tags.map((t) => (
        <li key={t} className="chip">
          {t}
          {onRemove && (
            <Button variant="ghost" onClick={() => onRemove(t)} aria-label={`Remove interest ${t}`}>
              ✕
            </Button>
          )}
        </li>
      ))}
    </ul>
  )
}

export function PreferencesSection() {
  const { patient, isManager, isClinician } = usePatient()
  const data = useAsync(
    async (signal) => {
      const [prefs, catalog] = await Promise.all([getPreferences(patient.id, signal), getCatalog(signal)])
      return { prefs, catalog }
    },
    [patient.id],
  )
  // Local edits; null means "showing what the server has".
  const [edited, setDraft] = useState<Preferences | null>(null)
  const [tagInput, setTagInput] = useState('')
  const [tagError, setTagError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const save = useAction((d: Preferences) =>
    putPreferences(patient.id, {
      interests: d.interests,
      disliked_activity_slugs: d.disliked_activity_slugs,
      session_minutes: d.session_minutes,
    }),
  )

  if (data.status === 'error' && !data.data) return <ErrorState error={data.error} onRetry={data.reload} />
  if (!data.data) return <Loading />
  const { prefs, catalog } = data.data
  const draft = edited ?? prefs
  const editable = isManager && !isClinician

  function addTag(raw: string) {
    const tag = normaliseTag(raw)
    setTagError(null)
    if (!tag) return
    if (!TAG_PATTERN.test(tag)) return setTagError('Use letters, numbers and spaces only (up to 40 characters).')
    if (draft.interests.includes(tag)) return setTagError('This interest is already listed.')
    if (draft.interests.length >= 30) return setTagError('Up to 30 interests can be listed.')
    setDraft({ ...draft, interests: [...draft.interests, tag].sort() })
    setTagInput('')
    setSaved(false)
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setSaved(false)
    const result = await save.run(draft)
    if (result) {
      setSaved(true)
      setDraft(null)
      data.reload()
    }
  }

  const memoryTags = Object.entries(prefs.memory_tags).filter(([t]) => !draft.interests.includes(t))

  return (
    <Card title="Interests & preferences">
      <p className="field__hint">
        Approved interests help SNEHA choose activities the person is likely to enjoy. Only a
        managing family member can change them. Language: {LANGUAGE_LABELS[prefs.preferred_language as keyof typeof LANGUAGE_LABELS] ?? prefs.preferred_language}.
      </p>
      {!editable && (
        <Notice tone="info">
          {isClinician ? 'You can view these preferences. Only the family can change them.' : 'A managing family member can change these preferences.'}
        </Notice>
      )}
      <form onSubmit={onSubmit} noValidate>
        <h3>Interests</h3>
        <TagList
          tags={draft.interests}
          onRemove={
            editable
              ? (t) => {
                  setDraft({ ...draft, interests: draft.interests.filter((x) => x !== t) })
                  setSaved(false)
                }
              : undefined
          }
        />
        {editable && (
          <div className="inline-fields">
            <TextField
              label="Add an interest"
              value={tagInput}
              maxLength={40}
              hint="For example: tea, gardening, Bihu, football"
              error={tagError ?? undefined}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  addTag(tagInput)
                }
              }}
            />
            <Button variant="secondary" onClick={() => addTag(tagInput)}>Add</Button>
          </div>
        )}
        {editable && memoryTags.length > 0 && (
          <div>
            <p className="field__hint">Tags already used in approved memories:</p>
            <ul className="chip-list">
              {memoryTags.map(([t, n]) => (
                <li key={t}>
                  <Button variant="ghost" onClick={() => addTag(t)} aria-label={`Add interest ${t} (used in ${n} memories)`}>
                    + {t} ({n})
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <h3>Activities they do not enjoy</h3>
        <p className="field__hint">These are never suggested.</p>
        {editable ? (
          catalog.map((a) => (
            <CheckboxField
              key={a.slug}
              label={a.title}
              checked={draft.disliked_activity_slugs.includes(a.slug)}
              onChange={(e) => {
                const set = new Set(draft.disliked_activity_slugs)
                if (e.target.checked) set.add(a.slug)
                else set.delete(a.slug)
                setDraft({ ...draft, disliked_activity_slugs: [...set].sort() })
                setSaved(false)
              }}
            />
          ))
        ) : draft.disliked_activity_slugs.length === 0 ? (
          <p>None.</p>
        ) : (
          <ul>
            {draft.disliked_activity_slugs.map((s) => (
              <li key={s}>{catalog.find((a) => a.slug === s)?.title ?? s}</li>
            ))}
          </ul>
        )}

        <h3>Session length</h3>
        {editable ? (
          <TextField
            label="Preferred session length (minutes)"
            type="number"
            min={5}
            max={60}
            value={String(draft.session_minutes)}
            onChange={(e) => {
              setDraft({ ...draft, session_minutes: Number(e.target.value) })
              setSaved(false)
            }}
            error={draft.session_minutes < 5 || draft.session_minutes > 60 ? 'Choose between 5 and 60 minutes.' : undefined}
          />
        ) : (
          <p>{draft.session_minutes} minutes</p>
        )}
        {prefs.updated_at && <p className="field__hint">Last changed {formatDateTime(prefs.updated_at, patient.timezone)}</p>}
        {editable && (
          <>
            <ActionError error={save.error} />
            {saved && <Notice tone="success">Preferences saved.</Notice>}
            <Button type="submit" pending={save.pending} disabled={draft.session_minutes < 5 || draft.session_minutes > 60}>
              Save preferences
            </Button>
          </>
        )}
      </form>
    </Card>
  )
}
