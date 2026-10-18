import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Memory } from '../../api/types'
import { apiError, baseRoutes, calls, CAREGIVER, mockApi, P, PATIENT, renderApp } from '../harness'

const pending: Memory = {
  id: 'm-1',
  patient_id: PATIENT.id,
  kind: 'place',
  title: 'Synthetic tea garden',
  description: null,
  approx_year: 1975,
  tags: [],
  media_file_id: null,
  status: 'pending_approval',
  source: 'dashboard',
  version: 3,
  created_by_id: 'someone',
  reviewed_by_id: null,
  reviewed_at: null,
  review_note: null,
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
}

describe('Memory Bank approval', () => {
  it('approves a pending memory with its current version', async () => {
    let current: Memory[] = [pending]
    mockApi([
      ...baseRoutes(CAREGIVER, { manager: true }),
      { path: `${P}/memories`, handler: () => current },
      {
        method: 'POST',
        path: `${P}/memories/m-1/approve`,
        handler: () => {
          current = [{ ...pending, status: 'approved', version: 4 }]
          return current[0]
        },
      },
    ])
    renderApp(`/app/patients/${PATIENT.id}/memories?status=pending_approval`)
    const card = await screen.findByRole('article', { name: 'Synthetic tea garden' })
    await userEvent.click(within(card).getByRole('button', { name: 'Approve' }))
    expect(await screen.findByText('“Synthetic tea garden” approved.')).toBeInTheDocument()
    const approve = calls.find((c) => c.path.endsWith('/approve'))
    expect(approve?.body).toEqual({ expected_version: 3 })
    expect(approve?.headers.get('Authorization')).toBe('Bearer test-token')
  })

  it('explains a version conflict instead of overwriting someone else’s change', async () => {
    mockApi([
      ...baseRoutes(CAREGIVER, { manager: true }),
      { path: `${P}/memories`, handler: () => [pending] },
      {
        method: 'POST',
        path: `${P}/memories/m-1/approve`,
        handler: () => apiError(409, 'version_conflict', 'This memory was changed by someone else.'),
      },
    ])
    renderApp(`/app/patients/${PATIENT.id}/memories`)
    const card = await screen.findByRole('article', { name: 'Synthetic tea garden' })
    await userEvent.click(within(card).getByRole('button', { name: 'Approve' }))
    expect((await screen.findAllByText(/Someone else changed this memory/)).length).toBeGreaterThan(0)
  })

  it('non-managing caregivers can propose but not approve', async () => {
    mockApi([
      ...baseRoutes(CAREGIVER, { manager: false }),
      { path: `${P}/memories`, handler: () => [{ ...pending, status: 'approved' }] },
    ])
    renderApp(`/app/patients/${PATIENT.id}/memories`)
    const card = await screen.findByRole('article', { name: 'Synthetic tea garden' })
    expect(within(card).queryByRole('button', { name: 'Approve' })).toBeNull()
    expect(within(card).queryByRole('button', { name: 'Delete' })).toBeNull()
    expect(screen.getByText(/wait for a managing family member/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add a memory' })).toBeEnabled()
  })

  it('creating a memory validates the title and posts the form', async () => {
    mockApi([
      ...baseRoutes(CAREGIVER, { manager: true }),
      { path: `${P}/memories`, handler: () => [] },
      { method: 'POST', path: `${P}/memories`, handler: () => ({ ...pending, status: 'approved' }) },
    ])
    renderApp(`/app/patients/${PATIENT.id}/memories`)
    await userEvent.click(await screen.findByRole('button', { name: 'Add a memory' }))
    const dialog = screen.getByRole('dialog', { name: 'Add a memory' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    expect(within(dialog).getByText('Give the memory a short title.')).toBeInTheDocument()
    await userEvent.type(within(dialog).getByLabelText(/Title/), 'Synthetic river walk')
    await userEvent.type(within(dialog).getByLabelText(/Tags/), 'river, family')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Memory added.')).toBeInTheDocument()
    const post = calls.find((c) => c.method === 'POST' && c.path === `${P}/memories`)
    expect(post?.body).toMatchObject({ title: 'Synthetic river walk', tags: ['river', 'family'], kind: 'person' })
  })

  it('dialogs close with Escape and keep focus inside', async () => {
    mockApi([...baseRoutes(CAREGIVER), { path: `${P}/memories`, handler: () => [] }])
    renderApp(`/app/patients/${PATIENT.id}/memories`)
    await userEvent.click(await screen.findByRole('button', { name: 'Add a memory' }))
    const dialog = screen.getByRole('dialog')
    expect(dialog.contains(document.activeElement)).toBe(true)
    for (let i = 0; i < 15; i++) await userEvent.tab()
    expect(dialog.contains(document.activeElement)).toBe(true)
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})

describe('Memory Bank: type filter and photo preview', () => {
  afterEach(() => vi.unstubAllGlobals())

  const memories: Memory[] = [
    { ...pending, id: 'm-place', kind: 'place', title: 'Synthetic tea garden', status: 'approved' },
    { ...pending, id: 'm-person', kind: 'person', title: 'Synthetic cousin', status: 'approved' },
    { ...pending, id: 'm-story', kind: 'story', title: 'Synthetic Bihu story', status: 'approved' },
  ]

  it('filters by type with counts, keeps it in the address and can show all again', async () => {
    mockApi([
      ...baseRoutes(CAREGIVER, { manager: true }),
      { path: `${P}/memories`, handler: () => memories },
    ])
    const { router } = renderApp(`/app/patients/${PATIENT.id}/memories`)
    const select = await screen.findByLabelText('Show')
    const requestsBefore = calls.length
    expect(within(select).getByRole('option', { name: 'All types (3)' })).toBeInTheDocument()
    expect(within(select).getByRole('option', { name: 'Object (0)' })).toBeInTheDocument()
    await userEvent.selectOptions(select, 'person')
    expect(screen.getByRole('heading', { name: 'Synthetic cousin' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Synthetic tea garden' })).toBeNull()
    expect(router.state.location.search).toBe('?kind=person')

    await userEvent.selectOptions(screen.getByLabelText('Show'), 'object')
    expect(screen.getByText('No object memories here')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show all types' }))
    expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(3)
    // No new requests: filtering by type happens on the list already loaded.
    expect(calls.length).toBe(requestsBefore)
  })

  it('shows the chosen photo before saving and releases it afterwards', async () => {
    const created: string[] = []
    const revoked: string[] = []
    vi.stubGlobal('URL', Object.assign(URL, {
      createObjectURL: () => {
        created.push('blob:synthetic-preview')
        return 'blob:synthetic-preview'
      },
      revokeObjectURL: (u: string) => revoked.push(u),
    }))
    mockApi([
      ...baseRoutes(CAREGIVER, { manager: true }),
      { path: `${P}/memories`, handler: () => [] },
    ])
    renderApp(`/app/patients/${PATIENT.id}/memories`)
    await userEvent.click(await screen.findByRole('button', { name: 'Add a memory' }))
    const dialog = screen.getByRole('dialog', { name: 'Add a memory' })
    expect(within(dialog).queryByAltText('The photo you chose')).toBeNull()
    const file = new File([new Uint8Array([137, 80, 78, 71])], 'synthetic.png', { type: 'image/png' })
    await userEvent.upload(within(dialog).getByLabelText(/^Photo/), file)
    expect(within(dialog).getByAltText('The photo you chose')).toHaveAttribute('src', 'blob:synthetic-preview')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(revoked).toEqual(['blob:synthetic-preview'])
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })
})
