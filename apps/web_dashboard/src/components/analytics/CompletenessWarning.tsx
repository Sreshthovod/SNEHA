import type { Completeness } from '../../api/types'
import { formatDate } from '../../lib/dates'
import { Notice } from '../ui/States'

/** Data-gap notice from the analytics completeness block. Missing days mean "no activity recorded". */
export function CompletenessWarning({ completeness }: { completeness: Completeness }) {
  const missing = completeness.missing_days
  if (missing.length === 0) return null
  const none = completeness.days_with_activity === 0
  return (
    <Notice tone="warning" title={none ? 'No activity recorded in this period' : 'Some days have no activity data'}>
      <p>
        No activities were recorded on {missing.length} of {completeness.days_elapsed} days
        {completeness.longest_gap_days > 1 ? ` (longest gap: ${completeness.longest_gap_days} days in a row)` : ''}.
        Missing days are gaps in the record. They are not counted as low results and say nothing
        about how the person is doing.
      </p>
      {missing.length <= 10 && (
        <p className="field__hint">Days without data: {missing.map((d) => formatDate(d)).join(', ')}</p>
      )}
    </Notice>
  )
}
