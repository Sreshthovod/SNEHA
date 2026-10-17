import { useEffect, useId, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { APP_TITLE, focusWhenReady } from '../../hooks/useDocumentTitle'
import { initials } from '../../lib/people'
import type { StringKey } from '../../i18n/strings'
import { useAuth } from '../../state/auth'
import { useSettings } from '../../state/settings'
import { ConnectionBanner } from '../ConnectionBanner'
import { Button } from '../ui/Button'

interface NavItem {
  to: string
  key: StringKey
  icon: IconName
  end?: boolean
}

const NAV: Record<'caregiver' | 'clinician', NavItem[]> = {
  caregiver: [
    { to: '/app/dashboard', key: 'nav.dashboard', icon: 'home' },
    { to: '/app/patients', key: 'nav.patients', icon: 'people' },
    { to: '/app/settings', key: 'nav.settings', icon: 'settings' },
  ],
  clinician: [
    { to: '/app/clinician', key: 'nav.clinician', icon: 'people' },
    { to: '/app/settings', key: 'nav.settings', icon: 'settings' },
  ],
}

/** Page titles for routes outside a patient record (patient pages set their own). */
const ROUTE_TITLES: Array<{ re: RegExp; key?: StringKey; text?: string }> = [
  { re: /^\/(login)?$/, key: 'login.title' },
  { re: /^\/register$/, key: 'register.title' },
  { re: /^\/app\/dashboard$/, key: 'nav.dashboard' },
  { re: /^\/app\/patients$/, key: 'nav.patients' },
  { re: /^\/app\/clinician$/, key: 'nav.clinician' },
  { re: /^\/app\/settings$/, key: 'settings.title' },
  { re: /^\/app\/?$/, text: 'Loading' },
  { re: /^\/app\/unsupported$/, text: 'Dashboard access' },
]

const PATIENT_PATH = /^\/app\/patients\/([^/]+)/

type IconName = 'home' | 'people' | 'settings'

/** Simple line icons (decorative; every nav item has a text label). */
function NavIcon({ name }: { name: IconName }) {
  const common = { width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true, focusable: false as const }
  if (name === 'home')
    return (
      <svg {...common}>
        <path d="M4 11.5 12 5l8 6.5" />
        <path d="M6.5 10v9h11v-9" />
      </svg>
    )
  if (name === 'people')
    return (
      <svg {...common}>
        <circle cx="9" cy="8.5" r="3.2" />
        <path d="M3.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5" />
        <path d="M15.5 5.6a3 3 0 0 1 0 5.8M17.5 14.3c1.6.6 2.7 2.2 3 4.7" />
      </svg>
    )
  return (
    <svg {...common}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M5.6 18.4l1.6-1.6M16.8 7.2l1.6-1.6" />
    </svg>
  )
}

function Brand({ to }: { to: string }) {
  const { t } = useSettings()
  return (
    <Link to={to} className="app-brand">
      <span className="app-brand__mark" aria-hidden="true">
        S
      </span>
      <span className="app-brand__name">{t('app.name')}</span>
    </Link>
  )
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function roleLabel(role: string): string {
  return role === 'clinician' ? 'Clinician' : role === 'caregiver' ? 'Caregiver' : role
}

export function AppShell() {
  const { user, signOut } = useAuth()
  const { t } = useSettings()
  const navigate = useNavigate()
  const location = useLocation()
  const items = user && (user.role === 'caregiver' || user.role === 'clinician') ? NAV[user.role] : []
  const hasSidebar = items.length > 0
  const home = items[0]?.to ?? '/'

  const [drawerOpen, setDrawerOpen] = useState(false)
  const drawerId = useId()
  const sidebarRef = useRef<HTMLElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const mainRef = useRef<HTMLElement>(null)

  // Document title for routes outside a patient record (PatientLayout sets its own).
  const isPatientRoute = PATIENT_PATH.test(location.pathname)
  const routeTitle = ROUTE_TITLES.find((r) => r.re.test(location.pathname))
  const pageTitle = routeTitle ? (routeTitle.key ? t(routeTitle.key) : routeTitle.text) : 'Page not found'
  useEffect(() => {
    if (!isPatientRoute) document.title = `${pageTitle} – ${APP_TITLE}`
  }, [isPatientRoute, pageTitle])

  // After navigation: close the drawer, scroll to top and move focus to the page heading.
  const previousPath = useRef(location.pathname)
  useEffect(() => {
    const prev = previousPath.current
    previousPath.current = location.pathname
    if (prev === location.pathname) return
    setDrawerOpen(false)
    const prevPatient = PATIENT_PATH.exec(prev)?.[1]
    const nextPatient = PATIENT_PATH.exec(location.pathname)?.[1]
    // Moving between sections of the same person's record is handled by PatientLayout.
    if (prevPatient && prevPatient === nextPatient) return
    document.documentElement.scrollTop = 0
    document.body.scrollTop = 0
    return focusWhenReady(() => mainRef.current, ['h1'], () => mainRef.current)
  }, [location.pathname])

  // Drawer: Escape closes, Tab is trapped, focus returns to the Menu button.
  useEffect(() => {
    if (!drawerOpen) return
    const panel = sidebarRef.current
    const first = panel?.querySelector<HTMLElement>(FOCUSABLE)
    first?.focus()
    const menuButton = menuButtonRef.current
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        setDrawerOpen(false)
        return
      }
      if (event.key !== 'Tab' || !panel) return
      const list = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE))
      if (list.length === 0) return
      const firstItem = list[0]
      const lastItem = list[list.length - 1]
      if (event.shiftKey && document.activeElement === firstItem) {
        event.preventDefault()
        lastItem.focus()
      } else if (!event.shiftKey && document.activeElement === lastItem) {
        event.preventDefault()
        firstItem.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      menuButton?.focus()
    }
  }, [drawerOpen])

  // The drawer only exists on small screens; close it if the window grows.
  useEffect(() => {
    if (!drawerOpen || typeof window.matchMedia !== 'function') return
    const mq = window.matchMedia('(min-width: 64rem)')
    const onChange = () => mq.matches && setDrawerOpen(false)
    mq.addEventListener?.('change', onChange)
    return () => mq.removeEventListener?.('change', onChange)
  }, [drawerOpen])

  async function onSignOut() {
    setDrawerOpen(false)
    await signOut()
    navigate('/login', { replace: true })
  }

  const userBlock = user && (
    <div className="app-user">
      <span className="app-user__avatar" aria-hidden="true">
        {initials(user.full_name)}
      </span>
      <span className="app-user__name">
        {user.full_name}
        <span className="app-user__role">{roleLabel(user.role)}</span>
      </span>
    </div>
  )

  return (
    <div className={hasSidebar ? 'app app--with-sidebar' : 'app'}>
      <a className="skip-link" href="#main-content">
        {t('nav.skip')}
      </a>
      {hasSidebar && (
        <>
          <aside
            ref={sidebarRef}
            id={drawerId}
            className={drawerOpen ? 'app-sidebar is-open' : 'app-sidebar'}
            aria-label={drawerOpen ? 'Menu' : undefined}
            role={drawerOpen ? 'dialog' : undefined}
            aria-modal={drawerOpen ? true : undefined}
          >
            <div className="app-sidebar__top">
              <Brand to={home} />
              <Button variant="ghost" className="app-sidebar__close" onClick={() => setDrawerOpen(false)}>
                Close menu
              </Button>
            </div>
            <nav className="app-nav" aria-label={t('nav.main')}>
              <ul>
                {items.map((item) => (
                  <li key={item.to}>
                    <NavLink to={item.to} end={item.end}>
                      <NavIcon name={item.icon} />
                      <span>{t(item.key)}</span>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </nav>
            <div className="app-sidebar__footer">
              {userBlock}
              <Button variant="ghost" className="app-signout" onClick={onSignOut}>
                {t('nav.signOut')}
              </Button>
            </div>
          </aside>
          {drawerOpen && <div className="app-drawer-backdrop" onMouseDown={() => setDrawerOpen(false)} aria-hidden="true" />}
        </>
      )}
      <div className="app-body" inert={drawerOpen || undefined}>
        <header className={hasSidebar ? 'app-topbar app-topbar--compact' : 'app-topbar'}>
          <Brand to={home} />
          {hasSidebar ? (
            <button
              ref={menuButtonRef}
              type="button"
              className="button button--secondary app-menu-button"
              aria-expanded={drawerOpen}
              aria-controls={drawerId}
              onClick={() => setDrawerOpen(true)}
            >
              <span className="app-menu-button__icon" aria-hidden="true" />
              Menu
            </button>
          ) : (
            user && (
              <div className="app-topbar__user">
                {userBlock}
                <Button variant="ghost" onClick={onSignOut}>
                  {t('nav.signOut')}
                </Button>
              </div>
            )
          )}
        </header>
        <ConnectionBanner />
        <main id="main-content" ref={mainRef} className="app-main" tabIndex={-1}>
          <Outlet />
        </main>
        <footer className="app-footer">{t('footer.disclaimer')}</footer>
      </div>
    </div>
  )
}

