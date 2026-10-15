import { apiRequest } from './client'
import type { CatalogEntry, Preferences, PreferencesUpdate, Progress, Recommendation } from './types'

const base = (pid: string) => `/patients/${encodeURIComponent(pid)}`

export const getCatalog = (signal?: AbortSignal) =>
  apiRequest<CatalogEntry[]>('/activities/catalog', { signal })
export const getPreferences = (pid: string, signal?: AbortSignal) =>
  apiRequest<Preferences>(`${base(pid)}/preferences`, { signal })
/** Managing caregivers only. Replaces the approved interests and preferences. */
export const putPreferences = (pid: string, body: PreferencesUpdate) =>
  apiRequest<Preferences>(`${base(pid)}/preferences`, { method: 'PUT', body })
export const getProgress = (pid: string, signal?: AbortSignal) =>
  apiRequest<Progress>(`${base(pid)}/progress`, { signal })
export const listRecommendations = (pid: string, limit = 20, signal?: AbortSignal) =>
  apiRequest<Recommendation[]>(`${base(pid)}/recommendations`, { query: { limit }, signal })
