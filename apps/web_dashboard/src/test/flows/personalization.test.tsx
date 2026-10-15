import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { CatalogEntry, Preferences, Progress } from '../../api/types'
import { baseRoutes, calls, CAREGIVER, CLINICIAN, mockApi, P, PATIENT, renderApp } from '../harness'
import { DIAGNOSTIC_WORDS } from '../banned-words'

const prefs: Preferences = {
  patient_id: PATIENT.id,
  preferred_language: 'as',
  interests: ['tea'],
  disliked_activity_slugs: [],
  session_minutes: 15,
  memory_tags: { garden: 2, tea: 1 },
  updated_at: null,
  updated_by_id: null,
}

const catalog: CatalogEntry[] = [
  {
    id: 'a1', slug: 'picture-pairs', title: 'Matching pairs', version: 1, description: 'Pairs', activity_type: 'picture_matching',
    cognitive_domains: [], min_difficulty: 1, max_difficulty: 5, default_duration_seconds: 300, supports_offline: true,
    uses_memory_bank: false, instructions: 'x', hint: 'x', evaluation: 'x', stop: 'x', accessibility: 'x',
    levels: [{ level: 1, parameters: { pairs: 3 } }], content_languages: ['*'], interest_tags: [],
  },
  {
    id: 'a2', slug: 'sort-into-groups', title: 'Sort into groups', version: 1, description: 'Sort', activity_type: 'categorization',
    cognitive_domains: [], min_difficulty: 1, max_difficulty: 3, default_duration_seconds: 180, supports_offline: true,
    uses_memory_bank: false, instructions: 'x', hint: 'x', evaluation: 'x', stop: 'x', accessibility: 'x',
    levels: [{ level: 1, parameters: {} }], content_languages: ['en'], interest_tags: ['gardening'],
  },
]

const progress: Progress = {
  patient_id: PATIENT.id,
  algorithm_version: '1.0.0',
  config_version: '2026.10.1',
  disclaimer: 'Recommendations follow engagement rules to keep activities comfortable and enjoyable. They do not measure or indicate any medical condition.',
  activities: [
    {
      activity_id: 'a1', slug: 'picture-pairs', title: 'Matching pairs', current_difficulty: 2, min_difficulty: 1, max_difficulty: 5,
      results: 3, completed: 3, interrupted: 0, hints_used: 0, enjoyed: 3, neutral: 0, not_enjoyed: 0, fatigue_reports: 0,
      last_played_at: '2026-10-09T05:00:00Z', difficulty_reason: 'DIFFICULTY_INCREASED_AFTER_COMFORTABLE_SUCCESS',
    },
    {
      activity_id: 'a2', slug: 'sort-into-groups', title: 'Sort into groups', current_difficulty: 1, min_difficulty: 1, max_difficulty: 3,
      results: 0, completed: 0, interrupted: 0, hints_used: 0, enjoyed: 0, neutral: 0, not_enjoyed: 0, fatigue_reports: 0,
      last_played_at: null, difficulty_reason: 'DIFFICULTY_STARTING_LEVEL',
    },
  ],
  recent_recommendations: [
    {
      id: 'rec1', patient_id: PATIENT.id, session_id: null, action: 'break', activity_id: 'a1', activity_slug: 'picture-pairs',
      activity_title: 'Matching pairs', difficulty: 1, level_parameters: { pairs: 3 }, instructions: 'x', hints_enabled: true,
      break_minutes: 10, reason_codes: ['FATIGUE_REPORTED_BREAK', 'RECENT_FATIGUE_OBSERVATION', 'LOW_EFFORT_FOR_FATIGUE'],
      supporting: [{ kind: 'caregiver_observation', id: 'o1', detail: 'caregiver noted tiredness at 10:00 UTC' }],
      content_refs: { memory_item_ids: [], routine_item_ids: [] }, algorithm_version: '1.0.0', config_version: '2026.10.1',
      fallback: { used: false, reason: null }, created_at: '2026-10-09T05:10:00Z',
    },
    {
      id: 'rec0', patient_id: PATIENT.id, session_id: null, action: 'activity', activity_id: 'a1', activity_slug: 'picture-pairs',
      activity_title: 'Matching pairs', difficulty: 1, level_parameters: null, instructions: null, hints_enabled: false,
      break_minutes: null, reason_codes: ['COLD_START_DEFAULT', 'SOME_FUTURE_CODE'], supporting: [],
      content_refs: {}, algorithm_version: '1.0.0', config_version: '2026.10.1',
      fallback: { used: true, reason: 'no_history' }, created_at: '2026-10-08T05:10:00Z',
    },
  ],
}

