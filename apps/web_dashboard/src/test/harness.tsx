import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { vi } from 'vitest'
import { setToken } from '../api/session'
import type { AnalyticsSummary, Observation, Patient, ReviewItem, User } from '../api/types'
import { routes } from '../routes'
import { AuthProvider } from '../state/AuthProvider'
import { SettingsProvider } from '../state/SettingsProvider'

type Handler = (req: { url: URL; method: string; body: unknown; init: RequestInit }) =>
  | Response
  | Promise<Response>
  | unknown

export interface Route {
  method?: string
  path: string | RegExp
  handler: Handler
}

/** All requests seen by the mock, for assertions. */
export const calls: Array<{ method: string; path: string; body: unknown; headers: Headers }> = []

export function json(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function apiError(status: number, code: string, message: string): Response {
  return json({ error: { code, message, request_id: 'test' } }, status)
}

/** Route fetch calls by method + path (after /api/v1). Unmatched calls fail loudly. */
export function mockApi(routesList: Route[]) {
  calls.length = 0
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init = {}) => {
    const url = new URL(String(input))
    const method = (init.method ?? 'GET').toUpperCase()
    const path = url.pathname.replace(/^\/api\/v1/, '')
    let body: unknown = undefined
    if (typeof init.body === 'string') body = JSON.parse(init.body)
    else if (init.body instanceof FormData) body = init.body
    calls.push({ method, path, body, headers: new Headers(init.headers) })
    const route = routesList.find(
      (r) =>
        (r.method ?? 'GET') === method &&
        (typeof r.path === 'string' ? r.path === path : r.path.test(path)),
    )
    if (!route) throw new Error(`Unmocked request: ${method} ${path}`)
    const result = await route.handler({ url, method, body, init })
    return result instanceof Response ? result : json(result)
  })
}

export const CAREGIVER: User = {
  id: 'u-care',
  email: 'synthetic.caregiver@example.org',
  full_name: 'Synthetic Caregiver',
  role: 'caregiver',
  is_verified: false,
  created_at: '2026-10-01T00:00:00Z',
}

export const CLINICIAN: User = {
  ...CAREGIVER,
  id: 'u-dr',
  email: 'synthetic.dr@example.org',
  full_name: 'Synthetic Clinician',
  role: 'clinician',
  is_verified: true,
}

export const PATIENT: Patient = {
  id: '11111111-1111-4111-8111-111111111111',
  display_name: 'Synthetic Patient',
  preferred_name: null,
  birth_year: 1950,
  preferred_language: 'as',
  region: 'Assam',
  timezone: 'Asia/Kolkata',
  is_synthetic: true,
  has_paired_device: true,
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
}

export const P = `/patients/${PATIENT.id}`

/** Standard routes for a signed-in user looking at PATIENT. */
export function baseRoutes(user: User, opts: { manager?: boolean } = {}): Route[] {
  return [
    { path: '/auth/me', handler: () => user },
    { path: '/patients', handler: () => [PATIENT] },
    { path: P, handler: () => PATIENT },
    {
      path: `${P}/caregivers`,
      handler: () =>
        user.role === 'caregiver'
          ? [
              {
                id: 'rel-1',
                caregiver_id: user.id,
                caregiver_name: user.full_name,
                relationship_label: 'daughter',
                can_manage: opts.manager ?? true,
                created_at: '2026-10-01T00:00:00Z',
              },
            ]
          : [],
    },
    { path: '/activities', handler: () => [] },
    // Review items: none by default. Tests that need them put their own routes first.
    { method: 'POST', path: `${P}/review-items/scan`, handler: () => [] },
    { path: `${P}/memory-relationships`, handler: () => [] },
    { path: `${P}/review-items`, handler: () => [] },
  ]
}

/** SYNTHETIC review item fixture (an automated prompt awaiting a caregiver's decision). */
export function reviewItem(overrides: Partial<ReviewItem> = {}): ReviewItem {
  return {
    id: 'ri-1',
    patient_id: PATIENT.id,
    rule_id: 'ACCURACY_LOWER_THAN_USUAL',
    kind: 'change',
    title: 'Scores lower than this person’s usual',
    explanation: 'Average score was 0.60 compared with a usual 0.90, lower on 100% of days with scored activities, at a similar difficulty level.',
    numbers: { baseline: 0.9, current: 0.6, share_of_days: 1 },
    observation_ids: [],
    period_start: '2026-10-01',
    period_end: '2026-10-09',
    method_version: 'analytics-1.0.0',
    config_version: '2026.10.1',
    status: 'awaiting_review',
    decided_by_id: null,
    decided_at: null,
    decision_reason: null,
    created_at: '2026-10-10T00:00:00Z',
    updated_at: '2026-10-10T00:00:00Z',
    wording: 'An automated prompt from the person’s own activity records. It is not a diagnosis and not a finding.',
    ...overrides,
  }
}

export function renderApp(path: string, opts: { signedIn?: boolean } = {}) {
  setToken(opts.signedIn === false ? null : 'test-token')
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const utils = render(
    <SettingsProvider>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </SettingsProvider>,
  )
  return { ...utils, router }
}

