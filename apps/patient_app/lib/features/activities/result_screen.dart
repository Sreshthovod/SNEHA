import 'package:flutter/material.dart';

import '../../app.dart';
import '../../app_services.dart';
import '../../data/repositories/profile_repository.dart';
import '../../ui/widgets.dart';
import 'activity_launcher.dart';

class RunSummary {
  const RunSummary({
    required this.activityTitle,
    required this.roundsPlayed,
    required this.hints,
    required this.activeTime,
    required this.stopped,
    this.tired = false,
  });

  final String activityTitle;
  final int roundsPlayed;
  final int hints;
  final Duration activeTime;
  final bool stopped;

  /// The person pressed "I'm tired".
  final bool tired;
}

/// Screen 13: activity result. Celebrates taking part; never grades, never
/// uses clinical or alarming words, never shows a percentage or score.
/// Asks "Did you enjoy this?" (optional) and, after "I'm tired", offers rest.
class ResultScreen extends StatefulWidget {
  const ResultScreen({
    super.key,
    required this.summary,
    required this.onPlayAgain,
    this.profile,
    this.resultId,
  });

  final RunSummary summary;
  final void Function(BuildContext context) onPlayAgain;
  final Profile? profile;

  /// The recorded result (null if nothing was recorded).
  final String? resultId;

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  bool _answered = false;

  Future<void> _answer(String? engagement) async {
    final id = widget.resultId;
    if (id != null && engagement != null) {
      await AppScope.of(context).recorder.setEngagement(id, engagement);
    }
    if (mounted) setState(() => _answered = true);
  }

  Future<void> _tryEasy() async {
    final services = AppScope.of(context);
    final profile = widget.profile!;
    final suggestion = await services.recommendations.next(profile.patientId);
    final catalog = await services.content.catalog();
    if (!mounted) return;
    final match = catalog.where((c) => c.id == suggestion.activityId);
    if (match.isEmpty) {
      Navigator.of(context).popUntil((r) => r.isFirst);
      return;
    }
    await launchActivity(
      context,
      catalog: match.first,
      profile: profile,
      replace: true,
      difficulty: suggestion.difficulty,
      recommendationId: suggestion.recommendationId,
    );
  }

  Widget _enjoyCard(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    if (_answered) {
      return NoticeBanner(
        message: s.t('result_enjoy_thanks'),
        icon: Icons.favorite,
        positive: true,
      );
    }
    return SnehaCard(
      title: s.t('result_enjoy_question'),
      icon: Icons.sentiment_satisfied_alt,
      child: Column(
        children: [
          for (final (value, key, icon) in [
            ('enjoyed', 'result_enjoy_yes', Icons.sentiment_very_satisfied),
            ('neutral', 'result_enjoy_ok', Icons.sentiment_neutral),
            ('not_enjoyed', 'result_enjoy_no', Icons.sentiment_dissatisfied),
          ])
            BigButton(
              label: s.t(key),
              icon: icon,
              secondary: true,
              onPressed: () => _answer(value),
            ),
          TextButton(
            onPressed: () => _answer(null),
            child: Text(
              s.t('result_enjoy_skip'),
              style: theme.textTheme.bodyLarge,
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    final summary = widget.summary;
    final minutes = (summary.activeTime.inSeconds / 60).ceil().clamp(1, 600);

    if (summary.tired) {
      return Scaffold(
        appBar: AppBar(title: Text(summary.activityTitle)),
        body: PageBody(
          children: [
            Icon(
              Icons.bedtime_outlined,
              size: 80,
              color: theme.colorScheme.primary,
            ),
            const SizedBox(height: 12),
            Semantics(
              header: true,
              child: Text(
                s.t('result_tired_title'),
                style: theme.textTheme.headlineLarge,
                textAlign: TextAlign.center,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              s.t('result_tired_body'),
              style: theme.textTheme.bodyLarge,
              textAlign: TextAlign.center,
            ),
            BigButton(
              label: s.t('result_rest'),
              icon: Icons.home,
              onPressed: () => Navigator.of(context).popUntil((r) => r.isFirst),
            ),
            if (widget.profile != null)
              BigButton(
                label: s.t('result_easy'),
                icon: Icons.spa_outlined,
                secondary: true,
                onPressed: _tryEasy,
              ),
          ],
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: Text(summary.activityTitle)),
      body: PageBody(
        children: [
          Icon(
            summary.stopped ? Icons.favorite_border : Icons.celebration,
            size: 80,
            color: theme.colorScheme.primary,
          ),
          const SizedBox(height: 12),
          Semantics(
            header: true,
            child: Text(
              summary.stopped
                  ? s.t('result_title_stopped')
                  : s.t('result_title_done'),
              style: theme.textTheme.headlineLarge,
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            summary.stopped
                ? s.t('result_body_stopped')
                : s.t('result_body_done', {'name': summary.activityTitle}),
            style: theme.textTheme.bodyLarge,
            textAlign: TextAlign.center,
          ),
          SnehaCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  s.t('result_rounds', {'count': summary.roundsPlayed}),
                  style: theme.textTheme.bodyLarge,
                ),
                Text(
                  s.t('result_time', {'minutes': minutes}),
                  style: theme.textTheme.bodyLarge,
                ),
                if (summary.hints > 0)
                  Text(
                    s.t('result_hints', {'count': summary.hints}),
                    style: theme.textTheme.bodyLarge,
                  ),
              ],
            ),
          ),
          if (widget.resultId != null) _enjoyCard(context),
          BigButton(
            label: s.t('result_again'),
            icon: Icons.replay,
            onPressed: () => widget.onPlayAgain(context),
          ),
          BigButton(
            label: s.t('result_other'),
            icon: Icons.extension,
            secondary: true,
            onPressed: () => Navigator.of(context).pop(),
          ),
          BigButton(
            label: s.t('result_home'),
            icon: Icons.home,
            secondary: true,
            onPressed: () => Navigator.of(context).popUntil((r) => r.isFirst),
          ),
        ],
      ),
    );
  }
}
