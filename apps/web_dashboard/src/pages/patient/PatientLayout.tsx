import { NavLink, Outlet, useParams } from 'react-router-dom'
import { listCaregivers, getPatient } from '../../api/patients'
import { ErrorState, Loading } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import type { StringKey } from '../../i18n/strings'
import { LANGUAGE_LABELS } from '../../lib/labels'
import { useAuth } from '../../state/auth'
import { PatientContext } from '../../state/patient'
import { useSettings } from '../../state/settings'

interface Section {
  path: string
  key: StringKey
  caregiverOnly?: boolean
}

const SECTIONS: Section[] = [
  { path: '', key: 'tab.overview' },
  { path: 'memories', key: 'tab.memories', caregiverOnly: true },
  { path: 'observations', key: 'tab.observations' },
  { path: 'history', key: 'tab.history' },
  { path: 'analytics', key: 'tab.analytics' },
  { path: 'progress', key: 'tab.progress' },
  { path: 'preferences', key: 'tab.preferences' },
  { path: 'reports', key: 'tab.reports' },
  { path: 'people', key: 'tab.people', caregiverOnly: true },
  { path: 'consent', key: 'tab.consent' },
]

export function PatientLayout() {
  const { patientId = '' } = useParams()
  const { user } = useAuth()
  const { t } = useSettings()
  const isClinician = user?.role === 'clinician'

  const patient = useAsync((signal) => getPatient(patientId, signal), [patientId])
  const caregivers = useAsync(
    (signal) => (isClinician ? Promise.resolve([]) : listCaregivers(patientId, signal)),
    [patientId, isClinician],
  )

  if (!user) return null
  if (patient.status === 'error' && !patient.data)
    return <ErrorState error={patient.error} onRetry={patient.reload} />
  if (!patient.data) return <Loading />

  const isManager = Boolean(
    caregivers.data?.find((c) => c.caregiver_id === user.id)?.can_manage,
  )
  const sections = SECTIONS.filter((s) => !(isClinician && s.caregiverOnly))
  const p = patient.data

  return (
    <PatientContext.Provider
      value={{ patient: p, reloadPatient: patient.reload, me: user, isClinician, isManager }}
    >
      <header className="page-header">
        <p className="eyebrow">{isClinician ? 'Patient record (read only)' : 'Person you care for'}</p>
        <h1>{p.preferred_name ? `${p.display_name} (${p.preferred_name})` : p.display_name}</h1>
        <p className="page-header__lede">
          {LANGUAGE_LABELS[p.preferred_language]} · {p.timezone}
          {p.is_synthetic && <span className="badge badge--neutral"> Synthetic demo profile</span>}
        </p>
      </header>
      <nav className="subnav" aria-label="Patient sections">
        <ul>
          {sections.map((s) => (
            <li key={s.path}>
              <NavLink to={s.path} end={s.path === ''}>
                {t(s.key)}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <Outlet />
    </PatientContext.Provider>
  )
}
