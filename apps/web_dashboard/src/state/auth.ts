import { createContext, useContext } from 'react'
import type { LoginRequest, User } from '../api/types'

export type AuthState =
  | { status: 'loading' }
  | { status: 'signed_out' }
  | { status: 'signed_in'; user: User }
  | { status: 'error'; message: string }

export interface AuthContextValue {
  state: AuthState
  user: User | null
  signIn: (credentials: LoginRequest) => Promise<User>
  signOut: () => Promise<void>
  reload: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}

export function homePathFor(user: User): string {
  if (user.role === 'caregiver') return '/app/dashboard'
  if (user.role === 'clinician') return '/app/clinician'
  return '/app/unsupported'
}
