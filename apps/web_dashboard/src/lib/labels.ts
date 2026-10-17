/** Plain-language labels for API enum values. Neutral wording only: no grading or diagnosis. */
import type {
  ActivityEventType,
  ConsentGiver,
  FatigueLevel,
  ConsentType,
  Language,
  MemoryKind,
  MemoryStatus,
  ObservationCategory,
  ObservationStatus,
  RecordSource,
  ReportStatus,
  ReviewItemStatus,
  SessionEvent,
} from '../api/types'

export const LANGUAGE_LABELS: Record<Language, string> = {
  as: 'Assamese',
  bn: 'Bengali',
  brx: 'Bodo',
  en: 'English',
  grt: 'Garo',
  hi: 'Hindi',
  kha: 'Khasi',
  mni: 'Manipuri (Meitei)',
  lus: 'Mizo',
  nag: 'Nagamese',
  ne: 'Nepali',
}

export const MEMORY_KIND_LABELS: Record<MemoryKind, string> = {
  person: 'Person',
  place: 'Place',
  event: 'Event',
  object: 'Object',
  story: 'Story',
}

export const MEMORY_STATUS_LABELS: Record<MemoryStatus, string> = {
  pending_approval: 'Waiting for approval',
  approved: 'Approved',
  rejected: 'Not approved',
}

export const OBSERVATION_LABELS: Record<ObservationCategory, string> = {
  mood: 'Mood',
  sleep: 'Sleep',
  appetite: 'Appetite',
  orientation: 'Orientation',
  behaviour: 'Behaviour',
  physical: 'Physical',
  fatigue: 'Tiredness',
  other: 'Other',
}

export const CONSENT_LABELS: Record<ConsentType, { title: string; description: string }> = {
  data_processing: {
    title: 'Store activity and Memory Bank data',
    description: 'Needed to save activity results, memories and photos.',
  },
  clinician_sharing: {
    title: 'Share with clinicians',
    description: 'Lets clinicians you choose view activity summaries and reports.',
  },
  cloud_ai: {
    title: 'Online conversation help',
    description: 'Allows conversation text to be sent to an online AI service.',
  },
  voice_processing: {
    title: 'Voice',
    description: 'Allows speech to be processed for voice conversations.',
  },
}

export const CONSENT_GIVER_LABELS: Record<ConsentGiver, string> = {
  patient: 'The person themselves',
  legal_representative: 'Legal representative',
  caregiver_on_behalf: 'Caregiver on their behalf',
}

export const REPORT_STATUS_LABELS: Record<ReportStatus, string> = {
  pending: 'Waiting to be prepared',
  generating: 'Being prepared',
  ready: 'Ready',
  failed: 'Could not be prepared',
}

export function options<K extends string>(labels: Record<K, string>) {
  return (Object.keys(labels) as K[]).map((value) => ({ value, label: labels[value] }))
}

export const OBSERVATION_STATUS_LABELS: Record<ObservationStatus, string> = {
  open: 'Open',
  reviewed: 'Reviewed',
  resolved: 'Resolved',
}

export const SOURCE_LABELS: Record<RecordSource, string> = {
  dashboard: 'Added on the dashboard',
  device: "Added on the person's phone",
}

export const FATIGUE_LEVEL_LABELS: Record<FatigueLevel, string> = {
  mild: 'A little tired: make activities easier',
  severe: 'Very tired: rest, no more activities for now',
}

export const REVIEW_STATUS_LABELS: Record<ReviewItemStatus, string> = {
  awaiting_review: 'Waiting for your review',
  confirmed: 'Confirmed: worth discussing with a clinician',
  dismissed: 'Dismissed',
}

/** Plain words for in-session decision reasons (phone policy and engine codes). */
export const ADAPTATION_REASON_LABELS: Record<string, string> = {
  STOP_REQUESTED: 'they asked to stop',
  SEVERE_FATIGUE_END_SESSION: 'they were very tired',
  SEVERE_FATIGUE_OFFER_BREAK: 'they were very tired',
  MILD_FATIGUE_SHORTEN: 'they were a little tired',
  MILD_FATIGUE_MORE_HINTS: 'they were a little tired',
  REPEATED_ERRORS_IN_ROUND: 'several answers in a row were not right',
  HINTS_ADVISED_BY_ENGINE: 'recent activities were hard',
  REPEATED_STRUGGLE_SHORTEN: 'two rounds in a row were hard',
  REPEATED_STRUGGLE_OFFER_BREAK: 'several rounds were hard',
  CAREGIVER_REPORT: 'reported by a caregiver',
  PATIENT_REPORT: 'they said so themselves',
  FATIGUE_REPORTED_BREAK: 'they said they were tired',
}

