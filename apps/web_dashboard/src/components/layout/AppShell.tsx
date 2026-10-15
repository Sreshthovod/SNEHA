import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import type { StringKey } from '../../i18n/strings'
import { useAuth } from '../../state/auth'
import { useSettings } from '../../state/settings'
import { ConnectionBanner } from '../ConnectionBanner'
import { Button } from '../ui/Button'

interface NavItem {
  to: string
  key: StringKey
  end?: boolean
}

const NAV: Record<'caregiver' | 'clinician', NavItem[]> = {
  caregiver: [
    { to: '/app/dashboard', key: 'nav.dashboard' },
    { to: '/app/patients', key: 'nav.patients' },
    { to: '/app/settings', key: 'nav.settings' },
  ],
  clinician: [
    { to: '/app/clinician', key: 'nav.clinician' },
    { to: '/app/settings', key: 'nav.settings' },
  ],
}

export function AppShell() {
  const { user, signOut } = useAuth()
  const { t } = useSettings()
  const navigate = useNavigate()
  const items = user && (user.role === 'caregiver' || user.role === 'clinician') ? NAV[user.role] : []

  return (
    <>
      <a className="skip-link" href="#main-content">
        {t('nav.skip')}
      </a>
      <header className="app-header">
        <div className="app-header__inner">
          <NavLink to={items[0]?.to ?? '/'} className="app-brand">
            {t('app.name')}
          </NavLink>
          {items.length > 0 && (
            <nav className="app-nav" aria-label={t('nav.main')}>
              <ul>
                {items.map((item) => (
                  <li key={item.to}>
                    <NavLink to={item.to} end={item.end}>
                      {t(item.key)}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </nav>
          )}
          {user && (
            <div className="app-user">
              <span className="app-user__name">
                {user.full_name}
                <span className="app-user__role">
                  {user.role === 'clinician' ? 'Clinician' : user.role === 'caregiver' ? 'Caregiver' : user.role}
                </span>
              </span>
              <Button
                variant="secondary"
                onClick={async () => {
                  await signOut()
                  navigate('/login', { replace: true })
                }}
              >
                {t('nav.signOut')}
              </Button>
            </div>
          )}
        </div>
      </header>
      <ConnectionBanner />
      <main id="main-content" className="app-main" tabIndex={-1}>
        <Outlet />
      </main>
      <footer className="app-footer">{t('footer.disclaimer')}</footer>
    </>
  )
}
