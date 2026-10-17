import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { ReviewFlag } from '../../api/types'
import { analytics, apiError, baseRoutes, calls, CAREGIVER, CLINICIAN, mockApi, observation, P, PATIENT, renderApp, reviewItem } from '../harness'
import { DIAGNOSTIC_WORDS } from '../banned-words'


function mainText(container: HTMLElement): string {
  return container.querySelector('main')?.textContent ?? ''
}

const FLAG: ReviewFlag = {
  rule_id: 'accuracy_below_usual',
  kind: 'change',
  title: 'Scores lower than usual',
  explanation: 'Across 4 of 5 days with activity, the share of answers correct was lower than in the 28 days before.',
  numbers: { baseline_accuracy: 0.85, period_accuracy: 0.62, days_lower: 4, days_with_data: 5 },
  observation_ids: ['o1'],
  wording: 'May be worth a caregiver or clinician taking a look. Not a finding.',
}

describe('activity trends (analytics)', () => {
  it('shows metrics, charts with a table alternative, the disclaimer and no diagnostic labels', async () => {
    mockApi([...baseRoutes(CAREGIVER), { path: `${P}/analytics`, handler: () => analytics() }])
    const { container } = renderApp(`/app/patients/${PATIENT.id}/analytics`)
    expect(await screen.findByText(/not a medical assessment/)).toBeInTheDocument()
    expect(screen.getByText('Activities recorded')).toBeInTheDocument()
    expect(screen.getByText('3 of 4')).toBeInTheDocument() // sessions completed
    const perDay = screen.getByRole('figure', { name: 'Activities per day' })
    expect(within(perDay).getByRole('listitem', { name: /3 Oct 2026: 3/ })).toBeInTheDocument()
    expect(within(perDay).getByRole('listitem', { name: /1 Oct 2026: no data/ })).toBeInTheDocument()
    const correct = screen.getByRole('figure', { name: 'Share of answers correct, per day' })
    expect(within(correct).getByRole('listitem', { name: /3 Oct 2026: 80%/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: 'Table' }))
    expect(screen.getByRole('table', { name: 'Activity by day' })).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Activities in this period' })).toBeInTheDocument()
    expect(mainText(container)).not.toMatch(DIAGNOSTIC_WORDS)
  })

  it('explains when there is not enough earlier activity to compare', async () => {
    mockApi([...baseRoutes(CAREGIVER), { path: `${P}/analytics`, handler: () => analytics() }])
    renderApp(`/app/patients/${PATIENT.id}/analytics`)
    expect(await screen.findByText(/Not enough earlier activity to compare yet/)).toBeInTheDocument()
    expect(screen.getByText(/at least 10 activities over 4 days/)).toBeInTheDocument()
    expect(screen.queryByRole('table', { name: /compared with their usual pattern/ })).toBeNull()
  })

  it('shows a baseline comparison table when the server compared', async () => {
    mockApi([
      ...baseRoutes(CAREGIVER),
      {
        path: `${P}/analytics`,
        handler: () =>
          analytics({
            baseline: {
              status: 'compared', from_date: '2026-09-03', to_date: '2026-09-30', results: 20, days: 8,
              required_results: 10, required_days: 4,
              comparisons: [{ metric: 'accuracy_mean', unit: 'score 0–1', baseline: 0.85, current: 0.8, change: -0.05 }],
            },
          }),
      },
    ])
    renderApp(`/app/patients/${PATIENT.id}/analytics`)
    const table = await screen.findByRole('table', { name: 'This period compared with their usual pattern' })
    expect(within(table).getByText('Share of answers correct')).toBeInTheDocument()
    expect(within(table).getByText('85%')).toBeInTheDocument()
    expect(within(table).getByText('−5 points')).toBeInTheDocument()
  })

  it('shows missing-data warnings and review flags with numbers and related notes', async () => {
    mockApi([
      ...baseRoutes(CAREGIVER),
      { path: `${P}/analytics`, handler: () => analytics({ review_flags: [FLAG] }) },
      { path: `${P}/observations`, handler: () => [observation()] },
    ])
    const { container } = renderApp(`/app/patients/${PATIENT.id}/analytics`)
    expect(await screen.findByText('Some days have no activity data')).toBeInTheDocument()
    expect(screen.getByText(/No activities were recorded on 7 of 9 days/)).toBeInTheDocument()
    expect(screen.getByText(/longest gap: 5 days/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'May be worth reviewing' })).toBeInTheDocument()
    expect(screen.getByText('Scores lower than usual')).toBeInTheDocument()
    expect(screen.getByText('Baseline accuracy')).toBeInTheDocument()
    expect(screen.getByText('0.85')).toBeInTheDocument()
    expect(screen.getByText(/Not a finding/)).toBeInTheDocument()
    expect(screen.getByText('Checks that could not be made (1)')).toBeInTheDocument()
    expect(mainText(container)).not.toMatch(DIAGNOSTIC_WORDS)
    await userEvent.click(screen.getByRole('link', { name: '1 related caregiver note' }))
    expect(await screen.findByText('Tired after lunch')).toBeInTheDocument()
  })

  it('shows an error state with retry when analytics fails', async () => {
    let fail = true
    mockApi([
      ...baseRoutes(CAREGIVER),
      { path: `${P}/analytics`, handler: () => (fail ? apiError(503, 'database_unavailable', 'The service is temporarily unavailable.') : analytics()) },
    ])
    renderApp(`/app/patients/${PATIENT.id}/analytics`)
    expect(await screen.findByText('The service is temporarily unavailable.')).toBeInTheDocument()
    fail = false
    await userEvent.click(screen.getAllByRole('button', { name: 'Try again' })[0])
    expect(await screen.findByText(/not a medical assessment/)).toBeInTheDocument()
  })

  it('tab list supports arrow keys', async () => {
    mockApi([...baseRoutes(CAREGIVER), { path: `${P}/analytics`, handler: () => analytics() }])
    renderApp(`/app/patients/${PATIENT.id}/analytics`)
    const charts = await screen.findByRole('tab', { name: 'Charts' })
    charts.focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'Table' })).toHaveAttribute('aria-selected', 'true')
  })
})

