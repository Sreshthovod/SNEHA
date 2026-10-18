import 'package:flutter/material.dart';

import '../../app.dart';
import '../../app_services.dart';
import '../../core/connectivity/server_status.dart';
import '../../data/api/models.dart';
import '../../data/repositories/profile_repository.dart';
import '../../l10n/strings.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import '../activities/activity_list_screen.dart';
import '../conversation/conversation_screen.dart';
import '../memories/story_time_screen.dart';
import '../caregiver/caregiver_screen.dart';
import 'suggestion_card.dart';

/// Screen 4: patient home.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.profile});

  final Profile profile;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  List<RoutineItem>? _today;
  bool _started = false;
  final _suggestionKey = GlobalKey<SuggestionCardState>();

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    final services = AppScope.of(context);
    _loadToday(services);
    // No activity is open on the home screen: any session left running (the
    // app was closed mid-activity) is recorded as interrupted, once.
    services.recorder
        .closeInterruptedSessions(widget.profile.patientId)
        .ignore();
    // Check the connection after the first frame (it notifies listeners);
    // if online, share progress quietly in the background.
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => _checkAndSync(services),
    );
  }

  void _checkAndSync(AppServices services) {
    services.serverStatus.refresh().then((_) async {
      if (!mounted) return;
      if (services.serverStatus.connection == ServerConnection.online) {
        await services.sync.syncProfile(widget.profile.patientId);
        await services.controller.refreshProfiles();
        if (mounted) _loadToday(services);
        await _suggestionKey.currentState?.reload();
      }
    });
  }

  Future<void> _loadToday(AppServices services) async {
    final all = await services.content.routines(widget.profile.patientId);
    final now = DateTime.now();
    if (mounted) {
      setState(() => _today = all.where((r) => r.occursOn(now)).toList());
    }
  }

  Future<void> _open(Widget screen) async {
    await Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (_) => screen));
    // Something may have been played: share it (if online), then refresh
    // the suggestion.
    await _suggestionKey.currentState?.refreshAfterActivity();
  }

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final services = AppScope.of(context);
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final profile = widget.profile;
    return Scaffold(
      // No app bar: the greeting is the title, so the main choices fit on
      // the first screen of a small phone.
      body: PageBody(
        children: [
          Row(
            children: [
              Icon(Icons.spa_outlined, size: 24, color: scheme.primary),
              const SizedBox(width: 8),
              GradientText(
                s.t('app_name'),
                style: theme.textTheme.titleSmall?.copyWith(
                  color: scheme.secondary,
                  letterSpacing: 1.2,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Semantics(
            header: true,
            child: Text(
              s.t('home_greeting', {'name': profile.greetingName}),
              style: theme.textTheme.headlineLarge,
            ),
          ),
          const SizedBox(height: 8),
          if (profile.needsRepair)
            NoticeBanner(message: s.t('home_needs_repair')),
          SuggestionCard(key: _suggestionKey, profile: profile),
          const SizedBox(height: 4),
          // Only a few large choices for the person. Caregiver tasks are one
          // tap away, behind "For caregivers".
          BigButton(
            label: s.t('home_play'),
            icon: Icons.extension_outlined,
            secondary: true,
            accent: scheme.primary,
            onPressed: () => _open(ActivityListScreen(profile: profile)),
          ),
          BigButton(
            label: s.t('home_memories'),
            icon: Icons.photo_album_outlined,
            secondary: true,
            accent: scheme.secondary,
            onPressed: () => _open(StoryTimeScreen(profile: profile)),
          ),
          BigButton(
            label: s.t('home_talk'),
            icon: Icons.chat_bubble_outline,
            secondary: true,
            accent: scheme.tertiary,
            onPressed: () => _open(ConversationScreen(profile: profile)),
          ),
          const SizedBox(height: 12),
          ListenableBuilder(
            listenable: services.serverStatus,
            builder: (context, _) =>
                ConnectionCard(connection: services.serverStatus.connection),
          ),
          SnehaCard(
            title: s.t('home_today'),
            icon: Icons.today_outlined,
            child: _today == null
                ? const SizedBox(height: 8)
                : _today!.isEmpty
                ? Text(
                    s.t('home_today_empty'),
                    style: theme.textTheme.bodyLarge,
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final r in _today!)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              SizedBox(
                                width: 72,
                                child: Text(
                                  r.localTime,
                                  style: theme.textTheme.bodyLarge?.copyWith(
                                    fontWeight: FontWeight.w600,
                                    fontFeatures: const [
                                      FontFeature.tabularFigures(),
                                    ],
                                  ),
                                ),
                              ),
                              Expanded(
                                child: Text(
                                  r.title,
                                  style: theme.textTheme.bodyLarge,
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
          ),
          const SizedBox(height: 8),
          Center(
            child: TextButton.icon(
              key: const ValueKey('home_caregiver'),
              style: TextButton.styleFrom(foregroundColor: scheme.tertiary),
              onPressed: () => _open(CaregiverScreen(profile: profile)),
              icon: const Icon(Icons.volunteer_activism_outlined),
              label: Text(s.t('home_caregiver')),
            ),
          ),
        ],
      ),
    );
  }
}

/// Always tells the user plainly what works right now. Icon + words, never
/// colour alone. A light status strip, not an alert.
class ConnectionCard extends StatelessWidget {
  const ConnectionCard({super.key, required this.connection});

  final ServerConnection connection;

  @override
  Widget build(BuildContext context) {
    final AppStrings s = context.s;
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final highContrast = SnehaTheme.isHighContrast(theme);
    final (IconData icon, String title, String body) = switch (connection) {
      ServerConnection.checking => (
        Icons.sync,
        s.t('conn_checking'),
        s.t('conn_checking_body'),
      ),
      ServerConnection.online => (
        Icons.cloud_done_outlined,
        s.t('conn_online'),
        s.t('conn_online_body'),
      ),
      ServerConnection.offline => (
        Icons.phone_android,
        s.t('conn_offline'),
        s.t('conn_offline_body'),
      ),
    };

    return Semantics(
      container: true,
      liveRegion: true,
      label: '$title. $body',
      excludeSemantics: true,
      child: Container(
        width: double.infinity,
        margin: const EdgeInsets.symmetric(vertical: 8),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: scheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: highContrast ? scheme.outline : scheme.outlineVariant,
            width: highContrast ? 3 : 1,
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 28, color: scheme.primary),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: theme.textTheme.titleMedium),
                  const SizedBox(height: 2),
                  Text(
                    body,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
