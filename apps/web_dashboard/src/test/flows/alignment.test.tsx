// Caregiver tiredness level and the step-by-step session record. SYNTHETIC data only.
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Observation, SessionEvent } from '../../api/types'
import { analytics, baseRoutes, calls, CAREGIVER, mockApi, observation, P, PATIENT, renderApp, reviewItem } from '../harness'
import { DIAGNOSTIC_WORDS } from '../banned-words'

describe('tiredness level', () => {
  it('sends the level for tiredness notes only, and shows it', async () => {
    let saved: Observation[] = []
    mockApi([
      ...baseRoutes(CAREGIVER),
      { path: `${P}/observations`, handler: () => saved },
      {
        method: 'POST',
        path: `${P}/observations`,
        handler: ({ body }) => {
          const o = observation({ ...(body as Partial<Observation>), id: `o${saved.length + 1}`, author_id: CAREGIVER.id })
          saved = [o, ...saved]
          return o
        },
      },
    ])
    renderApp(`/app/patients/${PATIENT.id}/observations`)
    expect(await screen.findByText(/Only the level and time go to the phone, never your note/)).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('How tired'), 'severe')
    await userEvent.type(screen.getByLabelText(/^Note/), 'Synthetic: dozing in the chair')
    await userEvent.click(screen.getByRole('button', { name: 'Save observation' }))
    expect(await screen.findByText(/Level: Very tired/)).toBeInTheDocument()
    const first = calls.filter((c) => c.method === 'POST')[0].body as Record<string, unknown>
    expect(first.fatigue_level).toBe('severe')

    await userEvent.selectOptions(screen.getByLabelText('About'), 'mood')
    expect(screen.queryByLabelText('How tired')).toBeNull()
    await userEvent.type(screen.getByLabelText(/^Note/), 'Synthetic: cheerful')
    await userEvent.click(screen.getByRole('button', { name: 'Save observation' }))
    await screen.findByText('Synthetic: cheerful')
    const second = calls.filter((c) => c.method === 'POST')[1].body as Record<string, unknown>
    expect(second.fatigue_level).toBeNull()
  })
})

