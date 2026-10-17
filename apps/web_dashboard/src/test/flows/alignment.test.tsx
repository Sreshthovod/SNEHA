// Caregiver tiredness level and the step-by-step session record. SYNTHETIC data only.
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Observation, SessionEvent } from '../../api/types'
import { baseRoutes, calls, CAREGIVER, mockApi, observation, P, PATIENT, renderApp } from '../harness'
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
