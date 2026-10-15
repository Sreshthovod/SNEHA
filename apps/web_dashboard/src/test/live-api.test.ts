// @vitest-environment node
/**
 * Opt-in end-to-end check of the dashboard API layer against a REAL running API.
 * Skipped unless VITE_LIVE_API_URL is set, e.g.:
 *   VITE_LIVE_API_URL=http://127.0.0.1:8770 npm test -- live-api
 * Uses synthetic data only.
 */
import { describe, expect, it } from 'vitest'
import { getHistory, listActivities } from '../api/activities'
import { getMe, login, logout, register } from '../api/auth'
import { ApiError, setApiBaseUrl } from '../api/client'
import { getConsents, recordConsent } from '../api/consents'
import { downloadFile, uploadMedia } from '../api/files'
import { createMemory, listMemories } from '../api/memories'
import { createObservation, listObservations } from '../api/observations'
import { createGrant, createPairingCode, createPatient, erasePatient, listPatients } from '../api/patients'
import { listReports, reportPdfAvailable, requestReport } from '../api/reports'
import { getAnalytics } from '../api/analytics'
import { resolveObservation, reviewObservation } from '../api/observations'
import { getProgress, putPreferences } from '../api/personalization'
import type { Recommendation, ResultSubmissionOut } from '../api/types'

const LIVE = import.meta.env.VITE_LIVE_API_URL
const PNG = Uint8Array.from(
  atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4//8/AAX+Av6nNYGEAAAAAElFTkSuQmCC'),
  (c) => c.charCodeAt(0),
)