export function history(overrides: Record<string, unknown> = {}) {
  return {
    patient_id: PATIENT.id,
    timezone: 'Asia/Kolkata',
    from_date: '2026-10-01',
    to_date: '2026-10-09',
    sessions_completed: 3,
    sessions_ended_for_fatigue: 1,
    total_results: 5,
    days_with_activity: 2,
    days_elapsed: 9,
    missing_days: ['2026-10-01', '2026-10-02', '2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08'],
    days: [
      { day: '2026-10-03', activity_id: 'a1', activity_slug: 'picture-pairs', results: 3, abandoned: 0, mean_score: 0.8, mean_duration_ms: 120000, mean_difficulty: 2 },
      { day: '2026-10-09', activity_id: 'a1', activity_slug: 'picture-pairs', results: 2, abandoned: 1, mean_score: null, mean_duration_ms: 90000, mean_difficulty: 2 },
    ],
    disclaimer:
      'Activity statistics describe game performance only. They are affected by mood, sleep, eyesight, familiarity and many other factors, and are not a medical assessment.',
    ...overrides,
  }
}

/** SYNTHETIC analytics fixture (typed against the generated contract). */
export function analytics(overrides: Partial<AnalyticsSummary> = {}): AnalyticsSummary {
  const days = ['2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08', '2026-10-09']
  return {
    patient_id: PATIENT.id,
    timezone: 'Asia/Kolkata',
    from_date: '2026-10-01',
    to_date: '2026-10-09',
    generated_at: '2026-10-10T00:00:00Z',
    method_version: 'analytics-1.0',
    config_version: '2026.10.1',
    disclaimer: 'These figures describe activities only. They are not a medical assessment and do not diagnose any condition.',
    methodology: ['Days are calendar days in the person’s timezone.', 'Missing days are not counted as low results.'],
    totals: {
      results: 5,
      scored_results: 4,
      interrupted_results: 1,
      accuracy_mean: 0.8,
      accuracy_median: 0.8,
      completion_rate: 0.75,
      interruption_rate: 0.2,
      hints_per_result: 0.4,
      share_results_with_hints: 0.2,
      median_response_ms: 2400,
      mean_difficulty: 2,
      median_session_minutes: 9,
      total_session_minutes: 36,
      sessions_started: 4,
      sessions_ended: 4,
      sessions_completed: 3,
      sessions_stopped: 1,
      sessions_ended_for_fatigue: 1,
    },
    engagement: { enjoyed: 3, neutral: 1, not_enjoyed: 0, unanswered: 1 },
    activities: [
      {
        activity_id: 'a1', slug: 'picture-pairs', title: 'Matching pairs', results: 5, completed: 4, interrupted: 1,
        accuracy_mean: 0.8, median_response_ms: 2400, hints_per_result: 0.4, mean_difficulty: 2, enjoyed: 3, not_enjoyed: 0,
        last_played: '2026-10-09T05:00:00Z',
      },
    ],
    preferences: [{ slug: 'picture-pairs', title: 'Matching pairs', results: 5, enjoyed: 3, not_enjoyed: 0 }],
    daily: days.map((day) => ({
      day,
      has_data: day === '2026-10-03' || day === '2026-10-09',
      results: day === '2026-10-03' ? 3 : day === '2026-10-09' ? 2 : 0,
      interrupted: day === '2026-10-09' ? 1 : 0,
      accuracy_mean: day === '2026-10-03' ? 0.8 : null,
      median_response_ms: day === '2026-10-03' ? 2400 : null,
      hints_per_result: day === '2026-10-03' ? 0.3 : null,
    })),
    completeness: {
      days_elapsed: 9,
      days_with_activity: 2,
      completeness_ratio: 2 / 9,
      longest_gap_days: 5,
      missing_days: days.filter((d) => d !== '2026-10-03' && d !== '2026-10-09'),
    },
    baseline: {
      status: 'insufficient_data',
      from_date: '2026-09-03',
      to_date: '2026-09-30',
      results: 2,
      days: 1,
      required_results: 10,
      required_days: 4,
      comparisons: [],
    },
    review_flags: [],
    rules_not_evaluated: [{ rule_id: 'accuracy_below_usual', reason: 'Not enough earlier activity to compare with.' }],
    context_observations: [],
    ...overrides,
  }
}

/** SYNTHETIC observation fixture. */
export function observation(overrides: Partial<Observation> = {}): Observation {
  return {
    id: 'o1',
    patient_id: PATIENT.id,
    author_id: 'u-care',
    observed_at: '2026-10-05T10:00:00Z',
    category: 'fatigue',
    note: 'Tired after lunch',
    created_at: '2026-10-05T10:05:00Z',
    updated_at: null,
    source: 'dashboard',
    status: 'open',
    version: 1,
    reviewed_at: null,
    reviewed_by_id: null,
    review_note: null,
    resolved_at: null,
    resolved_by_id: null,
    resolution_note: null,
    ...overrides,
  }
}

