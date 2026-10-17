import 'dart:math';

import 'package:flutter/material.dart';

import '../../l10n/strings.dart';
import '../activity.dart';
import '../everyday_content.dart';
import '../memory_content.dart';
import '../rounds/choice_round.dart';
import '../rounds/pairs_round.dart';
import '../rounds/sequence_round.dart';

/// Object recognition: look at a picture of an everyday object, choose its name.
class NameTheObjectActivity extends CognitiveActivity {
  const NameTheObjectActivity();

  @override
  String get slug => 'name-the-object';

  @override
  IconData get icon => Icons.category_outlined;

  @override
  List<RoundSpec> createRounds({
    required ActivityContent content,
    required int difficulty,
    required Random random,
    required AppStrings strings,
    LevelParams level = const LevelParams(),
  }) {
    final questions =
        level.intOf('questions') ?? CognitiveActivity.roundCount(difficulty);
    final targets = ([
      ...everydayThings,
    ]..shuffle(random)).take(questions).toList();
    final nOptions =
        (level.intOf('options') ?? CognitiveActivity.optionCount(difficulty))
            .clamp(2, everydayThings.length);
    return [
      for (final t in targets)
        ChoiceRoundSpec(
          prompt: strings.t('game_object_q'),
          promptIcon: t.icon,
          correctId: t.id,
          options:
              ([
                    t,
                    ...(everydayThings.where((x) => x.id != t.id).toList()
                          ..shuffle(random))
                        .take(nOptions - 1),
                  ]..shuffle(random))
                  .map((x) => ChoiceOption(id: x.id, label: x.label))
                  .toList(),
        ),
    ];
  }
}

/// Simple categorization: put an everyday thing into the right group.
class SortIntoGroupsActivity extends CognitiveActivity {
  const SortIntoGroupsActivity();

  @override
  String get slug => 'sort-into-groups';

  @override
  IconData get icon => Icons.dashboard_customize;

  @override
  ContentChoice contentChoice(ActivityContent content) => canSortByKind(content)
      ? ContentChoice(
          personal: true,
          reasons: withPreferredReason(content, [ContentReason.kindSorting]),
        )
      : const ContentChoice.generic([
          ContentReason.genericFallback,
          ContentReason.notEnoughPhotos,
        ]);

  @override
  List<RoundSpec> createRounds({
    required ActivityContent content,
    required int difficulty,
    required Random random,
    required AppStrings strings,
    LevelParams level = const LevelParams(),
  }) {
    if (canSortByKind(content)) {
      return _personalRounds(content, difficulty, random, strings, level);
    }
    // Bundled default: two groups at difficulty 1, otherwise three.
    final groupCount = (level.intOf('groups') ?? (difficulty <= 1 ? 2 : 3))
        .clamp(2, everydayCategories.length);
    final groups = (everydayCategories.keys.toList()..shuffle(random))
        .take(groupCount)
        .toList();
    final items =
        (everydayThings.where((t) => groups.contains(t.category)).toList()
              ..shuffle(random))
            .take(
              level.intOf('items') ?? CognitiveActivity.roundCount(difficulty),
            );
    return [
      for (final item in items)
        ChoiceRoundSpec(
          prompt: strings.t('game_sort_q', {'item': item.label}),
          promptIcon: item.icon,
          correctId: item.category,
          options: [
            for (final g in groups)
              ChoiceOption(id: g, label: everydayCategories[g]!),
          ],
        ),
    ];
  }

  /// "Is this a person or a place?" for the family's own photos, by the type
  /// the caregiver chose. Groups and photos come only from approved memories.
  List<RoundSpec> _personalRounds(
    ActivityContent content,
    int difficulty,
    Random random,
    AppStrings strings,
    LevelParams level,
  ) {
    final kinds = sortableKinds(content);
    final groupCount = (level.intOf('groups') ?? (difficulty <= 1 ? 2 : 3))
        .clamp(MemoryRules.minSortKinds, kinds.length);
    final groups = shuffled(kinds.keys, random).take(groupCount).toList();
    final photos = [for (final g in groups) ...kinds[g]!];
    final count = min(
      level.intOf('items') ?? CognitiveActivity.roundCount(difficulty),
      photos.length,
    );
    return [
      for (final m in content.pickPreferred(photos, count, random))
        ChoiceRoundSpec(
          prompt: strings.t('game_sort_memory_q'),
          promptImagePath: m.localPhotoPath,
          promptImageLabel: strings.t('game_memory_photo'),
          correctId: m.kind,
          memoryId: m.id,
          options: [
            for (final g in groups)
              ChoiceOption(id: g, label: strings.t('memory_kind_$g')),
          ],
        ),
    ];
  }
}

