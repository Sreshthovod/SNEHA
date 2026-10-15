// Stage 5: feedback fields, retry limits/backoff, recovery, memory guard.
// All data is SYNTHETIC.
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/data/repositories/activity_recorder.dart';
import 'package:sneha_patient/data/repositories/media_cache.dart';
import 'package:sneha_patient/data/repositories/sync_service.dart';

import '../helpers.dart';

ActivityOutcome outcome(
  DateTime start, {
  double? score = 1.0,
  bool abandoned = false,
  bool tired = false,
  String? engagement,
}) => ActivityOutcome(
  activityId: pairsId,
  difficultyLevel: 1,
  startedAt: start,
  completedAt: start.add(const Duration(seconds: 30)),
  score: score,
  correctCount: 3,
  attemptCount: 3,
  hintCount: 0,
  durationMs: 30000,
  abandoned: abandoned,
  fatigueReported: tired,
  engagement: engagement,
);

Future<String> recordOne(Harness h, {bool tired = false}) async {
  final pid = patientId;
  final (sid, start) = await h.services.recorder.startSession(pid);
  return h.services.recorder.recordResult(
    pid,
    sid,
    outcome(start.add(const Duration(seconds: 1)), tired: tired),
  );
}

Map<String, dynamic> payloadOf(Map<String, Object?> row) =>
    jsonDecode(row['payload_json'] as String) as Map<String, dynamic>;