describe('review items (human confirmation before anything reaches a clinician)', () => {
  it('a managing caregiver sees the evidence and must give a reason to confirm', async () => {
    let item = reviewItem()
    mockApi([
      { path: `${P}/analytics`, handler: () => analytics({ review_flags: [FLAG] }) },
      { method: 'POST', path: `${P}/review-items/scan`, handler: () => [item] },
      { path: `${P}/review-items`, handler: () => [item] },
      {
        method: 'POST',
        path: `${P}/review-items/ri-1/decision`,
        handler: ({ body }) => {
          const b = body as { decision: 'confirmed'; reason: string }
          item = { ...item, status: b.decision, decision_reason: b.reason, decided_at: '2026-10-10T05:00:00Z', decided_by_id: CAREGIVER.id }
          return item
        },
      },
      ...baseRoutes(CAREGIVER),
    ])
    const { container } = renderApp(`/app/patients/${PATIENT.id}/analytics`)
    expect(await screen.findByRole('heading', { name: 'Your review' })).toBeInTheDocument()
    expect(await screen.findByText(/Waiting for your review/)).toBeInTheDocument()
    expect(screen.getByText(/Nothing is shared with a clinician unless you confirm it/)).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST' && c.path === `${P}/review-items/scan`)).toBe(true)

    await userEvent.click(screen.getByRole('button', { name: /^Confirm: Scores lower/ }))
    const dialog = screen.getByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Confirm' }))
    expect(within(dialog).getByText(/Please write a short reason/)).toBeInTheDocument()
    expect(calls.some((c) => c.path.endsWith('/decision'))).toBe(false)

    await userEvent.type(within(dialog).getByLabelText(/What have you noticed at home/), 'Synthetic: forgetting names this week')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Confirm' }))
    const decision = calls.find((c) => c.path.endsWith('/decision'))
    expect(decision?.body).toEqual({ decision: 'confirmed', reason: 'Synthetic: forgetting names this week' })
    expect(await screen.findByText(/Already decided \(1\)/)).toBeInTheDocument()
    expect(mainText(container)).not.toMatch(DIAGNOSTIC_WORDS)
  })

  it('shows a prompt raised for overlapping periods once, with the others collapsed (presentation only)', async () => {
    const latest = reviewItem()
    const older = reviewItem({ id: 'ri-2', period_start: '2026-09-30', period_end: '2026-10-08' })
    mockApi([
      { path: `${P}/analytics`, handler: () => analytics({ review_flags: [{ ...FLAG, rule_id: latest.rule_id, title: latest.title }] }) },
      { method: 'POST', path: `${P}/review-items/scan`, handler: () => [latest] },
      { path: `${P}/review-items`, handler: () => [older, latest] },
      ...baseRoutes(CAREGIVER),
    ])
    renderApp(`/app/patients/${PATIENT.id}/analytics`)
    expect(await screen.findByText('1 prompt to look at')).toBeInTheDocument()
    expect(screen.getByText(/Also raised for 30 Sept 2026 – 8 Oct 2026 \(1 more\)/)).toBeInTheDocument()
    // Both stay decidable; the period flag is not repeated as a third card.
    expect(screen.getAllByRole('button', { name: /^Confirm: / })).toHaveLength(2)
    expect(screen.getByText(/listed once, with its numbers/)).toBeInTheDocument()
  })

  it('a helper caregiver sees why they cannot decide', async () => {
    mockApi([
      { path: `${P}/analytics`, handler: () => analytics() },
      { method: 'POST', path: `${P}/review-items/scan`, handler: () => [reviewItem()] },
      { path: `${P}/review-items`, handler: () => [reviewItem()] },
      ...baseRoutes(CAREGIVER, { manager: false }),
    ])
    renderApp(`/app/patients/${PATIENT.id}/analytics`)
    expect(await screen.findByText('A managing family member decides on review items.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Confirm: / })).toBeNull()
  })

  it('a clinician never sees unconfirmed prompts and is told why', async () => {
    mockApi([
      { path: `${P}/analytics`, handler: () => analytics({ review_flags: [], review_flags_withheld: true }) },
      {
        path: `${P}/review-items`,
        handler: () => [reviewItem({ status: 'confirmed', decision_reason: 'Synthetic: worth discussing', decided_at: '2026-10-10T05:00:00Z' })],
      },
      ...baseRoutes(CLINICIAN),
    ])
    renderApp(`/app/patients/${PATIENT.id}/analytics`)
    expect(await screen.findByText(/shared with clinicians only after a family caregiver confirms them/)).toBeInTheDocument()
    expect(await screen.findByText(/Synthetic: worth discussing/)).toBeInTheDocument()
    expect(screen.queryByText('Nothing stands out in this period.')).toBeNull()
    expect(calls.some((c) => c.path.endsWith('/review-items/scan'))).toBe(false)
    expect(screen.queryByRole('button', { name: /^Confirm: / })).toBeNull()
  })
})

describe('clinician dashboard', () => {
  it('shows descriptive metrics, confirmed items only, missing-data warning and the latest ready report', async () => {
    mockApi([
      { path: `${P}/review-items`, handler: () => [reviewItem({ status: 'confirmed', title: 'Confirmed synthetic item', decided_at: '2026-10-10T05:00:00Z', decision_reason: 'Synthetic' })] },
      ...baseRoutes(CLINICIAN),
      { path: `${P}/analytics`, handler: () => analytics({ review_flags: [], review_flags_withheld: true }) },
      {
        path: `${P}/reports`,
        handler: () => [
          {
            id: 'r1', patient_id: PATIENT.id, period_start: '2026-09-30T18:30:00Z', period_end: '2026-10-09T18:30:00Z',
            status: 'ready', requested_by_id: 'x', file_id: 'f1', generated_at: '2026-10-10T00:00:00Z',
            error_message: null, created_at: '2026-10-10T00:00:00Z', automated: true, method_version: 'analytics-1.0',
          },
        ],
      },
    ])
    const { container } = renderApp('/app/clinician')
    expect(await screen.findByRole('heading', { name: 'Synthetic Patient' })).toBeInTheDocument()
    expect(await screen.findByText('Some days have no activity data')).toBeInTheDocument()
    expect(screen.getByText('Sessions ended early for tiredness')).toBeInTheDocument()
    expect(screen.getByText('Confirmed synthetic item')).toBeInTheDocument()
    expect(screen.queryByText('Scores lower than usual')).toBeNull()
    expect(screen.getByText(/Latest report: 1 Oct 2026 – 9 Oct 2026/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download PDF' })).toBeEnabled()
    expect(mainText(container)).not.toMatch(DIAGNOSTIC_WORDS)
  })

  it('shows an explanatory empty state when nothing is shared', async () => {
    mockApi([{ path: '/auth/me', handler: () => CLINICIAN }, { path: '/patients', handler: () => [] }])
    renderApp('/app/clinician')
    expect(await screen.findByText('No shared patients')).toBeInTheDocument()
  })
})
