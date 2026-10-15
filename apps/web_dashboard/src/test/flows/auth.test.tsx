import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { apiError, baseRoutes, calls, CAREGIVER, CLINICIAN, mockApi, renderApp, analytics } from '../harness'

describe('login', () => {
  it('validates fields before calling the API', async () => {
    mockApi([])
    renderApp('/login', { signedIn: false })
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByText(/Enter your email address/)).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(screen.getByLabelText(/Email/)).toHaveAttribute('aria-invalid', 'true')
    expect(calls).toHaveLength(0)
  })

  it('shows the server message when sign-in fails', async () => {
    mockApi([
      { method: 'POST', path: '/auth/login', handler: () => apiError(401, 'unauthorized', 'Email or password is incorrect.') },
    ])
    renderApp('/login', { signedIn: false })
    await userEvent.type(screen.getByLabelText(/Email/), 'synthetic@example.org')
    await userEvent.type(screen.getByLabelText(/Password/), 'wrong password!')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Email or password is incorrect.')).toBeInTheDocument()
    expect(sessionStorage.getItem('sneha.session.token')).toBeNull()
  })

  it('reports an unreachable server in plain language', async () => {
    mockApi([{ method: 'POST', path: '/auth/login', handler: () => { throw new TypeError('Failed to fetch') } }])
    renderApp('/login', { signedIn: false })
    await userEvent.type(screen.getByLabelText(/Email/), 'synthetic@example.org')
    await userEvent.type(screen.getByLabelText(/Password/), 'a password here')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText(/Cannot reach the SNEHA server/)).toBeInTheDocument()
  })

  it('signs in, stores the token only in sessionStorage and opens the caregiver dashboard', async () => {
    mockApi([
      ...baseRoutes(CAREGIVER),
      {
        method: 'POST',
        path: '/auth/login',
        handler: () => ({ access_token: 'tok-123', token_type: 'bearer', expires_at: '2026-10-16T00:00:00Z', user: CAREGIVER }),
      },
      { path: /\/memories$/, handler: () => [] },
      { path: /\/observations$/, handler: () => [] },
      { path: /\/analytics$/, handler: () => analytics() },
    ])
    const { router } = renderApp('/login', { signedIn: false })
    await userEvent.type(screen.getByLabelText(/Email/), CAREGIVER.email!)
    await userEvent.type(screen.getByLabelText(/Password/), 'correct horse battery')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/app/dashboard'))
    expect(sessionStorage.getItem('sneha.session.token')).toBe('tok-123')
    expect(localStorage.getItem('sneha.session.token')).toBeNull()
  })
})

describe('route guards and roles', () => {
  it('sends signed-out visitors to the login page', async () => {
    mockApi([])
    const { router } = renderApp('/app/dashboard', { signedIn: false })
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
  })

  it('an expired session (401) signs the user out', async () => {
    mockApi([{ path: '/auth/me', handler: () => apiError(401, 'unauthorized', 'Expired') }])
    const { router } = renderApp('/app/dashboard')
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(sessionStorage.getItem('sneha.session.token')).toBeNull()
  })

  it('caregivers see caregiver navigation', async () => {
    mockApi([...baseRoutes(CAREGIVER), { path: /.*/, handler: () => [] }])
    renderApp('/app/patients')
    const nav = await screen.findByRole('navigation', { name: 'Main' })
    expect(nav).toHaveTextContent('Dashboard')
    expect(nav).toHaveTextContent('People I care for')
    expect(nav).not.toHaveTextContent('My patients')
  })

  it('clinicians see clinician navigation and never the Memory Bank or family tabs', async () => {
    mockApi([...baseRoutes(CLINICIAN)])
    renderApp(`/app/patients/11111111-1111-4111-8111-111111111111`)
    const sections = await screen.findByRole('navigation', { name: 'Patient sections' })
    expect(sections).toHaveTextContent('Reports')
    expect(sections).not.toHaveTextContent('Memory Bank')
    expect(sections).not.toHaveTextContent('Family & devices')
    expect(screen.getByRole('navigation', { name: 'Main' })).toHaveTextContent('My patients')
  })

  it('redirects a clinician away from caregiver-only routes', async () => {
    mockApi([...baseRoutes(CLINICIAN), { path: /.*/, handler: () => [] }])
    const { router } = renderApp(`/app/patients/11111111-1111-4111-8111-111111111111/memories`)
    await waitFor(() => expect(router.state.location.pathname).toBe('/app/clinician'))
    expect(calls.some((c) => c.path.endsWith('/memories'))).toBe(false)
  })

  it('explains that patient accounts use the phone app', async () => {
    mockApi([{ path: '/auth/me', handler: () => ({ ...CAREGIVER, role: 'patient', email: null }) }])
    renderApp('/app')
    expect(await screen.findByText(/use the SNEHA app on the phone/)).toBeInTheDocument()
  })
})
