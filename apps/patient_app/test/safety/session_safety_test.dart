// Session safety on the phone (docs/fatigue-safety-plan.md): stop wins,
// leaving the screen pauses, nothing restarts by itself, interrupted runs are
// recorded honestly, endings are written once, and a dashboard tiredness note
// reaches a running activity. SYNTHETIC data only.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../adaptation/runner_adaptation_test.dart'
    show events, openRunner, outboxOf, right, wrong;
import '../data/sync_service_test.dart' show change;
import '../helpers.dart';

void main() {
  testWidgets('stop: one short question, "Yes, stop" is the main choice, and '
      'nothing else is decided after it', (tester) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.online = false;
    await openRunner(tester, h, hintsAdvised: true);
    await wrong(tester); // support was active (an automatic hint)
    await tapVisible(tester, find.text('Stop'));
    final stop = tester.widget<ButtonStyleButton>(
      find.byKey(const ValueKey('stop_confirm')),
    );
    expect(stop, isA<FilledButton>(), reason: 'stopping is the primary action');
    expect(
      tester.widget<ButtonStyleButton>(
        find.byKey(const ValueKey('stop_keep_going')),
      ),
      isA<OutlinedButton>(),
    );
    await tapVisible(tester, find.byKey(const ValueKey('stop_confirm')));
    expect(find.byType(AlertDialog), findsNothing, reason: 'asked only once');

    final log = await events(tester, h);
    final i = log.indexWhere((e) => e['type'] == 'stop_requested');
    final after = log.sublist(i + 1).map((e) => e['type']).toList();
    expect(after, ['adaptation', 'activity_ended']);
    expect(log[i + 1]['data']['reason_codes'], ['STOP_REQUESTED']);
    final session = (await outboxOf(tester, h, 'activity_session')).last;
    expect(session['end_reason'], 'user_stopped');
  });

  testWidgets('leaving the screen pauses the run; time away is not counted; '
      'it waits for "Carry on"', (tester) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.online = false;
    await openRunner(tester, h);
    await wrong(tester);

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await settle(tester);
    // Time passes while the phone is in a pocket (the harness clock moves on
    // every read; settle reads it many times).
    for (var i = 0; i < 5; i++) {
      await real(tester, () async => h.services.clock());
    }
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await settle(tester);
    expect(find.text('Paused'), findsOneWidget, reason: 'no silent restart');

    final paused = (await events(
      tester,
      h,
    )).where((e) => e['type'] == 'paused').toList();
    expect(paused.single['data'], {'source': 'system'});

    await tapVisible(tester, find.text('Carry on').last);
    expect(find.text('Paused'), findsNothing);
    for (var r = 0; r < 4; r++) {
      await right(tester);
    }
    final result = (await outboxOf(tester, h, 'activity_result')).single;
    expect(result['metrics']['paused_ms'], greaterThan(0));
    expect(
      result['duration_ms'] + result['metrics']['paused_ms'],
      greaterThan(result['duration_ms']),
      reason: 'time in the background is pause time, not activity time',
    );
  });

  testWidgets('a finished run does not restart when the app comes back', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.online = false;
    await openRunner(tester, h);
    for (var r = 0; r < 4; r++) {
      await right(tester);
    }
    expect(find.text('Well done!'), findsOneWidget);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await settle(tester);
    expect(find.text('Well done!'), findsOneWidget);
    final sessions = await real(tester, () => h.local.db.query('sessions'));
    expect(sessions, hasLength(1));
    expect(sessions.single['status'], 'completed');
  });

  group('session records', () {
    late Harness h;
    setUp(() async {
      h = await Harness.create();
      await h.pairAndOnboard();
      h.server.online = false;
    });
    tearDown(() => h.dispose());

    test('ending twice is written once; a stop is never overwritten', () async {
      final r = h.services.recorder;
      final (sid, _) = await r.startSession(patientId);
      await r.finishSession(patientId, sid, endReason: 'user_stopped');
      await r.finishSession(patientId, sid, endReason: 'completed');
      await r.finishSession(patientId, sid, endReason: 'user_stopped');
      final row = (await h.local.db.query('sessions')).single;
      expect(row['end_reason'], 'user_stopped');
      final queued = [
        for (final o in await h.outbox())
          jsonDecode(o['payload_json'] as String) as Map<String, dynamic>,
      ];
      expect(queued.where((d) => d['ended_at'] != null), hasLength(1));
    });

    test('a session the app left running is closed as interrupted, at its '
        'last recorded step, once', () async {
      final r = h.services.recorder;
      final (sid, start) = await r.startSession(patientId);
      await r.recordEvent(
        patientId,
        sessionId: sid,
        activityId: objectId,
        seq: 0,
        eventType: 'attempt',
        data: {'correct': true, 'latency_ms': 1200},
      );
      final lastStep = (await h.local.db.query(
        'activity_events',
      )).single['occurred_at'];
      expect(await r.closeInterruptedSessions(patientId), 1);
      final row = (await h.local.db.query('sessions')).single;
      expect(row['status'], 'abandoned');
      expect(row['end_reason'], 'timeout');
      expect(
        row['ended_at'],
        lastStep,
        reason: 'not "now": durations stay honest',
      );
      expect(DateTime.parse(row['ended_at'] as String).isAfter(start), isTrue);
      expect(await r.closeInterruptedSessions(patientId), 0);
    });

    test('an interrupted session without any step ends at its start', () async {
      final (sid, start) = await h.services.recorder.startSession(patientId);
      await h.services.recorder.closeInterruptedSessions(patientId);
      final row = (await h.local.db.query('sessions')).single;
      expect(row['id'], sid);
      expect(row['ended_at'], start.toUtc().toIso8601String());
    });
  });

  testWidgets('a dashboard "very tired" note reaches the running activity '
      'through the background sync', (tester) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    // The server will hand out the caregiver's note on the next pull.
    h.server.pullPages.add({
      'changes': [
        change(1, 'fatigue_report', '55555555-5555-4555-8555-555555555555', {
          'id': '55555555-5555-4555-8555-555555555555',
          'level': 'severe',
          'observed_at': '2026-10-15T04:31:00Z',
          'source': 'dashboard',
        }),
      ],
      'next_since': 1,
      'has_more': false,
    });
    await real(tester, () => h.services.serverStatus.refresh());
    await openRunner(tester, h);
    final pullsBefore = h.server.pullCalls;
    await right(tester); // round 1 ends: background sync starts
    await settle(tester);
    expect(h.server.pullCalls, greaterThan(pullsBefore));
    await right(tester); // round 2 ends: the pulled note applies
    expect(find.text("Let's take a rest"), findsOneWidget);
    final log = await events(tester, h);
    expect(log.firstWhere((e) => e['type'] == 'fatigue_reported')['data'], {
      'source': 'caregiver',
      'level': 'severe',
    });
  });
}
