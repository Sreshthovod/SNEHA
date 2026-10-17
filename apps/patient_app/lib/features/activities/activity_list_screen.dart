import 'package:flutter/material.dart';

import '../../activities/activity.dart';
import '../../activities/registry.dart';
import '../../app.dart';
import '../../app_services.dart';
import '../../data/api/models.dart';
import '../../data/repositories/profile_repository.dart';
import '../../ui/widgets.dart';
import '../memories/story_time_screen.dart';
import 'activity_launcher.dart';

/// Screen 5: cognitive activity selection, built from the synced catalog.
class ActivityListScreen extends StatefulWidget {
  const ActivityListScreen({super.key, required this.profile});

  final Profile profile;

  @override
  State<ActivityListScreen> createState() => _ActivityListScreenState();
}

class _ActivityListScreenState extends State<ActivityListScreen> {
  late Future<(List<CatalogActivity>, ActivityContent)> _data;
  bool _loaded = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_loaded) {
      _loaded = true;
      _data = _load();
    }
  }

  Future<(List<CatalogActivity>, ActivityContent)> _load() async {
    final content = AppScope.of(context).content;
    final pid = widget.profile.patientId;
    return (
      await content.catalog(),
      ActivityContent(
        memories: await content.memories(pid),
        routines: await content.routines(pid),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    return Scaffold(
      appBar: AppBar(title: Text(s.t('activities_title'))),
      body: FutureBuilder(
        future: _data,
        builder: (context, snap) {
          if (snap.hasError) {
            return MessageView(
              icon: Icons.cloud_off_outlined,
              quiet: true,
              title: s.t('error_generic'),
              body: s.t('runner_error_body'),
              action: BigButton(
                label: s.t('common_retry'),
                icon: Icons.refresh,
                onPressed: () => setState(() => _data = _load()),
              ),
              secondaryAction: BigButton(
                label: s.t('result_home'),
                icon: Icons.home_outlined,
                secondary: true,
                onPressed: () => Navigator.of(context).pop(),
              ),
            );
          }
          if (!snap.hasData) return LoadingView(label: s.t('common_loading'));
          final (catalog, content) = snap.data!;
          if (catalog.isEmpty) {
            return MessageView(
              icon: Icons.cloud_download_outlined,
              title: s.t('activities_empty_title'),
              body: s.t('activities_empty_body'),
              action: BigButton(
                label: s.t('result_home'),
                icon: Icons.home_outlined,
                secondary: true,
                onPressed: () => Navigator.of(context).pop(),
              ),
            );
          }
          // Playable first, "coming soon" last.
          int rank(CatalogActivity c) =>
              activityRegistry.containsKey(c.slug) || c.slug == storyTimeSlug
              ? 0
              : 1;
          final sorted = [...catalog]..sort((a, b) => rank(a) - rank(b));
          return PageBody(
            children: [
              for (final c in sorted)
                _ActivityCard(
                  catalog: c,
                  content: content,
                  profile: widget.profile,
                ),
            ],
          );
        },
      ),
    );
  }
}

class _ActivityCard extends StatelessWidget {
  const _ActivityCard({
    required this.catalog,
    required this.content,
    required this.profile,
  });

  final CatalogActivity catalog;
  final ActivityContent content;
  final Profile profile;

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    final activity = activityRegistry[catalog.slug];
    final isStory = catalog.slug == storyTimeSlug;

    String? disabledReason;
    VoidCallback? onStart;
    if (isStory) {
      onStart = () => Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => StoryTimeScreen(profile: profile),
        ),
      );
    } else if (activity == null) {
      disabledReason = s.t('activities_coming_soon');
    } else {
      final reason = activity.unavailableReason(content);
      if (reason != null) {
        disabledReason = s.t(reason);
      } else {
        onStart = () =>
            launchActivity(context, catalog: catalog, profile: profile);
      }
    }

    final scheme = theme.colorScheme;
    final available = onStart != null;
    final icon =
        activity?.icon ??
        (isStory ? Icons.auto_stories : Icons.hourglass_empty);
    return SnehaCard(
      color: available ? null : scheme.surfaceContainerLow,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: available
                      ? scheme.primaryContainer
                      : scheme.surfaceContainer,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  icon,
                  size: 30,
                  color: available
                      ? scheme.onPrimaryContainer
                      : scheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Semantics(
                      header: true,
                      child: Text(
                        catalog.title,
                        style: theme.textTheme.titleLarge,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      catalog.description,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (disabledReason != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Row(
                children: [
                  Icon(
                    Icons.schedule,
                    size: 24,
                    color: scheme.onSurfaceVariant,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      disabledReason,
                      style: theme.textTheme.bodyLarge?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 8),
          BigButton(
            label: s.t('activities_start', {'name': catalog.title}),
            icon: Icons.play_arrow,
            secondary: true,
            onPressed: onStart,
          ),
        ],
      ),
    );
  }
}
