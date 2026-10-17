import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../activities/registry.dart';
import '../data/api/api_client.dart';
import '../data/api/stage7_models.dart';
import '../data/local/local_database.dart';
import '../data/repositories/clock.dart';
import '../data/repositories/profile_repository.dart';
import 'engine.dart';
import 'engine_config.dart';

/// A suggestion shown on the home screen.
class Suggestion {
  const Suggestion({
    required this.action,
    required this.activityId,
    required this.difficulty,
    required this.reasonCodes,
    required this.chosenOnDevice,
    this.recommendationId,
    this.breakMinutes,
    this.hintsEnabled = false,
    this.memoryItemIds = const [],
    this.readAloudFirst = false,
  });

  final EngineAction action;
  final String? activityId;
  final int? difficulty;
  final List<String> reasonCodes;

  /// True when the local engine chose it (works offline).
  final bool chosenOnDevice;

  /// Only set for server recommendations (sent back with the result).
  final String? recommendationId;
  final int? breakMinutes;

  /// The engine advises hints (recent struggle or tiredness).
  final bool hintsEnabled;

  /// Approved memories the engine chose for this activity, most relevant
  /// first.
  final List<String> memoryItemIds;

  /// The person often asked to hear questions again: read each one aloud.
  final bool readAloudFirst;
}

/// Where suggestions come from. The UI depends only on this interface.
abstract interface class RecommendationSource {
  Future<Suggestion> next(
    String patientId, {
    bool stopRequested = false,
    bool fatigueReported = false,
  });
}

/// Builds engine facts from what is stored on this phone.
class LocalFacts {
  LocalFacts(this._local, {Clock clock = systemClock}) : _clock = clock;

  final LocalDatabase _local;
  final Clock _clock;

  /// Slugs this app can actually run (registered games + story time).
  static Set<String> get playableSlugs => {
    ...activityRegistry.keys,
    storyTimeSlug,
  };

  Future<List<ActivityFact>> activities() async {
    final rows = await _local.db.query('catalog', where: 'is_active = 1');
    return [
      for (final r in rows)
        ActivityFact(
          id: r['id'] as String,
          slug: r['slug'] as String,
          minDifficulty: r['min_difficulty'] as int,
          maxDifficulty: r['max_difficulty'] as int,
          usesMemoryBank: (r['uses_memory_bank'] as int) == 1,
        ),
    ];
  }

  Future<List<ResultFact>> results(
    String patientId, {
    String? activityId,
  }) async {
    final rows = await _local.db.query(
      'results',
      where: activityId == null
          ? 'patient_id = ?'
          : 'patient_id = ? AND activity_id = ?',
      whereArgs: [patientId, ?activityId],
      orderBy: 'completed_at, rowid',
    );
    return [
      for (final r in rows)
        ResultFact(
          id: r['id'] as String,
          activityId: r['activity_id'] as String,
          completedAt: DateTime.parse(r['completed_at'] as String).toUtc(),
          difficulty: r['difficulty_level'] as int,
          score: (r['score'] as num?)?.toDouble(),
          hints: r['hint_count'] as int,
          abandoned: (r['abandoned'] as int) == 1,
          engagement: r['engagement'] as String?,
          fatigueReported: (r['fatigue_reported'] as int? ?? 0) == 1,
          meanResponseMs:
              ((jsonDecode(r['metrics_json'] as String)
                          as Map)['mean_response_ms']
                      as num?)
                  ?.toDouble(),
          instructionsRepeated:
              ((jsonDecode(r['metrics_json'] as String)
                          as Map)['instructions_repeated']
                      as num?)
                  ?.toInt(),
        ),
    ];
  }

  Future<List<SessionEndFact>> sessionEnds(String patientId) async {
    final rows = await _local.db.query(
      'sessions',
      where: 'patient_id = ? AND ended_at IS NOT NULL',
      whereArgs: [patientId],
    );
    return [
      for (final r in rows)
        SessionEndFact(
          id: r['id'] as String,
          endedAt: DateTime.parse(r['ended_at'] as String).toUtc(),
          endReason: r['end_reason'] as String?,
        ),
    ];
  }

