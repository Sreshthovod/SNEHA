import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import type { UserRole } from '../../api/types'
import { homePathFor, useAuth } from '../../state/auth'
import { Button } from '../ui/Button'
import { Loading } from '../ui/States'

/** Requires a signed-in user; optionally restricts to roles. The server still enforces access. */
export function RequireAuth({ roles, children }: { roles?: UserRole[]; children: ReactNode }) {
  const { state, reload } = useAuth()
  const location = useLocation()

  if (state.status === 'loading') return <Loading label="Checking your sign-in…" />
  if (state.status === 'error')
    return (
      <div className="state state--error" role="alert">
        <p>{state.message}</p>
        <Button variant="secondary" onClick={reload}>
          Try again
        </Button>
      </div>
    )
  if (state.status === 'signed_out')
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (roles && !roles.includes(state.user.role)) return <Navigate to={homePathFor(state.user)} replace />
  return <>{children}</>
}
