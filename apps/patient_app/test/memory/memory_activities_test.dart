// Memory-based activities: approved, cached memories become activity content
// by published rules; nothing is invented; use is recorded. SYNTHETIC data.
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/activities/activity.dart';
import 'package:sneha_patient/activities/games/everyday_games.dart';
import 'package:sneha_patient/activities/games/memory_games.dart';
import 'package:sneha_patient/activities/memory_content.dart';
import 'package:sneha_patient/activities/rounds/choice_round.dart';
import 'package:sneha_patient/activities/rounds/pairs_round.dart';
import 'package:sneha_patient/data/api/models.dart';
import 'package:sneha_patient/features/memories/story_time_screen.dart';
import 'package:sneha_patient/l10n/strings.dart';

import '../data/sync_service_test.dart' show change;
import '../helpers.dart';

final s = AppStrings('en');

MemoryItem mem(
  String id,
  String kind, {
  String? title,
  bool photo = true,
  String? relationship,
  String? description,
  int? year,
}) => MemoryItem(
  id: id,
  patientId: patientId,
  kind: kind,
  title: title ?? 'Synthetic $id',
  description: description,
  approxYear: year,
  relationship: relationship,
  localPhotoPath: photo ? '/cache/$id.png' : null,
  mediaFileId: 'f-$id',
);

List<RoundSpec> build(
  CognitiveActivity a,
  ActivityContent c, {
  int seed = 7,
  int difficulty = 1,
}) => a.createRounds(
  content: c,
  difficulty: difficulty,
  random: Random(seed),
  strings: s,
);

