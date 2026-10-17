import 'dart:math';

import 'package:flutter/widgets.dart';

import '../data/api/models.dart';
import '../data/api/stage7_models.dart';
import '../l10n/strings.dart';

/// Content available on this phone for building rounds. Fully offline.
class ActivityContent {
  const ActivityContent({
    this.memories = const [],
    this.routines = const [],
    this.preferredMemoryIds = const [],
    this.links = const [],
  });

  /// Approved memories only.
  final List<MemoryItem> memories;
  final List<RoutineItem> routines;

  /// Caregiver links between the approved memories (e.g. a person in an event).
  final List<MemoryLinkFact> links;

  /// Approved memories the engine picked as most relevant for this activity
  /// (interest matches, not recently used), most relevant first. Games use
  /// them before any others.
  final List<String> preferredMemoryIds;

  List<MemoryItem> get withPhotos => memories.where((m) => m.hasPhoto).toList();

  /// [n] of [items]: the engine's preferred memories first (in its order),
  /// then the rest in random order.
  List<MemoryItem> pickPreferred(List<MemoryItem> items, int n, Random rng) {
    final byId = {for (final m in items) m.id: m};
    final first = [
      for (final id in preferredMemoryIds)
        if (byId[id] != null) byId[id]!,
    ];
    final rest = items.where((m) => !first.contains(m)).toList()..shuffle(rng);
    return [...first, ...rest].take(n).toList();
  }
}

/// Per-level parameters for one run (e.g. `pairs`, `options`, `questions`,
/// `steps`, `groups`, `items`).
///
/// They come from the synced catalog spec (GET /activities/catalog, cached in
/// `catalog_specs`) whenever one is available. Before the first sync each game
/// uses its own BUNDLED defaults — see the `??` fallbacks in every
/// createRounds implementation.
class LevelParams {
  const LevelParams([this._values = const {}]);

  /// Parameters for [difficulty] from [spec], or empty (bundled defaults).
  factory LevelParams.of(ActivitySpec? spec, int difficulty) =>
      LevelParams(spec?.levels[difficulty] ?? const {});

  final Map<String, Object?> _values;

  /// True when the values came from the server catalog.
  bool get fromCatalog => _values.isNotEmpty;

  /// A positive integer parameter, or null when absent/invalid.
  int? intOf(String key) {
    final v = _values[key];
    return v is int && v > 0 ? v : null;
  }
}

/// Whether an activity run uses the person's approved memories or the bundled
/// everyday content, and why (reason codes recorded in `activity_started`).
/// See lib/activities/memory_content.dart for the rules.
class ContentChoice {
  const ContentChoice({required this.personal, this.reasons = const []});

  const ContentChoice.generic([this.reasons = const []]) : personal = false;

  final bool personal;
  final List<String> reasons;

  String get source => personal ? 'personal' : 'generic';
}

/// What a round reports back to the runner.
abstract interface class RoundHost {
  /// One answer attempt (a tap on an option, a card pair, a step).
  void attempt({required bool correct});

  /// The round's goal is reached; the runner moves to the next round.
  void solved();
}

/// Per-round context passed to [RoundSpec.build].
class RoundContext {
  const RoundContext({
    required this.host,
    required this.hintsUsed,
    required this.reduceMotion,
    required this.strings,
  });

  final RoundHost host;
  final int hintsUsed;
  final bool reduceMotion;
  final AppStrings strings;
}

/// One round of an activity: its logic and its view.
abstract class RoundSpec {
  const RoundSpec();

  /// How many hints this round can still give in total.
  int get maxHints;

  /// Spoken/shown when a hint is used.
  String hintMessage(AppStrings s, int hintNumber);

  /// The question or instruction for "Read aloud" (null = use the activity
  /// description).
  String? get spokenText => null;

  /// Approved memories this round shows (recorded with its events). Empty for
  /// everyday content.
  List<String> get memoryIds => const [];

  Widget build(BuildContext context, RoundContext round);
}

/// A cognitive activity. To add a game: implement this (usually by reusing
/// ChoiceRoundSpec / SequenceRoundSpec / PairsRoundSpec) and register it in
/// registry.dart. The generic ActivityRunnerScreen provides pause, hint, skip,
/// stop, progress, timing and result recording for every activity.
abstract class CognitiveActivity {
  const CognitiveActivity();

  /// Must match the server catalog slug.
  String get slug;

  IconData get icon;

  bool get usesMemoryBank => false;

  /// Personal or everyday content for this run, with reason codes. Must agree
  /// with what [createRounds] builds from the same [content].
  ContentChoice contentChoice(ActivityContent content) =>
      const ContentChoice.generic();

  /// Null when the activity can be played with [content]; otherwise a string
  /// key explaining what is missing (shown as a friendly empty state).
  String? unavailableReason(ActivityContent content) => null;

  /// Rounds for this run. [difficulty] is within the catalog's min/max;
  /// [level] carries the catalog's parameters for that difficulty.
  List<RoundSpec> createRounds({
    required ActivityContent content,
    required int difficulty,
    required Random random,
    required AppStrings strings,
    LevelParams level = const LevelParams(),
  });

  /// Shared sizing rules so difficulty means the same thing everywhere.
  static int roundCount(int difficulty) => (2 + difficulty).clamp(3, 5);
  static int optionCount(int difficulty) => (2 + difficulty).clamp(3, 4);
}
