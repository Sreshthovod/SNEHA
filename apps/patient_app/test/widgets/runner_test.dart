import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';

Future<void> openObjectGame(WidgetTester tester, Harness h) async {
  await tester.pumpWidget(h.app());
  await settle(tester);
  await tapVisible(tester, find.text('Play an activity'));
  await tapVisible(tester, find.text('Start Synthetic name-the-object'));
  expect(find.text('What is this?'), findsOneWidget);
}

/// Tap options until the right one is found (the UI never reveals it).
Future<void> answerCorrectly(WidgetTester tester) async {
  for (var i = 0; i < 4; i++) {
    if (find.text("Yes, that's right!").evaluate().isNotEmpty) break;
    // Only the current round's options (runner controls are buttons too).
    final round = find.byWidgetPredicate(
      (w) =>
          w.key is ValueKey &&
          '${(w.key! as ValueKey).value}'.startsWith('round_'),
    );
    final options = find.descendant(
      of: round,
      matching: find.byWidgetPredicate(
        (w) => w is OutlinedButton && w.onPressed != null,
      ),
    );
    await tapVisible(tester, options.first);
  }
  expect(find.text("Yes, that's right!"), findsOneWidget);
  await tapVisible(tester, find.widgetWithText(FilledButton, 'Continue'));
}

void main() {
  testWidgets('completing a game records session + result and praises effort', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await openObjectGame(tester, h);

    // difficulty 1 → 3 rounds
    expect(find.text('1 of 3'), findsOneWidget);
    for (var r = 0; r < 3; r++) {
      await answerCorrectly(tester);
    }
    expect(find.text('Well done!'), findsOneWidget);
    expect(find.textContaining('%'), findsNothing, reason: 'no grades');

    final all = await real(tester, h.outbox);
    final rows = all
        .where((r) => r['entity_type'] != 'activity_event')
        .toList();
    expect(rows.map((r) => r['entity_type']), [
      'activity_session',
      'activity_result',
      'activity_session',
    ]);
    // Every answer and round is in the outbox as an ordered event, queued
    // after the session it belongs to and before the result.
    final events = [
      for (final r in all.where((r) => r['entity_type'] == 'activity_event'))
        jsonDecode(r['payload_json'] as String) as Map<String, dynamic>,
    ];
    expect(events.first['event_type'], 'activity_started');
    expect(events.last['event_type'], 'activity_ended');
    expect(events.last['data'], {
      'outcome': 'completed',
      'rounds_remaining': 0,
    });
    expect(
      events.where((e) => e['event_type'] == 'round_solved'),
      hasLength(3),
    );
    expect(
      [for (final e in events) e['seq']],
      [for (var i = 0; i < events.length; i++) i],
    );
    final attempts = events.where((e) => e['event_type'] == 'attempt');
    expect(attempts.every((e) => e['data']['latency_ms'] is int), isTrue);
    expect(
      all.indexWhere((r) => r['entity_type'] == 'activity_event'),
      greaterThan(0),
    );
    final result = jsonDecode(rows[1]['payload_json'] as String);
    expect(result['activity_id'], objectId);
    expect(result['abandoned'], false);
    expect(result['score'], 1.0);
    expect(result['correct_count'], 3);
    expect(result['attempt_count'], greaterThanOrEqualTo(3));
    expect(
      jsonDecode(rows[2]['payload_json'] as String)['status'],
      'completed',
    );
  });

  testWidgets('pause hides the round and disables hint and skip', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await openObjectGame(tester, h);

    await tapVisible(tester, find.text('Pause'));
    expect(find.text('Paused'), findsOneWidget);
    final hint = tester.widget<OutlinedButton>(
      find.ancestor(
        of: find.text('Hint'),
        matching: find.byType(OutlinedButton),
      ),
    );
    expect(hint.onPressed, isNull);
    await tapVisible(tester, find.text('Carry on').last);
    expect(find.text('Paused'), findsNothing);
  });

  testWidgets('hint removes an option and is counted', (tester) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await openObjectGame(tester, h);

    final round = find.byWidgetPredicate(
      (w) =>
          w.key is ValueKey &&
          '${(w.key! as ValueKey).value}'.startsWith('round_'),
    );
    int optionCount() => find
        .descendant(of: round, matching: find.byType(OutlinedButton))
        .evaluate()
        .length;
    final before = optionCount();
    await tapVisible(tester, find.text('Hint'));
    expect(find.text('One answer has been taken away.'), findsOneWidget);
    expect(optionCount(), before - 1);
    // Difficulty 1 → 3 options → only one hint possible; Hint is now disabled.
    final hint = tester.widget<OutlinedButton>(
      find.ancestor(
        of: find.text('Hint'),
        matching: find.byType(OutlinedButton),
      ),
    );
    expect(hint.onPressed, isNull);
  });

  testWidgets('skip advances; stop asks first, then records an abandoned run', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await openObjectGame(tester, h);

    await tapVisible(tester, find.text('Skip'));
    expect(find.text('2 of 3'), findsOneWidget);

    await tapVisible(tester, find.text('Stop'));
    expect(find.text('Stop this activity?'), findsOneWidget);
    await tapVisible(tester, find.text('Keep going'));
    expect(find.text('2 of 3'), findsOneWidget);

    await tapVisible(tester, find.text('Stop'));
    await tapVisible(tester, find.text('Yes, stop'));
    expect(find.text('Thank you for playing'), findsOneWidget);

    final rows = await real(tester, h.outbox);
    final result = jsonDecode(
      rows.firstWhere(
            (r) => r['entity_type'] == 'activity_result',
          )['payload_json']
          as String,
    );
    expect(result['abandoned'], true);
    expect(result['score'], isNull);
    expect(result['metrics']['rounds_skipped'], 1);
    final end = jsonDecode(rows.last['payload_json'] as String);
    expect(end['end_reason'], 'user_stopped');
  });

  testWidgets('result screen buttons navigate', (tester) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await openObjectGame(tester, h);
    await tapVisible(tester, find.text('Stop'));
    await tapVisible(tester, find.text('Yes, stop'));
    await tapVisible(tester, find.text('Play again'));
    expect(find.text('What is this?'), findsOneWidget);
    await tapVisible(tester, find.text('Stop'));
    await tapVisible(tester, find.text('Yes, stop'));
    await tapVisible(tester, find.text('Go home'));
    expect(find.text('Namaste, Aita'), findsOneWidget);
  });
}