  /// Caregiver tiredness reports kept on this phone (made here, or pulled
  /// from the dashboard), as engine observations. Level and time only.
  Future<List<ObservationFact>> fatigueObservations(String patientId) async {
    final since = _clock().subtract(
      Duration(
        minutes: (engineConfig.fatigue.observationWindowHours * 60).ceil(),
      ),
    );
    final rows = await _local.db.query(
      'fatigue_reports',
      where: 'patient_id = ? AND reported_at >= ?',
      whereArgs: [patientId, isoUtc(since)],
      orderBy: 'reported_at',
    );
    return [
      for (final r in rows)
        ObservationFact(
          id: r['id'] as String,
          category: 'fatigue',
          observedAt: DateTime.parse(r['reported_at'] as String).toUtc(),
          fatigueLevel: r['level'] as String,
        ),
    ];
  }

  Future<({List<String> interests, Set<String> disliked})> preferences(
    String patientId,
  ) async {
    final rows = await _local.db.query(
      'preferences',
      where: 'patient_id = ?',
      whereArgs: [patientId],
    );
    if (rows.isEmpty) return (interests: <String>[], disliked: <String>{});
    return (
      interests: (jsonDecode(rows.first['interests_json'] as String) as List)
          .cast<String>(),
      disliked: (jsonDecode(rows.first['disliked_json'] as String) as List)
          .cast<String>()
          .toSet(),
    );
  }

  /// Whether Memory Bank activities have enough approved content, using the
  /// same thresholds as the server (engine_config.dart memory rules).
  Future<Map<String, ContentAvailability>> content(
    String patientId,
    List<String> interests,
  ) async {
    final m = engineConfig.memory;
    final memories = await _local.db.query(
      'memories',
      where: 'patient_id = ?',
      whereArgs: [patientId],
      orderBy: 'title, id',
    );
    final routines = await _local.db.query(
      'routines',
      where: 'patient_id = ? AND is_active = 1',
      whereArgs: [patientId],
      orderBy: 'local_time, id',
    );
    final wanted = {for (final i in interests) i.toLowerCase()};
    bool hasPhoto(Map<String, Object?> r) => r['local_photo_path'] != null;
    List<String> tagsOf(Map<String, Object?> r) =>
        (jsonDecode(r['tags_json'] as String) as List)
            .cast<String>()
            .map((t) => t.toLowerCase())
            .toList();

    ContentAvailability from(List<Map<String, Object?>> items, int minimum) {
      final ids = [
        for (final r in items.take(m.itemsPerActivity)) r['id'] as String,
      ];
      final matched = {
        for (final r in items) ...tagsOf(r).where(wanted.contains),
      }.toList()..sort();
      return ContentAvailability(
        sufficient: items.length >= minimum,
        memoryItemIds: items.length >= minimum ? ids : const [],
        matchedInterests: matched,
      );
    }

    final photos = memories.where(hasPhoto).toList();
    final people = photos.where((r) => r['kind'] == 'person').toList();
    final personal = routines.length >= m.minRoutineItems;
    return {
      'photo-recall': from(photos, m.minPhotoMemories),
      'familiar-faces': from(people, m.minPersonPhotoMemories),
      'story-time': from(memories, m.minStoryMemories),
      // Generic bundled steps always work; the patient's own routines are
      // used when there are enough of them.
      'daily-sequence': ContentAvailability(
        sufficient: true,
        routineItemIds: personal
            ? [for (final r in routines) r['id'] as String]
            : const [],
      ),
    };
  }

  /// Activities this phone can run RIGHT NOW: registered games plus story
  /// time, minus Memory Bank activities without enough approved content
  /// (including downloaded photos) on this phone. Sent to the server so it
  /// never suggests something the phone cannot play.
  Future<List<String>> availableSlugs(String patientId) async {
    final prefs = await preferences(patientId);
    final content = await this.content(patientId, prefs.interests);
    return [
      for (final slug in playableSlugs)
        if (content[slug]?.sufficient ?? true) slug,
    ]..sort();
  }

