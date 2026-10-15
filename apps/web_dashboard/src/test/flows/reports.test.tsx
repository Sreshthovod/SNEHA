import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Report } from '../../api/types'
import { analytics, apiError, baseRoutes, calls, CAREGIVER, CLINICIAN, mockApi, P, PATIENT, renderApp } from '../harness'

const report: Report = {
  id: 'r1',
  patient_id: PATIENT.id,
  period_start: '2026-09-30T18:30:00Z',
  period_end: '2026-10-09T18:30:00Z',
  status: 'pending',
  requested_by_id: 'x',
  file_id: null,
  generated_at: null,
  error_message: null,
  created_at: '2026-10-10T00:00:00Z',
  automated: false,
  method_version: null,
}
const ready: Report = { ...report, status: 'ready', file_id: 'f-pdf', generated_at: '2026-10-10T01:00:00Z', method_version: 'analytics-1.0' }
const failed: Report = { ...report, status: 'failed', error_message: 'The report could not be generated. Please try again.' }

function stubDownload() {
  const createObjectURL = vi.fn(() => 'blob:pdf')
  Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() })
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  return { createObjectURL, click }
}

describe('reports', () => {
  it('requesting a report yields a ready PDF that downloads with the sign-in token', async () => {
    const { click, createObjectURL } = stubDownload()
    mockApi([
      ...baseRoutes(CAREGIVER),
      { path: `${P}/reports`, handler: () => [] },
      { method: 'POST', path: `${P}/reports`, handler: () => json201(ready) },
      { path: '/files/f-pdf/content', handler: () => new Response(new Blob(['%PDF-1.7'], { type: 'application/pdf' })) },
    ])
    renderApp(`/app/patients/${PATIENT.id}/reports`)
    const first = await screen.findByLabelText(/First day/)
    await userEvent.clear(first)
    await userEvent.type(first, '2026-10-01')
    await userEvent.click(screen.getByRole('button', { name: 'Request report' }))
    expect(await screen.findByText('Report ready')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ period_start: '2026-10-01', period_end: '2026-10-09' })
    await userEvent.click(screen.getByRole('button', { name: 'Download PDF' }))
    await waitFor(() => expect(click).toHaveBeenCalled())
    const fileCall = calls.find((c) => c.path === '/files/f-pdf/content')!
    expect(fileCall.headers.get('Authorization')).toBe('Bearer test-token')
    expect(createObjectURL).toHaveBeenCalled()
  })

  it('a failed report offers "Prepare again", which retries and then allows download', async () => {
    mockApi([
      ...baseRoutes(CAREGIVER),
      { path: `${P}/reports`, handler: () => [] },
      { method: 'POST', path: `${P}/reports`, handler: () => json201(failed) },
      { method: 'POST', path: `${P}/reports/r1/generate`, handler: () => ready },
    ])
    renderApp(`/app/patients/${PATIENT.id}/reports`)
    await userEvent.click(await screen.findByRole('button', { name: 'Request report' }))
    expect(await screen.findByText('The report could not be prepared')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Prepare again' }))
    expect(await screen.findByText('Report ready')).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST' && c.path === `${P}/reports/r1/generate`)).toBe(true)
  })

  it('retry conflict (already ready) shows the server message', async () => {
    mockApi([
      ...baseRoutes(CLINICIAN),
      { path: `${P}/reports/r1`, handler: () => failed },
      { path: `${P}/analytics`, handler: () => analytics() },
      { method: 'POST', path: `${P}/reports/r1/generate`, handler: () => apiError(409, 'report_ready', 'This report is already ready to download.') },
    ])
    renderApp(`/app/patients/${PATIENT.id}/reports/r1`)
    await userEvent.click(await screen.findByRole('button', { name: 'Prepare again' }))
    expect(await screen.findByText('This report is already ready to download.')).toBeInTheDocument()
  })

  it('viewer: pending report has PDF disabled with a reason and shows the period analytics', async () => {
    mockApi([
      ...baseRoutes(CLINICIAN),
      { path: `${P}/reports/r1`, handler: () => report },
      { path: `${P}/analytics`, handler: ({ url }) => analytics({ from_date: url.searchParams.get('from')!, to_date: url.searchParams.get('to')! }) },
    ])
    renderApp(`/app/patients/${PATIENT.id}/reports/r1`)
    const button = await screen.findByRole('button', { name: 'Download PDF' })
    expect(button).toBeDisabled()
    expect(button).toHaveAccessibleDescription(/not available yet/)
    expect(screen.getByText(/1 Oct 2026 – 9 Oct 2026/)).toBeInTheDocument()
    const call = calls.find((c) => c.path.endsWith('/analytics'))!
    expect(call).toBeTruthy()
    expect(await screen.findByText(/not a medical assessment/)).toBeInTheDocument()
  })

  it('viewer: ready report downloads', async () => {
    const { click } = stubDownload()
    mockApi([
      ...baseRoutes(CLINICIAN),
      { path: `${P}/reports/r1`, handler: () => ready },
      { path: `${P}/analytics`, handler: () => analytics() },
      { path: '/files/f-pdf/content', handler: () => new Response(new Blob(['%PDF-1.7'], { type: 'application/pdf' })) },
    ])
    renderApp(`/app/patients/${PATIENT.id}/reports/r1`)
    const button = await screen.findByRole('button', { name: 'Download PDF' })
    expect(button).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Prepare again' })).toBeNull()
    await userEvent.click(button)
    await waitFor(() => expect(click).toHaveBeenCalled())
  })
})

function json201(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 201, headers: { 'Content-Type': 'application/json' } })
}
