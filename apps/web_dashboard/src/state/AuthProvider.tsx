import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import * as authApi from '../api/auth'
import { ApiError } from '../api/client'
import { getToken, onTokenChange } from '../api/session'
import type { LoginRequest } from '../api/types'
import { AuthContext, type AuthContextValue, type AuthState } from './auth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() =>
    getToken() ? { status: 'loading' } : { status: 'signed_out' },
  )
  const [attempt, setAttempt] = useState(0)

  // Restore the session from the stored token (initial state already reflects "no token").
  useEffect(() => {
    if (!getToken()) return
    const controller = new AbortController()
    authApi
      .getMe(controller.signal)
      .then((user) => setState({ status: 'signed_in', user }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 401) setState({ status: 'signed_out' })
        else
          setState({
            status: 'error',
            message: error instanceof Error ? error.message : 'Could not check your sign-in.',
          })
      })
    return () => controller.abort()
  }, [attempt])

  // Any 401 anywhere clears the token; reflect that immediately.
  useEffect(
    () =>
      onTokenChange((token) => {
        if (!token) setState({ status: 'signed_out' })
      }),
    [],
  )

  const signIn = useCallback(async (credentials: LoginRequest) => {
    const token = await authApi.login(credentials)
    setState({ status: 'signed_in', user: token.user })
    return token.user
  }, [])

  const signOut = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // Token is cleared locally regardless of whether the server call succeeded.
    }
    setState({ status: 'signed_out' })
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      state,
      user: state.status === 'signed_in' ? state.user : null,
      signIn,
      signOut,
      reload: () => {
        setState(getToken() ? { status: 'loading' } : { status: 'signed_out' })
        setAttempt((n) => n + 1)
      },
    }),
    [state, signIn, signOut],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

