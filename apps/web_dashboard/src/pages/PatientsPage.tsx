import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { createPatient, listPatients } from '../api/patients'
import type { Language } from '../api/types'
import { Button } from '../components/ui/Button'
import { Dialog } from '../components/ui/Dialog'
import { SelectField, TextField } from '../components/ui/Field'
import { PageHeader } from '../components/ui/PageHeader'
import { ActionError, EmptyState, ErrorState, Loading } from '../components/ui/States'
import { useAction, useAsync } from '../hooks/useAsync'
import { LANGUAGE_LABELS, options } from '../lib/labels'
import { initials } from '../lib/people'

export function PatientsPage() {
  const patients = useAsync((signal) => listPatients(signal), [])
  const [open, setOpen] = useState(false)
  return (
    <>
      <PageHeader
        title="People I care for"
        lede="Open a person's record to see their memories, notes, activity and sharing settings."
        actions={<Button onClick={() => setOpen(true)}>Add a person</Button>}
      />
      {patients.status === 'error' && <ErrorState error={patients.error} onRetry={patients.reload} />}
      {patients.status === 'loading' && !patients.data && <Loading />}
      {patients.data?.length === 0 && (
        <EmptyState title="No one added yet">
          <p>Add the person you care for to start building their Memory Bank.</p>
        </EmptyState>
      )}
      <ul className="card-grid">
        {patients.data?.map((p) => (
          <li key={p.id}>
            <section className="card person-card" aria-labelledby={`person-card-${p.id}`}>
              <div className="person-card__identity">
                <span className="app-user__avatar" aria-hidden="true">
                  {initials(p.display_name)}
                </span>
                <div>
                  <h2 id={`person-card-${p.id}`}>{p.display_name}</h2>
                  <p className="person-card__meta">
                    {LANGUAGE_LABELS[p.preferred_language]} · {p.has_paired_device ? 'Phone connected' : 'No phone connected yet'}
                  </p>
                </div>
              </div>
              <Link to={`/app/patients/${p.id}`} className="button button--secondary" aria-label={`Open profile: ${p.display_name}`}>
                Open profile
              </Link>
            </section>
          </li>
        ))}
      </ul>
      <CreatePatientDialog open={open} onClose={() => setOpen(false)} />
    </>
  )
}

function CreatePatientDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    display_name: '',
    preferred_name: '',
    preferred_language: 'as' as Language,
    birth_year: '',
    region: '',
    relationship_label: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const action = useAction(createPatient)
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }))

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const next: Record<string, string> = {}
    if (!form.display_name.trim()) next.display_name = 'Enter their name.'
    if (!form.relationship_label.trim()) next.relationship_label = 'For example: daughter, son, neighbour.'
    const year = form.birth_year ? Number(form.birth_year) : null
    if (year !== null && (!Number.isInteger(year) || year < 1900 || year > 2100))
      next.birth_year = 'Enter a year between 1900 and 2100, or leave it empty.'
    setErrors(next)
    if (Object.keys(next).length) return
    const created = await action.run({
      display_name: form.display_name.trim(),
      preferred_name: form.preferred_name.trim() || null,
      preferred_language: form.preferred_language,
      birth_year: year,
      region: form.region.trim() || null,
      relationship_label: form.relationship_label.trim(),
    })
    if (created) navigate(`/app/patients/${created.id}`)
  }

  return (
    <Dialog open={open} title="Add a person" onClose={onClose}>
      <form onSubmit={onSubmit} noValidate>
        <TextField label="Name" value={form.display_name} onChange={(e) => set('display_name')(e.target.value)} error={errors.display_name} required />
        <TextField label="What they like to be called" hint="Optional." value={form.preferred_name} onChange={(e) => set('preferred_name')(e.target.value)} />
        <SelectField label="Preferred language" value={form.preferred_language} onChange={(e) => set('preferred_language')(e.target.value)} options={options(LANGUAGE_LABELS)} />
        <TextField label="Year of birth" hint="Optional. Only the year is stored." inputMode="numeric" value={form.birth_year} onChange={(e) => set('birth_year')(e.target.value)} error={errors.birth_year} />
        <TextField label="Region or state" hint="Optional." value={form.region} onChange={(e) => set('region')(e.target.value)} />
        <TextField label="Your relationship to them" value={form.relationship_label} onChange={(e) => set('relationship_label')(e.target.value)} error={errors.relationship_label} required />
        <ActionError error={action.error} />
        <div className="form-actions">
          <Button type="submit" pending={action.pending}>Add person</Button>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Dialog>
  )
}
