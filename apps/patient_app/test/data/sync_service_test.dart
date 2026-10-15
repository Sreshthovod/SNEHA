import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/data/repositories/activity_recorder.dart';
import 'package:sneha_patient/data/repositories/sync_service.dart';

import '../helpers.dart';

const memoryId = '33333333-3333-4333-8333-333333333333';
const routineId = '44444444-4444-4444-8444-444444444444';

Map<String, dynamic> memoryJson({String title = 'Synthetic tea garden'}) => {
  'id': memoryId,
  'patient_id': patientId,
  'kind': 'place',
  'title': title,
  'description': null,
  'approx_year': 1980,
  'tags': ['garden'],
  'media_file_id': null,
  'status': 'approved',
  'source': 'dashboard',
  'version': 1,
};

Map<String, dynamic> change(
  int seq,
  String type,
  String id,
  Map<String, dynamic>? data,
) => {
  'seq': seq,
  'entity_type': type,
  'entity_id': id,
  'operation': data == null ? 'delete' : 'upsert',
  'changed_at': '2026-10-15T00:00:00Z',
  'data': data,
};

void main() {
  late Harness h;
  setUp(() async {
    h = await Harness.create();
    await h.pairAndOnboard(withCatalog: false);
  });
  tearDown(() => h.dispose());

  Future<void> recordRun() async {
    final r = h.services.recorder;
    final (sid, start) = await r.startSession(patientId);
    await r.recordResult(
      patientId,
      sid,
      ActivityOutcome(
        activityId: pairsId,
        difficultyLevel: 1,
        startedAt: start,
        completedAt: start.add(const Duration(minutes: 1)),
        score: 1,
        correctCount: 3,
        attemptCount: 3,
        hintCount: 0,
        durationMs: 60000,
        abandoned: false,
      ),
    );
    await r.finishSession(patientId, sid, endReason: 'completed');
  }

  test('pushes the outbox in creation order and clears applied rows', () async {
    await recordRun();
    final report = await h.services.sync.syncProfile(patientId);

    expect(report.outcome, SyncOutcome.success);
    expect(report.pushed, 3);
    expect(h.server.pushedBatches.single, [
      'activity_session',
      'activity_result',
      'activity_session',
    ]);
    expect(await h.outbox(), isEmpty);
    final status = await h.services.sync.status(patientId);
    expect(status.pending, 0);
    expect(status.lastSuccessAt, isNotNull);
  });

  test(
    'duplicates are cleared; conflicts and rejections are kept for attention',
    () async {
      await recordRun();
      h.server.pushStatus['activity_session'] = 'duplicate';
      h.server.pushStatus['activity_result'] = 'rejected';
      final report = await h.services.sync.syncProfile(patientId);
      expect(report.needsAttention, 1);
      final left = await h.outbox();
      expect(left.single['entity_type'], 'activity_result');
      expect(left.single['last_status'], 'rejected');

      // Not retried blindly on the next sync.
      h.server.pushedMutations.clear();
      await h.services.sync.syncProfile(patientId);
      expect(h.server.pushedMutations, isEmpty);
      expect((await h.services.sync.status(patientId)).needsAttention, 1);
    },
  );

  test('pull applies upserts and tombstones and stores the cursor', () async {
    h.server.pullPages.addAll([
      {
        'changes': [
          change(
            5,
            'activity_definition',
            pairsId,
            catalogJson(pairsId, 'picture-pairs'),
          ),
          change(6, 'memory_item', memoryId, memoryJson()),
          change(7, 'routine_item', routineId, {
            'id': routineId,
            'patient_id': patientId,
            'title': 'Morning tea',
            'local_time': '07:30',
            'days_of_week': 127,
            'is_active': true,
            'created_at': '2026-10-01T00:00:00Z',
            'updated_at': '2026-10-01T00:00:00Z',
          }),
        ],
        'next_since': 7,
        'has_more': true,
      },
      {
        'changes': [
          change(
            8,
            'memory_item',
            memoryId,
            memoryJson(title: 'Synthetic corrected'),
          ),
          change(9, 'routine_item', routineId, null),
          change(10, 'something_new', 'x', {'a': 1}),
        ],
        'next_since': 10,
        'has_more': false,
      },
    ]);

    final report = await h.services.sync.syncProfile(patientId);
    expect(report.outcome, SyncOutcome.success);
    expect(h.server.pullSince, [0, 7]);
    expect(await h.services.content.catalog(), hasLength(1));
    final memories = await h.services.content.memories(patientId);
    expect(memories.single.title, 'Synthetic corrected');
    expect(await h.services.content.routines(patientId), isEmpty);
    final cursor = (await h.local.db.query('sync_state')).single['cursor'];
    expect(cursor, 10);

    // Next sync resumes from the stored cursor.
    await h.services.sync.syncProfile(patientId);
    expect(h.server.pullSince.last, 10);

    // A memory tombstone deletes it locally.
    h.server.pullPages.add({
      'changes': [change(11, 'memory_item', memoryId, null)],
      'next_since': 11,
      'has_more': false,
    });
    await h.services.sync.syncProfile(patientId);
    expect(await h.services.content.memories(patientId), isEmpty);
  });

  test('profile and consent are refreshed during sync', () async {
    await h.services.sync.syncProfile(patientId);
    final profile = await h.services.profiles.get(patientId);
    expect(profile!.preferredName, 'Aita');
    expect(profile.consents!['data_processing'], 'granted');
    expect(profile.consentsFetchedAt, isNotNull);
  });

  test('offline sync keeps everything and reports offline', () async {
    await recordRun();
    h.server.online = false;
    final report = await h.services.sync.syncProfile(patientId);
    expect(report.outcome, SyncOutcome.offline);
    expect(await h.outbox(), hasLength(3));
    expect(
      (await h.services.sync.status(patientId)).lastError,
      contains('No internet'),
    );
  });

  test('a rejected device session marks the profile for re-pairing', () async {
    h.server.authStatus = 401;
    await recordRun();
    // Push 401s on the first request.
    final report = await h.services.sync.syncProfile(patientId);
    expect(report.outcome, SyncOutcome.needsRepair);
    expect((await h.services.profiles.get(patientId))!.needsRepair, isTrue);
    expect(await h.outbox(), hasLength(3), reason: 'nothing is lost');
  });

  test('push payload matches the server mutation shape', () async {
    await recordRun();
    await h.services.sync.syncProfile(patientId);
    final m = h.server.pushedMutations[1];
    expect(m.keys.toSet(), {'mutation_id', 'entity_type', 'operation', 'data'});
    expect(m['operation'], 'upsert');
    expect(jsonEncode(m['data']), contains('"session_id"'));
  });
}
