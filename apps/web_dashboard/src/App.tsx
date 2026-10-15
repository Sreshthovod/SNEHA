import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { routes } from './routes'
import { AuthProvider } from './state/AuthProvider'
import { SettingsProvider } from './state/SettingsProvider'

const router = createBrowserRouter(routes)

export default function App() {
  return (
    <SettingsProvider>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </SettingsProvider>
  )
}
