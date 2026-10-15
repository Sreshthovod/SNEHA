import 'package:flutter/material.dart';

import '../../app.dart';
import '../../app_services.dart';
import '../../core/connectivity/server_status.dart';
import '../../data/api/models.dart';
import '../../data/repositories/profile_repository.dart';
import '../../l10n/strings.dart';
import '../../ui/widgets.dart';
import '../activities/activity_list_screen.dart';
import '../conversation/conversation_screen.dart';
import '../memories/story_time_screen.dart';
import '../privacy/privacy_screen.dart';
import '../progress/progress_screen.dart';
import 'suggestion_card.dart';
import '../settings/settings_screen.dart';
import '../sync/sync_status_screen.dart';

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
    final profile = widget.profile;
    return Scaffold(
      appBar: AppBar(title: Text(s.t('app_name'))),
      body: PageBody(
        children: [
          Semantics(
            header: true,
            child: Text(
              s.t('home_greeting', {'name': profile.greetingName}),
              style: theme.textTheme.headlineLarge,
            ),
          ),
          const SizedBox(height: 16),
          ListenableBuilder(
            listenable: services.serverStatus,
            builder: (context, _) =>
                ConnectionCard(connection: services.serverStatus.connection),
          ),
          if (profile.needsRepair)
            NoticeBanner(message: s.t('home_needs_repair')),
          SuggestionCard(key: _suggestionKey, profile: profile),
          SnehaCard(
            title: s.t('home_today'),
            icon: Icons.today,
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
                          child: Text(
                            '${r.localTime}  ${r.title}',
                            style: theme.textTheme.bodyLarge,
                          ),
                        ),
                    ],
                  ),
          ),
          const SizedBox(height: 8),
          BigButton(
            label: s.t('home_play'),
            icon: Icons.extension,
            onPressed: () => _open(ActivityListScreen(profile: profile)),
          ),
          BigButton(
            label: s.t('home_memories'),
            icon: Icons.photo_album,
            onPressed: () => _open(StoryTimeScreen(profile: profile)),
          ),
          BigButton(
            label: s.t('home_progress'),
            icon: Icons.insights_outlined,
            secondary: true,
            onPressed: () => _open(ProgressScreen(profile: profile)),
          ),
          BigButton(
            label: s.t('home_talk'),
            icon: Icons.chat_bubble_outline,
            onPressed: () => _open(ConversationScreen(profile: profile)),
          ),
          const SizedBox(height: 12),
          BigButton(
            label: s.t('home_settings'),
            icon: Icons.settings,
            secondary: true,
            onPressed: () => _open(SettingsScreen(profile: profile)),
          ),
          BigButton(
            label: s.t('home_sync'),
            icon: Icons.sync,
            secondary: true,
            onPressed: () => _open(SyncStatusScreen(profile: profile)),
          ),
          BigButton(
            label: s.t('home_privacy'),
            icon: Icons.lock_outline,
            secondary: true,
            onPressed: () => _open(PrivacyScreen(profile: profile)),
          ),
          BigButton(
            label: s.t('home_switch'),
            icon: Icons.people_outline,
            secondary: true,
            onPressed: () => services.controller.selectProfile(null),
          ),
        ],
      ),
    );
  }
}

/// Always tells the user plainly what works right now. Icon + words, never colour alone.
class ConnectionCard extends StatelessWidget {
  const ConnectionCard({super.key, required this.connection});

  final ServerConnection connection;

  @override
  Widget build(BuildContext context) {
    final AppStrings s = context.s;
    final theme = Theme.of(context);
    final (IconData icon, String title, String body) = switch (connection) {
      ServerConnection.checking => (
        Icons.sync,
        s.t('conn_checking'),
        s.t('conn_checking_body'),
      ),
      ServerConnection.online => (
        Icons.cloud_done,
        s.t('conn_online'),
        s.t('conn_online_body'),
      ),
      ServerConnection.offline => (
        Icons.phone_android,
        s.t('conn_offline'),
        s.t('conn_offline_body'),
      ),
    };

    return Card(
      child: Semantics(
        container: true,
        liveRegion: true,
        label: '$title. $body',
        excludeSemantics: true,
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: 40, color: theme.colorScheme.primary),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: theme.textTheme.titleLarge),
                    const SizedBox(height: 4),
                    Text(body, style: theme.textTheme.bodyLarge),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
