/** Calendar date (YYYY-MM-DD) of an instant in a given IANA timezone. */
export function dateInZone(instant: Date, timeZone: string): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(instant)
}

export function todayInZone(timeZone: string): string {
  return dateInZone(new Date(), timeZone)
}

/** Add days to a YYYY-MM-DD date (calendar arithmetic, timezone-free). */
export function addDays(date: string, days: number): string {
  const d = new Date(`${date}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

export function formatDateTime(iso: string, timeZone?: string): string {
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone,
  }).format(new Date(iso))
}

export function formatDate(date: string): string {
  return new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeZone: 'UTC' }).format(
    new Date(`${date}T00:00:00Z`),
  )
}

/** Convert a <input type="datetime-local"> value to an ISO string with offset. */
export function localInputToIso(value: string): string {
  return new Date(value).toISOString()
}

export function nowLocalInput(): string {
  const d = new Date()
  d.setSeconds(0, 0)
  const offset = d.getTimezoneOffset() * 60000
  return new Date(d.getTime() - offset).toISOString().slice(0, 16)
}

export function formatDuration(ms: number): string {
  const totalSeconds = Math.round(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return minutes ? `${minutes} min ${seconds} s` : `${seconds} s`
}

/** ISO instant → value for <input type="datetime-local"> in the browser's timezone. */
export function isoToLocalInput(iso: string): string {
  const d = new Date(iso)
  const offset = d.getTimezoneOffset() * 60000
  return new Date(d.getTime() - offset).toISOString().slice(0, 16)
}
