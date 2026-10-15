import { useState, type FormEvent } from 'react'
import { addCaregiver, createPairingCode, listCaregivers, removeCaregiver, revokeDevices } from '../../api/patients'
import type { PairingCode } from '../../api/types'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Dialog } from '../../components/ui/Dialog'
import { CheckboxField, TextField } from '../../components/ui/Field'
import { ActionError, ErrorState, Loading, Notice } from '../../components/ui/States'
import { useAction, useAsync } from '../../hooks/useAsync'
import { formatDateTime } from '../../lib/dates'
import { usePatient } from '../../state/patient'

export function PeopleSection() {
  const { patient, isManager, me, reloadPatient } = usePatient()
  const caregivers = useAsync((signal) => listCaregivers(patient.id, signal), [patient.id])
  const [code, setCode] = useState<PairingCode | null>(null)
  const [confirmRevoke, setConfirmRevoke] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [form, setForm] = useState({ email: '', relationship_label: '', can_manage: false })
  const [formError, setFormError] = useState<string | null>(null)
  const pair = useAction(() => createPairingCode(patient.id))
  const revoke = useAction(async () => {
    await revokeDevices(patient.id)
    return true
  })
  const add = useAction((body: typeof form) => addCaregiver(patient.id, body))
  const remove = useAction((id: string) => removeCaregiver(patient.id, id))

  async function onAdd(e: FormEvent) {
    e.preventDefault()
    setFormError(null)
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()) || !form.relationship_label.trim()) {
      setFormError('Enter their email and how they are related.')
      return
    }
    const result = await add.run({ ...form, email: form.email.trim(), relationship_label: form.relationship_label.trim() })
    if (result) {
      setForm({ email: '', relationship_label: '', can_manage: false })
      setNotice(`${result.caregiver_name} can now help care for ${patient.display_name}.`)
      caregivers.reload()
    }
  }

  return (
    <>
      <Card title="The phone app">
        <p>
          {patient.has_paired_device
            ? 'A phone is connected. You can connect another phone or sign out all phones.'
            : 'No phone is connected yet. Create a code and type it into the SNEHA app on their phone.'}
        </p>
        {isManager ? (
          <>
            <div className="form-actions">
              <Button onClick={async () => { const c = await pair.run(); if (c) setCode(c) }} pending={pair.pending}>
                Create connection code
              </Button>
              {patient.has_paired_device && (
                <Button variant="danger" onClick={() => setConfirmRevoke(true)}>Sign out all phones</Button>
              )}
            </div>
            <ActionError error={pair.error ?? revoke.error} />
            {code && (
              <Notice tone="info" title="Connection code">
                <p className="pairing-code" aria-label={`Code ${code.code.split('').join(' ')}`}>{code.code}</p>
                <p>Use it before {formatDateTime(code.expires_at)}. It works once.</p>
              </Notice>
            )}
          </>
        ) : (
          <p className="field__hint">A managing family member connects phones.</p>
        )}
      </Card>
      <Card title="Family and caregivers">
        {notice && <Notice tone="success">{notice}</Notice>}
        {caregivers.status === 'error' && <ErrorState error={caregivers.error} onRetry={caregivers.reload} />}
        {!caregivers.data && caregivers.status === 'loading' && <Loading />}
        <ActionError error={remove.error} />
        <ul className="plain-list">
          {caregivers.data?.map((c) => (
            <li key={c.id} className="person-row">
              <span>
                <strong>{c.caregiver_name}</strong> · {c.relationship_label}
                {c.can_manage && ' · manages profile'}
                {c.caregiver_id === me.id && ' · you'}
              </span>
              {isManager && c.caregiver_id !== me.id && (
                <Button variant="ghost" onClick={async () => { await remove.run(c.id); caregivers.reload() }} disabled={remove.pending}>
                  Remove
                </Button>
              )}
            </li>
          ))}
        </ul>
        {isManager && (
          <form onSubmit={onAdd} noValidate>
            <h3>Add a family member</h3>
            <p className="field__hint">They need their own SNEHA caregiver account first.</p>
            <TextField label="Their email" type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
            <TextField label="Relationship" value={form.relationship_label} onChange={(e) => setForm((f) => ({ ...f, relationship_label: e.target.value }))} />
            <CheckboxField label="Can manage the profile, memories and access" checked={form.can_manage} onChange={(e) => setForm((f) => ({ ...f, can_manage: e.target.checked }))} />
            {formError && <p className="field__error" role="alert">{formError}</p>}
            <ActionError error={add.error} />
            <Button type="submit" pending={add.pending}>Add family member</Button>
          </form>
        )}
      </Card>
      <Dialog
        open={confirmRevoke}
        title="Sign out all phones?"
        onClose={() => setConfirmRevoke(false)}
        footer={
          <>
            <Button variant="danger" pending={revoke.pending} onClick={async () => {
              if (!(await revoke.run())) return
              setConfirmRevoke(false)
              setNotice('All phones have been signed out. Create a new code to connect again.')
              reloadPatient()
            }}>Sign out phones</Button>
            <Button variant="secondary" onClick={() => setConfirmRevoke(false)}>Cancel</Button>
          </>
        }
      >
        <p>Use this if a phone is lost. Activities already on the phone that have not synced cannot be recovered.</p>
        <ActionError error={revoke.error} />
      </Dialog>
    </>
  )
}
