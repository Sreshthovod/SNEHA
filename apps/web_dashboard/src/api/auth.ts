import { apiRequest } from './client'
import { setToken } from './session'
import type { LoginRequest, RegisterRequest, TokenResponse, User } from './types'

export async function login(body: LoginRequest): Promise<TokenResponse> {
  const token = await apiRequest<TokenResponse>('/auth/login', {
    method: 'POST',
    body,
    auth: false,
  })
  setToken(token.access_token)
  return token
}

export function register(body: RegisterRequest): Promise<User> {
  return apiRequest<User>('/auth/register', { method: 'POST', body, auth: false })
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
