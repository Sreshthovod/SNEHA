// Memory Bank: relationship, safe re-submission, what the phone does with a memory,
// and which memories a session used. SYNTHETIC data only.
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Memory, SessionEvent } from '../../api/types'
import { apiError, baseRoutes, calls, CAREGIVER, CLINICIAN, mockApi, P, PATIENT, renderApp } from '../harness'

const memory = (over: Partial<Memory>): Memory => ({
  id: 'm-1',
  patient_id: PATIENT.id,
  kind: 'person',
  title: 'Synthetic Mina',
  description: 'Visits on Sundays.',
  approx_year: 2015,
  relationship: 'granddaughter',
  tags: ['family'],
  media_file_id: 'f-1',
  status: 'approved',
  source: 'dashboard',
  version: 1,
  created_by_id: CAREGIVER.id,
  reviewed_by_id: CAREGIVER.id,
  reviewed_at: '2026-10-01T00:00:00Z',
  review_note: null,
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
  ...over,
})

const garden = memory({ id: 'm-2', kind: 'place', title: 'Synthetic tea garden', relationship: null, media_file_id: 'f-2' })
const pendingCousin = memory({ id: 'm-3', title: 'Synthetic cousin', status: 'pending_approval', media_file_id: null })

describe('caregiver Memory Bank', () => {
  it('asks how a person is related, only for people, and sends a client ID once', async () => {
    const posted: Array<Record<string, unknown>> = []
    let attempt = 0
    mockApi([
      { path: `${P}/memories`, handler: () => [] },
      {
        method: 'POST',
        path: `${P}/memories`,
        handler: ({ body }) => {
          posted.push(body as Record<string, unknown>)
          attempt += 1
          // First answer lost (as if the network dropped): the retry gets id_conflict.
          if (attempt === 1) return apiError(503, 'unavailable', 'Lost response')
          return apiError(409, 'id_conflict', 'A memory with this ID already exists.')
        },
      },
      {
        path: /\/memories\/[0-9a-f-]{36}$/,
        handler: ({ url }) => memory({ id: url.pathname.split('/').pop()!, title: 'Synthetic Bijoy' }),
      },
      ...baseRoutes(CAREGIVER),
    ])
    renderApp(`/app/patients/${PATIENT.id}/memories`)
    await userEvent.click(await screen.findByRole('button', { name: 'Add a memory' }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByLabelText(/How is this person related to/)).toBeInTheDocument()
    await userEvent.selectOptions(within(dialog).getByLabelText('Type'), 'place')
    expect(within(dialog).queryByLabelText(/How is this person related to/)).toBeNull()
    await userEvent.selectOptions(within(dialog).getByLabelText('Type'), 'person')
    await userEvent.type(within(dialog).getByLabelText(/^Title/), 'Synthetic Bijoy')
    await userEvent.type(within(dialog).getByLabelText(/How is this person related to/), 'grandson')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    expect(await within(dialog).findByText('Lost response')).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Memory added.')).toBeInTheDocument()
    expect(posted).toHaveLength(2)
    expect(posted[0].relationship).toBe('grandson')
    expect(posted[0].id).toMatch(/^[0-9a-f-]{36}$/)
    expect(posted[1].id).toBe(posted[0].id)
  })

  it('explains whether a memory is on the phone and which activities it can feed', async () => {
    mockApi([
      { path: `${P}/memories`, handler: ({ url }) => (url.searchParams.get('status') === 'approved' ? [memory({}), garden] : [memory({}), garden, pendingCousin]) },
      { path: `${P}/memory-relationships`, handler: () => [{ id: 'l-1', from_memory_id: 'm-1', to_memory_id: 'm-2', relation_type: 'located_at', created_at: '2026-10-01T00:00:00Z' }] },
      ...baseRoutes(CAREGIVER),
    ])
    renderApp(`/app/patients/${PATIENT.id}/memories`)
    const mina = (await screen.findByRole('heading', { name: 'Synthetic Mina' })).closest('article')!
    expect(within(mina).getByText(/Person · granddaughter/)).toBeInTheDocument()
    await userEvent.click(within(mina).getByText('How SNEHA uses this'))
    expect(within(mina).getByText(/phone downloads it, with the photo, at its next sync/)).toBeInTheDocument()
    expect(within(mina).getByText('Photo recall')).toBeInTheDocument()
    expect(within(mina).getByText(/Hint: “granddaughter”/)).toBeInTheDocument()
    expect(within(mina).getByText(/Synthetic Mina is at Synthetic tea garden/)).toBeInTheDocument()

    const cousin = screen.getByRole('heading', { name: 'Synthetic cousin' }).closest('article')!
    await userEvent.click(within(cousin).getByText('How SNEHA uses this'))
    expect(within(cousin).getByText('Not on the phone: waiting for approval.')).toBeInTheDocument()
    expect(within(cousin).queryByText('Photo recall')).toBeNull()
  })
})

describe('session timeline', () => {
  const events: SessionEvent[] = [
    {
      id: 'e0', session_id: 's1', activity_id: 'a1', seq: 0, event_type: 'activity_started',
      occurred_at: '2026-10-05T04:30:00Z', round_index: null,
      data: { rounds_planned: 2, difficulty: 1, memory_ids: ['m-1', 'm-gone'], content_source: 'personal', reason_codes: ['PERSONAL_PHOTOS_USED'] },
    },
    {
      id: 'e1', session_id: 's1', activity_id: 'a1', seq: 1, event_type: 'attempt',
      occurred_at: '2026-10-05T04:30:10Z', round_index: 0, data: { correct: true, latency_ms: 2100, memory_id: 'm-1' },
    },
  ]
  const routes = (user: typeof CAREGIVER) => [
    { path: `${P}/sessions`, handler: () => [{ id: 's1', patient_id: PATIENT.id, status: 'completed', end_reason: 'completed', started_at: '2026-10-05T04:30:00Z', ended_at: '2026-10-05T04:40:00Z', created_at: '2026-10-05T04:30:00Z' }] },
    { path: `${P}/sessions/s1/events`, handler: () => events },
    { path: `${P}/memories`, handler: () => [memory({})] },
    ...baseRoutes(user),
  ]

  it('names the approved memories a session used, for the family', async () => {
    mockApi(routes(CAREGIVER))
    renderApp(`/app/patients/${PATIENT.id}/history`)
    await userEvent.click(await screen.findByRole('button', { name: 'What happened' }))
    expect(await screen.findByText(/with 2 approved memories: Synthetic Mina, a family memory · family photos/)).toBeInTheDocument()
    expect(screen.getByText('Right answer after 2.1 s (Synthetic Mina)')).toBeInTheDocument()
  })

  it('never shows memory titles to a clinician', async () => {
    mockApi(routes(CLINICIAN))
    renderApp(`/app/patients/${PATIENT.id}/history`)
    await userEvent.click(await screen.findByRole('button', { name: 'What happened' }))
    expect(await screen.findByText(/with 2 approved memories: a family memory, a family memory/)).toBeInTheDocument()
    expect(screen.queryByText(/Synthetic Mina/)).toBeNull()
    expect(calls.some((c) => c.path === `${P}/memories`)).toBe(false)
  })
})
