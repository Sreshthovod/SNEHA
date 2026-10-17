import 'dart:convert';

import '../../personalization/engine.dart';
import '../../personalization/engine_config.dart';
import '../../personalization/recommendation_source.dart';
import '../api/models.dart';
import '../api/stage7_models.dart';
import '../local/local_database.dart';

/// Read-only access to content synced to this phone: catalog, approved
/// memories, routines and difficulty state. Works fully offline.
class ContentRepository {
  ContentRepository(this._local);

  final LocalDatabase _local;

  Future<List<CatalogActivity>> catalog() async {
    final rows = await _local.db.query(
      'catalog',
      where: 'is_active = 1',
      orderBy: 'title',
    );
    return rows
        .map(
          (r) => CatalogActivity(
            id: r['id'] as String,
            slug: r['slug'] as String,
            version: r['version'] as int,
            title: r['title'] as String,
            description: r['description'] as String,
            activityType: r['activity_type'] as String,
            minDifficulty: r['min_difficulty'] as int,
            maxDifficulty: r['max_difficulty'] as int,
            defaultDurationSeconds: r['default_duration_seconds'] as int,
            usesMemoryBank: (r['uses_memory_bank'] as int) == 1,
          ),
        )
        .toList();
  }

  /// The synced spec for an activity, or null if none has been fetched yet
  /// (games then use their bundled defaults).
  Future<ActivitySpec?> spec(String activityId) async {
    final rows = await _local.db.query(
      'catalog_specs',
      where: 'activity_id = ?',
      whereArgs: [activityId],
    );
    if (rows.isEmpty) return null;
    return ActivitySpec.fromJson(
      jsonDecode(rows.first['spec_json'] as String) as Map<String, dynamic>,
    );
  }

  Future<List<MemoryItem>> memories(String patientId) async {
    final rows = await _local.db.query(
      'memories',
      where: 'patient_id = ?',
      whereArgs: [patientId],
      orderBy: 'title',
    );
    return rows
        .map(
          (r) => MemoryItem(
            id: r['id'] as String,
            patientId: r['patient_id'] as String,
            kind: r['kind'] as String,
            title: r['title'] as String,
            description: r['description'] as String?,
            approxYear: r['approx_year'] as int?,
            relationship: r['relationship'] as String?,
            tags: (jsonDecode(r['tags_json'] as String) as List).cast<String>(),
            mediaFileId: r['media_file_id'] as String?,
            version: r['version'] as int,
            localPhotoPath: r['local_photo_path'] as String?,
          ),
        )
        .toList();
  }

  /// Caregiver-made links between approved memories on this phone (the server
  /// only sends a link while both ends are approved).
  Future<List<MemoryLinkFact>> memoryLinks(String patientId) async {
    final rows = await _local.db.query(
      'memory_links',
      where: 'patient_id = ?',
      whereArgs: [patientId],
    );
    return [
      for (final r in rows)
        MemoryLinkFact(
          fromId: r['from_memory_id'] as String,
          toId: r['to_memory_id'] as String,
          type: r['relation_type'] as String,
        ),
    ];
  }

  Future<List<RoutineItem>> routines(String patientId) async {
    final rows = await _local.db.query(
      'routines',
      where: 'patient_id = ? AND is_active = 1',
      whereArgs: [patientId],
      orderBy: 'local_time',
    );
    return rows
        .map(
          (r) => RoutineItem(
            id: r['id'] as String,
            patientId: r['patient_id'] as String,
            title: r['title'] as String,
            localTime: r['local_time'] as String,
            daysOfWeek: r['days_of_week'] as int,
            isActive: true,
          ),
        )
        .toList();
  }

  /// Current difficulty for an activity, adapted ON THIS PHONE by the
  /// engagement rules (lib/personalization/engine.dart) from local results.
  /// Without local results, the synced server state (if any) or the
  /// activity's minimum is used. Always within the catalog range.
  Future<int> difficultyFor(String patientId, CatalogActivity activity) async {
    final local = await LocalFacts(
      _local,
    ).results(patientId, activityId: activity.id);
    if (local.isNotEmpty) {
      return decideDifficulty(
        ActivityFact(
          id: activity.id,
          slug: activity.slug,
          minDifficulty: activity.minDifficulty,
          maxDifficulty: activity.maxDifficulty,
          usesMemoryBank: activity.usesMemoryBank,
        ),
        local,
        engineConfig,
      ).level;
    }
    final rows = await _local.db.query(
      'personalization',
      columns: ['current_difficulty'],
      where: 'patient_id = ? AND activity_id = ?',
      whereArgs: [patientId, activity.id],
    );
    final stored = rows.isEmpty
        ? activity.minDifficulty
        : rows.first['current_difficulty'] as int;
    return stored.clamp(activity.minDifficulty, activity.maxDifficulty);
  }
}
