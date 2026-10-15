/** Plain-language labels for API enum values. Neutral wording only: no grading or diagnosis. */
import type {
  ConsentGiver,
  ConsentType,
  Language,
  MemoryKind,
  MemoryStatus,
  ObservationCategory,
  ObservationStatus,
  RecordSource,
  ReportStatus,
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
