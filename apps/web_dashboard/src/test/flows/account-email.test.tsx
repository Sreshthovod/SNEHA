import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { apiError, calls, CAREGIVER, json, mockApi, renderApp } from '../harness'

const TOKEN = 'synthetic-link-token-0123456789abcdef'

describe('email verification', () => {
  it('confirms the email from the link once and offers sign-in', async () => {
    mockApi([
      { method: 'POST', path: '/auth/verify-email', handler: () => ({ ...CAREGIVER, email_verified: true }) },
    ])
    renderApp(`/verify-email?token=${TOKEN}`, { signedIn: false })
    expect(await screen.findByText('Thank you. Your email is confirmed.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go to sign in' })).toBeInTheDocument()
    const verifyCalls = calls.filter((c) => c.path === '/auth/verify-email')
    expect(verifyCalls).toHaveLength(1)
    expect(verifyCalls[0].body).toEqual({ token: TOKEN })
  })

  it('explains an expired link and sends a new one', async () => {
    mockApi([
      {
        method: 'POST',
        path: '/auth/verify-email',
        handler: () => apiError(400, 'invalid_link', 'This link has expired or was already used.'),
      },
      { method: 'POST', path: '/auth/resend-verification', handler: () => json(null, 202) },
    ])
    renderApp(`/verify-email?token=${TOKEN}`, { signedIn: false })
    expect(await screen.findByText('This link has expired or was already used.')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/Email for the new link/), 'synthetic@example.org')
    await userEvent.click(screen.getByRole('button', { name: 'Send a new confirmation link' }))
    expect(await screen.findByText(/a new link is on its way/)).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/auth/resend-verification')?.body).toEqual({
      email: 'synthetic@example.org',
    })
  })

  it('offers a new link when sign-in is waiting for confirmation', async () => {
    mockApi([
      {
        method: 'POST',
        path: '/auth/login',
        handler: () => apiError(403, 'email_not_verified', 'Please confirm your email first.'),
      },
      { method: 'POST', path: '/auth/resend-verification', handler: () => json(null, 202) },
    ])
    renderApp('/login', { signedIn: false })
    await userEvent.type(screen.getByLabelText(/^Email \(required\)$/), 'synthetic@example.org')
    await userEvent.type(screen.getByLabelText(/Password/), 'a synthetic password')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Please confirm your email first.')).toBeInTheDocument()
    expect(screen.getByLabelText(/Email for the new link/)).toHaveValue('synthetic@example.org')
    await userEvent.click(screen.getByRole('button', { name: 'Send a new confirmation link' }))
    expect(await screen.findByText(/a new link is on its way/)).toBeInTheDocument()
  })

  it('tells a new caregiver to check their email after registering', async () => {
    mockApi([{ method: 'POST', path: '/auth/register', handler: () => json(CAREGIVER, 201) }])
    renderApp('/register', { signedIn: false })
    await userEvent.type(screen.getByLabelText(/^Your name/), 'Synthetic Caregiver')
    await userEvent.type(screen.getByLabelText(/^Email \(required\)$/), 'synthetic@example.org')
    await userEvent.type(screen.getByLabelText(/^Password/), 'a long synthetic passphrase')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText(/We sent a link to/)).toBeInTheDocument()
    expect(screen.getByText('synthetic@example.org')).toBeInTheDocument()
  })
})

describe('forgot password', () => {
  it('is linked from sign-in and never says whether the account exists', async () => {
    mockApi([{ method: 'POST', path: '/auth/forgot-password', handler: () => json(null, 202) }])
    renderApp('/login', { signedIn: false })
    await userEvent.click(screen.getByRole('link', { name: 'Forgot your password?' }))
    await userEvent.type(await screen.findByLabelText(/^Email \(required\)$/), 'synthetic@example.org')
    await userEvent.click(screen.getByRole('button', { name: 'Send reset link' }))
    expect(await screen.findByText(/If an account uses synthetic@example.org/)).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/auth/forgot-password')?.body).toEqual({
      email: 'synthetic@example.org',
    })
  })

  it('checks the new password, saves it and says every device was signed out', async () => {
    mockApi([{ method: 'POST', path: '/auth/reset-password', handler: () => json(null, 204) }])
    renderApp(`/reset-password?token=${TOKEN}`, { signedIn: false })
    await userEvent.type(screen.getByLabelText(/^New password \(required\)$/), 'short')
    await userEvent.click(screen.getByRole('button', { name: 'Save new password' }))
    expect(screen.getByText(/Use at least 12 characters/)).toBeInTheDocument()
    expect(calls).toHaveLength(0)

    await userEvent.clear(screen.getByLabelText(/^New password \(required\)$/))
    await userEvent.type(screen.getByLabelText(/^New password \(required\)$/), 'a new synthetic passphrase')
    await userEvent.type(screen.getByLabelText(/^New password again/), 'a different passphrase')
    await userEvent.click(screen.getByRole('button', { name: 'Save new password' }))
    expect(screen.getByText('The two passwords are different.')).toBeInTheDocument()

    await userEvent.clear(screen.getByLabelText(/^New password again/))
    await userEvent.type(screen.getByLabelText(/^New password again/), 'a new synthetic passphrase')
    await userEvent.click(screen.getByRole('button', { name: 'Save new password' }))
    expect(await screen.findByText(/signed out on every device/)).toBeInTheDocument()
    expect(calls[0].body).toEqual({ token: TOKEN, password: 'a new synthetic passphrase' })
  })

  it('explains a used link and links to a new one', async () => {
    mockApi([
      {
        method: 'POST',
        path: '/auth/reset-password',
        handler: () => apiError(400, 'invalid_link', 'This link has expired or was already used.'),
      },
    ])
    renderApp(`/reset-password?token=${TOKEN}`, { signedIn: false })
    await userEvent.type(screen.getByLabelText(/^New password \(required\)$/), 'a new synthetic passphrase')
    await userEvent.type(screen.getByLabelText(/^New password again/), 'a new synthetic passphrase')
    await userEvent.click(screen.getByRole('button', { name: 'Save new password' }))
    expect(await screen.findByText(/This link has expired/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ask for a new link' })).toHaveAttribute('href', '/forgot-password')
  })
})
