import { apiRequest } from './client'
import type { Activity, PerformanceHistory, Result, Session } from './types'

const base = (pid: string) => `/patients/${encodeURIComponent(pid)}`

export const listActivities = (signal?: AbortSignal) =>
  apiRequest<Activity[]>('/activities', { signal })
export const listSessions = (pid: string, limit = 50, signal?: AbortSignal) =>
  apiRequest<Session[]>(`${base(pid)}/sessions`, { query: { limit }, signal })
export const listResults = (pid: string, sessionId: string, signal?: AbortSignal) =>
  apiRequest<Result[]>(`${base(pid)}/sessions/${encodeURIComponent(sessionId)}/results`, {
    signal,
  })
/** Inclusive calendar dates (YYYY-MM-DD) in the patient's timezone. */
export const getHistory = (pid: string, from: string, to: string, signal?: AbortSignal) =>
  apiRequest<PerformanceHistory>(`${base(pid)}/history`, { query: { from, to }, signal })
