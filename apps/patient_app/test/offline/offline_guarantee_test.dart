// The patient app's offline promise, end to end at the data layer:
// with NO network, approved memories open, every game can be played, results
// are recorded, difficulty adapts on the phone, progress is shown; when the
// network returns, sync drains the outbox and nothing is counted twice.
// All data is SYNTHETIC.
import 'dart:io';
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/activities/activity.dart';
import 'package:sneha_patient/activities/registry.dart';
import 'package:sneha_patient/data/repositories/activity_recorder.dart';
import 'package:sneha_patient/data/repositories/sync_service.dart';
import 'package:sneha_patient/l10n/strings.dart';
import 'package:sneha_patient/personalization/engine.dart';

import '../helpers.dart';

const extraCatalog = {
  'daily-sequence': ('4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0003', 5, false),
  'familiar-faces': ('4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0008', 3, true),
  'sort-into-groups': ('4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0010', 3, false),
};

Future<void> seedOfflineContent(Harness h) async {
  for (final e in extraCatalog.entries) {
    await h.local.db.insert('catalog', {
      'id': e.value.$1,
      'slug': e.key,
      'version': 1,
      'title': 'Synthetic ${e.key}',
      'description': 'Synthetic.',
      'activity_type': 'attention',
      'min_difficulty': 1,
      'max_difficulty': e.value.$2,
      'default_duration_seconds': 120,
      'uses_memory_bank': e.value.$3 ? 1 : 0,
      'is_active': 1,
    });
  }
  // Approved memories with photos already cached on the phone.
  for (var i = 0; i < 4; i++) {
    final photo = File('${h.mediaDir.path}/synthetic_$i.png')
      ..writeAsBytesSync([0x89, 0x50, 0x4E, 0x47]);
    await h.local.db.insert('memories', {
      'id': 'mem-$i',
      'patient_id': patientId,
      'kind': i < 3 ? 'person' : 'place',
      'title': 'Synthetic memory $i',
      'description': null,
      'approx_year': null,
      'tags_json': '["family"]',
      'media_file_id': 'file-$i',
      'version': 1,
      'local_photo_path': photo.path,
    });
  }
  for (final (id, time, title) in [
    ('r1', '07:00', 'Synthetic tea'),
    ('r2', '08:00', 'Synthetic prayer'),
    ('r3', '12:30', 'Synthetic lunch'),
  ]) {
    await h.local.db.insert('routines', {
      'id': id,
      'patient_id': patientId,
      'title': title,
      'local_time': time,
      'days_of_week': 127,
      'is_active': 1,
    });
  }
}

void main() {
  test(
    'everything core works offline, then syncs once without double counting',
    () async {
      final h = await Harness.create();
      addTearDown(h.dispose);
      await h.pairAndOnboard(); // pairing itself needs the internet
      await seedOfflineContent(h);
      final s = h.services;

      h.server.online = false; // ---------------- no network from here on

      // Approved local memories open.
      final memories = await s.content.memories(patientId);
      expect(memories, hasLength(4));
      final content = ActivityContent(
        memories: memories,
        routines: await s.content.routines(patientId),
      );

      // Every registered game can build rounds from on-phone content.
      final catalog = await s.content.catalog();
      for (final entry in activityRegistry.entries) {
        final activity = entry.value;
        expect(
          activity.unavailableReason(content),
          isNull,
          reason: '${entry.key} should be playable offline',
        );
        final rounds = activity.createRounds(
          content: content,
          difficulty: 1,
          random: Random(1),
          strings: AppStrings('en'),
        );
        expect(rounds, isNotEmpty, reason: entry.key);
      }
      expect(catalog.map((c) => c.slug), containsAll(activityRegistry.keys));

      // Play picture pairs comfortably three times → the phone steps it up.
      final pairs = catalog.firstWhere((c) => c.slug == 'picture-pairs');
      expect(await s.content.difficultyFor(patientId, pairs), 1);
      for (var i = 0; i < 3; i++) {
        final (sid, start) = await s.recorder.startSession(patientId);
        await s.recorder.recordResult(
          patientId,
          sid,
          ActivityOutcome(
            activityId: pairs.id,
            difficultyLevel: await s.content.difficultyFor(patientId, pairs),
            startedAt: start.add(const Duration(seconds: 1)),
            completedAt: start.add(const Duration(seconds: 60)),
            score: 1.0,
            correctCount: 6,
            attemptCount: 6,
            hintCount: 0,
            durationMs: 59000,
            abandoned: false,
          ),
        );
        await s.recorder.finishSession(patientId, sid, endReason: 'completed');
      }
      expect(await s.content.difficultyFor(patientId, pairs), 2);

      // Local progress is descriptive and computed on the phone.
      final progress = await s.progress.forPatient(patientId, catalog);
      final p = progress.single;
      expect(
        (p.activity.slug, p.level, p.maxLevel, p.timesPlayed),
        ('picture-pairs', 2, 5, 3),
      );

      // The on-device engine still suggests something — and not the same game.
      final suggestion = await s.recommendations.next(patientId);
      expect(suggestion.chosenOnDevice, isTrue);
      expect(suggestion.action, EngineAction.activity);
      expect(suggestion.activityId, isNot(pairs.id));

      // Saying "I'm tired" offers a break, offline too.
      final rest = await s.recommendations.next(
        patientId,
        fatigueReported: true,
      );
      expect(rest.action, EngineAction.breakTime);

      // Outbox grew: 3 × (session start, result, session end).
      expect(await h.outbox(), hasLength(9));
      final offline = await s.sync.syncProfile(patientId);
      expect(offline.outcome, SyncOutcome.offline);
      expect(await h.outbox(), hasLength(9), reason: 'nothing lost');

      // ---------------- network returns; the first reply is lost mid-sync
      h.server.online = true;
      h.server.dropNextPushResponse = true;
      await s.sync.syncProfile(patientId);
      final report = await s.sync.syncProfile(patientId);
      expect(report.outcome, SyncOutcome.success);
      expect(await h.outbox(), isEmpty);
      expect(h.server.stored['activity_result'], hasLength(3));
      expect(h.server.stored['activity_session'], hasLength(3));
    },
  );
}
