// Replays scenarios whose expected outputs were produced by the PYTHON engine
// (tool/engine_parity/generate.py). Any divergence between the server engine
// and this port fails here. All data is SYNTHETIC.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/personalization/engine.dart';
import 'package:sneha_patient/personalization/engine_config.dart';

EngineInput inputFrom(Map<String, dynamic> sc, DateTime now) {
  DateTime dt(Object? v) => DateTime.parse(v as String).toUtc();
  List<String> strings(Object? v) => (v as List? ?? const []).cast<String>();
  return EngineInput(
    now: now,
    language: sc['language'] as String? ?? 'as',
    activities: [
      for (final a in sc['activities'] as List)
        ActivityFact(
          id: a['id'] as String,
          slug: a['slug'] as String,
          minDifficulty: a['min'] as int,
          maxDifficulty: a['max'] as int,
          usesMemoryBank: a['memory'] as bool,
        ),
    ],
    results: [
      for (final r in sc['results'] as List)
        ResultFact(
          id: r['id'] as String,
          activityId: r['activity_id'] as String,
          completedAt: dt(r['completed_at']),
          difficulty: r['difficulty'] as int,
          score: (r['score'] as num?)?.toDouble(),
          hints: r['hints'] as int,
          abandoned: r['abandoned'] as bool,
          engagement: r['engagement'] as String?,
          fatigueReported: r['fatigue_reported'] as bool,
          meanResponseMs: (r['mean_response_ms'] as num?)?.toDouble(),
        ),
    ],
    interests: strings(sc['interests']),
    contextTags: strings(sc['context_tags']),
    dislikedSlugs: strings(sc['disliked']).toSet(),
    observations: [
      for (final o in sc['observations'] as List? ?? const [])
        ObservationFact(
          id: o['id'] as String,
          category: o['category'] as String,
          observedAt: dt(o['observed_at']),
        ),
    ],
    sessionEnds: [
      for (final s in sc['session_ends'] as List? ?? const [])
        SessionEndFact(
          id: s['id'] as String,
          endedAt: dt(s['ended_at']),
          endReason: s['end_reason'] as String?,
        ),
    ],
    content: {
      for (final e
          in (sc['content'] as Map<String, dynamic>? ?? const {}).entries)
        e.key: ContentAvailability(
          sufficient: e.value['sufficient'] as bool,
          memoryItemIds: strings(e.value['memory_item_ids']),
          routineItemIds: strings(e.value['routine_item_ids']),
          matchedInterests: strings(e.value['matched_interests']),
        ),
    },
    stopRequested: sc['stop'] as bool? ?? false,
    fatigueReported: sc['fatigue'] as bool? ?? false,
    availableSlugs: sc['available'] == null
        ? null
        : strings(sc['available']).toSet(),
  );
}

void main() {
  final fixture =
      jsonDecode(File('test/fixtures/engine_parity.json').readAsStringSync())
          as Map<String, dynamic>;
  final now = DateTime.parse(fixture['now'] as String).toUtc();

  test('fixture was generated for this algorithm and config version', () {
    expect(fixture['algorithm_version'], algorithmVersion);
    expect(fixture['config_version'], engineConfig.configVersion);
  });

  test('Python engine source still reports the same algorithm version', () {
    final source = File(
      '../../services/api/app/personalization/engine.py',
    ).readAsStringSync();
    expect(source, contains('ALGORITHM_VERSION = "$algorithmVersion"'));
  });

  for (final s in (fixture['scenarios'] as List).cast<Map<String, dynamic>>()) {
    final sc = s['input'] as Map<String, dynamic>;
    final expected = s['expected'] as Map<String, dynamic>;
    test('parity: ${sc['name']}', () {
      final rec = recommend(inputFrom(sc, now));
      expect(rec.action.code, expected['action']);
      expect(rec.activity?.slug, expected['activity_slug']);
      expect(rec.difficulty, expected['difficulty']);
      expect(rec.reasonCodes, expected['reason_codes']);
      expect(rec.hintsEnabled, expected['hints_enabled']);
      expect(rec.fallbackUsed, expected['fallback_used']);
      expect(rec.fallbackReason, expected['fallback_reason']);
      expect(rec.breakMinutes, expected['break_minutes']);
      expect(rec.memoryItemIds, expected['memory_item_ids']);
      expect(rec.routineItemIds, expected['routine_item_ids']);
      expect([
        for (final x in rec.supporting) [x.kind, x.id, x.detail],
      ], expected['supporting']);
    });
  }

  test('the same input always gives the same recommendation', () {
    final sc =
        (fixture['scenarios'] as List).cast<Map<String, dynamic>>()[20]['input']
            as Map<String, dynamic>;
    final a = recommend(inputFrom(sc, now));
    final b = recommend(inputFrom(sc, now));
    expect(a.reasonCodes, b.reasonCodes);
    expect(a.activity?.slug, b.activity?.slug);
  });
}
