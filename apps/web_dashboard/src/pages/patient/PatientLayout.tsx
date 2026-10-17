import { useEffect, useId, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useParams } from 'react-router-dom'
import { listCaregivers, getPatient } from '../../api/patients'
import { ErrorState, Loading } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { focusWhenReady, useDocumentTitle } from '../../hooks/useDocumentTitle'
import type { StringKey } from '../../i18n/strings'
import { LANGUAGE_LABELS } from '../../lib/labels'
import { initials } from '../../lib/people'
import { useAuth } from '../../state/auth'
import { PatientContext } from '../../state/patient'
import { useSettings } from '../../state/settings'

interface Section {
  path: string
  key: StringKey
  caregiverOnly?: boolean
}

interface SectionGroup {
  id: string
  label: string
  sections: Section[]
}

/** The ten record sections, grouped so they fit and scan at every width (routes unchanged). */
const GROUPS: SectionGroup[] = [
  {
    id: 'person',
    label: 'Person',
    sections: [
      { path: '', key: 'tab.overview' },
      { path: 'memories', key: 'tab.memories', caregiverOnly: true },
      { path: 'observations', key: 'tab.observations' },
    ],
  },
  {
    id: 'activity',
    label: 'Activity',
    sections: [
      { path: 'history', key: 'tab.history' },
      { path: 'analytics', key: 'tab.analytics' },
      { path: 'progress', key: 'tab.progress' },
      { path: 'reports', key: 'tab.reports' },
    ],
  },
  {
    id: 'care',
    label: 'Care & privacy',
    sections: [
      { path: 'preferences', key: 'tab.preferences' },
      { path: 'people', key: 'tab.people', caregiverOnly: true },
      { path: 'consent', key: 'tab.consent' },
    ],
  },
]

/** Which section the current URL belongs to ("reports/:id" belongs to Reports). */
function currentSection(pathname: string, base: string): Section {
  const rest = pathname.slice(base.length).replace(/^\/+/, '')
  const first = rest.split('/')[0] ?? ''
  for (const g of GROUPS) for (const s of g.sections) if (s.path === first) return s
  return GROUPS[0].sections[0]
}

export function PatientLayout() {
  const { patientId = '' } = useParams()
  const { user } = useAuth()
  const { t } = useSettings()
  const location = useLocation()
  const isClinician = user?.role === 'clinician'
  const [menuOpen, setMenuOpen] = useState(false)
  const panelId = useId()
  const sectionRef = useRef<HTMLDivElement>(null)

  const patient = useAsync((signal) => getPatient(patientId, signal), [patientId])
  const caregivers = useAsync(
    (signal) => (isClinician ? Promise.resolve([]) : listCaregivers(patientId, signal)),
    [patientId, isClinician],
  )

  const base = `/app/patients/${patientId}`
  const section = currentSection(location.pathname, base)
  const p = patient.data
  useDocumentTitle(t(section.key), p?.display_name)

  // Moving between sections: close the compact menu and focus the new section's heading.
  const previousPath = useRef(location.pathname)
  useEffect(() => {
    const prev = previousPath.current
    previousPath.current = location.pathname
    if (prev === location.pathname) return
    setMenuOpen(false)
    if (!prev.startsWith(base)) return // AppShell handles arriving from elsewhere.
    return focusWhenReady(() => sectionRef.current, ['h1', 'h2', '.card__title'], () => sectionRef.current)
  }, [location.pathname, base])

  if (!user) return null
  if (patient.status === 'error' && !p) return <ErrorState error={patient.error} onRetry={patient.reload} />
  if (!p) return <Loading />

  const isManager = Boolean(caregivers.data?.find((c) => c.caregiver_id === user.id)?.can_manage)
  const groups = GROUPS.map((g) => ({
    ...g,
    sections: g.sections.filter((s) => !(isClinician && s.caregiverOnly)),
  })).filter((g) => g.sections.length > 0)
  const name = p.preferred_name ? `${p.display_name} (${p.preferred_name})` : p.display_name

  return (
    <PatientContext.Provider value={{ patient: p, reloadPatient: patient.reload, me: user, isClinician, isManager }}>
      <header className="patient-header">
        <span className="patient-header__avatar" aria-hidden="true">
          {initials(p.display_name)}
        </span>
        <div className="patient-header__text">
          <p className="eyebrow">{isClinician ? 'Patient record (read only)' : 'Person you care for'}</p>
          <h1 className="patient-header__name">{name}</h1>
          <ul className="patient-header__meta" aria-label="About this record">
            <li>{LANGUAGE_LABELS[p.preferred_language]}</li>
            <li>{p.timezone}</li>
            {p.is_synthetic && (
              <li>
                <span className="badge badge--neutral">
                  <span aria-hidden="true">○</span>Synthetic demo profile
                </span>
              </li>
            )}
            {isClinician && (
              <li>
                <span className="badge badge--info">
                  <span aria-hidden="true">◆</span>Read only
                </span>
              </li>
            )}
          </ul>
        </div>
      </header>

      <div className="patient-workspace">
        <nav className="patient-nav" aria-label="Patient sections">
          <button
            type="button"
            className="patient-nav__toggle"
            aria-expanded={menuOpen}
            aria-controls={panelId}
            onClick={() => setMenuOpen((v) => !v)}
          >
            <span className="patient-nav__toggle-label">
              <span className="patient-nav__toggle-eyebrow">Section</span>
              <span className="patient-nav__toggle-current">{t(section.key)}</span>
            </span>
            <span className="patient-nav__chevron" aria-hidden="true" />
            <span className="visually-hidden">{menuOpen ? '(hide sections)' : '(show all sections)'}</span>
          </button>
          <div id={panelId} className={menuOpen ? 'patient-nav__panel is-open' : 'patient-nav__panel'}>
            {groups.map((g) => (
              <div key={g.id} className="patient-nav__group">
                <p className="patient-nav__group-label" id={`${panelId}-${g.id}`}>
                  {g.label}
                </p>
                <ul aria-labelledby={`${panelId}-${g.id}`}>
                  {g.sections.map((s) => (
                    <li key={s.path}>
                      <NavLink to={s.path === '' ? base : `${base}/${s.path}`} end={s.path === ''}>
                        {t(s.key)}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </nav>
        <div className="patient-section" ref={sectionRef}>
          <Outlet />
        </div>
      </div>
    </PatientContext.Provider>
  )
}
