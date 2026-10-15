import { useState } from 'react'
import { downloadFile } from '../api/files'
import { reportPdfAvailable } from '../api/reports'
import type { Report } from '../api/types'
import { REPORT_STATUS_LABELS } from '../lib/labels'
import { Button } from './ui/Button'
import { DisabledWithReason } from './ui/DisabledReason'
import { ActionError } from './ui/States'
import { useAction } from '../hooks/useAsync'

/** Real authenticated download when a PDF exists; otherwise disabled with the reason shown. */
export function PdfDownloadButton({ report, fileName }: { report: Report; fileName: string }) {
  const [done, setDone] = useState(false)
  const action = useAction(async () => {
    const blob = await downloadFile(report.file_id as string)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    setDone(true)
  })

  if (!reportPdfAvailable(report)) {
    const reason =
      report.status === 'failed'
        ? 'This report could not be prepared, so there is no PDF. Use "Prepare again" to retry.'
        : `The PDF is not available yet (${REPORT_STATUS_LABELS[report.status].toLowerCase()}). Use "Prepare again" if it does not become ready.`
    return <DisabledWithReason label="Download PDF" reason={reason} />
  }
  return (
    <div>
      <Button onClick={() => action.run()} pending={action.pending}>
        Download PDF
      </Button>
      {done && <p className="field__hint" role="status">Download started.</p>}
      <ActionError error={action.error} />
    </div>
  )
}
