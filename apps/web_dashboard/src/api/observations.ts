import { apiRequest } from './client'
import type {
  Observation,
  ObservationCorrection,
  ObservationCreate,
  ObservationResolve,
  ObservationReview,
  ObservationRevision,
  ObservationStatus,
} from './types'

const base = (pid: string) => `/patients/${encodeURIComponent(pid)}/observations`
const one = (pid: string, id: string) => `${base(pid)}/${encodeURIComponent(id)}`

export interface ObservationQuery {
  limit?: number
  status?: ObservationStatus
}

export const listObservations = (pid: string, query: ObservationQuery = {}, signal?: AbortSignal) =>
  apiRequest<Observation[]>(base(pid), { query: { limit: query.limit ?? 50, status: query.status }, signal })
export const getObservation = (pid: string, id: string, signal?: AbortSignal) =>
  apiRequest<Observation>(one(pid, id), { signal })
export const createObservation = (pid: string, body: ObservationCreate) =>
  apiRequest<Observation>(base(pid), { method: 'POST', body })
/** Correct an observation. `expected_version` must match (409 `version_conflict` otherwise). */
export const correctObservation = (pid: string, id: string, body: ObservationCorrection) =>
  apiRequest<Observation>(one(pid, id), { method: 'PATCH', body })
export const reviewObservation = (pid: string, id: string, body: ObservationReview) =>
  apiRequest<Observation>(`${one(pid, id)}/review`, { method: 'POST', body })
export const resolveObservation = (pid: string, id: string, body: ObservationResolve) =>
  apiRequest<Observation>(`${one(pid, id)}/resolve`, { method: 'POST', body })
export const listRevisions = (pid: string, id: string, signal?: AbortSignal) =>
  apiRequest<ObservationRevision[]>(`${one(pid, id)}/revisions`, { signal })
export const deleteObservation = (pid: string, id: string) =>
  apiRequest<void>(one(pid, id), { method: 'DELETE', responseType: 'none' })