/// Routine sequencing: put the steps of an everyday task in order. When the
/// family has set up at least three routines for today, one round uses them.
class DailySequenceActivity extends CognitiveActivity {
  const DailySequenceActivity({this.today});

  /// For tests; defaults to the phone's current day.
  final DateTime? today;

  @override
  String get slug => 'daily-sequence';

  @override
  IconData get icon => Icons.format_list_numbered;

  @override
  List<RoundSpec> createRounds({
    required ActivityContent content,
    required int difficulty,
    required Random random,
    required AppStrings strings,
    LevelParams level = const LevelParams(),
  }) {
    // Bundled default: 3 steps at difficulty 1, otherwise 4.
    final stepCount = (level.intOf('steps') ?? (difficulty <= 1 ? 3 : 4)).clamp(
      3,
      maxTaskSteps,
    );
    final day = today ?? DateTime.now();
    final todays = content.routines.where((r) => r.occursOn(day)).toList()
      ..sort((a, b) => a.localTime.compareTo(b.localTime));
    final rounds = <RoundSpec>[];
    if (todays.length >= 3) {
      final steps = todays.take(stepCount).map((r) => r.title).toSet().toList();
      if (steps.length >= 3) {
        rounds.add(
          SequenceRoundSpec(
            task: strings.t('game_sequence_today'),
            steps: steps,
            shuffled: [...steps]..shuffle(random),
          ),
        );
      }
    }
    final tasks = [...everydayTasks]..shuffle(random);
    final wanted = (CognitiveActivity.roundCount(difficulty) - 1).clamp(2, 4);
    for (final task in tasks.take(wanted - rounds.length + 1)) {
      final steps = task.steps.take(stepCount).toList();
      var shuffled = [...steps]..shuffle(random);
      // Never present the steps already in the right order.
      while (_sameOrder(shuffled, steps)) {
        shuffled = [...steps]..shuffle(random);
      }
      rounds.add(
        SequenceRoundSpec(task: task.title, steps: steps, shuffled: shuffled),
      );
    }
    return rounds;
  }

  static bool _sameOrder(List<String> a, List<String> b) {
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }
}

/// Picture matching: find pairs of matching everyday pictures.
class PicturePairsActivity extends CognitiveActivity {
  const PicturePairsActivity();

  @override
  String get slug => 'picture-pairs';

  @override
  IconData get icon => Icons.grid_view;

  /// Pairs on the board by difficulty 1..5.
  static int pairsFor(int difficulty) => (2 + difficulty).clamp(3, 6);

  @override
  ContentChoice contentChoice(ActivityContent content) => canPairPhotos(content)
      ? ContentChoice(
          personal: true,
          reasons: withPreferredReason(content, [ContentReason.personalPhotos]),
        )
      : const ContentChoice.generic([
          ContentReason.genericFallback,
          ContentReason.notEnoughPhotos,
        ]);

  @override
  List<RoundSpec> createRounds({
    required ActivityContent content,
    required int difficulty,
    required Random random,
    required AppStrings strings,
    LevelParams level = const LevelParams(),
  }) {
    final boards = difficulty <= 2 ? 2 : 3;
    final pairs = level.intOf('pairs') ?? pairsFor(difficulty);
    if (canPairPhotos(content)) {
      // The family's own photos as the pictures (fewer pairs if fewer photos).
      final photos = distinctPhotoMemories(content);
      return [
        for (var b = 0; b < boards; b++)
          PairsRoundSpec([
            for (final m in content.pickPreferred(
              photos,
              pairs.clamp(2, photos.length),
              random,
            ))
              PairCard(
                m.id,
                m.title,
                Icons.photo,
                imagePath: m.localPhotoPath,
                memoryId: m.id,
              ),
          ], random),
      ];
    }
    return [
      for (var b = 0; b < boards; b++)
        PairsRoundSpec(
          ([...everydayThings]..shuffle(random))
              .take(
                (level.intOf('pairs') ?? pairsFor(difficulty)).clamp(
                  2,
                  everydayThings.length,
                ),
              )
              .map((t) => PairCard(t.id, t.label, t.icon))
              .toList(),
          random,
        ),
    ];
  }
}
