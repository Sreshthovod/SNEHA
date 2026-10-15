// Stage 7: conversation online flow and a full patient session end to end.
// All data is SYNTHETIC.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';

Map<String, dynamic> memoryJson(String id, String title) => {
  'id': id,
  'patient_id': patientId,
  'kind': 'place',
  'title': title,
  'description': null,
  'approx_year': null,
  'tags': ['tea'],
  'media_file_id': null,
  'status': 'approved',
  'source': 'dashboard',
  'version': 1,
  'created_by_id': null,
  'reviewed_by_id': null,
  'reviewed_at': null,
  'review_note': null,
  'created_at': '2026-10-01T00:00:00Z',
  'updated_at': '2026-10-01T00:00:00Z',
};

Future<void> openTalk(WidgetTester tester, Harness h) async {
  await tester.pumpWidget(h.app());
  await settle(tester);
  await tapVisible(tester, find.text('Talk with the helper'));
  await settle(tester);
}

Future<void> say(WidgetTester tester, String text) async {
  await tester.enterText(find.byType(TextField), text);
  await tester.tap(find.text('Send'));
  await settle(tester);
}

Future<void> scrollTo(WidgetTester tester, Finder f) => tester
    .scrollUntilVisible(f, 150, scrollable: find.byType(Scrollable).first);

