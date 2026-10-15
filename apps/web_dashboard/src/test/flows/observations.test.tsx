import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Observation } from '../../api/types'
import { apiError, baseRoutes, calls, CAREGIVER, CLINICIAN, mockApi, observation, P, PATIENT, renderApp } from '../harness'

describe('caregiver observations', () => {
  it('requires a note, then saves a tiredness observation with a timezone-aware time', async () => {
    let saved: Observation[] = []
    mockApi([
      ...baseRoutes(CAREGIVER),
      { path: `${P}/observations`, handler: () => saved },
      {
        method: 'POST',
        path: `${P}/observations`,
        handler: ({ body }) => {
          const o = observation({ ...(body as Partial<Observation>), author_id: CAREGIVER.id })
          saved = [o]
          return o
        },
      },
    ])
    renderApp(`/app/patients/${PATIENT.id}/observations`)
    await userEvent.click(await screen.findByRole('button', { name: 'Save observation' }))
    expect(screen.getByText(/Write a short note/)).toBeInTheDocument()

    expect(screen.getByLabelText('About')).toHaveValue('fatigue')
    await userEvent.type(screen.getByLabelText(/^Note/), 'Tired after lunch, rested for an hour')
    await userEvent.click(screen.getByRole('button', { name: 'Save observation' }))
    expect(await screen.findByText('Observation saved.')).toBeInTheDocument()
    expect(await screen.findByText('Tired after lunch, rested for an hour')).toBeInTheDocument()
    const body = calls.find((c) => c.method === 'POST')!.body as { category: string; observed_at: string }
    expect(body.category).toBe('fatigue')
    expect(body.observed_at).toMatch(/Z$/)
  })

  it('shows source, status and timestamps, and filters by status', async () => {
    mockApi([...baseRoutes(CAREGIVER), { path: `${P}/observations`, handler: () => [observation({ source: 'device' })] }])
    renderApp(`/app/patients/${PATIENT.id}/observations`)
    expect(await screen.findByText(/Added on the person's phone/)).toBeInTheDocument()
    expect(screen.getByText('Open')).toBeInTheDocument()
    expect(screen.getByText(/recorded/)).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Show'), 'resolved')
    expect(calls.some((c) => c.path === `${P}/observations`)).toBe(true)
    // status is sent as a query parameter
    const url = (globalThis.fetch as unknown as { mock: { calls: [string][] } }).mock.calls.map((c) => String(c[0]))
    expect(url.some((u) => u.includes('status=resolved'))).toBe(true)
  })

  it('manager reviews, then resolves with a note', async () => {
    let current = observation({ author_id: 'someone-else' })
    mockApi([
      ...baseRoutes(CAREGIVER, { manager: true }),
      { path: `${P}/observations`, handler: () => [current] },
      {
        method: 'POST',
        path: `${P}/observations/o1/review`,
        handler: ({ body }) => {
          current = { ...current, status: 'reviewed', version: 2, reviewed_at: '2026-10-06T00:00:00Z', reviewed_by_id: CAREGIVER.id, review_note: (body as { note: string | null }).note }
          return current
        },
      },
      {
        method: 'POST',
        path: `${P}/observations/o1/resolve`,
        handler: ({ body }) => {
          current = { ...current, status: 'resolved', version: 3, resolved_at: '2026-10-07T00:00:00Z', resolved_by_id: CAREGIVER.id, resolution_note: (body as { note: string }).note }
          return current
        },
      },
    ])
    renderApp(`/app/patients/${PATIENT.id}/observations`)
    await userEvent.click(await screen.findByRole('button', { name: /Mark as reviewed:/ }))
    const dialog = screen.getByRole('dialog', { name: 'Mark as reviewed' })
    await userEvent.type(within(dialog).getByLabelText(/Review note/), 'Talked with the family')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Mark as reviewed' }))
    expect(await screen.findByText(/Review note: Talked with the family/)).toBeInTheDocument()
    expect(calls.find((c) => c.path.endsWith('/review'))?.body).toEqual({ expected_version: 1, note: 'Talked with the family' })

    await userEvent.click(screen.getByRole('button', { name: /Resolve:/ }))
    const resolve = screen.getByRole('dialog', { name: 'Resolve this note' })
    await userEvent.click(within(resolve).getByRole('button', { name: 'Resolve this note' }))
    expect(within(resolve).getByText(/how this was resolved/)).toBeInTheDocument()
    await userEvent.type(within(resolve).getByLabelText(/How was this resolved/), 'Rested more; fine now')
    await userEvent.click(within(resolve).getByRole('button', { name: 'Resolve this note' }))
    expect(await screen.findByText(/Resolution: Rested more; fine now/)).toBeInTheDocument()
    expect(calls.find((c) => c.path.endsWith('/resolve'))?.body).toEqual({ expected_version: 2, note: 'Rested more; fine now' })
    expect(screen.queryByRole('button', { name: /Correct:/ })).toBeNull()
  })

  it('correction needs a reason, sends only changed fields, and handles a version conflict', async () => {
    let conflict = true
    mockApi([
      ...baseRoutes(CAREGIVER, { manager: false }),
      { path: `${P}/observations`, handler: () => [observation({ author_id: CAREGIVER.id, version: conflict ? 1 : 2 })] },
      {
        method: 'PATCH',
        path: `${P}/observations/o1`,
        handler: () => {
          conflict = false
          return apiError(409, 'version_conflict', 'This observation was changed by someone else.')
        },
      },
      { path: `${P}/observations/o1/revisions`, handler: () => [] },
    ])
    renderApp(`/app/patients/${PATIENT.id}/observations`)
    // Non-managing author: can correct, cannot review/resolve.
    expect(await screen.findByRole('button', { name: /Correct:/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Mark as reviewed:/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Resolve:/ })).toBeNull()

    await userEvent.click(screen.getByRole('button', { name: /Correct:/ }))
    const dialog = screen.getByRole('dialog', { name: 'Correct this note' })
    const note = within(dialog).getByLabelText(/^Note/)
    await userEvent.clear(note)
    await userEvent.type(note, 'Tired after a long walk')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Correct this note' }))
    expect(within(dialog).getByText(/why this note is being corrected/)).toBeInTheDocument()
    await userEvent.type(within(dialog).getByLabelText(/Reason for the correction/), 'Wrong cause written')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Correct this note' }))
    expect(await within(dialog).findByText(/Someone else changed this note/)).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ expected_version: 1, reason: 'Wrong cause written', note: 'Tired after a long walk' })

    await userEvent.click(within(dialog).getByRole('button', { name: 'Show the latest version' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(await screen.findByText(/Someone else changed this note/)).toBeInTheDocument()
  })

  it('shows the revision history', async () => {
    mockApi([
      ...baseRoutes(CAREGIVER),
      { path: `${P}/observations`, handler: () => [observation({ version: 2, updated_at: '2026-10-06T00:00:00Z', note: 'Tired after a walk' })] },
      {
        path: `${P}/observations/o1/revisions`,
        handler: () => [
          { id: 'rev1', observation_id: 'o1', version: 1, category: 'fatigue', note: 'Tired after lunch', observed_at: '2026-10-05T10:00:00Z', corrected_by_id: CAREGIVER.id, correction_reason: 'Wrong cause', created_at: '2026-10-06T00:00:00Z' },
        ],
      },
    ])
    renderApp(`/app/patients/${PATIENT.id}/observations`)
    await userEvent.click(await screen.findByRole('button', { name: /History:/ }))
    expect(await screen.findByText('Tired after lunch')).toBeInTheDocument()
    expect(screen.getByText('Reason for correction: Wrong cause')).toBeInTheDocument()
    expect(screen.getByText(/version 2/)).toBeInTheDocument()
  })

  it('clinicians can read observations but cannot change them', async () => {
    mockApi([
      ...baseRoutes(CLINICIAN),
      { path: `${P}/observations`, handler: () => [observation({ category: 'sleep', note: 'Slept well', author_id: 'x' })] },
    ])
    renderApp(`/app/patients/${PATIENT.id}/observations`)
    expect(await screen.findByText('Slept well')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save observation' })).toBeNull()
    for (const name of [/Delete:/, /Correct:/, /Mark as reviewed:/, /Resolve:/]) {
      expect(screen.queryByRole('button', { name })).toBeNull()
    }
    expect(screen.getByRole('button', { name: /History:/ })).toBeInTheDocument()
  })
})
