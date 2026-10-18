import { apiRequest, WAKE_TIMEOUT_MS } from './client'
import { getHealth } from './health'
import { setToken } from './session'
import type { LoginRequest, RegisterRequest, TokenResponse, User } from './types'

export async function login(body: LoginRequest): Promise<TokenResponse> {
  const token = await apiRequest<TokenResponse>('/auth/login', {
    method: 'POST',
    body,
    auth: false,
    timeoutMs: WAKE_TIMEOUT_MS,
  })
  setToken(token.access_token)
  return token
}

export function register(body: RegisterRequest): Promise<User> {
  return apiRequest<User>('/auth/register', {
    method: 'POST',
    body,
    auth: false,
    timeoutMs: WAKE_TIMEOUT_MS,
  })
}

export function getMe(signal?: AbortSignal): Promise<User> {
  return apiRequest<User>('/auth/me', { signal })
}

export async function logout(): Promise<void> {
  try {
    await apiRequest<void>('/auth/logout', { method: 'POST', responseType: 'none' })
  } finally {
    setToken(null)
  }
}

export function verifyEmail(token: string): Promise<User> {
  return apiRequest<User>('/auth/verify-email', {
    method: 'POST',
    body: { token },
    auth: false,
    timeoutMs: WAKE_TIMEOUT_MS,
  })
}

/** Always "accepted": the server never says whether an account exists. */
export function resendVerification(email: string): Promise<void> {
  return apiRequest<void>('/auth/resend-verification', {
    method: 'POST',
    body: { email },
    auth: false,
    responseType: 'none',
    timeoutMs: WAKE_TIMEOUT_MS,
  })
}

export function forgotPassword(email: string): Promise<void> {
  return apiRequest<void>('/auth/forgot-password', {
    method: 'POST',
    body: { email },
    auth: false,
    responseType: 'none',
    timeoutMs: WAKE_TIMEOUT_MS,
  })
}

export function resetPassword(token: string, password: string): Promise<void> {
  return apiRequest<void>('/auth/reset-password', {
    method: 'POST',
    body: { token, password },
    auth: false,
    responseType: 'none',
    timeoutMs: WAKE_TIMEOUT_MS,
  })
}

/**
 * Start waking the server as soon as a sign-in page opens, so it is ready by the time the
 * person has typed. Fire and forget: failures here are never shown.
 */
export function wakeServer(): void {
  getHealth({ timeoutMs: WAKE_TIMEOUT_MS }).catch(() => undefined)
}
