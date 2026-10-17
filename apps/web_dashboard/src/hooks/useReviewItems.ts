import { listReviewItems, scanReviewItems } from '../api/review'
import type { ReviewItem } from '../api/types'
import { usePatient } from '../state/patient'
import { useAsync } from './useAsync'

/** Loads review items: caregivers scan the period shown first (3–31 days); clinicians only read. */
export function useReviewItems(from: string, to: string, enabled = true) {
  const { patient, isClinician } = usePatient()
  const days = (new Date(to).getTime() - new Date(from).getTime()) / 86_400_000 + 1
  const canScan = !isClinician && days >= 3 && days <= 31
  const items = useAsync(
    async (signal) => {
      if (!enabled) return [] as ReviewItem[]
      if (canScan) await scanReviewItems(patient.id, from, to, signal)
      return listReviewItems(patient.id, undefined, signal)
    },
    [patient.id, from, to, canScan, enabled],
  )
  return { items, canScan }
}

export type ReviewItemsState = ReturnType<typeof useReviewItems>
