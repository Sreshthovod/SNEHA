import { apiRequest } from './client'
import type { AnalyticsSummary, ReviewFlagsResponse } from './types'

const base = (pid: string) => `/patients/${encodeURIComponent(pid)}/analytics`

/** Descriptive metrics for inclusive calendar dates (patient's timezone). */
export const getAnalytics = (pid: string, from: string, to: string, signal?: AbortSignal) =>
  apiRequest<AnalyticsSummary>(base(pid), { query: { from, to }, signal })
export const getReviewFlags = (pid: string, from: string, to: string, signal?: AbortSignal) =>
  apiRequest<ReviewFlagsResponse>(`${base(pid)}/review-flags`, { query: { from, to }, signal })
