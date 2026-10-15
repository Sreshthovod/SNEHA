import '../../personalization/engine.dart';
import '../../personalization/engine_config.dart';
import '../../personalization/recommendation_source.dart';
import '../api/models.dart';

/// Descriptive progress for one activity. No grades, no scores shown.
class ActivityProgress {
  const ActivityProgress({
    required this.activity,
    required this.level,
    required this.maxLevel,
    required this.timesPlayed,
    required this.enjoyedCount,
    this.lastPlayed,
  });

  final CatalogActivity activity;
  final int level;
  final int maxLevel;
  final int timesPlayed;
  final int enjoyedCount;
  final DateTime? lastPlayed;
}

/// Computed entirely from this phone's data, so it works offline.
class ProgressRepository {
  ProgressRepository(this._facts);

  final LocalFacts _facts;

  Future<List<ActivityProgress>> forPatient(
    String patientId,
    List<CatalogActivity> catalog,
  ) async {
    final all = await _facts.results(patientId);
    final out = <ActivityProgress>[];
    for (final a in catalog) {
      final mine = all.where((r) => r.activityId == a.id).toList();
      if (mine.isEmpty) continue;
      final decision = decideDifficulty(
        ActivityFact(
          id: a.id,
          slug: a.slug,
          minDifficulty: a.minDifficulty,
          maxDifficulty: a.maxDifficulty,
          usesMemoryBank: a.usesMemoryBank,
        ),
        mine,
        engineConfig,
      );
      out.add(
        ActivityProgress(
          activity: a,
          level: decision.level,
          maxLevel: a.maxDifficulty,
          timesPlayed: mine.length,
          enjoyedCount: mine.where((r) => r.engagement == 'enjoyed').length,
          lastPlayed: mine.last.completedAt,
        ),
      );
    }
    out.sort((x, y) => y.lastPlayed!.compareTo(x.lastPlayed!));
    return out;
  }
}
