// Stage 7: server recommendations with local fallback, catalog specs.
// All data is SYNTHETIC.
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/activities/activity.dart';
import 'package:sneha_patient/activities/games/everyday_games.dart';
import 'package:sneha_patient/activities/rounds/pairs_round.dart';
import 'package:sneha_patient/activities/rounds/sequence_round.dart';
import 'package:sneha_patient/l10n/strings.dart';
import 'package:sneha_patient/personalization/engine.dart';

import '../helpers.dart';

void main() {
  test('online: the server engine is used, labelled, and told what this '
      'phone can play', () async {
    final h = await Harness.create();
    addTearDown(h.dispose);
    await h.pairAndOnboard();
    h.server.onNext = (_) => recommendationJson(id: 'rec-online');

    final s = await h.services.recommendations.next(
      patientId,
      fatigueReported: true,
    );
    expect(s.chosenOnDevice, isFalse);
    expect(s.recommendationId, 'rec-online');
    expect(s.activityId, objectId);
    expect(s.difficulty, 2);

    final body = h.server.nextRequests.single;
    expect(body['fatigue_reported'], isTrue);
    final slugs = (body['available_slugs'] as List).cast<String>();
    // Registered games are offered; Memory Bank activities without approved
    // photos/memories on THIS phone are not.
    expect(slugs, containsAll(['picture-pairs', 'name-the-object']));
    expect(slugs, isNot(contains('photo-recall')));
    expect(slugs, isNot(contains('story-time')));
    expect(slugs, isNot(contains('word-partners'))); // not playable yet
  });

  test('offline or server error: the phone engine answers', () async {
    final h = await Harness.create();
    addTearDown(h.dispose);
    await h.pairAndOnboard();

    h.server.online = false;
    final offline = await h.services.recommendations.next(patientId);
    expect(offline.chosenOnDevice, isTrue);
    expect(offline.recommendationId, isNull);
    expect(offline.action, EngineAction.activity);

    h.server.online = true; // no handler → 404 from an older server
    final older = await h.services.recommendations.next(patientId);
    expect(older.chosenOnDevice, isTrue);
  });

  test('a suggestion this phone cannot play falls back to the phone', () async {
    final h = await Harness.create();
    addTearDown(h.dispose);
    await h.pairAndOnboard();
    h.server.onNext = (_) => recommendationJson(
      activityId: '4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0006',
      slug: 'photo-recall',
    );
    final s = await h.services.recommendations.next(patientId);
    expect(s.chosenOnDevice, isTrue);
  });

  test('malformed server response is never trusted', () async {
    final h = await Harness.create();
    addTearDown(h.dispose);
    await h.pairAndOnboard();
    h.server.onNext = (_) => {'action': 'activity'}; // missing required fields
    final s = await h.services.recommendations.next(patientId);
    expect(s.chosenOnDevice, isTrue);
  });

  test('stop request from the server means no activity', () async {
    final h = await Harness.create();
    addTearDown(h.dispose);
    await h.pairAndOnboard();
    h.server.onNext = (_) => recommendationJson(
      action: 'stop',
      activityId: null,
      slug: null,
      difficulty: null,
      reasons: ['STOP_REQUESTED'],
    );
    final s = await h.services.recommendations.next(
      patientId,
      stopRequested: true,
    );
    expect(s.action, EngineAction.stop);
    expect(s.activityId, isNull);
    expect(h.server.nextRequests.single['stop_requested'], isTrue);
  });

  test('sync caches catalog specs; they drive level parameters', () async {
    final h = await Harness.create();
    addTearDown(h.dispose);
    await h.pairAndOnboard();
    h.server.catalogSpecs = [
      specJson(pairsId, 'picture-pairs', {
        1: {'pairs': 5},
        2: {'pairs': 6},
      }, instructions: 'Synthetic: find the pairs.'),
    ];
    await h.services.sync.syncProfile(patientId);

    final rows = await h.local.db.query('catalog_specs');
    expect(rows.single['slug'], 'picture-pairs');
    final spec = await h.services.content.spec(pairsId);
    expect(spec!.instructions, 'Synthetic: find the pairs.');
    expect(spec.levels[2], {'pairs': 6});
    expect(await h.services.content.spec(objectId), isNull);

    final fromSpec = const PicturePairsActivity().createRounds(
      content: const ActivityContent(),
      difficulty: 1,
      random: Random(1),
      strings: AppStrings('en'),
      level: LevelParams.of(spec, 1),
    );
    expect((fromSpec.first as PairsRoundSpec).symbols.length, 5);

    // Bundled default (no spec yet) is unchanged.
    final bundled = const PicturePairsActivity().createRounds(
      content: const ActivityContent(),
      difficulty: 1,
      random: Random(1),
      strings: AppStrings('en'),
    );
    expect(
      (bundled.first as PairsRoundSpec).symbols.length,
      PicturePairsActivity.pairsFor(1),
    );
  });

  test('catalog "steps", "groups/items" and "questions/options" levels are '
      'honoured', () {
    final s = AppStrings('en');
    final seq = const DailySequenceActivity().createRounds(
      content: const ActivityContent(),
      difficulty: 5,
      random: Random(3),
      strings: s,
      level: const LevelParams({'steps': 7}),
    );
    expect((seq.first as SequenceRoundSpec).steps.length, 7);

    final sort = const SortIntoGroupsActivity().createRounds(
      content: const ActivityContent(),
      difficulty: 3,
      random: Random(3),
      strings: s,
      level: const LevelParams({'groups': 3, 'items': 8}),
    );
    expect(sort.length, 8);

    final names = const NameTheObjectActivity().createRounds(
      content: const ActivityContent(),
      difficulty: 1,
      random: Random(3),
      strings: s,
      level: const LevelParams({'options': 2, 'questions': 4}),
    );
    expect(names.length, 4);
  });

  test('invalid level values fall back to bundled defaults', () {
    const level = LevelParams({'pairs': 0, 'options': 'three'});
    expect(level.intOf('pairs'), isNull);
    expect(level.intOf('options'), isNull);
    expect(const LevelParams().fromCatalog, isFalse);
  });
}
