import { dateInZone } from './dates'

/** Report periods are stored as UTC instants of local midnights; show local calendar dates. */
export function reportDates(periodStart: string, periodEnd: string, timezone: string) {
  return {
    from: dateInZone(new Date(periodStart), timezone),
    to: dateInZone(new Date(new Date(periodEnd).getTime() - 1), timezone),
  }
}
