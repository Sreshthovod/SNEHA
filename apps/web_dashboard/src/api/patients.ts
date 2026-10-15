import { apiRequest } from './client'
import type {
  Caregiver,
  CaregiverAdd,
  ClinicianGrant,
  ClinicianGrantCreate,
  PairingCode,
  Patient,
  PatientCreate,
  PatientUpdate,
} from './types'

const p = (id: string) => `/patients/${encodeURIComponent(id)}`

export const listPatients = (signal?: AbortSignal) => apiRequest<Patient[]>('/patients', { signal })
export const getPatient = (id: string, signal?: AbortSignal) =>
  apiRequest<Patient>(p(id), { signal })
export const createPatient = (body: PatientCreate) =>
  apiRequest<Patient>('/patients', { method: 'POST', body })
export const updatePatient = (id: string, body: PatientUpdate) =>
  apiRequest<Patient>(p(id), { method: 'PATCH', body })
export const erasePatient = (id: string, confirmDisplayName: string) =>
  apiRequest<void>(`${p(id)}/erase`, {
    method: 'POST',
    body: { confirm_display_name: confirmDisplayName },
    responseType: 'none',
  })

export const createPairingCode = (id: string) =>
  apiRequest<PairingCode>(`${p(id)}/pairing-codes`, { method: 'POST' })
export const revokeDevices = (id: string) =>
  apiRequest<void>(`${p(id)}/devices/revoke`, { method: 'POST', responseType: 'none' })

export const listCaregivers = (id: string, signal?: AbortSignal) =>
  apiRequest<Caregiver[]>(`${p(id)}/caregivers`, { signal })
export const addCaregiver = (id: string, body: CaregiverAdd) =>
  apiRequest<Caregiver>(`${p(id)}/caregivers`, { method: 'POST', body })
export const removeCaregiver = (id: string, relationshipId: string) =>
  apiRequest<void>(`${p(id)}/caregivers/${encodeURIComponent(relationshipId)}`, {
    method: 'DELETE',
    responseType: 'none',
  })

export const listGrants = (id: string, signal?: AbortSignal) =>
  apiRequest<ClinicianGrant[]>(`${p(id)}/clinician-grants`, { signal })
export const createGrant = (id: string, body: ClinicianGrantCreate) =>
  apiRequest<ClinicianGrant>(`${p(id)}/clinician-grants`, { method: 'POST', body })
export const revokeGrant = (id: string, grantId: string) =>
  apiRequest<void>(`${p(id)}/clinician-grants/${encodeURIComponent(grantId)}`, {
    method: 'DELETE',
    responseType: 'none',
  })
