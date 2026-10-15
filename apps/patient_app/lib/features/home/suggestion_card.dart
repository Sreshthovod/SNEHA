import 'package:flutter/material.dart';

import '../../app.dart';
import '../../app_services.dart';
import '../../core/connectivity/server_status.dart';
import '../../data/api/models.dart';
import '../../data/repositories/profile_repository.dart';
import '../../l10n/strings.dart';
import '../../personalization/engine.dart';
import '../../personalization/recommendation_source.dart';
import '../../ui/widgets.dart';
import '../activities/activity_launcher.dart';

/// One plain-language reason for a suggestion (never a technical code).
String suggestionWhy(AppStrings s, List<String> codes) {
  bool has(Reason r) => codes.contains(r.code);
  if (has(Reason.lowEffortForFatigue)) return s.t('suggest_why_easy');
  if (has(Reason.interestMatch)) return s.t('suggest_why_interest');
  if (has(Reason.conversationContextMatch)) return s.t('suggest_why_talk');
  if (has(Reason.memoryContentUsed)) return s.t('suggest_why_memories');
  if (has(Reason.personalRoutinesUsed)) return s.t('suggest_why_routine');
  if (has(Reason.enjoyedBefore)) return s.t('suggest_why_enjoyed');
  if (has(Reason.lowEngagementSwitch) || has(Reason.avoidRepetition)) {
    return s.t('suggest_why_change');
  }
  if (has(Reason.coldStartDefault)) return s.t('suggest_why_new');
  if (has(Reason.familiarActivity)) return s.t('suggest_why_familiar');
  return s.t('suggest_why_default');
}

/// "Suggested for you" on the home screen. Uses [AppServices.recommendations]
/// (the on-device engine unless server recommendations are switched on).
class SuggestionCard extends StatefulWidget {
  const SuggestionCard({super.key, required this.profile});

  final Profile profile;

  @override
  State<SuggestionCard> createState() => SuggestionCardState();
}

class SuggestionCardState extends State<SuggestionCard> {
  Suggestion? _suggestion;
  CatalogActivity? _activity;
  bool _loading = true;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_loading && _suggestion == null) reload();
  }

  Future<void> reload() async {
    final services = AppScope.of(context);
    try {
      final suggestion = await services.recommendations.next(
        widget.profile.patientId,
      );
      final catalog = await services.content.catalog();
      final match = catalog.where((c) => c.id == suggestion.activityId);
      if (!mounted) return;
      setState(() {
        _suggestion = suggestion;
        _activity = match.isEmpty ? null : match.first;
        _loading = false;
      });
    } on Object {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _start() async {
    await launchActivity(
      context,
      catalog: _activity!,
      profile: widget.profile,
      difficulty: _suggestion!.difficulty,
      recommendationId: _suggestion!.recommendationId,
    );
    if (mounted) await refreshAfterActivity();
  }

  /// After something was played: share the new result first when online (so
  /// the server's next suggestion takes it into account), then ask again.
  /// Offline, the phone's own engine already sees the local result.
  Future<void> refreshAfterActivity() async {
    final services = AppScope.of(context);
    if (services.serverStatus.connection == ServerConnection.online) {
      await services.sync.syncProfile(widget.profile.patientId);
    }
    if (mounted) await reload();
  }

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    final suggestion = _suggestion;
    final activity = _activity;

    Widget body;
    if (_loading) {
      body = Text(s.t('suggest_loading'), style: theme.textTheme.bodyLarge);
    } else if (suggestion == null ||
        activity == null ||
        suggestion.action == EngineAction.none ||
        suggestion.action == EngineAction.stop) {
      body = Text(s.t('suggest_none'), style: theme.textTheme.bodyLarge);
    } else {
      final resting = suggestion.action == EngineAction.breakTime;
      body = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (resting) ...[
            Text(s.t('suggest_break_title'), style: theme.textTheme.titleLarge),
            Text(
              s.t('suggest_break_body', {
                'minutes': suggestion.breakMinutes ?? 10,
              }),
              style: theme.textTheme.bodyLarge,
            ),
            const SizedBox(height: 8),
          ],
          Text(activity.title, style: theme.textTheme.titleLarge),
          Text(
            suggestionWhy(s, suggestion.reasonCodes),
            style: theme.textTheme.bodyLarge,
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              Icon(
                suggestion.chosenOnDevice
                    ? Icons.phone_android
                    : Icons.cloud_done,
                size: 20,
              ),
              const SizedBox(width: 6),
              Flexible(
                child: Text(
                  suggestion.chosenOnDevice
                      ? s.t('suggest_device')
                      : s.t('suggest_server'),
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ],
          ),
          BigButton(
            label: resting ? s.t('suggest_easy') : s.t('suggest_start'),
            icon: resting ? Icons.spa_outlined : Icons.play_arrow,
            onPressed: _start,
          ),
        ],
      );
    }
    return SnehaCard(
      title: s.t('suggest_title'),
      icon: Icons.auto_awesome_outlined,
      child: body,
    );
  }
}
