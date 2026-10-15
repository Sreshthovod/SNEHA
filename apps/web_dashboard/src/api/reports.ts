import { apiRequest } from './client'
import type { Report, ReportRequest } from './types'

const base = (pid: string) => `/patients/${encodeURIComponent(pid)}/reports`

export const listReports = (pid: string, signal?: AbortSignal) =>
  apiRequest<Report[]>(base(pid), { signal })
export const getReport = (pid: string, rid: string, signal?: AbortSignal) =>
  apiRequest<Report>(`${base(pid)}/${encodeURIComponent(rid)}`, { signal })
/** Generates the PDF during the request: returns `ready` (or `failed`). */
export const requestReport = (pid: string, body: ReportRequest) =>
  apiRequest<Report>(base(pid), { method: 'POST', body })
/** Try again for a pending or failed report (409 `report_ready` if already ready). */
export const generateReport = (pid: string, rid: string) =>
  apiRequest<Report>(`${base(pid)}/${encodeURIComponent(rid)}/generate`, { method: 'POST' })

/** A PDF exists only when the report is ready and has a file. */
export function reportPdfAvailable(report: Report): boolean {
  return report.status === 'ready' && Boolean(report.file_id)
}
