import 'package:flutter/material.dart';

import '../../activities/registry.dart';
import '../../app.dart';
import '../../app_services.dart';
import '../../data/repositories/profile_repository.dart';
import '../../data/repositories/progress_repository.dart';
import '../../ui/widgets.dart';
import '../sync/sync_status_screen.dart' show formatLocal;

/// Local progress: what was played on this phone. Descriptive only — no
/// grades, percentages or judgements. Works offline.
class ProgressScreen extends StatefulWidget {
  const ProgressScreen({super.key, required this.profile});

  final Profile profile;

  @override
  State<ProgressScreen> createState() => _ProgressScreenState();
}

class _ProgressScreenState extends State<ProgressScreen> {
  Future<List<ActivityProgress>>? _future;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_future != null) return;
    _load();
  }

  void _load() {
    final services = AppScope.of(context);
    _future = services.content.catalog().then(
      (catalog) =>
          services.progress.forPatient(widget.profile.patientId, catalog),
    );
  }

  IconData _iconFor(ActivityProgress p) =>
      activityRegistry[p.activity.slug]?.icon ??
      (p.activity.slug == storyTimeSlug
          ? Icons.auto_stories
          : Icons.extension_outlined);

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Scaffold(
      appBar: AppBar(title: Text(s.t('progress_title'))),
      body: FutureBuilder<List<ActivityProgress>>(
        future: _future,
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
                onPressed: () => setState(_load),
              ),
            );
          }
          if (!snap.hasData) return LoadingView(label: s.t('common_loading'));
          final items = snap.data!;
          Widget line(IconData icon, String text) => Padding(
            padding: const EdgeInsets.symmetric(vertical: 3),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.only(top: 3),
                  child: Icon(icon, size: 24, color: scheme.onSurfaceVariant),
                ),
                const SizedBox(width: 10),
                Expanded(child: Text(text, style: theme.textTheme.bodyLarge)),
              ],
            ),
          );
          return PageBody(
            children: [
              Text(
                s.t('progress_note'),
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 8),
              if (items.isEmpty)
                SnehaCard(
                  child: Row(
                    children: [
                      Icon(
                        Icons.hourglass_empty,
                        size: 28,
                        color: scheme.primary,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          s.t('progress_empty'),
                          style: theme.textTheme.bodyLarge,
                        ),
                      ),
                    ],
                  ),
                ),
              for (final p in items)
                SnehaCard(
                  title: p.activity.title,
                  icon: _iconFor(p),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Unscored activities (one level only) have no level.
                      if (p.maxLevel > 1)
                        line(
                          Icons.stairs_outlined,
                          s.t('progress_level', {
                            'level': p.level,
                            'max': p.maxLevel,
                          }),
                        ),
                      line(
                        Icons.replay,
                        s.tCount('progress_played', p.timesPlayed),
                      ),
                      if (p.lastPlayed != null)
                        line(
                          Icons.event_outlined,
                          s.t('progress_last', {
                            'date': formatLocal(p.lastPlayed!),
                          }),
                        ),
                      if (p.enjoyedCount > 0)
                        line(
                          Icons.sentiment_satisfied_alt,
                          s.t('progress_enjoyed', {'count': p.enjoyedCount}),
                        ),
                    ],
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}