const ACTION_LABELS: Record<string, string> = {
  show_hint: 'The app showed a hint',
  shorten: 'The app shortened the activity',
  offer_break: 'The app offered a rest',
  end_session: 'The app ended the activity',
}

const EVENT_LABELS: Record<ActivityEventType, string> = {
  activity_started: 'Started',
  attempt: 'Answer',
  hint_requested: 'Asked for a hint',
  hint_auto: 'Hint shown by the app',
  round_solved: 'Round done',
  round_skipped: 'Round skipped',
  paused: 'Paused',
  resumed: 'Carried on',
  fatigue_reported: 'Tiredness reported',
  stop_requested: 'Asked to stop',
  adaptation: 'The app adjusted the activity',
  break_taken: 'Took a rest',
  break_declined: 'Chose to keep going',
  activity_ended: 'Ended',
  instructions_repeated: 'Asked to hear the question again',
}

const CONTENT_REASON_LABELS: Record<string, string> = {
  PERSONAL_PHOTOS_USED: 'family photos',
  PERSONAL_PEOPLE_USED: 'family members',
  MEMORY_KIND_SORTING: 'sorting family photos by type',
  GUIDED_STORY_FROM_APPROVED_FIELDS: 'questions from what the family wrote',
  RELATIONSHIP_HINT_AVAILABLE: 'relationship hints',
  GENERIC_CONTENT_FALLBACK: 'everyday pictures',
  NOT_ENOUGH_CACHED_PHOTOS: 'not enough family photos on the phone yet',
}

/**
 * One line per event, in plain words. Never a grade. `memoryTitle` resolves memory IDs
 * for viewers who may see the Memory Bank; otherwise a neutral phrase is used.
 */
export function describeEvent(e: SessionEvent, memoryTitle?: (id: string) => string | undefined): string {
  const d = e.data as Record<string, unknown>
  const named = (id: unknown) => (typeof id === 'string' && memoryTitle?.(id)) || 'a family memory'
  const about = typeof d.memory_id === 'string' ? ` (${named(d.memory_id)})` : ''
  switch (e.event_type) {
    case 'attempt': {
      const secs = typeof d.latency_ms === 'number' ? ` after ${(d.latency_ms / 1000).toFixed(1)} s` : ''
      return `${d.correct ? 'Right answer' : 'Not this one'}${secs}${about}`
    }
    case 'round_solved':
      return `Round done${about}`
    case 'round_skipped':
      return `Round skipped${about}`
    case 'adaptation': {
      const reasons = Array.isArray(d.reason_codes)
        ? d.reason_codes.map((c) => ADAPTATION_REASON_LABELS[String(c)] ?? String(c)).join('; ')
        : ''
      return `${ACTION_LABELS[String(d.action)] ?? 'The app adjusted the activity'}${reasons ? ` because ${reasons}` : ''}`
    }
    case 'fatigue_reported': {
      const who = d.source === 'caregiver' ? 'by a caregiver' : 'by the person'
      const level = d.level === 'severe' ? ' (very tired)' : d.level === 'mild' ? ' (a little tired)' : ''
      return `Tiredness reported ${who}${level}`
    }
    case 'activity_started': {
      const base = `Started (${String(d.rounds_planned ?? '?')} rounds, level ${String(d.difficulty ?? '?')})`
      const ids = Array.isArray(d.memory_ids) ? d.memory_ids : []
      const why = Array.isArray(d.reason_codes)
        ? d.reason_codes.map((c) => CONTENT_REASON_LABELS[String(c)]).filter(Boolean)
        : []
      const source =
        d.content_source === 'personal'
          ? ` with ${ids.length === 1 ? '1 approved memory' : `${ids.length} approved memories`}: ${ids.map(named).join(', ')}`
          : d.content_source === 'generic'
            ? ' with everyday content'
            : ''
      const decided =
        d.decided_on === 'device'
          ? ' · suggested by the phone'
          : d.decided_on === 'server'
            ? ' · suggested by SNEHA online'
            : ''
      return `${base}${source}${why.length ? ` · ${why.join(', ')}` : ''}${decided}`
    }
    case 'activity_ended':
      return `Ended: ${String(d.outcome ?? 'finished')}`
    default:
      return EVENT_LABELS[e.event_type] ?? e.event_type
  }
}
