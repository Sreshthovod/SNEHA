import 'package:flutter/material.dart';

import '../../activities/activity.dart';
import '../../activities/run_tracker.dart';
import '../../app.dart';
import '../../app_services.dart';
import '../../data/api/models.dart';
import '../../data/api/stage7_models.dart';
import '../../data/repositories/profile_repository.dart';
import '../../ui/read_aloud.dart';
import '../../ui/widgets.dart';
import 'activity_launcher.dart';
import 'result_screen.dart';

/// The ONE generic screen that runs every game (screens 6–11): pause, hint,
/// skip, stop, progress, timing and result recording live here, so a new game
/// only supplies rounds.
class ActivityRunnerScreen extends StatefulWidget {
  const ActivityRunnerScreen({
    super.key,
    required this.activity,
    required this.catalog,
    required this.profile,
    required this.content,
    required this.difficulty,
    this.spec,
    this.recommendationId,
  });

  final CognitiveActivity activity;
  final CatalogActivity catalog;
  final Profile profile;
  final ActivityContent content;
  final int difficulty;

  /// Catalog spec for this activity (null before the first sync).
  final ActivitySpec? spec;

  /// Server recommendation this run follows (null for on-device suggestions).
  final String? recommendationId;

  @override
  State<ActivityRunnerScreen> createState() => _ActivityRunnerScreenState();
}

