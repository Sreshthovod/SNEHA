/**
 * How the phone uses one memory, explained for caregivers. These mirror the phone's
 * published rules (apps/patient_app/lib/activities/memory_content.dart and
 * docs/memory-personalization-plan.md §3). Nothing here is a prediction: it only says
 * which activities this memory is eligible for, given what the family has entered.
 */
import type { Memory, MemoryKind } from '../api/types'

export interface PhoneStatus {
  shared: boolean
  text: string
}

export interface ActivityUse {
  title: string
  ready: boolean
  detail: string
}

const KIND_GROUPS: MemoryKind[] = ['person', 'place', 'event', 'object']

export function phoneStatus(m: Memory, hasPairedDevice: boolean): PhoneStatus {
  if (m.status === 'pending_approval')
    return { shared: false, text: 'Not on the phone: waiting for approval.' }
  if (m.status === 'rejected') return { shared: false, text: 'Not on the phone: not approved.' }
  if (!hasPairedDevice)
    return { shared: false, text: 'Approved. No phone is paired yet, so nothing is downloaded.' }
  return {
    shared: true,
    text: m.media_file_id
      ? 'Approved: the phone downloads it, with the photo, at its next sync. After that it works offline.'
      : 'Approved: the phone downloads it at its next sync. After that it works offline.',
  }
}

/** Activities this memory can appear in, and whether there is enough approved content yet. */
export function activityUses(m: Memory, approved: Memory[]): ActivityUse[] {
  if (m.status !== 'approved') return []
  const withPhoto = approved.filter((a) => a.media_file_id)
  const people = withPhoto.filter((a) => a.kind === 'person')
  const uses: ActivityUse[] = [
    {
      title: 'Story time',
      ready: true,
      detail: storyDetail(m, approved),
    },
  ]
  if (!m.media_file_id) {
    uses.push({
      title: 'Photo activities',
      ready: false,
      detail: 'Add a photo to use this memory in photo recall, matching pairs and sorting.',
    })
    return uses
  }
  uses.push({
    title: 'Photo recall',
    ready: withPhoto.length >= 2,
    detail: `Shows the photo and asks which memory it is. Needs 2 approved photos (now ${withPhoto.length}).`,
  })
  uses.push({
    title: 'Matching pairs',
    ready: withPhoto.length >= 3,
    detail: `Uses the family's photos as the pairs. Needs 3 approved photos (now ${withPhoto.length}); otherwise everyday pictures are used.`,
  })
  if (m.kind !== 'story') {
    const counts = KIND_GROUPS.map((k) => withPhoto.filter((a) => a.kind === k).length)
    const groups = counts.filter((n) => n >= 2).length
    uses.push({
      title: 'Sort into groups',
      ready: groups >= 2,
      detail: `Asks whether the photo shows a person, a place, an event or an object (the type you chose). Needs 2 types with 2 photos each (now ${groups}).`,
    })
  }
  if (m.kind === 'person') {
    uses.push({
      title: 'Familiar faces',
      ready: people.length >= 2,
      detail:
        `Shows the name and asks for the photo. Needs 2 people with photos (now ${people.length}).` +
        (m.relationship ? ` Hint: “${m.relationship}”.` : ' Add how they are related for a gentle hint.'),
    })
  }
  return uses
}

function storyDetail(m: Memory, approved: Memory[]): string {
  const parts = ['the title']
  if (m.description) parts.push('your description')
  if (m.approx_year) parts.push('the year')
  if (m.relationship) parts.push('how they are related')
  const missing = !m.description ? ' Add a description for a richer conversation.' : ''
  return `Talks about it using ${parts.join(', ')}, and any linked memories (${approved.length} approved in total).${missing}`
}
