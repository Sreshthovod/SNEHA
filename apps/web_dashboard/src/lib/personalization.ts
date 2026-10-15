/**
 * Plain-language explanations for the personalization engine's reason codes and
 * supporting records. These describe engagement rules (keeping activities comfortable
 * and enjoyable); none of them is a health measure.
 */
import type { Recommendation, RecommendationAction } from '../api/types'

export const REASON_LABELS: Record<string, string> = {
  STOP_REQUESTED: 'They asked to stop, so nothing more was suggested.',
  FATIGUE_REPORTED_BREAK: 'They said they were tired, so a rest was offered first.',
  RECENT_FATIGUE_FEEDBACK: 'Tiredness was mentioned recently.',
  RECENT_FATIGUE_OBSERVATION: 'A caregiver noted tiredness recently.',
  LOW_EFFORT_FOR_FATIGUE: 'A gentle activity at the easiest level was chosen because of tiredness.',
  COLD_START_DEFAULT: 'No activities have been recorded yet, so a standard first choice was used.',
  INTEREST_MATCH: 'It matches interests your family approved.',
  CONVERSATION_CONTEXT_MATCH: 'It relates to something they talked about.',
  ENJOYED_BEFORE: 'They enjoyed this activity before.',
  FAMILIAR_ACTIVITY: 'It is a familiar activity they have finished before.',
  LOW_ENGAGEMENT_SWITCH: 'Recent activities were stopped early or not enjoyed, so something different was chosen.',
  AVOID_REPETITION: 'A different activity was chosen to avoid repeating the last one.',
  ONLY_AVAILABLE_ACTIVITY: 'It was the only activity available.',
  DIFFICULTY_INCREASED_AFTER_COMFORTABLE_SUCCESS: 'The level went up one step after several comfortable successes.',
  DIFFICULTY_DECREASED_AFTER_REPEATED_ERRORS: 'The level went down one step to keep it comfortable.',
  DIFFICULTY_HELD_TO_AVOID_OSCILLATION: 'The level was kept the same for now, so it does not change too quickly.',
  DIFFICULTY_UNCHANGED: 'The level stayed the same.',
  DIFFICULTY_STARTING_LEVEL: 'This activity starts at the first level.',
  HINTS_OFFERED_AFTER_ERRORS: 'Hints are offered to make it easier.',
  MISSING_DATA_NOT_COUNTED_AS_ERROR: 'A recent activity had no score; that is not counted as a mistake.',
  APPROVED_MEMORIES_USED: 'It uses memories your family approved.',
  PERSONAL_ROUTINES_USED: "It uses the person's own daily routines.",
  DISLIKED_ACTIVITY_EXCLUDED: 'Activities marked as not liked were left out.',
  LIMITED_TO_AVAILABLE_OFFLINE_CONTENT: 'Only activities available on the phone were considered.',
  LANGUAGE_CONTENT_FALLBACK: 'There was no content in their language, so another language was used.',
  NO_AVAILABLE_ACTIVITY: 'No suitable activity was available.',
}

export function reasonLabel(code: string): string {
  return REASON_LABELS[code] ?? `Other reason (${code.toLowerCase().replace(/_/g, ' ')})`
}

export const SUPPORT_KIND_LABELS: Record<string, string> = {
  activity_result: 'Activity',
  caregiver_observation: 'Caregiver note',
  activity_session: 'Session',
  memory_item: 'Memory',
  routine_item: 'Routine',
  preference: 'Preference',
  request: 'Request',
  conversation: 'Conversation',
}

export const FALLBACK_LABELS: Record<string, string> = {
  no_history: 'Standard first choice (no activity history yet)',
  no_available_activity: 'Nothing suitable was available',
  language_content_unavailable: 'Content in their language was not available',
}

export function actionLabel(rec: Pick<Recommendation, 'action' | 'activity_title'>): string {
  const labels: Record<RecommendationAction, string> = {
    activity: rec.activity_title ?? 'An activity',
    break: `A rest first${rec.activity_title ? `, then ${rec.activity_title}` : ''}`,
    stop: 'Stop for now',
    none: 'No suggestion',
  }
  return labels[rec.action]
}

export const ANALYTICS_DISCLAIMER_FALLBACK =
  'These numbers describe activities only and are not a medical assessment.'