void main() {
  late Harness h;

  Future<void> setUpWith({RetryPolicy retry = const RetryPolicy()}) async {
    h = await Harness.create(retry: retry);
    await h.pairAndOnboard();
  }

  tearDown(() => h.dispose());

  group('feedback fields', () {
    test('optional feedback is only sent when set', () async {
      await setUpWith();
      await recordOne(h);
      await recordOne(h, tired: true);
      final results = (await h.outbox())
          .where((r) => r['entity_type'] == 'activity_result')
          .map(payloadOf)
          .toList();
      expect(results[0].containsKey('fatigue_reported'), isFalse);
      expect(results[0].containsKey('engagement'), isFalse);
      expect(results[0].containsKey('recommendation_id'), isFalse);
      expect(results[1]['fatigue_reported'], isTrue);
    });

    test('engagement answer travels with an unsent result', () async {
      await setUpWith();
      final id = await recordOne(h);
      expect(await h.services.recorder.setEngagement(id, 'enjoyed'), isTrue);
      final row = (await h.outbox()).firstWhere((r) => r['entity_id'] == id);
      expect(payloadOf(row)['engagement'], 'enjoyed');
      final local = await h.local.db.query(
        'results',
        where: 'id = ?',
        whereArgs: [id],
      );
      expect(local.single['engagement'], 'enjoyed');
    });

    test(
      'engagement after sharing stays local (results are immutable)',
      () async {
        await setUpWith();
        final id = await recordOne(h);
        await h.services.sync.syncProfile(patientId);
        expect(await h.outbox(), isEmpty);
        expect(await h.services.recorder.setEngagement(id, 'neutral'), isFalse);
        expect(
          () => h.services.recorder.setEngagement(id, 'loved it'),
          throwsArgumentError,
        );
      },
    );
  });

  group('retry limits and backoff', () {
    test('network errors never use up retries', () async {
      await setUpWith();
      await recordOne(h);
      h.server.online = false;
      for (var i = 0; i < 12; i++) {
        final r = await h.services.sync.syncProfile(patientId);
        expect(r.outcome, SyncOutcome.offline);
      }
      final rows = await h.outbox();
      expect(rows, hasLength(2));
      expect(rows.every((r) => r['attempts'] == 0), isTrue);
      expect(rows.every((r) => r['last_status'] == null), isTrue);
    });

    test(
      'server errors back off; the entry waits before the next try',
      () async {
        await setUpWith();
        await recordOne(h);
        h.server.failPushes = 1;
        final first = await h.services.sync.syncProfile(patientId);
        expect(first.outcome, SyncOutcome.failed);
        final rows = await h.outbox();
        expect(rows.every((r) => r['attempts'] == 1), isTrue);
        expect(rows.every((r) => r['next_attempt_at'] != null), isTrue);
        expect(await h.services.sync.backedOffCount(patientId), 2);

        // Immediately syncing again does not hammer the server.
        final pushesBefore = h.server.pushedBatches.length;
        await h.services.sync.syncProfile(patientId);
        expect(h.server.pushedBatches.length, pushesBefore);
        expect(await h.outbox(), hasLength(2));
      },
    );

    test(
      'after max attempts entries need attention, are kept, and can be retried',
      () async {
        await setUpWith(
          retry: const RetryPolicy(maxAttempts: 3, baseDelay: Duration.zero),
        );
        await recordOne(h);
        h.server.failPushes = 3;
        for (var i = 0; i < 3; i++) {
          await h.services.sync.syncProfile(patientId);
        }
        final items = await h.services.sync.attentionItems(patientId);
        expect(items, hasLength(2));
        expect(items.every((i) => i.status == 'failed' && i.retryable), isTrue);
        expect(await h.outbox(), hasLength(2), reason: 'never deleted');

        for (final i in items) {
          await h.services.sync.retryItem(i.mutationId);
        }
        final ok = await h.services.sync.syncProfile(patientId);
        expect(ok.outcome, SyncOutcome.success);
        expect(await h.outbox(), isEmpty);
      },
    );

    test('conflicts are kept locally and are not retryable', () async {
      await setUpWith();
      await recordOne(h);
      h.server.pushStatus['activity_result'] = 'conflict';
      await h.services.sync.syncProfile(patientId);
      final items = await h.services.sync.attentionItems(patientId);
      expect(items.single.entityType, 'activity_result');
      expect(items.single.retryable, isFalse);
      await h.services.sync.retryItem(items.single.mutationId);
      expect(
        (await h.services.sync.attentionItems(patientId)).single.status,
        'conflict',
      );
      expect(await h.local.db.query('results'), hasLength(1));
    });

    test('unacknowledged entries back off instead of looping', () async {
      await setUpWith();
      await recordOne(h);
      h.server.pushStatus['activity_session'] = 'missing';
      // An unknown status is treated as needing attention, not as success.
      await h.services.sync.syncProfile(patientId);
      expect(
        (await h.services.sync.attentionItems(patientId)).map((i) => i.status),
        contains('missing'),
      );
    });
  });

  test(
    'recovery: a push applied but whose reply was lost is not double counted',
    () async {
      await setUpWith();
      await recordOne(h);
      h.server.dropNextPushResponse = true;
      final lost = await h.services.sync.syncProfile(patientId);
      expect(lost.outcome, SyncOutcome.offline);
      expect(await h.outbox(), hasLength(2), reason: 'kept until confirmed');
      expect(h.server.stored['activity_result'], hasLength(1));

      // "Restart": a brand-new SyncService on the same database.
      final restarted = SyncService(
        local: h.local,
        api: h.services.api,
        profiles: h.services.profiles,
        media: MediaCache(h.mediaDir),
      );
      final report = await restarted.syncProfile(patientId);
      expect(report.outcome, SyncOutcome.success);
      expect(await h.outbox(), isEmpty);
      expect(h.server.stored['activity_result'], hasLength(1));
      expect(
        h.server.pushedMutations
            .where((m) => m['entity_type'] == 'activity_result')
            .length,
        2,
        reason: 'sent twice, stored once',
      );
    },
  );

  test(
    'an older memory version never overwrites the approved local copy',
    () async {
      await setUpWith();
      Map<String, dynamic> memory(int version, String title) => {
        'seq': version,
        'entity_type': 'memory_item',
        'entity_id': 'mem-1',
        'operation': 'upsert',
        'changed_at': '2026-10-15T00:00:00Z',
        'data': {
          'id': 'mem-1',
          'patient_id': patientId,
          'kind': 'place',
          'title': title,
          'description': null,
          'approx_year': null,
          'tags': ['tea'],
          'media_file_id': null,
          'status': 'approved',
          'source': 'dashboard',
          'version': version,
          'created_by_id': null,
          'reviewed_by_id': null,
          'reviewed_at': null,
          'review_note': null,
          'created_at': '2026-10-15T00:00:00Z',
          'updated_at': '2026-10-15T00:00:00Z',
        },
      };
      h.server.pullPages.add({
        'changes': [memory(3, 'Synthetic tea garden (corrected)')],
        'next_since': 3,
        'has_more': false,
      });
      await h.services.sync.syncProfile(patientId);
      h.server.pullPages.add({
        'changes': [memory(2, 'Synthetic stale title')],
        'next_since': 4,
        'has_more': false,
      });
      await h.services.sync.syncProfile(patientId);
      final rows = await h.local.db.query('memories');
      expect(rows.single['title'], 'Synthetic tea garden (corrected)');
      expect(rows.single['version'], 3);
    },
  );

  test(
    'caregiver-approved interests are fetched and steer local suggestions',
    () async {
      await setUpWith();
      await h.local.db.insert('catalog', {
        'id': '4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0003',
        'slug': 'daily-sequence',
        'version': 1,
        'title': 'Synthetic daily-sequence',
        'description': 'Synthetic.',
        'activity_type': 'sequencing',
        'min_difficulty': 1,
        'max_difficulty': 5,
        'default_duration_seconds': 120,
        'uses_memory_bank': 0,
        'is_active': 1,
      });
      final before = await h.services.recommendations.next(patientId);
      expect(before.activityId, pairsId, reason: 'cold-start default');

      h.server.preferences = {
        'interests': ['weaving'],
        'disliked_activity_slugs': <String>[],
      };
      await h.services.sync.syncProfile(patientId);
      final after = await h.services.recommendations.next(patientId);
      expect(after.activityId, '4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0003');
      expect(after.reasonCodes, contains('INTEREST_MATCH'));
      expect(after.chosenOnDevice, isTrue);
    },
  );

  test('missing preferences endpoint is not a sync failure', () async {
    await setUpWith();
    h.server.preferences = null;
    final r = await h.services.sync.syncProfile(patientId);
    expect(r.outcome, SyncOutcome.success);
  });
}