describe.skipIf(!LIVE)('live API smoke test', () => {
  it('register → login → patient → consent → memory → observation → history → report → erase', async () => {
    setApiBaseUrl(LIVE!)
    const run = Math.random().toString(36).slice(2, 8)
    const email = `synthetic.dash.${run}@example.org`
    const password = 'synthetic passphrase 123'

    await register({ email, password, full_name: 'Synthetic Dashboard Caregiver', role: 'caregiver' })
    const token = await login({ email, password })
    expect(token.user.role).toBe('caregiver')
    expect((await getMe()).email).toBe(email)

    const patient = await createPatient({
      display_name: `Synthetic Live ${run}`,
      preferred_language: 'as',
      relationship_label: 'daughter',
      timezone: 'Asia/Kolkata',
    })
    expect((await listPatients()).map((p) => p.id)).toContain(patient.id)

    await recordConsent(patient.id, { consent_type: 'data_processing', status: 'granted', given_by: 'patient' })
    expect((await getConsents(patient.id)).current.data_processing).toBe('granted')

    const photo = await uploadMedia(patient.id, new File([PNG], 'photo.png', { type: 'image/png' }))
    expect(photo.content_type).toBe('image/png')
    const memory = await createMemory(patient.id, {
      kind: 'place',
      title: 'Synthetic tea garden',
      tags: ['garden'],
      media_file_id: photo.id,
    })
    expect(memory.status).toBe('approved')
    expect((await listMemories(patient.id, 'approved')).map((m) => m.id)).toContain(memory.id)
    const bytes = new Uint8Array(await (await downloadFile(photo.id)).arrayBuffer())
    expect(Array.from(bytes.slice(0, 4))).toEqual([0x89, 0x50, 0x4e, 0x47])

    await createObservation(patient.id, {
      category: 'fatigue',
      note: 'Synthetic: tired after lunch',
      observed_at: new Date().toISOString(),
    })
    expect((await listObservations(patient.id))[0].category).toBe('fatigue')

    expect((await listActivities()).length).toBeGreaterThanOrEqual(10)
    const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date())
    const history = await getHistory(patient.id, today, today)
    expect(history.total_results).toBe(0)
    expect(history.missing_days).toEqual([today])

    const start = new Date(Date.now() - 8 * 86400000)
    const startDay = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(start)
    const report = await requestReport(patient.id, { period_start: startDay, period_end: today })
    expect(report.status).toBe('ready') // PDFs are generated during the request (Stage 6)
    expect(reportPdfAvailable(report)).toBe(true)
    expect((await listReports(patient.id)).length).toBe(1)

    const code = await createPairingCode(patient.id)
    expect(code.code).toMatch(/^[A-Z0-9]{4}-[A-Z0-9]{4}$/)

    // Unverified clinicians cannot be granted access.
    await recordConsent(patient.id, { consent_type: 'clinician_sharing', status: 'granted', given_by: 'patient' })
    const drEmail = `synthetic.dr.${run}@example.org`
    await register({ email: drEmail, password, full_name: 'Synthetic Clinician', role: 'clinician' })
    const grantError = await createGrant(patient.id, {
      clinician_email: drEmail,
      expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
      purpose: 'Synthetic review',
    }).catch((e: unknown) => e)
    expect(grantError).toBeInstanceOf(ApiError)
    expect((grantError as ApiError).code).toBe('clinician_not_verified')

    await erasePatient(patient.id, `Synthetic Live ${run}`)
    expect((await listPatients()).map((p) => p.id)).not.toContain(patient.id)

    await logout()
    await expect(getMe()).rejects.toMatchObject({ status: 401 })
    setApiBaseUrl(null)
  }, 30000)

  it('device session → recommendation → results → analytics → fatigue note → review/resolve → PDF report', async () => {
    setApiBaseUrl(LIVE!)
    const run = Math.random().toString(36).slice(2, 8)
    const email = `synthetic.e2e.${run}@example.org`
    const password = 'synthetic passphrase 123'
    await register({ email, password, full_name: 'Synthetic E2E Caregiver', role: 'caregiver' })
    await login({ email, password })
    const name = `Synthetic E2E ${run}`
    const patient = await createPatient({ display_name: name, preferred_language: 'as', relationship_label: 'son', timezone: 'Asia/Kolkata' })
    await recordConsent(patient.id, { consent_type: 'data_processing', status: 'granted', given_by: 'patient' })
    await putPreferences(patient.id, { interests: ['tools'], disliked_activity_slugs: [], session_minutes: 15 })

    // Pair the patient's phone through the real API, then act as the device.
    const code = await createPairingCode(patient.id)
    const pair = await fetch(`${LIVE}/api/v1/auth/device/pair`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code.code, device_name: 'Synthetic phone' }),
    })
    expect(pair.status).toBe(200)
    const deviceToken = ((await pair.json()) as { access_token: string }).access_token
    async function device<T>(path: string, body: unknown): Promise<T> {
      const r = await fetch(`${LIVE}/api/v1${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${deviceToken}` },
        body: JSON.stringify(body),
      })
      expect(r.status, `${path} → ${r.status}`).toBeLessThan(300)
      return (await r.json()) as T
    }

    const sessionId = crypto.randomUUID()
    const t0 = Date.now() - 30 * 60_000
    await device(`/patients/${patient.id}/sessions`, { id: sessionId, started_at: new Date(t0).toISOString() })
    let rec = await device<Recommendation>('/activities/next', { patient_id: patient.id, session_id: sessionId })
    expect(rec.action).toBe('activity')
    expect(rec.activity_slug).toBe('name-the-object') // approved interest "tools"
    expect(rec.reason_codes).toContain('INTEREST_MATCH')
    for (let i = 0; i < 2; i++) {
      const start = t0 + (i + 1) * 5 * 60_000
      const out = await device<ResultSubmissionOut>('/activities/result', {
        patient_id: patient.id,
        session_id: sessionId,
        result: {
          id: crypto.randomUUID(),
          activity_id: rec.activity_id,
          difficulty_level: rec.difficulty,
          started_at: new Date(start).toISOString(),
          completed_at: new Date(start + 2 * 60_000).toISOString(),
          score: 0.9,
          correct_count: 9,
          attempt_count: 10,
          hint_count: 0,
          duration_ms: 120_000,
          metrics: { mean_response_ms: 2100 },
          engagement: 'enjoyed',
          recommendation_id: rec.id,
        },
      })
      expect(out.duplicate).toBe(false)
      rec = out.next
      expect(rec.activity_slug).not.toBeNull()
    }

    const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date())
    const nineDaysAgo = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date(Date.now() - 8 * 86400000))
    const analytics = await getAnalytics(patient.id, nineDaysAgo, today)
    expect(analytics.totals.results).toBe(2)
    expect(analytics.engagement.enjoyed).toBe(2)
    expect(analytics.completeness.days_with_activity).toBeGreaterThanOrEqual(1)
    expect(analytics.baseline.status).toBe('insufficient_data')

    const progress = await getProgress(patient.id)
    // The second activity differs from the first: the engine avoids repeating itself.
    expect(progress.activities.reduce((n, a) => n + a.results, 0)).toBe(2)
    expect(progress.activities.find((a) => a.slug === 'name-the-object')?.results).toBe(1)
    expect(progress.recent_recommendations.length).toBeGreaterThanOrEqual(3)

    // A caregiver tiredness note changes the next suggestion on the phone.
    const note = await createObservation(patient.id, {
      category: 'fatigue',
      note: 'Synthetic: tired after lunch',
      observed_at: new Date(Date.now() - 10 * 60_000).toISOString(),
    })
    const gentle = await device<Recommendation>('/activities/next', { patient_id: patient.id, session_id: sessionId })
    expect(gentle.reason_codes).toContain('RECENT_FATIGUE_OBSERVATION')
    expect(gentle.difficulty).toBe(1)
    const reviewed = await reviewObservation(patient.id, note.id, { expected_version: note.version, note: 'Synthetic review' })
    expect(reviewed.status).toBe('reviewed')
    const resolved = await resolveObservation(patient.id, note.id, { expected_version: reviewed.version, note: 'Synthetic: rested' })
    expect(resolved.status).toBe('resolved')
    expect((await listObservations(patient.id, { status: 'resolved' })).map((o) => o.id)).toContain(note.id)

    const report = await requestReport(patient.id, { period_start: nineDaysAgo, period_end: today })
    expect(report.status).toBe('ready')
    const pdf = new Uint8Array(await (await downloadFile(report.file_id!)).arrayBuffer())
    expect(new TextDecoder().decode(pdf.slice(0, 5))).toBe('%PDF-')

    await erasePatient(patient.id, name)
    await logout()
    setApiBaseUrl(null)
  }, 60000)
})
