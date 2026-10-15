import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { ReviewFlag } from '../../api/types'
import { analytics, apiError, baseRoutes, CAREGIVER, CLINICIAN, mockApi, observation, P, PATIENT, renderApp } from '../harness'
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
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
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

describe('clinician dashboard', () => {
  it('shows descriptive metrics, review flags, missing-data warning and the latest ready report', async () => {
    mockApi([
      ...baseRoutes(CLINICIAN),
      { path: `${P}/analytics`, handler: () => analytics({ review_flags: [FLAG] }) },
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
    expect(screen.getByText('Scores lower than usual')).toBeInTheDocument()
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