class _ActivityRunnerScreenState extends State<ActivityRunnerScreen>
    implements RoundHost {
  late AppServices _services;
  List<RoundSpec>? _rounds;
  RunTracker? _tracker;
  String? _sessionId;
  String? _hintMessage;
  bool _saving = false;
  Object? _error;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_rounds != null) return;
    _services = AppScope.of(context);
    _rounds = widget.activity.createRounds(
      content: widget.content,
      difficulty: widget.difficulty,
      random: _services.random,
      strings: _services.controller.strings,
      level: LevelParams.of(widget.spec, widget.difficulty),
    );
    _start();
  }

  Future<void> _start() async {
    try {
      final (id, _) = await _services.recorder.startSession(
        widget.profile.patientId,
      );
      if (!mounted) return;
      setState(() {
        _sessionId = id;
        // Created after the session so results never start before it.
        _tracker = RunTracker(
          totalRounds: _rounds!.length,
          clock: _services.clock,
        );
      });
    } on Object catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  RoundSpec get _round => _rounds![_tracker!.roundIndex];

  // ----- RoundHost -----

  @override
  void attempt({required bool correct}) => _tracker!.attempt(correct: correct);

  @override
  void solved() {
    _tracker!.solveRound();
    _afterRound();
  }

  void _afterRound() {
    if (_tracker!.finished) {
      _finish(abandoned: false);
    } else {
      setState(() => _hintMessage = null);
    }
  }

  // ----- controls -----

  void _pause() => setState(_tracker!.pause);
  void _resume() => setState(_tracker!.resume);

  bool get _hintAvailable =>
      !_tracker!.isPaused && _tracker!.hintsThisRound < _round.maxHints;

  void _hint() {
    if (!_hintAvailable) return;
    setState(() {
      _tracker!.hint();
      _hintMessage = _round.hintMessage(context.s, _tracker!.hintsThisRound);
    });
  }

  void _skip() {
    _tracker!.skipRound();
    _afterRound();
  }

  Future<void> _confirmStop() async {
    final s = context.s;
    _tracker!.pause();
    setState(() {});
    final stop = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(s.t('runner_stop_title')),
        content: Text(s.t('runner_stop_body')),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(s.t('common_keep_going')),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(s.t('common_yes_stop')),
          ),
        ],
      ),
    );
    if (stop == true) {
      await _finish(abandoned: true);
    } else {
      _resume();
    }
  }

  /// "I'm tired": end gently, record the tiredness (never as a mistake) and
  /// offer a rest.
  Future<void> _tired() => _finish(abandoned: !_tracker!.finished, tired: true);

  Future<void> _finish({required bool abandoned, bool tired = false}) async {
    if (_saving) return;
    setState(() => _saving = true);
    final tracker = _tracker!;
    final pid = widget.profile.patientId;
    final navigator = Navigator.of(context);
    try {
      final outcome = tracker.toOutcome(
        activityId: widget.catalog.id,
        difficulty: widget.difficulty,
        abandoned: abandoned,
        fatigueReported: tired,
        recommendationId: widget.recommendationId,
      );
      // Nothing to record if the person stopped before trying anything —
      // except tiredness, which the suggestions must know about.
      String? resultId;
      if (tired ||
          !(abandoned && tracker.attempts == 0 && tracker.skipped == 0)) {
        resultId = await _services.recorder.recordResult(
          pid,
          _sessionId!,
          outcome,
        );
      }
      await _services.recorder.finishSession(
        pid,
        _sessionId!,
        endReason: tired
            ? 'fatigue_detected'
            : abandoned
            ? 'user_stopped'
            : 'completed',
      );
      if (!mounted) return;
      await navigator.pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => ResultScreen(
            summary: RunSummary(
              activityTitle: widget.catalog.title,
              roundsPlayed: tracker.roundsPlayed,
              hints: tracker.hints,
              activeTime: tracker.activeTime,
              stopped: abandoned,
              tired: tired,
            ),
            profile: widget.profile,
            resultId: resultId,
            onPlayAgain: (ctx) => launchActivity(
              ctx,
              catalog: widget.catalog,
              profile: widget.profile,
              replace: true,
            ),
          ),
        ),
      );
    } on Object catch (e) {
      if (mounted) {
        setState(() {
          _saving = false;
          _error = e;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final tracker = _tracker;
    final theme = Theme.of(context);

    if (_error != null) {
      return Scaffold(
        appBar: AppBar(title: Text(widget.catalog.title)),
        body: MessageView(
          icon: Icons.error_outline,
          title: s.t('error_generic'),
          body: '',
          action: BigButton(
            label: s.t('common_back'),
            onPressed: () => Navigator.of(context).pop(),
          ),
        ),
      );
    }
    if (tracker == null || _saving) {
      return Scaffold(
        appBar: AppBar(title: Text(widget.catalog.title)),
        body: LoadingView(
          label: _saving ? s.t('runner_saving') : s.t('common_loading'),
        ),
      );
    }

    final paused = tracker.isPaused;
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _confirmStop();
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(widget.catalog.title),
          automaticallyImplyLeading: false,
          actions: [
            Center(
              child: Padding(
                padding: const EdgeInsets.only(right: 16),
                child: Semantics(
                  label: s.t('runner_round', {
                    'current': tracker.roundIndex + 1,
                    'total': tracker.totalRounds,
                  }),
                  child: Text(
                    s.t('runner_round', {
                      'current': tracker.roundIndex + 1,
                      'total': tracker.totalRounds,
                    }),
                    style: theme.textTheme.titleLarge,
                  ),
                ),
              ),
            ),
          ],
        ),
        body: Stack(
          children: [
            // Kept alive (but hidden from touch and screen readers) while paused.
            ExcludeSemantics(
              excluding: paused,
              child: IgnorePointer(
                ignoring: paused,
                child: ListView(
                  padding: const EdgeInsets.all(24),
                  children: [
                    if (widget.spec != null) ...[
                      Text(
                        widget.spec!.instructions,
                        key: const ValueKey('activity_instructions'),
                        style: theme.textTheme.bodyLarge,
                      ),
                      const SizedBox(height: 8),
                    ],
                    ReadAloudButton(
                      key: ValueKey('speak_${tracker.roundIndex}'),
                      text:
                          _round.spokenText ??
                          widget.spec?.instructions ??
                          widget.catalog.description,
                    ),
                    const SizedBox(height: 8),
                    if (_hintMessage != null)
                      NoticeBanner(
                        message: _hintMessage!,
                        icon: Icons.lightbulb_outline,
                      ),
                    KeyedSubtree(
                      key: ValueKey('round_${tracker.roundIndex}'),
                      child: _round.build(
                        context,
                        RoundContext(
                          host: this,
                          hintsUsed: tracker.hintsThisRound,
                          reduceMotion: reduceMotionOf(context),
                          strings: s,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            if (paused)
              Positioned.fill(
                child: ColoredBox(
                  color: theme.colorScheme.surface,
                  child: MessageView(
                    icon: Icons.pause_circle_outline,
                    title: s.t('runner_paused_title'),
                    body: s.t('runner_paused_body'),
                  ),
                ),
              ),
          ],
        ),
        bottomNavigationBar: SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: _ControlButton(
                        icon: paused ? Icons.play_arrow : Icons.pause,
                        label: paused
                            ? s.t('runner_resume')
                            : s.t('runner_pause'),
                        onPressed: paused ? _resume : _pause,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: _ControlButton(
                        icon: Icons.lightbulb_outline,
                        label: s.t('runner_hint'),
                        onPressed: _hintAvailable ? _hint : null,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: _ControlButton(
                        icon: Icons.skip_next,
                        label: s.t('runner_skip'),
                        onPressed: paused ? null : _skip,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: _ControlButton(
                        icon: Icons.stop_circle_outlined,
                        label: s.t('runner_stop'),
                        onPressed: _confirmStop,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: _ControlButton(
                    icon: Icons.bedtime_outlined,
                    label: s.t('runner_tired'),
                    onPressed: _tired,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ControlButton extends StatelessWidget {
  const _ControlButton({
    required this.icon,
    required this.label,
    required this.onPressed,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) => OutlinedButton.icon(
    onPressed: onPressed,
    icon: Icon(icon, size: 28),
    label: Text(label, maxLines: 2, overflow: TextOverflow.ellipsis),
  );
}
