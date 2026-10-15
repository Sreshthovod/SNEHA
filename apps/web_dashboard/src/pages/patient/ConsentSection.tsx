import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { getConsents, recordConsent } from '../../api/consents'
import { createGrant, erasePatient, listGrants, revokeGrant } from '../../api/patients'
import type { ConsentGiver, ConsentStatus, ConsentType } from '../../api/types'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { DisabledWithReason } from '../../components/ui/DisabledReason'
import { Dialog } from '../../components/ui/Dialog'
import { SelectField, TextField } from '../../components/ui/Field'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { ActionError, ErrorState, Loading, Notice } from '../../components/ui/States'
import { Table } from '../../components/ui/Table'
import { useAction, useAsync } from '../../hooks/useAsync'
import { addDays, formatDateTime, todayInZone } from '../../lib/dates'
import { CONSENT_GIVER_LABELS, CONSENT_LABELS, options } from '../../lib/labels'
import { usePatient } from '../../state/patient'

const TYPES = Object.keys(CONSENT_LABELS) as ConsentType[]

export function ConsentSection() {
  const { patient, isManager, isClinician } = usePatient()
  const consents = useAsync((signal) => getConsents(patient.id, signal), [patient.id])
  const [giver, setGiver] = useState<ConsentGiver>('patient')
  const record = useAction((type: ConsentType, status: ConsentStatus) =>
    recordConsent(patient.id, { consent_type: type, status, given_by: giver }),
  )

  return (
    <>
      <Card title="Consent">
        {isClinician && <p className="field__hint">Shown for your information. Only the family can change consent.</p>}
        {consents.status === 'error' && <ErrorState error={consents.error} onRetry={consents.reload} />}
        {!consents.data && consents.status === 'loading' && <Loading />}
        {consents.data && (
          <>
            {isManager && (
              <SelectField label="Decision made by" value={giver} onChange={(e) => setGiver(e.target.value as ConsentGiver)} options={options(CONSENT_GIVER_LABELS)} />
            )}
            <ul className="plain-list">
              {TYPES.map((type) => {
                const status = consents.data?.current[type] ?? null
                return (
                  <li key={type} className="consent-row">
                    <div>
                      <strong>{CONSENT_LABELS[type].title}</strong>
                      <p className="field__hint">{CONSENT_LABELS[type].description}</p>
                    </div>
                    <StatusBadge tone={status === 'granted' ? 'success' : 'neutral'} label={status === 'granted' ? 'Given' : status === 'withdrawn' ? 'Withdrawn' : 'Not recorded'} />
                    {isManager && (
                      <Button
                        variant="secondary"
                        disabled={record.pending}
                        onClick={async () => {
                          await record.run(type, status === 'granted' ? 'withdrawn' : 'granted')
                          consents.reload()
                        }}
                      >
                        {status === 'granted' ? 'Withdraw' : 'Record consent'}
                      </Button>
                    )}
                  </li>
                )
              })}
            </ul>
            <ActionError error={record.error} />
            {consents.data.history.length > 0 && (
              <Table
                caption="Consent history"
                rowKey={(r) => r.id}
                rows={consents.data.history}
                columns={[
                  { header: 'When', cell: (r) => formatDateTime(r.recorded_at, patient.timezone) },
                  { header: 'Consent', cell: (r) => CONSENT_LABELS[r.consent_type].title },
                  { header: 'Decision', cell: (r) => (r.status === 'granted' ? 'Given' : 'Withdrawn') },
                  { header: 'By', cell: (r) => CONSENT_GIVER_LABELS[r.given_by] },
                  { header: 'Policy', cell: (r) => r.policy_version },
                ]}
              />
            )}
          </>
        )}
      </Card>
      {isManager && <ClinicianAccessCard onConsentChange={consents.reload} />}
      {isManager && <DataManagementCard />}
    </>
  )
}

