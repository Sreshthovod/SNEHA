import 'dart:math';

import 'package:flutter/material.dart';

import '../../data/api/models.dart';
import '../../l10n/strings.dart';
import '../activity.dart';
import '../rounds/choice_round.dart';

List<T> _pick<T>(List<T> items, int n, Random rng) =>
    ([...items]..shuffle(rng)).take(n).toList();

/// Photo recall: show an approved memory photo, choose what it shows.
class PhotoRecallActivity extends CognitiveActivity {
  const PhotoRecallActivity();

  @override
  String get slug => 'photo-recall';

  @override
  IconData get icon => Icons.photo_library;

  @override
  bool get usesMemoryBank => true;

  List<MemoryItem> _usable(ActivityContent c) {
    final byTitle = <String, MemoryItem>{};
    for (final m in c.withPhotos) {
      byTitle.putIfAbsent(m.title.toLowerCase(), () => m);
    }
    return byTitle.values.toList();
  }

  @override
  String? unavailableReason(ActivityContent content) =>
      _usable(content).length < 2 ? 'activities_needs_memories' : null;

  @override
  List<RoundSpec> createRounds({
    required ActivityContent content,
    required int difficulty,
    required Random random,
    required AppStrings strings,
    LevelParams level = const LevelParams(),
  }) {
    final memories = _usable(content);
    final rounds = min(
      level.intOf('questions') ?? CognitiveActivity.roundCount(difficulty),
      memories.length,
    );
    final nOptions = min(
      level.intOf('options') ?? CognitiveActivity.optionCount(difficulty),
      memories.length,
    );
    return [
      for (final target in _pick(memories, rounds, random))
        ChoiceRoundSpec(
          prompt: strings.t('game_photo_recall_q'),
          promptImagePath: target.localPhotoPath,
          promptImageLabel: strings.t('game_memory_photo'),
          correctId: target.id,
          extraHint: target.approxYear == null
              ? null
              : strings.t('hint_year', {'year': target.approxYear!}),
          options:
              ([
                    target,
                    ..._pick(
                      memories.where((m) => m.id != target.id).toList(),
                      nOptions - 1,
                      random,
                    ),
                  ]..shuffle(random))
                  .map((m) => ChoiceOption(id: m.id, label: m.title))
                  .toList(),
        ),
    ];
  }
}

/// Familiar faces: given a name, choose the photo of that person.
class FamiliarFacesActivity extends CognitiveActivity {
  const FamiliarFacesActivity();

  @override
  String get slug => 'familiar-faces';

  @override
  IconData get icon => Icons.face;

  @override
  bool get usesMemoryBank => true;

  List<MemoryItem> _people(ActivityContent c) =>
      c.withPhotos.where((m) => m.kind == 'person').toList();

  @override
  String? unavailableReason(ActivityContent content) =>
      _people(content).length < 2 ? 'activities_needs_memories' : null;

  @override
  List<RoundSpec> createRounds({
    required ActivityContent content,
    required int difficulty,
    required Random random,
    required AppStrings strings,
    LevelParams level = const LevelParams(),
  }) {
    final people = _people(content);
    final rounds = min(
      level.intOf('questions') ?? CognitiveActivity.roundCount(difficulty),
      people.length,
    );
    final nOptions = min(
      level.intOf('options') ?? CognitiveActivity.optionCount(difficulty),
      people.length,
    );
    return [
      for (final target in _pick(people, rounds, random))
        () {
          final options = [
            target,
            ..._pick(
              people.where((m) => m.id != target.id).toList(),
              nOptions - 1,
              random,
            ),
          ]..shuffle(random);
          return ChoiceRoundSpec(
            prompt: strings.t('game_faces_q', {'name': target.title}),
            promptIcon: Icons.person,
            correctId: target.id,
            options: [
              for (var i = 0; i < options.length; i++)
                ChoiceOption(
                  id: options[i].id,
                  // Screen-reader label must not give the answer away.
                  label: strings.t('game_photo_option', {'number': i + 1}),
                  imagePath: options[i].localPhotoPath,
                ),
            ],
          );
        }(),
    ];
  }
}
