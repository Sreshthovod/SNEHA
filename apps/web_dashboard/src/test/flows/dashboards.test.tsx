import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { analytics, baseRoutes, CAREGIVER, mockApi, observation, P, renderApp } from '../harness'

describe('caregiver dashboard', () => {
  it('managers see pending memories, notes waiting for review and review prompts', async () => {
    mockApi([
      ...baseRoutes(CAREGIVER, { manager: true }),
      { path: `${P}/memories`, handler: () => [{ id: 'm1' }, { id: 'm2' }] },
      {
        path: `${P}/observations`,
        handler: ({ url }) =>
          url.searchParams.get('status') === 'open'
            ? [observation(), observation({ id: 'o2' })]
            : [observation({ note: 'Tired after lunch' })],
      },
      {
        path: `${P}/analytics`,
        handler: () =>
          analytics({
            review_flags: [
              { rule_id: 'repeated_tiredness', kind: 'context', title: 'Tiredness mentioned several times', explanation: 'x', numbers: {}, observation_ids: [] },
            ],
          }),
      },
    ])
    renderApp('/app/dashboard')
    expect(await screen.findByText('Notes waiting for review')).toBeInTheDocument()
    expect(screen.getByText('Memories waiting for approval').nextSibling).toHaveTextContent('2')
    expect(screen.getByText('Notes waiting for review').nextSibling).toHaveTextContent('2')
    expect(screen.getByText('Tiredness mentioned several times')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Review notes' })).toBeInTheDocument()
    expect(screen.getByText('Tired after lunch')).toBeInTheDocument()
  })

  it('non-managers are told who approves and reviews', async () => {
    mockApi([
      ...baseRoutes(CAREGIVER, { manager: false }),
      { path: `${P}/observations`, handler: () => [] },
      { path: `${P}/analytics`, handler: () => analytics() },
    ])
    renderApp('/app/dashboard')
    expect(await screen.findByText('A managing family member reviews notes.')).toBeInTheDocument()
    expect(screen.getByText('A managing family member approves memories.')).toBeInTheDocument()
    expect(screen.getByText('Nothing stands out this week.')).toBeInTheDocument()
  })
})
