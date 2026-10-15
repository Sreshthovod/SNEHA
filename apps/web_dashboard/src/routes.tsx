import type { ReactNode } from 'react'
import type { RouteObject } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { RequireAuth } from './components/layout/Guards'
import { OutletPassthrough, RoleHome } from './components/layout/RouteHelpers'
import { CaregiverDashboardPage } from './pages/CaregiverDashboardPage'
import { ClinicianDashboardPage } from './pages/ClinicianDashboardPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PatientsPage } from './pages/PatientsPage'
import { RegisterPage } from './pages/RegisterPage'
import { SettingsPage } from './pages/SettingsPage'
import { UnsupportedRolePage } from './pages/UnsupportedRolePage'
import { AnalyticsSection } from './pages/patient/AnalyticsSection'
import { ConsentSection } from './pages/patient/ConsentSection'
import { HistorySection } from './pages/patient/HistorySection'
import { MemoriesSection } from './pages/patient/MemoriesSection'
import { ObservationsSection } from './pages/patient/ObservationsSection'
import { PatientLayout } from './pages/patient/PatientLayout'
import { PeopleSection } from './pages/patient/PeopleSection'
import { PreferencesSection } from './pages/patient/PreferencesSection'
import { ProgressSection } from './pages/patient/ProgressSection'
import { ProfileSection } from './pages/patient/ProfileSection'
import { ReportViewer } from './pages/patient/ReportViewer'
import { ReportsSection } from './pages/patient/ReportsSection'

const caregiver = (el: ReactNode) => <RequireAuth roles={['caregiver']}>{el}</RequireAuth>
const clinician = (el: ReactNode) => <RequireAuth roles={['clinician']}>{el}</RequireAuth>

export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { index: true, element: <LoginPage /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      {
        path: 'app',
        element: <RequireAuth><OutletPassthrough /></RequireAuth>,
        children: [
          { index: true, element: <RoleHome /> },
          { path: 'dashboard', element: caregiver(<CaregiverDashboardPage />) },
          { path: 'patients', element: caregiver(<PatientsPage />) },
          { path: 'clinician', element: clinician(<ClinicianDashboardPage />) },
          { path: 'settings', element: <SettingsPage /> },
          { path: 'unsupported', element: <UnsupportedRolePage /> },
          {
            path: 'patients/:patientId',
            element: <RequireAuth roles={['caregiver', 'clinician']}><PatientLayout /></RequireAuth>,
            children: [
              { index: true, element: <ProfileSection /> },
              { path: 'memories', element: caregiver(<MemoriesSection />) },
              { path: 'observations', element: <ObservationsSection /> },
              { path: 'history', element: <HistorySection /> },
              { path: 'analytics', element: <AnalyticsSection /> },
              { path: 'progress', element: <ProgressSection /> },
              { path: 'preferences', element: <PreferencesSection /> },
              { path: 'reports', element: <ReportsSection /> },
              { path: 'reports/:reportId', element: <ReportViewer /> },
              { path: 'people', element: caregiver(<PeopleSection />) },
              { path: 'consent', element: <ConsentSection /> },
            ],
          },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
