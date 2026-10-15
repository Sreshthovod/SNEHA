import { apiRequest } from './client'
import type { Consent, ConsentCreate, ConsentSummary } from './types'

export const getConsents = (patientId: string, signal?: AbortSignal) =>
  apiRequest<ConsentSummary>(`/patients/${encodeURIComponent(patientId)}/consents`, { signal })
export const recordConsent = (patientId: string, body: ConsentCreate) =>
  apiRequest<Consent>(`/patients/${encodeURIComponent(patientId)}/consents`, {
    method: 'POST',
    body,
  })