describe('tiredness note delivery to the phone', () => {
  it('says honestly whether the phone has each note', async () => {
    mockApi([
      {
        path: `${P}/observations`,
        handler: () => [
          observation({ id: 'o-sent', fatigue_level: 'severe', note: 'Synthetic: very sleepy' }),
          observation({ id: 'o-wait', fatigue_level: 'mild', note: 'Synthetic: a bit slow today' }),
          observation({ id: 'o-mood', category: 'mood', note: 'Synthetic: cheerful' }),
        ],
      },
      {
        path: `${P}/fatigue-delivery`,
        handler: () => ({
          devices: [{ device_name: 'Synthetic phone', last_sync_at: '2026-10-05T04:00:00Z' }],
          items: [
            { observation_id: 'o-sent', status: 'sent', sent_at: '2026-10-05T04:00:00Z' },
            { observation_id: 'o-wait', status: 'waiting', sent_at: null },
          ],
        }),
      },
      ...baseRoutes(CAREGIVER),
    ])
    renderApp(`/app/patients/${PATIENT.id}/observations`)
    expect(await screen.findByTestId('delivery-o-sent')).toHaveTextContent(/On the phone \(the phone last synced/)
    expect(screen.getByTestId('delivery-o-wait')).toHaveTextContent(
      /Not on the phone yet.*Waiting for the phone to sync/,
    )
    expect(screen.queryByTestId('delivery-o-mood')).toBeNull()
  })
})

describe('session history', () => {
  const event = (seq: number, event_type: SessionEvent['event_type'], data: Record<string, unknown>, round: number | null = 0): SessionEvent => ({
    id: `e${seq}`,
    session_id: 's1',
    activity_id: 'a1',
    seq,
    event_type,
    occurred_at: `2026-10-05T04:3${seq}:00Z`,
    round_index: round,
    data,
  })

  it('shows what happened, including what the app changed and why', async () => {
    mockApi([
      ...baseRoutes(CAREGIVER),
      {
        path: `${P}/sessions`,
        handler: () => [
          { id: 's1', patient_id: PATIENT.id, status: 'completed', end_reason: 'fatigue_detected', started_at: '2026-10-05T04:30:00Z', ended_at: '2026-10-05T04:40:00Z', created_at: '2026-10-05T04:30:00Z' },
        ],
      },
      {
        path: `${P}/sessions/s1/events`,
        handler: () => [
          event(0, 'activity_started', { rounds_planned: 4, difficulty: 2 }, null),
          event(1, 'attempt', { correct: false, latency_ms: 4200 }),
          event(2, 'attempt', { correct: false, latency_ms: 5100 }),
          event(3, 'adaptation', { action: 'show_hint', reason_codes: ['REPEATED_ERRORS_IN_ROUND'] }),
          event(4, 'fatigue_reported', { source: 'caregiver', level: 'severe' }),
          event(5, 'adaptation', { action: 'end_session', reason_codes: ['SEVERE_FATIGUE_END_SESSION', 'CAREGIVER_REPORT'] }),
          event(6, 'activity_ended', { outcome: 'tired' }, null),
        ],
      },
    ])
    const { container } = renderApp(`/app/patients/${PATIENT.id}/history`)
    await userEvent.click(await screen.findByRole('button', { name: 'What happened' }))
    expect(await screen.findByText('Started (4 rounds, level 2)')).toBeInTheDocument()
    expect(screen.getByText('Not this one after 4.2 s')).toBeInTheDocument()
    expect(screen.getByText('The app showed a hint because several answers in a row were not right')).toBeInTheDocument()
    expect(screen.getByText('Tiredness reported by a caregiver (very tired)')).toBeInTheDocument()
    expect(screen.getByText('The app ended the activity because they were very tired; reported by a caregiver')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(DIAGNOSTIC_WORDS)
  })

  it('says so when a session has no step-by-step record', async () => {
    mockApi([
      ...baseRoutes(CAREGIVER),
      {
        path: `${P}/sessions`,
        handler: () => [
          { id: 's1', patient_id: PATIENT.id, status: 'completed', end_reason: 'completed', started_at: '2026-10-05T04:30:00Z', ended_at: '2026-10-05T04:40:00Z', created_at: '2026-10-05T04:30:00Z' },
        ],
      },
      { path: `${P}/sessions/s1/events`, handler: () => [] },
    ])
    renderApp(`/app/patients/${PATIENT.id}/history`)
    await userEvent.click(await screen.findByRole('button', { name: 'What happened' }))
    expect(await screen.findByText(/No step-by-step record for this session/)).toBeInTheDocument()
  })
})

describe('caregiver analytics (Part 5)', () => {
  it('warns that numbers may be incomplete, shows support given, and keeps unknown as unknown', async () => {
    mockApi([
      {
        path: `${P}/analytics`,
        handler: () =>
          analytics({
            sync: {
              phone_paired: true,
              last_phone_sync_at: '2026-10-05T04:00:00Z',
              may_be_incomplete: true,
              reason: 'the phone has not shared its records since the end of this period; activities done offline may be missing',
            },
            support: {
              sessions_with_events: 2,
              sessions_started: 4,
              hints_asked_for: 3,
              hints_given_automatically: 1,
              read_aloud_presses: 0,
              pauses_by_person: 1,
              pauses_screen_left: 2,
              stop_requests: 1,
              rests_taken: 1,
              rests_declined: 0,
              adjustments: { shorten: 2, show_hint: 1 },
            },
          }),
      },
      ...baseRoutes(CAREGIVER),
    ])
    renderApp(`/app/patients/${PATIENT.id}/analytics`)
    expect(await screen.findByText('These numbers may be incomplete')).toBeInTheDocument()
    expect(screen.getByText(/The phone has not shared its records since the end of this period/)).toBeInTheDocument()
    expect(screen.getByText(/From the step-by-step record of 2 of 4 sessions/)).toBeInTheDocument()
    expect(screen.getByText('Activities shortened by the app').nextSibling).toHaveTextContent('2')
  })

  it('says when there is no step-by-step record instead of showing zeros', async () => {
    mockApi([
      { path: `${P}/analytics`, handler: () => analytics({ support: { sessions_with_events: 0, sessions_started: 3 } }) },
      ...baseRoutes(CAREGIVER),
    ])
    renderApp(`/app/patients/${PATIENT.id}/analytics`)
    expect(await screen.findByText(/No step-by-step record for these sessions/)).toBeInTheDocument()
    expect(screen.queryByText('Hints asked for')).toBeNull()
  })

  it('shows what a review item is based on and lets a caregiver add context', async () => {
    let item = reviewItem({
      evidence: {
        result_ids: ['r1', 'r2'],
        results_considered: 7,
        activities: ['Matching pairs'],
        missing_days: ['2026-10-04'],
        limitations: ['LOW_ENJOYMENT: too few enjoyment answers'],
      },
      context_notes: [],
    })
    mockApi([
      { path: `${P}/analytics`, handler: () => analytics() },
      { method: 'POST', path: `${P}/review-items/scan`, handler: () => [item] },
      { path: `${P}/review-items`, handler: () => [item] },
      {
        method: 'POST',
        path: `${P}/review-items/ri-1/context`,
        handler: ({ body }) => {
          item = { ...item, context_notes: [{ by: CAREGIVER.id, at: '2026-10-10T05:00:00Z', note: (body as { note: string }).note }] }
          return item
        },
      },
      ...baseRoutes(CAREGIVER, { manager: false }),
    ])
    renderApp(`/app/patients/${PATIENT.id}/analytics`)
    await userEvent.click(await screen.findByText('What this is based on'))
    expect(screen.getByText(/7 recorded activities \(Matching pairs\)/)).toBeInTheDocument()
    expect(screen.getByText('LOW_ENJOYMENT: too few enjoyment answers')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^Add context: / }))
    await userEvent.type(screen.getByLabelText(/^Context/), 'Synthetic: relatives visiting')
    await userEvent.click(screen.getByRole('button', { name: 'Save context' }))
    expect(await screen.findByText(/Context added .*: Synthetic: relatives visiting/)).toBeInTheDocument()
    const sent = calls.find((c) => c.path.endsWith('/context'))
    expect(sent?.body).toEqual({ note: 'Synthetic: relatives visiting' })
    // A helper can add context but still cannot decide.
    expect(screen.getByText('A managing family member decides on review items.')).toBeInTheDocument()
  })
})
