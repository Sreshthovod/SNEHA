import 'package:flutter/material.dart';

import '../../app.dart';
import '../../app_services.dart';
import '../../core/connectivity/server_status.dart';
import '../../data/api/models.dart';
import '../../data/repositories/profile_repository.dart';
import '../../l10n/strings.dart';
import '../../personalization/engine.dart';
import '../../personalization/recommendation_source.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import '../activities/activity_launcher.dart';

/// One plain-language reason for a suggestion (never a technical code).
String suggestionWhy(AppStrings s, List<String> codes) {
  bool has(Reason r) => codes.contains(r.code);
  if (has(Reason.lowEffortForFatigue)) return s.t('suggest_why_easy');
  if (has(Reason.easierAlternative)) return s.t('suggest_why_gentler');
  if (has(Reason.readAloudFirst)) return s.t('suggest_why_read_aloud');
  if (has(Reason.hintSupport)) return s.t('suggest_why_hints');
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
      hintsAdvised: _suggestion!.hintsEnabled,
      preferredMemoryIds: _suggestion!.memoryItemIds,
      readAloudFirst: _suggestion!.readAloudFirst,
      engineReasonCodes: _suggestion!.reasonCodes,
      decidedOn: _suggestion!.chosenOnDevice ? 'device' : 'server',
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
    final scheme = theme.colorScheme;
    final suggestion = _suggestion;
    final activity = _activity;

    final hasSuggestion =
        !_loading &&
        suggestion != null &&
        activity != null &&
        suggestion.action != EngineAction.none &&
        suggestion.action != EngineAction.stop;
    final resting =
        hasSuggestion && suggestion.action == EngineAction.breakTime;
    // A rest suggestion is as positive as an activity: warm, not alarming.
    final bg = resting ? scheme.tertiaryContainer : scheme.primaryContainer;
    final fg = resting ? scheme.onTertiaryContainer : scheme.onPrimaryContainer;

    final children = <Widget>[
      Row(
        children: [
          Icon(
            resting ? Icons.bedtime_outlined : Icons.spa_outlined,
            size: 28,
            color: fg,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Semantics(
              header: true,
              child: Text(
                s.t('suggest_title'),
                style: theme.textTheme.titleMedium?.copyWith(color: fg),
              ),
            ),
          ),
        ],
      ),
      const SizedBox(height: 8),
    ];

    if (_loading) {
      // Reserve the space so the page does not jump when it arrives.
      children.add(
        ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 96),
          child: Text(
            s.t('suggest_loading'),
            style: theme.textTheme.bodyLarge?.copyWith(color: fg),
          ),
        ),
      );
    } else if (!hasSuggestion) {
      children.add(
        Text(
          s.t('suggest_none'),
          style: theme.textTheme.bodyLarge?.copyWith(color: fg),
        ),
      );
    } else {
      children.addAll([
        if (resting) ...[
          Text(
            s.t('suggest_break_title'),
            style: theme.textTheme.headlineSmall?.copyWith(color: fg),
          ),
          Text(
            s.t('suggest_break_body', {
              'minutes': suggestion.breakMinutes ?? 10,
            }),
            style: theme.textTheme.bodyLarge?.copyWith(color: fg),
          ),
          const SizedBox(height: 8),
        ],
        Text(
          activity.title,
          style:
              (resting
                      ? theme.textTheme.titleLarge
                      : theme.textTheme.headlineSmall)
                  ?.copyWith(color: fg),
        ),
        const SizedBox(height: 2),
        Text(
          suggestionWhy(s, suggestion.reasonCodes),
          style: theme.textTheme.bodyLarge?.copyWith(color: fg),
        ),
        const SizedBox(height: 4),
        Row(
          children: [
            Icon(
              suggestion.chosenOnDevice
                  ? Icons.phone_android
                  : Icons.cloud_done_outlined,
              size: 20,
              color: scheme.onSurfaceVariant,
            ),
            const SizedBox(width: 6),
            Flexible(
              child: Text(
                suggestion.chosenOnDevice
                    ? s.t('suggest_device')
                    : s.t('suggest_server'),
                style: theme.textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        BigButton(
          label: resting ? s.t('suggest_easy') : s.t('suggest_start'),
          icon: resting ? Icons.spa_outlined : Icons.play_arrow,
          secondary: resting,
          onPressed: _start,
        ),
      ]);
    }

    final flags = SnehaTheme.flags(theme);
    return SnehaCard(
      color: bg,
      gradient: resting ? flags.restGradient : flags.softGradient,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: children,
      ),
    );
  }
}
