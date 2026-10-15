import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/data/repositories/activity_recorder.dart';

import '../helpers.dart';

void main() {
  late Harness h;
  setUp(() async {
    h = await Harness.create();
    await h.pairAndOnboard();
  });
  tearDown(() => h.dispose());

  ActivityOutcome outcome(
    DateTime start, {
    Map<String, num> metrics = const {},
  }) => ActivityOutcome(
    activityId: pairsId,
    difficultyLevel: 2,
    startedAt: start,
    completedAt: start.add(const Duration(minutes: 2)),
    score: 0.75,
    correctCount: 3,
    attemptCount: 4,
    hintCount: 1,
    durationMs: 120000,
    abandoned: false,
    metrics: metrics,
  );

  test(
    'session, result and end are stored with outbox rows in order',
    () async {
      final r = h.services.recorder;
      final (sid, started) = await r.startSession(patientId);
      await r.recordResult(
        patientId,
        sid,
        outcome(started, metrics: {'rounds_total': 4}),
      );
      await r.finishSession(patientId, sid, endReason: 'completed');

      final rows = await h.outbox();
      expect(rows.map((r) => r['entity_type']), [
        'activity_session',
        'activity_result',
        'activity_session',
      ]);
      final result = jsonDecode(rows[1]['payload_json'] as String);
      // Shape the server validates (ResultPayload).
      expect(result['session_id'], sid);
      expect(result['score'], 0.75);
      expect(result['correct_count'] <= result['attempt_count'], isTrue);
      expect(result['metrics'], {'rounds_total': 4});
      expect((result['started_at'] as String).endsWith('Z'), isTrue);
      final end = jsonDecode(rows[2]['payload_json'] as String);
      expect(end['status'], 'completed');
      expect(
        end['started_at'],
        isNotNull,
        reason: 'server needs started_at on every upsert',
      );
      expect(await h.local.db.query('results'), hasLength(1));
    },
  );

  test('stopping marks the session abandoned', () async {
    final r = h.services.recorder;
    final (sid, _) = await r.startSession(patientId);
    await r.finishSession(patientId, sid, endReason: 'user_stopped');
    final session = (await h.local.db.query('sessions')).single;
    expect(session['status'], 'abandoned');
    expect(session['end_reason'], 'user_stopped');
  });

  test('invalid metrics are rejected before anything is stored', () async {
    final r = h.services.recorder;
    final (sid, started) = await r.startSession(patientId);
    expect(
      () => r.recordResult(
        patientId,
        sid,
        outcome(started, metrics: {'Bad Key': 1}),
      ),
      throwsArgumentError,
    );
    expect(await h.local.db.query('results'), isEmpty);
  });

  test('conversation records metadata only — no words', () async {
    await h.services.recorder.recordConversation(
      patientId,
      ConversationSummary(
        startedAt: DateTime.utc(2026, 10, 15, 4),
        endedAt: DateTime.utc(2026, 10, 15, 4, 5),
        language: 'as',
        turnCount: 3,
        intents: ['greeting', 'ask_time', 'greeting'],
      ),
    );
    final row = (await h.outbox()).single;
    final data =
        jsonDecode(row['payload_json'] as String) as Map<String, dynamic>;
    expect(data.keys.toSet(), {
      'id',
      'started_at',
      'ended_at',
      'language',
      'provider',
      'fallback_used',
      'turn_count',
      'intents',
    });
    expect(data['provider'], 'deterministic');
    expect(data['intents'], ['greeting', 'ask_time']);
  });
}