function routes(user = CAREGIVER, manager = true) {
  return [
    ...baseRoutes(user, { manager }),
    { path: `${P}/preferences`, handler: () => prefs },
    { path: '/activities/catalog', handler: () => catalog },
    { path: `${P}/progress`, handler: () => progress },
  ]
}

describe('interests & preferences', () => {
  it('managers add and remove interests, mark disliked activities and save', async () => {
    mockApi([
      ...routes(),
      { method: 'PUT', path: `${P}/preferences`, handler: ({ body }) => ({ ...prefs, ...(body as object), updated_at: '2026-10-10T00:00:00Z' }) },
    ])
    renderApp(`/app/patients/${PATIENT.id}/preferences`)
    expect(await screen.findByText('tea')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/Add an interest/), '  Bihu {Enter}')
    expect(screen.getByText('bihu')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Add interest garden (used in 2 memories)' }))
    await userEvent.click(screen.getByRole('button', { name: 'Remove interest tea' }))
    await userEvent.type(screen.getByLabelText(/Add an interest/), 'bihu')
    await userEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(screen.getByText('This interest is already listed.')).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('Matching pairs'))
    await userEvent.click(screen.getByRole('button', { name: 'Save preferences' }))
    expect(await screen.findByText('Preferences saved.')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({
      interests: ['bihu', 'garden'],
      disliked_activity_slugs: ['picture-pairs'],
      session_minutes: 15,
    })
  })

  it('non-managing caregivers and clinicians see preferences read-only', async () => {
    for (const [user, manager] of [[CAREGIVER, false], [CLINICIAN, false]] as const) {
      mockApi(routes(user, manager))
      const { unmount } = renderApp(`/app/patients/${PATIENT.id}/preferences`)
      expect(await screen.findByText('tea')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Save preferences' })).toBeNull()
      expect(screen.queryByLabelText(/Add an interest/)).toBeNull()
      expect(screen.queryByRole('button', { name: /Remove interest/ })).toBeNull()
      unmount()
    }
  })
})

describe('progress & suggestions', () => {
  it('shows levels and explains recommendations in plain language', async () => {
    mockApi(routes())
    const { container } = renderApp(`/app/patients/${PATIENT.id}/progress`)
    expect(await screen.findByText('Level 2 of 5')).toBeInTheDocument()
    expect(screen.queryByText('Sort into groups')).toBeNull() // not played yet
    expect(screen.getByText(/The level went up one step after several comfortable successes/)).toBeInTheDocument()
    expect(screen.getByText('A rest first, then Matching pairs')).toBeInTheDocument()
    expect(screen.getByText('They said they were tired, so a rest was offered first.')).toBeInTheDocument()
    expect(screen.getByText('A caregiver noted tiredness recently.')).toBeInTheDocument()
    expect(screen.getByText(/rest for about 10 minutes/)).toBeInTheDocument()
    expect(screen.getByText(/Based on 1 stored record/)).toBeInTheDocument()
    expect(screen.getByText(/Caregiver note: caregiver noted tiredness/)).toBeInTheDocument()
    expect(screen.getByText(/Default choice: Standard first choice/)).toBeInTheDocument()
    expect(screen.getByText(/Other reason \(some future code\)/)).toBeInTheDocument()
    expect(screen.getByText(/do not measure or indicate any medical condition/)).toBeInTheDocument()
    expect(container.querySelector('main')?.textContent).not.toMatch(DIAGNOSTIC_WORDS)
  })

  it('clinicians can open progress (read only) but not the Memory Bank', async () => {
    mockApi(routes(CLINICIAN))
    renderApp(`/app/patients/${PATIENT.id}/progress`)
    expect(await screen.findByText('Level 2 of 5')).toBeInTheDocument()
    expect(screen.getByText('Read only.')).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Patient sections' })
    expect(nav).toHaveTextContent('Progress & suggestions')
    expect(nav).toHaveTextContent('Interests & preferences')
    expect(nav).not.toHaveTextContent('Memory Bank')
    expect(nav).not.toHaveTextContent('Family & devices')
  })
})
