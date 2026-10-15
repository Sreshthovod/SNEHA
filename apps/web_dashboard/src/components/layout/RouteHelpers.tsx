import { Navigate, Outlet } from 'react-router-dom'
import { homePathFor, useAuth } from '../../state/auth'

export function OutletPassthrough() {
  return <Outlet />
}

export function RoleHome() {
  const { user } = useAuth()
  return user ? <Navigate to={homePathFor(user)} replace /> : null
}