void main() {
  group('rules (pure)', () {
    test('different approved memories produce different content', () {
      final garden = ActivityContent(
        memories: [
          mem('g1', 'place', title: 'Synthetic flower garden'),
          mem('g2', 'place', title: 'Synthetic river bank'),
          mem('g3', 'event', title: 'Synthetic Bihu'),
        ],
      );
      final family = ActivityContent(
        memories: [
          mem('p1', 'person', title: 'Synthetic Mina'),
          mem('p2', 'person', title: 'Synthetic Bijoy'),
        ],
      );
      String labels(ActivityContent c) => [
        for (final r in build(
          const PhotoRecallActivity(),
          c,
        ).cast<ChoiceRoundSpec>())
          ...r.options.map((o) => o.label),
      ].join(',');
      expect(labels(garden), contains('Synthetic flower garden'));
      expect(labels(garden), isNot(contains('Synthetic Mina')));
      expect(labels(family), contains('Synthetic Mina'));
      // Every round names the memory it shows.
      for (final r in build(const PhotoRecallActivity(), garden)) {
        expect(r.memoryIds, hasLength(1));
        expect({'g1', 'g2', 'g3'}, contains(r.memoryIds.single));
      }
    });

    test('photos that are not on this phone are never used', () {
      final c = ActivityContent(
        memories: [
          mem('a', 'place'),
          mem('b', 'place', photo: false),
          mem('c', 'person', photo: false),
        ],
      );
      expect(
        const PhotoRecallActivity().unavailableReason(c),
        'activities_needs_memories',
      );
      final pairs = const PicturePairsActivity();
      expect(pairs.contentChoice(c).personal, isFalse);
      expect(
        pairs.contentChoice(c).reasons,
        containsAll([
          ContentReason.genericFallback,
          ContentReason.notEnoughPhotos,
        ]),
      );
      final round = build(pairs, c).first as PairsRoundSpec;
      expect(round.symbols.every((card) => card.imagePath == null), isTrue);
      expect(round.memoryIds, isEmpty);
    });

    test('enough cached photos turn picture pairs into family photos', () {
      final c = ActivityContent(
        memories: [
          for (final id in ['a', 'b', 'c', 'd']) mem(id, 'place'),
        ],
        preferredMemoryIds: const ['d'],
      );
      final choice = const PicturePairsActivity().contentChoice(c);
      expect(choice.personal, isTrue);
      expect(choice.reasons, [
        ContentReason.personalPhotos,
        ContentReason.enginePreferred,
      ]);
      final round =
          build(const PicturePairsActivity(), c).first as PairsRoundSpec;
      expect(round.symbols.first.memoryId, 'd', reason: 'engine choice first');
      expect(round.symbols.every((card) => card.imagePath != null), isTrue);
    });

    test(
      'sorting uses the caregiver-chosen type, only with enough of each',
      () {
        final thin = ActivityContent(
          memories: [
            mem('p1', 'person'),
            mem('p2', 'person'),
            mem('l1', 'place'),
          ],
        );
        expect(
          const SortIntoGroupsActivity().contentChoice(thin).personal,
          isFalse,
        );
        expect(
          (build(const SortIntoGroupsActivity(), thin).first as ChoiceRoundSpec)
              .memoryId,
          isNull,
          reason: 'everyday content',
        );

        final rich = ActivityContent(
          memories: [
            mem('p1', 'person'),
            mem('p2', 'person'),
            mem('l1', 'place'),
            mem('l2', 'place'),
            mem('s1', 'story'), // stories are never a sorting group
            mem('s2', 'story'),
          ],
        );
        expect(
          const SortIntoGroupsActivity().contentChoice(rich).personal,
          isTrue,
        );
        final rounds = build(
          const SortIntoGroupsActivity(),
          rich,
        ).cast<ChoiceRoundSpec>();
        final byId = {for (final m in rich.memories) m.id: m};
        for (final r in rounds) {
          expect(r.correctId, byId[r.memoryId]!.kind);
          expect(r.options.map((o) => o.id).toSet(), {'person', 'place'});
          expect(r.promptImagePath, byId[r.memoryId]!.localPhotoPath);
        }
      },
    );

    test(
      'familiar faces gives a relationship hint only when one was entered',
      () {
        final c = ActivityContent(
          memories: [
            mem(
              'p1',
              'person',
              title: 'Synthetic Mina',
              relationship: 'granddaughter',
            ),
            mem('p2', 'person', title: 'Synthetic Bijoy'),
          ],
        );
        final rounds = build(
          const FamiliarFacesActivity(),
          c,
        ).cast<ChoiceRoundSpec>();
        for (final r in rounds) {
          if (r.memoryId == 'p1') {
            expect(r.extraHint, 'Synthetic Mina is your granddaughter.');
          } else {
            expect(r.extraHint, isNull, reason: 'never guessed');
          }
        }
        expect(
          const FamiliarFacesActivity().contentChoice(c).reasons,
          contains(ContentReason.relationshipHint),
        );
      },
    );

    test(
      'story prompts use only approved fields and links; missing fields add nothing',
      () {
        final mina = mem(
          'p1',
          'person',
          title: 'Synthetic Mina',
          relationship: 'granddaughter',
        );
        final bijoy = mem('p2', 'person', title: 'Synthetic Bijoy');
        final bihu = mem('e1', 'event', title: 'Synthetic Bihu');
        final garden = mem(
          'l1',
          'place',
          title: 'Synthetic garden',
          photo: false,
        );
        final story = mem('s1', 'story', title: 'Synthetic old story');
        final c = ActivityContent(
          memories: [mina, bijoy, bihu, garden, story],
          links: const [
            MemoryLinkFact(fromId: 'p1', toId: 'e1', type: 'person_in'),
            MemoryLinkFact(fromId: 'e1', toId: 'l1', type: 'located_at'),
          ],
        );
        expect(
          guidedStoryPrompt(mina, c, s),
          'This is Synthetic Mina, your granddaughter. What do you remember about them?',
        );
        final b = guidedStoryPrompt(bijoy, c, s)!;
        expect(b, 'This is Synthetic Bijoy. What do you remember about them?');
        expect(b, isNot(contains('your')), reason: 'no invented relationship');
        expect(
          guidedStoryPrompt(bihu, c, s),
          'Synthetic Mina was there too. This was at Synthetic garden. '
          'This is Synthetic Bihu. What do you remember about that day?',
        );
        expect(
          guidedStoryPrompt(story, c, s),
          isNull,
          reason: 'general prompt instead',
        );
      },
    );

    test('story order: the engine choice first, then by title', () {
      final c = ActivityContent(
        memories: [
          mem('b', 'place', title: 'B'),
          mem('a', 'place', title: 'A'),
          mem('c', 'place', title: 'C'),
        ],
        preferredMemoryIds: const ['c', 'unknown-id'],
      );
      expect(storyOrder(c).map((m) => m.id), ['c', 'a', 'b']);
    });
  });

  group('on the phone', () {
    late Harness h;
    setUp(() async {
      h = await Harness.create();
      await h.pairAndOnboard();
    });
    tearDown(() => h.dispose());

    test(
      'sync stores the relationship and links, and refuses unapproved or foreign memories',
      () async {
        Map<String, dynamic> m(
          String id, {
          String status = 'approved',
          String pid = patientId,
        }) => {
          'id': id,
          'patient_id': pid,
          'kind': 'person',
          'title': 'Synthetic $id',
          'description': null,
          'approx_year': null,
          'relationship': 'granddaughter',
          'tags': [],
          'media_file_id': null,
          'status': status,
          'source': 'dashboard',
          'version': 1,
        };
        const a = '71111111-1111-4111-8111-111111111111';
        const b = '72222222-2222-4222-8222-222222222222';
        const c = '73333333-3333-4333-8333-333333333333';
        h.server.pullPages.add({
          'changes': [
            change(1, 'memory_item', a, m(a)),
            change(2, 'memory_item', b, m(b, status: 'pending_approval')),
            change(
              3,
              'memory_item',
              c,
              m(c, pid: '99999999-9999-4999-8999-999999999999'),
            ),
            change(4, 'memory_relationship', 'link-1', {
              'id': 'link-1',
              'from_memory_id': a,
              'to_memory_id': a,
              'relation_type': 'related_to',
            }),
          ],
          'next_since': 4,
          'has_more': false,
        });
        await h.services.sync.syncProfile(patientId);
        final stored = await h.services.content.memories(patientId);
        expect(stored.map((x) => x.id), [a]);
        expect(stored.single.relationship, 'granddaughter');
        expect(await h.services.content.memoryLinks(patientId), hasLength(1));
      },
    );
  });

  group('recording', () {
    Future<void> seed(Harness h, {int photos = 3}) async {
      final dir = Directory.systemTemp.createTempSync('sneha_mem').path;
      for (var i = 0; i < photos; i++) {
        final path = '$dir/p$i.png';
        File(path).writeAsBytesSync(
          base64Decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==',
          ),
        );
        await h.local.db.insert('memories', {
          'id': 'mem-$i',
          'patient_id': patientId,
          'kind': i.isEven ? 'place' : 'person',
          'title': 'Synthetic memory $i',
          'description': i == 0 ? 'Synthetic: where flowers grow.' : null,
          'approx_year': null,
          'relationship': i == 1 ? 'granddaughter' : null,
          'tags_json': '[]',
          'media_file_id': 'f-$i',
          'version': 1,
          'local_photo_path': path,
        });
      }
    }

    Future<List<Map<String, dynamic>>> events(WidgetTester t, Harness h) =>
        real(
          t,
          () async => [
            for (final r in await h.outbox())
              if (r['entity_type'] == 'activity_event')
                jsonDecode(r['payload_json'] as String) as Map<String, dynamic>,
          ],
        );

    testWidgets('a photo-recall run records the memories it used, per round', (
      tester,
    ) async {
      final h = await pairedHarness(tester);
      addTearDown(h.dispose);
      await real(tester, () => seed(h));
      await tester.pumpWidget(h.app());
      await settle(tester);
      await tapVisible(tester, find.text('Play an activity'));
      await tapVisible(tester, find.text('Start Synthetic photo-recall'));
      // Any first answer.
      final round = find.byWidgetPredicate(
        (w) =>
            w.key is ValueKey &&
            '${(w.key! as ValueKey).value}'.startsWith('round_'),
      );
      await tapVisible(
        tester,
        find.descendant(of: round, matching: find.byType(OutlinedButton)).first,
      );
      final log = await events(tester, h);
      final start = log.firstWhere(
        (e) => e['event_type'] == 'activity_started',
      );
      expect(start['data']['content_source'], 'personal');
      expect(start['data']['reason_codes'], contains('PERSONAL_PHOTOS_USED'));
      final used = (start['data']['memory_ids'] as List).cast<String>();
      expect(used, isNotEmpty);
      expect(used.every((id) => id.startsWith('mem-')), isTrue);
      final attempt = log.firstWhere((e) => e['event_type'] == 'attempt');
      expect(used, contains(attempt['data']['memory_id']));
    });

    testWidgets(
      'story time shows a guided prompt and records each memory viewed',
      (tester) async {
        final h = await pairedHarness(tester);
        addTearDown(h.dispose);
        await real(tester, () => seed(h, photos: 2));
        final profile = await real(
          tester,
          () => h.services.profiles.get(patientId),
        );
        await tester.pumpWidget(h.app());
        await settle(tester);
        final nav = tester.state<NavigatorState>(find.byType(Navigator).first);
        nav.push(
          MaterialPageRoute<void>(
            builder: (_) => StoryTimeScreen(
              profile: profile!,
              preferredMemoryIds: const ['mem-1'],
            ),
          ),
        );
        await settle(tester);
        // The engine's memory first, with the caregiver's relationship.
        expect(
          find.text(
            'This is Synthetic memory 1, your granddaughter. What do you remember about them?',
          ),
          findsOneWidget,
        );
        await tapVisible(tester, find.text('Next memory'));
        expect(find.text('Synthetic: where flowers grow.'), findsOneWidget);
        await tapVisible(tester, find.text('Finish'));
        final log = await events(tester, h);
        expect(log.first['event_type'], 'activity_started');
        expect(log.first['data']['memory_ids'], ['mem-1', 'mem-0']);
        expect(log.first['data']['reason_codes'], [
          'GUIDED_STORY_FROM_APPROVED_FIELDS',
          'ENGINE_PREFERRED_MEMORIES_FIRST',
        ]);
        final viewed = [
          for (final e in log)
            if (e['event_type'] == 'round_solved') e['data']['memory_id'],
        ];
        expect(viewed, ['mem-1', 'mem-0']);
        expect(log.last['event_type'], 'activity_ended');
      },
    );
  });
}