function ClinicianAccessCard({ onConsentChange }: { onConsentChange: () => void }) {
  const { patient } = usePatient()
  const grants = useAsync((signal) => listGrants(patient.id, signal), [patient.id])
  const today = todayInZone(patient.timezone)
  const [form, setForm] = useState({ email: '', purpose: '', until: addDays(today, 30) })
  const [formError, setFormError] = useState<string | null>(null)
  const create = useAction((body: Parameters<typeof createGrant>[1]) => createGrant(patient.id, body))
  const revoke = useAction((id: string) => revokeGrant(patient.id, id))
  const [now] = useState(() => Date.now())

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setFormError(null)
    if (!form.email.trim() || form.purpose.trim().length < 3 || !form.until) {
      setFormError('Enter the clinician’s email, a short purpose and an end date.')
      return
    }
    const result = await create.run({
      clinician_email: form.email.trim(),
      purpose: form.purpose.trim(),
      expires_at: new Date(`${form.until}T23:59:00`).toISOString(),
    })
    if (result) {
      setForm({ email: '', purpose: '', until: addDays(today, 30) })
      grants.reload()
      onConsentChange()
    }
  }

  return (
    <Card title="Clinician access">
      <p className="field__hint">Clinicians can view activity summaries, observations and reports, never the Memory Bank. “Share with clinicians” consent must be given first.</p>
      {grants.status === 'error' && <ErrorState error={grants.error} onRetry={grants.reload} />}
      <ActionError error={revoke.error} />
      <ul className="plain-list">
        {grants.data?.map((g) => {
          const active = !g.revoked_at && new Date(g.expires_at).getTime() > now
          return (
            <li key={g.id} className="person-row">
              <span>
                <strong>{g.clinician_name}</strong> · {g.purpose} ·{' '}
                {g.revoked_at ? 'access ended' : active ? `until ${formatDateTime(g.expires_at, patient.timezone)}` : 'expired'}
              </span>
              {active && (
                <Button variant="ghost" onClick={async () => { await revoke.run(g.id); grants.reload() }} disabled={revoke.pending}>
                  End access
                </Button>
              )}
            </li>
          )
        })}
      </ul>
      <form onSubmit={onSubmit} noValidate>
        <h3>Share with a clinician</h3>
        <TextField label="Clinician’s email" type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
        <TextField label="Purpose" hint="For example: memory clinic follow-up." value={form.purpose} onChange={(e) => setForm((f) => ({ ...f, purpose: e.target.value }))} />
        <TextField label="Access ends on" type="date" min={addDays(today, 1)} max={addDays(today, 180)} value={form.until} onChange={(e) => setForm((f) => ({ ...f, until: e.target.value }))} hint="Up to 180 days." />
        {formError && <p className="field__error" role="alert">{formError}</p>}
        <ActionError error={create.error} />
        <Button type="submit" pending={create.pending}>Share access</Button>
      </form>
    </Card>
  )
}

function DataManagementCard() {
  const { patient } = usePatient()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const erase = useAction(async () => {
    await erasePatient(patient.id, typed)
    return true
  })
  return (
    <Card title="Data management">
      <DisabledWithReason label="Download a copy of all data" reason="Data export is not available yet. It is planned for a later version." />
      <Notice tone="warning" title="Erase everything">
        <p>Permanently deletes {patient.display_name}’s profile, Memory Bank and photos, activity history, observations, reports and consent records, and signs out their phone. This cannot be undone.</p>
        <Button variant="danger" onClick={() => setOpen(true)}>Erase all data…</Button>
      </Notice>
      <Dialog
        open={open}
        title="Erase all data permanently?"
        onClose={() => { setOpen(false); setTyped('') }}
        footer={
          <>
            <Button
              variant="danger"
              disabled={typed !== patient.display_name}
              pending={erase.pending}
              onClick={async () => {
                if (await erase.run()) navigate('/app/patients', { replace: true })
              }}
            >
              Erase permanently
            </Button>
            <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
          </>
        }
      >
        <TextField label={`Type “${patient.display_name}” to confirm`} value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
        <ActionError error={erase.error} />
      </Dialog>
    </Card>
  )
}
