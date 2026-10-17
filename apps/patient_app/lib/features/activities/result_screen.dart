import 'package:flutter/material.dart';

import '../../app.dart';
import '../../app_services.dart';
import '../../data/repositories/profile_repository.dart';
import '../../ui/widgets.dart';
import 'activity_launcher.dart';
import 'activity_list_screen.dart';

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

  /// "Choose another activity" always opens the activity list, wherever
  /// the activity was started from (home suggestion or the list).
  void _chooseAnother() {
    final navigator = Navigator.of(context);
    final profile = widget.profile;
    navigator.popUntil((r) => r.isFirst);
    if (profile != null) {
      navigator.push(
        MaterialPageRoute<void>(
          builder: (_) => ActivityListScreen(profile: profile),
        ),
      );
    }
  }

  void _goHome() => Navigator.of(context).popUntil((r) => r.isFirst);

  /// Step 1 of 2: the optional question, with three large answers.
  Widget _enjoyCard(BuildContext context) {
    final s = context.s;
    return SnehaCard(
      title: s.t('result_enjoy_question'),
      icon: Icons.sentiment_satisfied_alt,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
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
          const SizedBox(height: 4),
          TextButton(
            onPressed: () => _answer(null),
            child: Text(s.t('result_enjoy_skip')),
          ),
        ],
      ),
    );
  }

  Widget _header(
    BuildContext context, {
    required IconData icon,
    required String title,
    required String body,
    TextStyle? titleStyle,
  }) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Icon(icon, size: 56, color: theme.colorScheme.primary),
        const SizedBox(height: 12),
        Semantics(
          header: true,
          child: Text(
            title,
            style: titleStyle ?? theme.textTheme.headlineLarge,
            textAlign: TextAlign.center,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          body,
          style: theme.textTheme.bodyLarge,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 8),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final summary = widget.summary;
    final minutes = (summary.activeTime.inSeconds / 60).ceil().clamp(1, 600);
    // The big buttons are the only way on from here (no back arrow).
    final appBar = AppBar(
      title: Text(summary.activityTitle),
      automaticallyImplyLeading: false,
    );

    if (summary.tired) {
      return Scaffold(
        appBar: appBar,
        body: PageBody(
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: scheme.tertiaryContainer,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Icon(
                    Icons.bedtime_outlined,
                    size: 72,
                    color: scheme.onTertiaryContainer,
                  ),
                  const SizedBox(height: 12),
                  Semantics(
                    header: true,
                    child: Text(
                      s.t('result_tired_title'),
                      style: theme.textTheme.displaySmall?.copyWith(
                        color: scheme.onTertiaryContainer,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    s.t('result_tired_body'),
                    style: theme.textTheme.bodyLarge?.copyWith(
                      color: scheme.onTertiaryContainer,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            BigButton(
              label: s.t('result_rest'),
              icon: Icons.home,
              onPressed: _goHome,
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

    final asking = widget.resultId != null && !_answered;
    return Scaffold(
      appBar: appBar,
      body: PageBody(
        children: [
          _header(
            context,
            icon: summary.stopped
                ? Icons.favorite_border
                : Icons.local_florist_outlined,
            title: summary.stopped
                ? s.t('result_title_stopped')
                : s.t('result_title_done'),
            body: summary.stopped
                ? s.t('result_body_stopped')
                : s.t('result_body_done', {'name': summary.activityTitle}),
          ),
          if (asking) ...[
            _enjoyCard(context),
            // Leaving without answering is always fine.
            TextButton.icon(
              onPressed: _goHome,
              icon: const Icon(Icons.home_outlined),
              label: Text(s.t('result_home')),
            ),
          ] else ...[
            if (_answered)
              NoticeBanner(
                message: s.t('result_enjoy_thanks'),
                icon: Icons.favorite,
                tone: NoticeTone.positive,
              ),
            const SizedBox(height: 4),
            BigButton(
              label: s.t('result_again'),
              icon: Icons.replay,
              onPressed: () => widget.onPlayAgain(context),
            ),
            BigButton(
              label: s.t('result_home'),
              icon: Icons.home_outlined,
              secondary: true,
              onPressed: _goHome,
            ),
            TextButton.icon(
              onPressed: _chooseAnother,
              icon: const Icon(Icons.extension_outlined),
              label: Text(s.t('result_other')),
            ),
          ],
          // What happened, in plain words. Never a score.
          SnehaCard(
            color: scheme.surfaceContainerLow,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _fact(
                  context,
                  Icons.check_circle_outline,
                  s.tCount('result_rounds', summary.roundsPlayed),
                ),
                _fact(
                  context,
                  Icons.schedule,
                  s.t('result_time', {'minutes': minutes}),
                ),
                if (summary.hints > 0)
                  _fact(
                    context,
                    Icons.lightbulb_outline,
                    s.t('result_hints', {'count': summary.hints}),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _fact(BuildContext context, IconData icon, String text) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(icon, size: 26, color: theme.colorScheme.primary),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: theme.textTheme.bodyLarge)),
        ],
      ),
    );
  }
}
