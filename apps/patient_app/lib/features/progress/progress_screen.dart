import 'package:flutter/material.dart';

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
    final services = AppScope.of(context);
    _future = services.content.catalog().then(
      (catalog) =>
          services.progress.forPatient(widget.profile.patientId, catalog),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(s.t('progress_title'))),
      body: FutureBuilder<List<ActivityProgress>>(
        future: _future,
        builder: (context, snap) {
          if (snap.hasError) {
            return MessageView(
              icon: Icons.error_outline,
              title: s.t('error_generic'),
              body: '',
            );
          }
          if (!snap.hasData) return LoadingView(label: s.t('common_loading'));
          final items = snap.data!;
          return PageBody(
            children: [
              Text(s.t('progress_note'), style: theme.textTheme.bodyLarge),
              if (items.isEmpty)
                MessageView(
                  icon: Icons.hourglass_empty,
                  title: s.t('progress_empty'),
                  body: '',
                ),
              for (final p in items)
                SnehaCard(
                  title: p.activity.title,
                  icon: Icons.extension,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        s.t('progress_level', {
                          'level': p.level,
                          'max': p.maxLevel,
                        }),
                        style: theme.textTheme.bodyLarge,
                      ),
                      Text(
                        s.t('progress_played', {'count': p.timesPlayed}),
                        style: theme.textTheme.bodyLarge,
                      ),
                      if (p.lastPlayed != null)
                        Text(
                          s.t('progress_last', {
                            'date': formatLocal(p.lastPlayed!),
                          }),
                          style: theme.textTheme.bodyLarge,
                        ),
                      if (p.enjoyedCount > 0)
                        Text(
                          s.t('progress_enjoyed', {'count': p.enjoyedCount}),
                          style: theme.textTheme.bodyLarge,
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