  Future<EngineInput> input(
    Profile profile, {
    bool stopRequested = false,
    bool fatigueReported = false,
  }) async {
    final prefs = await preferences(profile.patientId);
    return EngineInput(
      now: _clock(),
      language: profile.preferredLanguage,
      activities: await activities(),
      results: await results(profile.patientId),
      interests: prefs.interests,
      dislikedSlugs: prefs.disliked,
      // Only caregiver tiredness reports reach the phone (level and time,
      // never note text); other observations stay on the server.
      observations: await fatigueObservations(profile.patientId),
      sessionEnds: await sessionEnds(profile.patientId),
      content: await content(profile.patientId, prefs.interests),
      stopRequested: stopRequested,
      fatigueReported: fatigueReported,
      availableSlugs: playableSlugs,
    );
  }
}

/// The on-device engine: works with no network at all.
class LocalRecommendationSource implements RecommendationSource {
  LocalRecommendationSource(this._facts, this._profiles);

  final LocalFacts _facts;
  final ProfileRepository _profiles;

  @override
  Future<Suggestion> next(
    String patientId, {
    bool stopRequested = false,
    bool fatigueReported = false,
  }) async {
    final profile = await _profiles.get(patientId);
    if (profile == null) throw StateError('Unknown profile $patientId');
    final rec = recommend(
      await _facts.input(
        profile,
        stopRequested: stopRequested,
        fatigueReported: fatigueReported,
      ),
    );
    return Suggestion(
      action: rec.action,
      activityId: rec.activity?.id,
      difficulty: rec.difficulty,
      reasonCodes: rec.reasonCodes,
      chosenOnDevice: true,
      breakMinutes: rec.breakMinutes,
      hintsEnabled: rec.hintsEnabled,
      memoryItemIds: rec.memoryItemIds,
      readAloudFirst: rec.readAloudFirst,
    );
  }
}

/// Server recommendations (POST /api/v1/activities/next) are used whenever
/// the server is reachable; the on-device engine is the fallback. Wired and
/// verified in Stage 7.
const serverRecommendationsEnabled = true;

/// Server engine first (it also sees caregiver observations), local engine
/// whenever the server is unreachable, refuses, or suggests something this
/// phone cannot play.
class ServerFirstRecommendationSource implements RecommendationSource {
  ServerFirstRecommendationSource(
    this._api,
    this._profiles,
    this._local,
    this._facts,
  );

  final SnehaApiClient _api;
  final ProfileRepository _profiles;
  final RecommendationSource _local;
  final LocalFacts _facts;

  static EngineAction _action(String code) => EngineAction.values.firstWhere(
    (a) => a.code == code,
    orElse: () => EngineAction.none,
  );

  @override
  Future<Suggestion> next(
    String patientId, {
    bool stopRequested = false,
    bool fatigueReported = false,
  }) async {
    final profile = await _profiles.get(patientId);
    final token = await _profiles.token(patientId);
    if (profile != null && token != null && !profile.needsRepair) {
      try {
        final available = await _facts.availableSlugs(patientId);
        final rec = ServerRecommendation.fromJson(
          await _api.nextActivity(
            token,
            patientId: patientId,
            stopRequested: stopRequested,
            fatigueReported: fatigueReported,
            availableSlugs: available,
          ),
        );
        final action = _action(rec.action);
        final known = {for (final a in await _facts.activities()) a.id};
        final playable =
            rec.activityId == null ||
            (known.contains(rec.activityId) &&
                available.contains(rec.activitySlug));
        if (playable) {
          return Suggestion(
            action: action,
            activityId: rec.activityId,
            difficulty: rec.difficulty,
            reasonCodes: rec.reasonCodes,
            chosenOnDevice: false,
            recommendationId: rec.id,
            breakMinutes: rec.breakMinutes,
            hintsEnabled: rec.hintsEnabled,
            memoryItemIds: rec.memoryItemIds,
            readAloudFirst: rec.readAloudFirst,
          );
        }
        debugPrint('Recommendation: server suggested an unplayable activity');
      } on ApiException catch (e) {
        debugPrint('Recommendation: server unavailable (${e.code})');
      } on Object catch (e) {
        // Unexpected response shape: never trust it, use the phone's engine.
        debugPrint('Recommendation: invalid server response ($e)');
      }
    }
    return _local.next(
      patientId,
      stopRequested: stopRequested,
      fatigueReported: fatigueReported,
    );
  }
}
