import { createContext, useContext } from 'react'
import type { Patient, User } from '../api/types'

export interface PatientWorkspace {
  patient: Patient
  reloadPatient: () => void
  me: User
  isClinician: boolean
  /** Managing caregiver: may approve memories, edit the profile, manage access and consent. */
  isManager: boolean
}

export const PatientContext = createContext<PatientWorkspace | null>(null)

export function usePatient(): PatientWorkspace {
  const ctx = useContext(PatientContext)
  if (!ctx) throw new Error('usePatient must be used inside PatientLayout')
  return ctx
}