void main() {
  testWidgets('online: safe reply, approved memory, suggestion Start launches '
      'the right activity at the right difficulty', (tester) async {
    final server = FakeServer()
      ..onAnalyze = (_) => analyzeJson(
        reply: 'Synthetic: tea gardens are lovely.',
        memories: [
          memoryJson(
            '55555555-5555-4555-8555-555555555555',
            'Synthetic tea garden',
          ),
        ],
        suggestion: recommendationJson(id: 'rec-talk', difficulty: 2),
      );
    final h = await pairedHarness(tester, server: server);
    addTearDown(h.dispose);
    await openTalk(tester, h);
    await say(tester, 'I used to work in the tea garden');

    final sent = server.analyzeRequests.single;
    expect(sent['text'], 'I used to work in the tea garden');
    expect(sent['patient_id'], patientId);
    expect(sent['conversation_id'], isNotNull);
    expect(sent['available_slugs'], contains('name-the-object'));

    expect(find.text('Synthetic: tea gardens are lovely.'), findsOneWidget);
    await scrollTo(tester, find.text('Answered with help from SNEHA'));
    expect(find.text('Answered with help from SNEHA'), findsOneWidget);
    await scrollTo(tester, find.text('Synthetic tea garden'));
    expect(find.text('Memories your family added'), findsOneWidget);

    final start = find.byKey(const ValueKey('talk_suggest_start'));
    await scrollTo(tester, start);
    await tapVisible(tester, start);
    await settle(tester);
    // name-the-object at difficulty 2 with bundled defaults → 4 questions.
    expect(find.text('Synthetic name-the-object'), findsWidgets);
    expect(find.text('1 of 4'), findsOneWidget);
  });

  testWidgets('memory candidates are only sent as proposals, on request', (
    tester,
  ) async {
    final server = FakeServer()
      ..onAnalyze = (_) => analyzeJson(
        candidates: [
          {
            'title': 'Synthetic picnic by the river',
            'kind': 'event',
            'description': 'Synthetic.',
            'requires_approval': true,
            'note': 'Not saved.',
          },
        ],
      );
    final h = await pairedHarness(tester, server: server);
    addTearDown(h.dispose);
    await openTalk(tester, h);
    await say(tester, 'We had a picnic by the river');

    final save = find.text('Save for my family to check');
    await scrollTo(tester, save);
    expect(find.text('Synthetic picnic by the river'), findsOneWidget);
    expect(server.memoryProposals, isEmpty); // nothing saved automatically
    await tapVisible(tester, save);
    expect(
      server.memoryProposals.single['title'],
      'Synthetic picnic by the river',
    );
    expect(server.memoryProposals.single['kind'], 'event');
    await scrollTo(
      tester,
      find.text('Sent. Your family will check this first.'),
    );
    expect(
      find.text('Sent. Your family will check this first.'),
      findsOneWidget,
    );
  });

  testWidgets('distress: safety message and no activity', (tester) async {
    final server = FakeServer()
      ..onAnalyze = (_) => analyzeJson(
        distress: true,
        reply: 'Synthetic calm reply.',
        suggestion: recommendationJson(),
      );
    final h = await pairedHarness(tester, server: server);
    addTearDown(h.dispose);
    await openTalk(tester, h);
    await say(tester, 'I feel very frightened');
    await scrollTo(tester, find.textContaining('Synthetic safety message'));
    expect(find.textContaining('Synthetic safety message'), findsOneWidget);
    expect(find.byKey(const ValueKey('talk_suggest_start')), findsNothing);

    // One conversation id per screen visit, reused for every message.
    await say(tester, 'still frightened');
    final ids = server.analyzeRequests.map((r) => r['conversation_id']).toSet();
    expect(server.analyzeRequests, hasLength(2));
    expect(ids, hasLength(1));
  });

  testWidgets('server problem: the phone helper answers, no raw output', (
    tester,
  ) async {
    final server = FakeServer()..analyzeStatus = 500;
    final h = await pairedHarness(tester, server: server);
    addTearDown(h.dispose);
    await openTalk(tester, h);
    await say(tester, 'hello');
    expect(find.textContaining('Namaste'), findsOneWidget);
    await scrollTo(tester, find.text('Answered on this phone (simple helper)'));
    expect(find.text('Answered on this phone (simple helper)'), findsOneWidget);
    expect(find.textContaining('provider_error'), findsNothing);
  });

  testWidgets('E2E patient session: server suggestion → play with catalog '
      'levels → result shared by sync → next suggestion updated', (
    tester,
  ) async {
    final server = FakeServer()
      ..catalogSpecs = [
        specJson(objectId, 'name-the-object', {
          1: {'options': 2, 'questions': 3},
          2: {'options': 3, 'questions': 5},
          3: {'options': 4, 'questions': 6},
        }, instructions: 'Synthetic: choose the name.'),
      ];
    var issued = 0;
    server.onNext = (_) {
      // Like the real engine: results already shared raise the level.
      final played = server.stored['activity_result']?.length ?? 0;
      issued++;
      return recommendationJson(id: 'rec-$issued', difficulty: 1 + played);
    };
    final h = await pairedHarness(tester, server: server);
    addTearDown(h.dispose);
    await tester.pumpWidget(h.app());
    await settle(tester, rounds: 20);

    expect(find.text('Chosen for you'), findsOneWidget);
    final lastBefore = 'rec-$issued';
    await tapVisible(tester, find.text('Start'));
    await settle(tester);

    // Catalog spec: instructions shown, level 1 → 3 questions.
    expect(find.text('Synthetic: choose the name.'), findsOneWidget);
    expect(find.text('1 of 3'), findsOneWidget);
    for (var i = 0; i < 3; i++) {
      await tapVisible(tester, find.text('Skip'));
    }
    await tapVisible(tester, find.text('Skip this question'));
    await tapVisible(tester, find.text('Go home'));
    await settle(tester, rounds: 20);

    // Shared through the single idempotent path (outbox → sync).
    final results = server.pushedMutations
        .where((m) => m['entity_type'] == 'activity_result')
        .toList();
    expect(results, hasLength(1));
    expect((results.single['data'] as Map)['recommendation_id'], lastBefore);
    expect(await real(tester, h.outbox), isEmpty);

    // The next suggestion came from the server AFTER the result was shared.
    final rec = await real(
      tester,
      () => h.services.recommendations.next(patientId),
    );
    expect(rec.chosenOnDevice, isFalse);
    expect(rec.difficulty, 2);
    await tapVisible(tester, find.text('Start'));
    await settle(tester);
    expect(find.text('1 of 5'), findsOneWidget); // level 2 from the catalog
  });
}
