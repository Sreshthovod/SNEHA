import 'package:flutter/material.dart';

import '../../activities/activity.dart';
import '../../activities/registry.dart';
import '../../app_services.dart';
import '../../data/api/models.dart';
import '../../data/repositories/profile_repository.dart';
import '../memories/story_time_screen.dart';
import 'activity_runner_screen.dart';

/// Loads local content + difficulty and opens the generic runner.
Future<void> launchActivity(
  BuildContext context, {
  required CatalogActivity catalog,
  required Profile profile,
  bool replace = false,
  int? difficulty,
  String? recommendationId,
  bool hintsAdvised = false,
  List<String> preferredMemoryIds = const [],
  bool readAloudFirst = false,
  List<String> engineReasonCodes = const [],
  String? decidedOn,
}) async {
  final services = AppScope.of(context);
  final navigator = Navigator.of(context);
  if (catalog.slug == storyTimeSlug) {
    // Story time is unscored and has its own screen (not the runner).
    final route = MaterialPageRoute<void>(
      builder: (_) => StoryTimeScreen(
        profile: profile,
        preferredMemoryIds: preferredMemoryIds,
      ),
    );
    replace
        ? await navigator.pushReplacement(route)
        : await navigator.push(route);
    return;
  }
  final activity = activityRegistry[catalog.slug];
  if (activity == null) return; // "Coming soon" entries are disabled in the UI.
  final content = ActivityContent(
    memories: await services.content.memories(profile.patientId),
    routines: await services.content.routines(profile.patientId),
    preferredMemoryIds: preferredMemoryIds,
  );
  // A suggestion already carries the engine's difficulty; otherwise ask the
  // local engine. Either way it stays within the catalog range.
  final level =
      (difficulty ??
              await services.content.difficultyFor(profile.patientId, catalog))
          .clamp(catalog.minDifficulty, catalog.maxDifficulty);
  // Synced catalog spec (levels, instructions); null before the first sync,
  // in which case the game's bundled defaults apply.
  final spec = await services.content.spec(catalog.id);
  final route = MaterialPageRoute<void>(
    builder: (_) => ActivityRunnerScreen(
      activity: activity,
      catalog: catalog,
      profile: profile,
      content: content,
      difficulty: level,
      spec: spec,
      recommendationId: recommendationId,
      hintsAdvised: hintsAdvised,
      readAloudFirst: readAloudFirst,
      engineReasonCodes: engineReasonCodes,
      decidedOn: decidedOn,
    ),
  );
  replace
      ? await navigator.pushReplacement(route)
      : await navigator.push(route);
}
