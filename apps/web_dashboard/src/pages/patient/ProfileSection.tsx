import { useState, type FormEvent } from 'react'
import { updatePatient } from '../../api/patients'
import type { Language } from '../../api/types'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { SelectField, TextField } from '../../components/ui/Field'
import { ActionError, Notice } from '../../components/ui/States'
import { useAction } from '../../hooks/useAsync'
import { LANGUAGE_LABELS, options } from '../../lib/labels'
import { usePatient } from '../../state/patient'

export function ProfileSection() {
  const { patient, isManager, reloadPatient } = usePatient()
  const [editing, setEditing] = useState(false)
  const [saved, setSaved] = useState(false)
  const [form, setForm] = useState({
    display_name: patient.display_name,
    preferred_name: patient.preferred_name ?? '',
    preferred_language: patient.preferred_language,
    birth_year: patient.birth_year?.toString() ?? '',
    region: patient.region ?? '',
    timezone: patient.timezone,
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const action = useAction((body: Parameters<typeof updatePatient>[1]) => updatePatient(patient.id, body))
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }))

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const next: Record<string, string> = {}
    if (!form.display_name.trim()) next.display_name = 'Name cannot be empty.'
    const year = form.birth_year ? Number(form.birth_year) : null
    if (year !== null && (!Number.isInteger(year) || year < 1900 || year > 2100))
      next.birth_year = 'Enter a year between 1900 and 2100, or leave it empty.'
    setErrors(next)
    if (Object.keys(next).length) return
    const result = await action.run({
      display_name: form.display_name.trim(),
      preferred_name: form.preferred_name.trim() || null,
      preferred_language: form.preferred_language,
      birth_year: year,
      region: form.region.trim() || null,
      timezone: form.timezone,
    })
    if (result) {
      setEditing(false)
      setSaved(true)
      reloadPatient()
    }
  }

  if (!editing)
    return (
      <Card
        title="Profile"
        actions={
          isManager ? (
            <Button variant="secondary" onClick={() => { setSaved(false); setEditing(true) }}>
              Edit profile
            </Button>
          ) : undefined
        }
      >
        {saved && <Notice tone="success">Profile saved.</Notice>}
        <dl className="definition-list">
          <dt>Name</dt>
          <dd>{patient.display_name}</dd>
          <dt>Likes to be called</dt>
          <dd>{patient.preferred_name ?? '—'}</dd>
          <dt>Preferred language</dt>
          <dd>{LANGUAGE_LABELS[patient.preferred_language]}</dd>
          <dt>Year of birth</dt>
          <dd>{patient.birth_year ?? '—'}</dd>
          <dt>Region</dt>
          <dd>{patient.region ?? '—'}</dd>
          <dt>Time zone</dt>
          <dd>{patient.timezone}</dd>
          <dt>Phone app</dt>
          <dd>{patient.has_paired_device ? 'Connected' : 'Not connected yet'}</dd>
        </dl>
        {!isManager && (
          <p className="field__hint">Only a managing family member can change these details.</p>
        )}
      </Card>
    )

  return (
    <Card title="Edit profile">
      <form onSubmit={onSubmit} noValidate>
        <TextField label="Name" value={form.display_name} onChange={(e) => set('display_name')(e.target.value)} error={errors.display_name} required />
        <TextField label="What they like to be called" value={form.preferred_name} onChange={(e) => set('preferred_name')(e.target.value)} />
        <SelectField label="Preferred language" value={form.preferred_language} onChange={(e) => set('preferred_language')(e.target.value as Language)} options={options(LANGUAGE_LABELS)} />
        <TextField label="Year of birth" inputMode="numeric" value={form.birth_year} onChange={(e) => set('birth_year')(e.target.value)} error={errors.birth_year} />
        <TextField label="Region or state" value={form.region} onChange={(e) => set('region')(e.target.value)} />
        <TextField label="Time zone" hint="For example Asia/Kolkata." value={form.timezone} onChange={(e) => set('timezone')(e.target.value)} />
        <ActionError error={action.error} />
        <div className="form-actions">
          <Button type="submit" pending={action.pending}>Save</Button>
          <Button variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
        </div>
      </form>
    </Card>
  )
}
