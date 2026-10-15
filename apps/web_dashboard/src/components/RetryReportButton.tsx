import { generateReport } from '../api/reports'
import type { Report } from '../api/types'
import { useAction } from '../hooks/useAsync'
import { Button } from './ui/Button'
import { ActionError } from './ui/States'

/** Re-runs PDF preparation for a pending or failed report. Hidden once a report is ready. */
export function RetryReportButton({ report, onDone }: { report: Report; onDone: (r: Report) => void }) {
  const action = useAction(() => generateReport(report.patient_id, report.id))
  if (report.status === 'ready' || report.status === 'generating') return null
  return (
    <div>
      <Button
        variant="secondary"
        pending={action.pending}
        onClick={async () => {
          const result = await action.run()
          if (result) onDone(result)
        }}
      >
        Prepare again
      </Button>
      <ActionError error={action.error} />
    </div>
  )
}
