// Engine 1.2.0 on the phone, offline: recorded history changes the next
// suggestion, and the suggestion changes what the runner does. SYNTHETIC data.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/data/repositories/activity_recorder.dart';
import 'package:sneha_patient/speech/speech.dart';

import '../helpers.dart';
import '../widgets/stage5_widgets_test.dart' show FakeSpeech, enableReadAloud;

/// Records one finished run as the phone would (session + result).
Future<void> played(
  Harness h,
  String activityId, {
  double score = 0.9,
  int hints = 0,
  int readAloud = 0,
}) async {
  final r = h.services.recorder;
  final (sid, start) = await r.startSession(patientId);
  await r.recordResult(
    patientId,
    sid,
    ActivityOutcome(
      activityId: activityId,
      difficultyLevel: 1,
      startedAt: start,
      completedAt: start.add(const Duration(minutes: 2)),
      score: score,
      correctCount: 3,
      attemptCount: 3 + hints,
      hintCount: hints,
      durationMs: 120000,
      abandoned: false,
      metrics: {'instructions_repeated': readAloud},
    ),
  );
  await r.finishSession(patientId, sid, endReason: 'completed');
}

Future<List<Map<String, dynamic>>> events(WidgetTester t, Harness h) => real(
  t,
  () async => [
    for (final r in await h.outbox())
      if (r['entity_type'] == 'activity_event')
        jsonDecode(r['payload_json'] as String) as Map<String, dynamic>,
  ],
);

void main() {
  group('offline engine decisions', () {
    late Harness h;
    setUp(() async {
      h = await Harness.create();
      await h.pairAndOnboard();
      h.server.online = false; // every decision below is made on the phone
    });
    tearDown(() => h.dispose());

    test('no history: a safe default, no invented support', () async {
      final s = await h.services.recommendations.next(patientId);
      expect(s.chosenOnDevice, isTrue);
      expect(s.reasonCodes, contains('COLD_START_DEFAULT'));
      expect(s.hintsEnabled, isFalse);
      expect(s.readAloudFirst, isFalse);
    });

    test('runs that needed many hints turn hints on next time', () async {
      for (final id in [pairsId, objectId, pairsId, objectId]) {
        await played(h, id, score: 0.7, hints: 3);
      }
      final s = await h.services.recommendations.next(patientId);
      expect(s.activityId, pairsId, reason: 'varies from the last activity');
      expect(s.hintsEnabled, isTrue);
      expect(s.reasonCodes, contains('HINT_SUPPORT_AFTER_HINT_USE'));
    });

    test(
      'struggling at the easiest level steers to a gentler activity',
      () async {
        await played(h, pairsId);
        await played(h, objectId, score: 0.2);
        await played(h, objectId, score: 0.3);
        final s = await h.services.recommendations.next(patientId);
        expect(s.activityId, pairsId);
        expect(s.reasonCodes, contains('EASIER_ALTERNATIVE_AFTER_STRUGGLE'));
      },
    );

    test('identical history gives the identical suggestion', () async {
      await played(h, objectId, score: 0.2);
      await played(h, pairsId, hints: 3, readAloud: 2);
      final a = await h.services.recommendations.next(patientId);
      final b = await h.services.recommendations.next(patientId);
      expect(b.activityId, a.activityId);
      expect(b.difficulty, a.difficulty);
      expect(b.reasonCodes, a.reasonCodes);
      expect(b.hintsEnabled, a.hintsEnabled);
      expect(b.readAloudFirst, a.readAloudFirst);
    });

    test('stop and tiredness win over every support rule', () async {
      for (final id in [pairsId, objectId, pairsId, objectId]) {
        await played(h, id, score: 0.7, hints: 3, readAloud: 2);
      }
      final stop = await h.services.recommendations.next(
        patientId,
        stopRequested: true,
        fatigueReported: true,
      );
      expect(stop.action.code, 'stop');
      expect(stop.reasonCodes, ['STOP_REQUESTED']);
      final tired = await h.services.recommendations.next(
        patientId,
        fatigueReported: true,
      );
      expect(tired.action.code, 'break');
      expect(tired.difficulty, 1);
    });
  });

  testWidgets('repeated "Read aloud" presses: the next run reads each question '
      'first, records the presses and why it was suggested', (tester) async {
    final speech = FakeSpeech(SpeechAvailability.available);
    final h = await pairedHarness(tester, speech: speech);
    addTearDown(h.dispose);
    h.server.online = false;
    await enableReadAloud(tester, h);
    await real(tester, () async {
      await played(h, pairsId, readAloud: 2);
      await played(h, pairsId, readAloud: 1);
    });

    await tester.pumpWidget(h.app());
    await settle(tester);
    expect(
      find.text('Each question will be read aloud for you.'),
      findsOneWidget,
      reason: 'the patient sees a calm sentence, never a code',
    );
    await tapVisible(tester, find.widgetWithText(FilledButton, 'Start'));
    expect(speech.spoken, isNotEmpty, reason: 'read aloud when it appeared');
    final spokenOnOpen = speech.spoken.length;

    await tapVisible(tester, find.widgetWithText(OutlinedButton, 'Read aloud'));
    expect(speech.spoken.length, spokenOnOpen + 1);
    final log = await events(tester, h);
    final start = log.firstWhere((e) => e['event_type'] == 'activity_started');
    expect(start['data']['decided_on'], 'device');
    expect(
      start['data']['engine_reason_codes'],
      contains('INSTRUCTIONS_READ_ALOUD_FIRST'),
    );
    expect(
      log.where((e) => e['event_type'] == 'instructions_repeated'),
      hasLength(1),
      reason: 'only the press counts, not the automatic reading',
    );
  });

  testWidgets('an activity picked from the list records no engine reasons', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await tester.pumpWidget(h.app());
    await settle(tester);
    await tapVisible(tester, find.text('Play an activity'));
    await tapVisible(tester, find.text('Start Synthetic name-the-object'));
    final start = (await events(
      tester,
      h,
    )).firstWhere((e) => e['event_type'] == 'activity_started');
    expect(start['data'].containsKey('decided_on'), isFalse);
    expect(start['data'].containsKey('engine_reason_codes'), isFalse);
  });
}
