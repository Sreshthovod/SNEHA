import 'package:flutter/material.dart';

import '../../activities/activity.dart';
import '../../activities/run_tracker.dart';
import '../../adaptation/session_policy.dart';
import '../../app.dart';
import '../../app_services.dart';
import '../../data/api/models.dart';
import '../../data/api/stage7_models.dart';
import '../../data/repositories/profile_repository.dart';
import '../../personalization/engine_config.dart';
import '../../ui/read_aloud.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import '../caregiver/caregiver_fatigue_sheet.dart';
import 'activity_launcher.dart';
import 'result_screen.dart';

/// The ONE generic screen that runs every game (screens 6–11): pause, hint,
/// skip, stop, progress, timing and result recording live here, so a new game
/// only supplies rounds.
///
/// Every answer, hint, pause, tiredness report and stop request is written to
/// the phone's database as an event while it happens (and queued for sync).
/// After each wrong answer and each round, the in-session policy
/// (adaptation/session_policy.dart) decides whether to carry on, show a hint,
/// shorten the activity, offer a rest or end it. Its decisions are recorded
/// with their reason codes too.
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
    this.hintsAdvised = false,
    this.readAloudFirst = false,
    this.engineReasonCodes = const [],
    this.decidedOn,
    this.config = engineConfig,
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

  /// The engine asked for hints (recent struggle or tiredness): automatic
  /// hints come sooner.
  final bool hintsAdvised;

  /// The engine saw repeated "Read aloud" presses: read each question aloud
  /// when it appears (only if read-aloud is on and a voice exists).
  final bool readAloudFirst;

  /// Why the engine suggested this run (recorded, never shown as codes).
  final List<String> engineReasonCodes;

  /// `device` or `server` when the engine suggested this run; null when the
  /// person picked it from the list.
  final String? decidedOn;

  /// Thresholds (personalization.toml, mirrored in engine_config.dart).
  final EngineConfig config;

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
  String? _notice;
  bool _saving = false;
  Object? _error;

  // In-session adaptation state.
  FatigueLevel? _fatigue;
  bool _fatigueFromCaregiver = false;
  bool _breakOffered = false;

  /// Caregiver reports already on the phone when the run started. The engine
  /// already took them into account (easiest level, hints), so only reports
  /// that arrive during the run change it.
  final Set<String> _knownReports = {};

  // Events are written one after another, in order, and awaited before the
  // result is saved, so nothing is held only in screen state.
  int _seq = 0;
  Future<void> _events = Future.value();

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
      _knownReports.addAll([
        for (final o in await _services.facts.fatigueObservations(
          widget.profile.patientId,
        ))
          o.id,
      ]);
      if (!mounted) return;
      setState(() {
        _sessionId = id;
        // Created after the session so results never start before it.
        _tracker = RunTracker(
          totalRounds: _rounds!.length,
          clock: _services.clock,
          struggledRoundErrors: widget.config.inSession.struggledRoundErrors,
        );
      });
      // Which approved memories this run uses (if any), and why: the same
      // rules that built the rounds (activities/memory_content.dart).
      final choice = widget.activity.contentChoice(widget.content);
      final memoryIds = <String>{
        for (final r in _rounds!) ...r.memoryIds,
      }.take(20).toList();
      _log(
        'activity_started',
        data: {
          'rounds_planned': _rounds!.length,
          'difficulty': widget.difficulty,
          'content_source': choice.source,
          'memory_ids': memoryIds,
          'reason_codes': choice.reasons.take(10).toList(),
          if (widget.engineReasonCodes.isNotEmpty)
            'engine_reason_codes': widget.engineReasonCodes.take(16).toList(),
          'decided_on': ?widget.decidedOn,
        },
      );
    } on Object catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  RoundSpec get _round => _rounds![_tracker!.roundIndex];

  // ----- events -----

  void _log(String type, {Map<String, Object> data = const {}}) {
    final tracker = _tracker;
    final seq = _seq++;
    final round = tracker == null || tracker.finished
        ? null
        : tracker.roundIndex;
    // Answers and round outcomes name the approved memory the round showed.
    final ids = round == null ? const <String>[] : _rounds![round].memoryIds;
    if (ids.length == 1 &&
        const {'attempt', 'round_solved', 'round_skipped'}.contains(type)) {
      data = {...data, 'memory_id': ids.single};
    }
    _events = _events.then((_) async {
      try {
        await _services.recorder.recordEvent(
          widget.profile.patientId,
          sessionId: _sessionId!,
          activityId: widget.catalog.id,
          seq: seq,
          eventType: type,
          roundIndex: round,
          data: data,
        );
      } on Object catch (e) {
        // Never block the person over a log write; the result still records
        // the totals.
        debugPrint('Runner: could not record $type event ($e)');
      }
    });
  }

  // ----- policy -----

  SessionSignals _signals({bool stop = false}) {
    final t = _tracker!;
    return SessionSignals(
      stopRequested: stop,
      fatigue: _fatigue,
      fatigueFromCaregiver: _fatigueFromCaregiver,
      errorsThisRound: t.errorsThisRound,
      hintsThisRound: t.hintsThisRound,
      maxHintsThisRound: t.finished ? 0 : _round.maxHints,
      consecutiveStruggledRounds: t.consecutiveStruggledRounds,
      struggledRounds: t.struggledRounds,
      roundsRemaining: t.roundsRemaining,
      hintsAdvised: widget.hintsAdvised,
      breakAlreadyOffered: _breakOffered,
    );
  }

  /// Applies a decision. Returns true when the run has ended.
  Future<bool> _apply(SessionDecision d) async {
    if (d.action == SessionAction.continueRun) return false;
    final tracker = _tracker!;
    _log(
      'adaptation',
      data: {
        'action': d.action.code,
        'reason_codes': d.reasons,
        'rounds_remaining': ?d.roundsRemaining,
      },
    );
    final tiredReason =
        d.reasons.contains(SessionReason.severeFatigueEnd) ||
        d.reasons.contains(SessionReason.severeFatigueBreak);
    switch (d.action) {
      case SessionAction.continueRun:
        return false;
      case SessionAction.showHint:
        setState(() {
          tracker.hint(automatic: true);
          _hintMessage =
              '${context.s.t('runner_auto_hint')} '
              '${_round.hintMessage(context.s, tracker.hintsThisRound)}';
        });
        _log(
          'hint_auto',
          data: {'hint_number': tracker.hintsThisRound, 'source': 'system'},
        );
        return false;
      case SessionAction.shorten:
        tracker.limitRemaining(d.roundsRemaining ?? 1);
        if (tracker.finished) {
          await _finish(abandoned: false);
          return true;
        }
        setState(() => _notice = context.s.t('runner_shortened'));
        return false;
      case SessionAction.offerBreak:
        _breakOffered = true;
        final rest = await _askForBreak();
        if (!mounted) return true;
        if (rest) {
          _log('break_taken');
          if (tiredReason) {
            await _finish(abandoned: !tracker.finished, tired: true);
          } else {
            // A rest after struggling ends the activity early but keeps its
            // score, so the next suggestion can be easier.
            tracker.limitRemaining(0);
            await _finish(abandoned: false);
          }
          return true;
        }
        _log('break_declined');
        return false;
      case SessionAction.endSession:
        if (d.reasons.contains(SessionReason.stopRequested)) {
          await _finish(abandoned: true);
        } else {
          await _finish(abandoned: !tracker.finished, tired: tiredReason);
        }
        return true;
    }
  }

  Future<bool> _askForBreak() async {
    final s = context.s;
    _tracker!.pause();
    setState(() {});
    final rest = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        scrollable: true,
        actionsOverflowDirection: VerticalDirection.up,
        actionsOverflowButtonSpacing: 8,
        title: Text(s.t('runner_break_title')),
        content: Text(s.t('runner_break_body')),
        actions: [
          TextButton(
            key: const ValueKey('break_continue'),
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(s.t('runner_break_continue')),
          ),
          FilledButton(
            key: const ValueKey('break_rest'),
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(s.t('runner_break_rest')),
          ),
        ],
      ),
    );
    if (mounted) setState(_tracker!.resume);
    return rest ?? false;
  }

  /// Picks up caregiver reports that reached the phone during the run (for
  /// example pulled from the dashboard). Returns true when the run has ended.
  Future<bool> _checkCaregiverReports() async {
    final fresh = [
      for (final o in await _services.facts.fatigueObservations(
        widget.profile.patientId,
      ))
        if (_knownReports.add(o.id)) o,
    ];
    if (fresh.isEmpty || !mounted) return false;
    final severe = fresh.any((o) => o.fatigueLevel == FatigueLevel.severe.code);
    return _onFatigue(severe ? FatigueLevel.severe : FatigueLevel.mild);
  }

  Future<bool> _onFatigue(FatigueLevel level) async {
    // A later "a little tired" never softens an earlier "very tired".
    if (_fatigue != FatigueLevel.severe) _fatigue = level;
    _fatigueFromCaregiver = true;
    _log(
      'fatigue_reported',
      data: {'source': 'caregiver', 'level': level.code},
    );
    return _apply(
      decideInSession(Checkpoint.onReport, _signals(), config: widget.config),
    );
  }

  // ----- RoundHost -----

  @override
  void attempt({required bool correct}) {
    final latency = _tracker!.attempt(correct: correct);
    _log('attempt', data: {'correct': correct, 'latency_ms': latency});
    if (!correct) {
      _apply(
        decideInSession(
          Checkpoint.afterWrongAnswer,
          _signals(),
          config: widget.config,
        ),
      );
    }
  }

  @override
  void solved() {
    // Logged before the round counter moves on, so it names this round.
    _log('round_solved');
    _tracker!.solveRound();
    _afterRound();
  }

  Future<void> _afterRound() async {
    final tracker = _tracker!;
    if (tracker.finished) {
      await _finish(abandoned: false);
      return;
    }
    setState(() => _hintMessage = null);
    // A report pulled from the dashboard during the activity applies now.
    if (await _checkCaregiverReports()) return;
    if (!mounted || _saving) return;
    await _apply(
      decideInSession(Checkpoint.afterRound, _signals(), config: widget.config),
    );
  }

  // ----- controls -----

  /// "Read aloud" pressed: the person wanted to hear the question again.
  void _instructionsRepeated() {
    _tracker!.instructionsRepeated++;
    _log('instructions_repeated');
  }

  void _pause() {
    setState(_tracker!.pause);
    _log('paused');
  }

  void _resume() {
    setState(_tracker!.resume);
    _log('resumed');
  }

  bool get _hintAvailable =>
      !_tracker!.isPaused && _tracker!.hintsThisRound < _round.maxHints;

  void _hint() {
    if (!_hintAvailable) return;
    setState(() {
      _tracker!.hint();
      _hintMessage = _round.hintMessage(context.s, _tracker!.hintsThisRound);
    });
    _log(
      'hint_requested',
      data: {'hint_number': _tracker!.hintsThisRound, 'source': 'patient'},
    );
  }

  void _skip() {
    _log('round_skipped');
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
        scrollable: true,
        actionsOverflowDirection: VerticalDirection.up,
        actionsOverflowButtonSpacing: 8,
        title: Text(s.t('runner_stop_title')),
        content: Text(s.t('runner_stop_body')),
        // Calm, never danger-coloured: carrying on is the main choice.
        actions: [
          OutlinedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(s.t('common_yes_stop')),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(s.t('common_keep_going')),
          ),
        ],
      ),
    );
    if (stop == true) {
      _log('stop_requested', data: {'source': 'patient'});
      // Stop always wins: the policy has nothing that could keep it going.
      await _apply(
        decideInSession(
          Checkpoint.onReport,
          _signals(stop: true),
          config: widget.config,
        ),
      );
    } else {
      _resume();
    }
  }

  /// "I'm tired": end gently, record the tiredness (never as a mistake) and
  /// offer a rest.
  Future<void> _tired() async {
    _log('fatigue_reported', data: {'source': 'patient'});
    _log(
      'adaptation',
      data: {
        'action': SessionAction.endSession.code,
        'reason_codes': [SessionReason.patientReport, 'FATIGUE_REPORTED_BREAK'],
      },
    );
    await _finish(
      abandoned: !_tracker!.finished,
      tired: true,
      patientSaidTired: true,
    );
  }

  Future<void> _caregiver() async {
    final tracker = _tracker!;
    final wasPaused = tracker.isPaused;
    tracker.pause();
    setState(() {});
    final level = await showCaregiverFatigueSheet(context, widget.profile);
    if (!mounted) return;
    if (!wasPaused) setState(tracker.resume);
    if (level == null) return;
    _knownReports.add(
      await _services.recorder.reportCaregiverFatigue(
        widget.profile.patientId,
        level: level.code,
      ),
    );
    if (!mounted) return;
    final ended = await _onFatigue(level);
    if (!ended && mounted) {
      setState(() => _notice ??= context.s.t('caregiver_reported_mild'));
    }
  }

  /// [tired] ends the session as `fatigue_detected`. [patientSaidTired] also
  /// marks the result: only the person's own "I'm tired", because a
  /// caregiver's report is already its own synced record and must not be
  /// counted twice.
  Future<void> _finish({
    required bool abandoned,
    bool tired = false,
    bool patientSaidTired = false,
  }) async {
    if (_saving) return;
    setState(() => _saving = true);
    final tracker = _tracker!;
    final pid = widget.profile.patientId;
    final navigator = Navigator.of(context);
    try {
      _log(
        'activity_ended',
        data: {
          'outcome': tired
              ? 'tired'
              : abandoned
              ? 'stopped'
              : tracker.shortened
              ? 'shortened'
              : 'completed',
          'rounds_remaining': tracker.roundsRemaining,
        },
      );
      await _events;
      final outcome = tracker.toOutcome(
        activityId: widget.catalog.id,
        difficulty: widget.difficulty,
        abandoned: abandoned,
        fatigueReported: patientSaidTired,
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
    final scheme = theme.colorScheme;

    if (_error != null) {
      return Scaffold(
        appBar: AppBar(title: Text(widget.catalog.title)),
        body: MessageView(
          icon: Icons.cloud_off_outlined,
          quiet: true,
          title: s.t('error_generic'),
          body: s.t('runner_error_body'),
          action: BigButton(
            label: s.t('common_back'),
            icon: Icons.arrow_back,
            onPressed: () => Navigator.of(context).pop(),
          ),
        ),
      );
    }
    if (tracker == null || _saving || tracker.finished) {
      return Scaffold(
        appBar: AppBar(title: Text(widget.catalog.title)),
        body: LoadingView(
          label: _saving ? s.t('runner_saving') : s.t('common_loading'),
        ),
      );
    }

    final paused = tracker.isPaused;
    final roundLabel = s.t('runner_round', {
      'current': tracker.roundIndex + 1,
      'total': tracker.totalRounds,
    });
    final pad = pagePadding(context);
    final scaler = MediaQuery.textScalerOf(context);
    // Title and "1 of 3" share the app bar so the game gets the space.
    final toolbarHeight = (scaler.scale(22 * 1.3) + scaler.scale(20 * 1.5) + 18)
        .clamp(64.0, 160.0);
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _confirmStop();
      },
      child: Scaffold(
        appBar: AppBar(
          toolbarHeight: toolbarHeight,
          titleSpacing: pad,
          automaticallyImplyLeading: false,
          title: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                widget.catalog.title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.titleMedium,
              ),
              const SizedBox(height: 2),
              Row(
                children: [
                  Text(
                    roundLabel,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ExcludeSemantics(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: LinearProgressIndicator(
                          value: (tracker.roundIndex + 1) / tracker.totalRounds,
                          minHeight: 8,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
          actions: [
            // With very large text the label would squeeze the title, so the
            // caregiver entry becomes an icon (named by its tooltip).
            if (scaler.scale(1) > 1.3)
              IconButton(
                key: const ValueKey('caregiver_button'),
                tooltip: s.t('caregiver_button'),
                color: scheme.tertiary,
                iconSize: 30,
                onPressed: _caregiver,
                icon: const Icon(Icons.volunteer_activism_outlined),
              )
            else
              TextButton.icon(
                key: const ValueKey('caregiver_button'),
                style: TextButton.styleFrom(foregroundColor: scheme.tertiary),
                onPressed: _caregiver,
                icon: const Icon(Icons.volunteer_activism_outlined),
                label: Text(s.t('caregiver_button')),
              ),
            const SizedBox(width: 8),
          ],
        ),
        body: Stack(
          children: [
            // Kept alive (but hidden from touch and screen readers) while paused.
            ExcludeSemantics(
              excluding: paused,
              child: IgnorePointer(
                ignoring: paused,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Hints and notices stay in view above the game, even
                    // when the answers are scrolled.
                    if (_notice != null || _hintMessage != null)
                      Padding(
                        padding: EdgeInsets.fromLTRB(pad, 0, pad, 0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            if (_notice != null)
                              NoticeBanner(
                                key: const ValueKey('runner_notice'),
                                message: _notice!,
                                tone: NoticeTone.rest,
                              ),
                            if (_hintMessage != null)
                              NoticeBanner(
                                key: const ValueKey('runner_hint_message'),
                                message: _hintMessage!,
                                icon: Icons.lightbulb_outline,
                              ),
                          ],
                        ),
                      ),
                    Expanded(
                      child: ListView(
                        padding: EdgeInsets.fromLTRB(pad, 8, pad, pad),
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
                            speakOnOpen: widget.readAloudFirst,
                            onPressed: _instructionsRepeated,
                            text:
                                _round.spokenText ??
                                widget.spec?.instructions ??
                                widget.catalog.description,
                          ),
                          const SizedBox(height: 12),
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
                  ],
                ),
              ),
            ),
            if (paused)
              Positioned.fill(
                child: ColoredBox(
                  color: scheme.surface,
                  child: MessageView(
                    icon: Icons.pause_circle_outline,
                    title: s.t('runner_paused_title'),
                    body: s.t('runner_paused_body'),
                    action: BigButton(
                      key: const ValueKey('runner_paused_resume'),
                      label: s.t('runner_resume'),
                      icon: Icons.play_arrow,
                      onPressed: _resume,
                    ),
                  ),
                ),
              ),
          ],
        ),
        bottomNavigationBar: _ControlBar(
          paused: paused,
          onPauseToggle: paused ? _resume : _pause,
          onHint: _hintAvailable ? _hint : null,
          onSkip: paused ? null : _skip,
          onStop: _confirmStop,
          onTired: _tired,
        ),
      ),
    );
  }
}

/// The runner's controls, in two levels:
/// - large (64dp): "Hint" and "I'm tired", the two things a person most needs;
/// - compact (>= 48dp): Pause / Carry on, Skip and Stop.
/// All five are always visible and never cut off: labels wrap instead of
/// being shortened, and the text size is capped at 2x only inside this bar
/// (the game above it scrolls).
class _ControlBar extends StatelessWidget {
  const _ControlBar({
    required this.paused,
    required this.onPauseToggle,
    required this.onHint,
    required this.onSkip,
    required this.onStop,
    required this.onTired,
  });

  final bool paused;
  final VoidCallback onPauseToggle;
  final VoidCallback? onHint;
  final VoidCallback? onSkip;
  final VoidCallback onStop;
  final VoidCallback onTired;

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final highContrast = SnehaTheme.isHighContrast(theme);
    final pad = pagePadding(context) - 4;
    return MediaQuery.withClampedTextScaling(
      maxScaleFactor: 2.0,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: scheme.surfaceContainerLow,
          border: Border(
            top: BorderSide(
              color: highContrast ? scheme.outline : scheme.outlineVariant,
              width: highContrast ? 3 : 1,
            ),
          ),
        ),
        child: SafeArea(
          top: false,
          child: Padding(
            padding: EdgeInsets.fromLTRB(pad, 12, pad, 12),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                IntrinsicHeight(
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: onHint,
                          icon: const Icon(Icons.lightbulb_outline, size: 26),
                          label: _label(s.t('runner_hint')),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: FilledButton.icon(
                          style: FilledButton.styleFrom(
                            backgroundColor: scheme.tertiaryContainer,
                            foregroundColor: scheme.onTertiaryContainer,
                            iconColor: scheme.onTertiaryContainer,
                            side: highContrast
                                ? BorderSide(color: scheme.outline, width: 3)
                                : null,
                          ),
                          onPressed: onTired,
                          icon: const Icon(Icons.bedtime_outlined, size: 26),
                          label: _label(s.t('runner_tired')),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 8),
                IntrinsicHeight(
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Expanded(
                        child: _CompactControl(
                          icon: paused ? Icons.play_arrow : Icons.pause,
                          label: paused
                              ? s.t('runner_resume')
                              : s.t('runner_pause'),
                          onPressed: onPauseToggle,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: _CompactControl(
                          icon: Icons.skip_next,
                          label: s.t('runner_skip'),
                          onPressed: onSkip,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: _CompactControl(
                          icon: Icons.stop_circle_outlined,
                          label: s.t('runner_stop'),
                          onPressed: onStop,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  static Widget _label(String text) =>
      Text(text, textAlign: TextAlign.center, softWrap: true);
}

/// Secondary runner control: icon above a short label, >= 48dp tall.
class _CompactControl extends StatelessWidget {
  const _CompactControl({
    required this.icon,
    required this.label,
    required this.onPressed,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final highContrast = SnehaTheme.isHighContrast(theme);
    return OutlinedButton(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(48, 56),
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
        textStyle: theme.textTheme.labelMedium,
        foregroundColor: scheme.onSurfaceVariant,
        side: BorderSide(color: scheme.outline, width: highContrast ? 3 : 1.5),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      onPressed: onPressed,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 24),
          const SizedBox(height: 2),
          Text(label, textAlign: TextAlign.center, softWrap: true),
        ],
      ),
    );
  }
}
