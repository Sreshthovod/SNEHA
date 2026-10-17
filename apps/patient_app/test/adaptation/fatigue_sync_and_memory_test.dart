// Caregiver fatigue reports and session events across sync, and the engine's
// chosen memories reaching the games. SYNTHETIC data only.
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/activities/activity.dart';
import 'package:sneha_patient/activities/games/memory_games.dart';
import 'package:sneha_patient/activities/rounds/choice_round.dart';
import 'package:sneha_patient/data/api/models.dart';
import 'package:sneha_patient/data/api/stage7_models.dart';
import 'package:sneha_patient/data/repositories/sync_service.dart';
import 'package:sneha_patient/l10n/strings.dart';

import '../data/sync_service_test.dart' show change;
import '../helpers.dart';

const reportId = '66666666-6666-4666-8666-666666666666';

void main() {
  group('fatigue reports', () {
    late Harness h;
    setUp(() async {
      h = await Harness.create();
      await h.pairAndOnboard();
    });
    tearDown(() => h.dispose());

    Future<void> pull(List<Map<String, dynamic>> changes, int next) async {
      h.server.pullPages.add({
        'changes': changes,
        'next_since': next,
        'has_more': false,
      });
      await h.services.sync.syncProfile(patientId);
    }

    test('a dashboard "very tired" report reaches the offline engine; a '
        'delete removes it', () async {
      expect(
        (await h.services.recommendations.next(patientId)).action.code,
        'activity',
      );
      await pull([
        change(1, 'fatigue_report', reportId, {
          'id': reportId,
          'level': 'severe',
          'observed_at': h.services.clock().toUtc().toIso8601String(),
          'source': 'dashboard',
        }),
      ], 1);
      final row = (await h.local.db.query('fatigue_reports')).single;
      expect(row['source'], 'caregiver_dashboard');
      expect(row.containsKey('note'), isFalse);

      h.server.online = false; // the decision is made on the phone
      final rest = await h.services.recommendations.next(patientId);
      expect(rest.action.code, 'break');
      expect(rest.reasonCodes, contains('CAREGIVER_REPORTED_SEVERE_FATIGUE'));

      h.server.online = true;
      await pull([change(2, 'fatigue_report', reportId, null)], 2);
      expect(await h.local.db.query('fatigue_reports'), isEmpty);
      expect(
        (await h.services.recommendations.next(patientId)).action.code,
        'activity',
      );
    });

    test('a level-less dashboard note counts as "a little tired"', () async {
      await pull([
        change(1, 'fatigue_report', reportId, {
          'id': reportId,
          'level': null,
          'observed_at': h.services.clock().toUtc().toIso8601String(),
          'source': 'dashboard',
        }),
      ], 1);
      final next = await h.services.recommendations.next(patientId);
      expect(next.action.code, 'activity');
      expect(next.difficulty, 1);
      expect(next.reasonCodes, contains('RECENT_FATIGUE_OBSERVATION'));
    });

    test('a report made offline is kept, pushed once, and its echo from the '
        'server does not duplicate it', () async {
      h.server.online = false;
      final id = await h.services.recorder.reportCaregiverFatigue(
        patientId,
        level: 'mild',
      );
      final offline = await h.services.sync.syncProfile(patientId);
      expect(offline.outcome, isNot(SyncOutcome.success));
      expect((await h.outbox()).single['entity_type'], 'fatigue_report');

      h.server.online = true;
      await h.services.sync.syncProfile(patientId);
      expect(await h.outbox(), isEmpty);
      await h.services.sync.syncProfile(patientId);
      final pushed = h.server.pushedMutations.where(
        (m) => m['entity_type'] == 'fatigue_report',
      );
      expect(pushed, hasLength(1), reason: 'pushed exactly once');

      await pull([
        change(9, 'fatigue_report', id, {
          'id': id,
          'level': 'mild',
          'observed_at': h.services.clock().toUtc().toIso8601String(),
          'source': 'device',
        }),
      ], 9);
      final rows = await h.local.db.query('fatigue_reports');
      expect(rows, hasLength(1));
      expect(rows.single['source'], 'caregiver_phone');
    });

    test(
      'events recorded offline survive a failed sync and are pushed once',
      () async {
        h.server.online = false;
        final r = h.services.recorder;
        final (sid, _) = await r.startSession(patientId);
        for (var i = 0; i < 3; i++) {
          await r.recordEvent(
            patientId,
            sessionId: sid,
            activityId: objectId,
            seq: i,
            eventType: 'attempt',
            roundIndex: 0,
            data: {'correct': i == 2, 'latency_ms': 1000 + i},
          );
        }
        expect(
          await h.local.db.query('activity_events'),
          hasLength(3),
          reason: 'stored on the phone, not in screen state',
        );
        await h.services.sync.syncProfile(patientId);
        expect(await h.outbox(), hasLength(4), reason: 'nothing lost offline');

        h.server.online = true;
        await h.services.sync.syncProfile(patientId);
        await h.services.sync.syncProfile(patientId);
        final events = h.server.pushedMutations.where(
          (m) => m['entity_type'] == 'activity_event',
        );
        expect(events, hasLength(3));
        expect({for (final e in events) e['data']['id']}, hasLength(3));
        expect(
          h.server.pushedBatches.first.first,
          'activity_session',
          reason: 'the session is pushed before its events',
        );
        expect(await h.outbox(), isEmpty);
        expect(
          await h.local.db.query('activity_events'),
          hasLength(3),
          reason: 'the local log stays for the progress screen',
        );
      },
    );

    test('event types and levels outside the contract are refused', () async {
      final (sid, _) = await h.services.recorder.startSession(patientId);
      expect(
        () => h.services.recorder.recordEvent(
          patientId,
          sessionId: sid,
          activityId: objectId,
          seq: 0,
          eventType: 'mood_score',
        ),
        throwsArgumentError,
      );
      expect(
        () => h.services.recorder.reportCaregiverFatigue(
          patientId,
          level: 'exhausted',
        ),
        throwsArgumentError,
      );
    });
  });

  group('approved memories chosen by the engine', () {
    MemoryItem memory(int i) => MemoryItem(
      id: 'm$i',
      patientId: 'p',
      kind: 'person',
      title: 'Synthetic memory $i',
      localPhotoPath: '/photos/$i.jpg',
    );

    test('photo recall asks about the engine\'s memories first', () {
      final content = ActivityContent(
        memories: [for (var i = 0; i < 6; i++) memory(i)],
        preferredMemoryIds: const ['m4', 'm2', 'not-on-this-phone'],
      );
      for (final seed in [1, 2, 3]) {
        final rs = const PhotoRecallActivity().createRounds(
          content: content,
          difficulty: 1,
          random: Random(seed),
          strings: AppStrings('en'),
        );
        final targets = [for (final r in rs) (r as ChoiceRoundSpec).correctId];
        expect(targets.take(2), ['m4', 'm2']);
        expect(targets.toSet(), hasLength(targets.length));
      }
    });

    test('server recommendations carry their memory refs and hint advice', () {
      final rec = ServerRecommendation.fromJson({
        ...recommendationJson(),
        'hints_enabled': true,
        'content_refs': {
          'memory_item_ids': ['m4', 'm2'],
          'routine_item_ids': [],
        },
      });
      expect(rec.memoryItemIds, ['m4', 'm2']);
      expect(rec.hintsEnabled, isTrue);
    });
  });
}
