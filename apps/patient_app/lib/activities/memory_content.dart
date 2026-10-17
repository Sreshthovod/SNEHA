import 'dart:math';

import '../data/api/models.dart';
import '../l10n/strings.dart';
import 'activity.dart';

/// Deterministic rules that turn the person's APPROVED, cached memories into
/// activity content. Published in docs/memory-personalization-plan.md §3 and
/// mirrored for caregivers in the dashboard (apps/web_dashboard/src/lib/memoryUse.ts).
///
/// Nothing here invents a person, place or relationship: every sentence is
/// built from fields a caregiver entered and approved. When there is not
/// enough, the everyday version of the activity runs instead and says so.
abstract final class MemoryRules {
  /// Picture pairs uses family photos as cards from this many photos.
  static const minPairsPhotos = 3;

  /// Sorting by type needs this many types, each with this many photos.
  static const minSortKinds = 2;
  static const minPhotosPerKind = 2;

  /// Types a photo can be sorted into (the caregiver-chosen `kind`).
  static const sortKinds = ['person', 'place', 'event', 'object'];
}

/// Reason codes for content choices (recorded in `activity_started`).
abstract final class ContentReason {
  static const personalPhotos = 'PERSONAL_PHOTOS_USED';
  static const personalPeople = 'PERSONAL_PEOPLE_USED';
  static const kindSorting = 'MEMORY_KIND_SORTING';
  static const guidedStory = 'GUIDED_STORY_FROM_APPROVED_FIELDS';
  static const relationshipHint = 'RELATIONSHIP_HINT_AVAILABLE';
  static const enginePreferred = 'ENGINE_PREFERRED_MEMORIES_FIRST';
  static const genericFallback = 'GENERIC_CONTENT_FALLBACK';
  static const notEnoughPhotos = 'NOT_ENOUGH_CACHED_PHOTOS';
}

/// Approved memories whose photo is on this phone, one per title (two
/// memories with the same title would make a choice ambiguous).
List<MemoryItem> distinctPhotoMemories(ActivityContent c) {
  final byTitle = <String, MemoryItem>{};
  for (final m in c.withPhotos) {
    byTitle.putIfAbsent(m.title.trim().toLowerCase(), () => m);
  }
  return byTitle.values.toList();
}

/// Kinds that have enough photos for sorting, with their memories.
Map<String, List<MemoryItem>> sortableKinds(ActivityContent c) {
  final photos = distinctPhotoMemories(c);
  return {
    for (final k in MemoryRules.sortKinds)
      if (photos.where((m) => m.kind == k).length >=
          MemoryRules.minPhotosPerKind)
        k: photos.where((m) => m.kind == k).toList(),
  };
}

bool canSortByKind(ActivityContent c) =>
    sortableKinds(c).length >= MemoryRules.minSortKinds;

bool canPairPhotos(ActivityContent c) =>
    distinctPhotoMemories(c).length >= MemoryRules.minPairsPhotos;

List<String> withPreferredReason(ActivityContent c, List<String> reasons) => [
  ...reasons,
  if (c.preferredMemoryIds.isNotEmpty) ContentReason.enginePreferred,
];

/// Story order: the engine's preferred memories first, then the rest by title.
List<MemoryItem> storyOrder(ActivityContent c) {
  final byId = {for (final m in c.memories) m.id: m};
  final first = [
    for (final id in c.preferredMemoryIds)
      if (byId[id] != null) byId[id]!,
  ];
  final rest = c.memories.where((m) => !first.contains(m)).toList()
    ..sort((a, b) => a.title.compareTo(b.title));
  return [...first, ...rest];
}

/// A gentle conversation prompt for one memory, built ONLY from approved,
/// caregiver-entered fields and links. Returns null when there is nothing
/// specific to say; the caller then uses a general prompt.
String? guidedStoryPrompt(MemoryItem m, ActivityContent c, AppStrings s) {
  final byId = {for (final x in c.memories) x.id: x};
  final parts = <String>[];
  if (m.kind == 'person' && m.relationship != null) {
    parts.add(
      s.t('story_q_person_rel', {
        'name': m.title,
        'relationship': m.relationship!,
      }),
    );
  }
  // Facts from caregiver links, e.g. "Synthetic Mina was there too."
  for (final l in c.links) {
    final other = l.fromId == m.id
        ? byId[l.toId]
        : l.toId == m.id
        ? byId[l.fromId]
        : null;
    if (other == null) continue;
    if (l.type == 'person_in' && l.toId == m.id) {
      parts.add(s.t('story_fact_person_in', {'name': other.title}));
    } else if (l.type == 'located_at' && l.fromId == m.id) {
      parts.add(s.t('story_fact_located_at', {'place': other.title}));
    }
    if (parts.length >= 3) break;
  }
  final question = switch (m.kind) {
    'person' when m.relationship == null => s.t('story_q_person', {
      'name': m.title,
    }),
    'person' => null, // the relationship sentence already asks
    'place' => s.t('story_q_place', {'title': m.title}),
    'event' => s.t('story_q_event', {'title': m.title}),
    'object' => s.t('story_q_object', {'title': m.title}),
    _ => null,
  };
  if (question != null) parts.add(question);
  // Without a link or relationship, a bare question is still built only from
  // the title the family gave, so it counts as guided.
  return parts.isEmpty ? null : parts.join(' ');
}

/// Shuffled copy, for option lists.
List<T> shuffled<T>(Iterable<T> items, Random rng) => [...items]..shuffle(rng);
