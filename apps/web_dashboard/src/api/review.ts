import { apiRequest } from './client'
import type { ReviewDecision, ReviewItem, ReviewItemStatus } from './types'

const base = (pid: string) => `/patients/${encodeURIComponent(pid)}/review-items`

/** Caregivers see every item; clinicians only confirmed ones (enforced by the API). */
export const listReviewItems = (pid: string, status?: ReviewItemStatus, signal?: AbortSignal) =>
  apiRequest<ReviewItem[]>(base(pid), { query: { status }, signal })
/** Keep the current automated prompts for a period as items awaiting a caregiver's review. */
export const scanReviewItems = (pid: string, periodStart: string, periodEnd: string, signal?: AbortSignal) =>
  apiRequest<ReviewItem[]>(`${base(pid)}/scan`, {
    method: 'POST',
    body: { period_start: periodStart, period_end: periodEnd },
    signal,
  })
/** Confirm or dismiss, with a reason. Final: a second decision is a 409 `already_decided`. */
export const decideReviewItem = (pid: string, id: string, body: ReviewDecision) =>
  apiRequest<ReviewItem>(`${base(pid)}/${encodeURIComponent(id)}/decision`, { method: 'POST', body })
/** Add caregiver context (any caregiver). Never changes the decision or the evidence. */
export const addReviewContext = (pid: string, id: string, note: string) =>
  apiRequest<ReviewItem>(`${base(pid)}/${encodeURIComponent(id)}/context`, { method: 'POST', body: { note } })
