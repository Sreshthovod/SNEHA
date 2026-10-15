import { act, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { loadSettings, SETTINGS_KEY } from '../../state/settings'
import { baseRoutes, CAREGIVER, mockApi, renderApp } from '../harness'

describe('offline and server indicators', () => {
  it('shows a banner when the browser goes offline and hides it when back', async () => {
    mockApi([...baseRoutes(CAREGIVER), { path: /.*/, handler: () => [] }])
    renderApp('/app/patients')
    await screen.findByRole('navigation', { name: 'Main' })
    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
      window.dispatchEvent(new Event('offline'))
    })
    expect(screen.getByText(/You are offline/)).toBeInTheDocument()
    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
      window.dispatchEvent(new Event('online'))
    })
    expect(screen.queryByText(/You are offline/)).toBeNull()
  })

  it('shows a server-unreachable banner and an error state when requests fail', async () => {
    mockApi([
      { path: '/auth/me', handler: () => CAREGIVER },
      { path: '/patients', handler: () => { throw new TypeError('Failed to fetch') } },
    ])
    renderApp('/app/patients')
    expect(await screen.findByText(/server cannot be reached/)).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(/Cannot reach the SNEHA server/)
  })
})

describe('language and accessibility settings', () => {
  it('persists text size and contrast, and applies them to the page', async () => {
    mockApi([...baseRoutes(CAREGIVER), { path: /.*/, handler: () => ({ status: 'ok', service: 'SNEHA API', version: '0', environment: 'test', server_time: '', checks: [] }) }])
    renderApp('/app/settings')
    await userEvent.selectOptions(await screen.findByLabelText('Text size'), 'larger')
    await userEvent.click(screen.getByLabelText('Extra high contrast'))
    expect(document.documentElement.dataset.textSize).toBe('larger')
    expect(document.documentElement.dataset.contrast).toBe('high')
    expect(JSON.parse(localStorage.getItem(SETTINGS_KEY)!)).toMatchObject({ textSize: 'larger', highContrast: true })
    expect(loadSettings().textSize).toBe('larger')
  })

  it('switching to Hindi translates navigation and flags the draft', async () => {
    mockApi([...baseRoutes(CAREGIVER), { path: /.*/, handler: () => ({ status: 'ok', service: 'SNEHA API', version: '0', environment: 'test', server_time: '', checks: [] }) }])
    renderApp('/app/settings')
    await userEvent.selectOptions(await screen.findByLabelText('Language'), 'hi')
    expect(screen.getByRole('navigation', { name: 'Main' })).toHaveTextContent('सेटिंग्स')
    expect(screen.getByText(/draft that has not yet been checked/)).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('hi')
  })

  it('survives blocked storage', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(loadSettings().language).toBe('en')
    spy.mockRestore()
  })
})
