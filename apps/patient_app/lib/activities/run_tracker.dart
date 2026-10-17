import '../data/repositories/activity_recorder.dart';
import '../data/repositories/clock.dart';

/// Counts attempts, hints, skips and active time for one activity run.
/// Pure logic (no widgets) so scoring rules are unit-tested.
class RunTracker {
  RunTracker({
    required this.totalRounds,
    required Clock clock,
    this.struggledRoundErrors = 2,
  }) : _clock = clock,
       startedAt = clock(),
       roundsPlanned = totalRounds;

  /// Rounds in this run. Only ever lowered (see [limitRemaining]).
  int totalRounds;

  /// Rounds when the run started.
  final int roundsPlanned;

  /// A round with at least this many wrong answers (or skipped) is "struggled".
  final int struggledRoundErrors;
  final Clock _clock;
  final DateTime startedAt;

  int roundIndex = 0;
  int attempts = 0;
  int correct = 0;
  int hints = 0;
  int skipped = 0;
  int solved = 0;
  int solvedFirstTry = 0;
  int hintsAutomatic = 0;

  /// "Read aloud" presses: the person asked to hear the question again.
  int instructionsRepeated = 0;
  int errorsThisRound = 0;
  int struggledRounds = 0;
  int consecutiveStruggledRounds = 0;
  bool _hintThisRound = false;
  int hintsThisRound = 0;

  /// Active time (pauses excluded) from the round appearing or the previous
  /// answer to each answer, in milliseconds.
  final List<int> latenciesMs = [];
  Duration _markActive = Duration.zero;

  DateTime? _pausedAt;
  Duration _paused = Duration.zero;

  bool get isPaused => _pausedAt != null;
  bool get finished => roundIndex >= totalRounds;

  /// True once the run was cut short by [limitRemaining].
  bool get shortened => totalRounds < roundsPlanned;

  /// Rounds still to play, counting the one on screen.
  int get roundsRemaining => (totalRounds - roundIndex).clamp(0, totalRounds);

  /// Rounds the person reached (solved or skipped).
  int get roundsPlayed => solved + skipped;

  void pause() => _pausedAt ??= _clock();

  void resume() {
    if (_pausedAt != null) {
      _paused += _clock().difference(_pausedAt!);
      _pausedAt = null;
    }
  }

  /// Records one answer and returns its latency in milliseconds.
  int attempt({required bool correct}) {
    attempts++;
    final now = activeTime;
    final latency = (now - _markActive).inMilliseconds.clamp(0, 3600000);
    _markActive = now;
    latenciesMs.add(latency);
    if (correct) {
      this.correct++;
    } else {
      errorsThisRound++;
    }
    return latency;
  }

  /// A hint was shown: asked for, or [automatic] (the in-session policy).
  void hint({bool automatic = false}) {
    hints++;
    if (automatic) hintsAutomatic++;
    hintsThisRound++;
    _hintThisRound = true;
  }

  void solveRound() {
    solved++;
    if (errorsThisRound == 0 && !_hintThisRound) solvedFirstTry++;
    _endRound(struggled: errorsThisRound >= struggledRoundErrors);
  }

  void skipRound() {
    skipped++;
    _endRound(struggled: true);
  }

  /// At most [remaining] more rounds (counting the one on screen). Never adds
  /// rounds.
  void limitRemaining(int remaining) {
    final limit = roundIndex + remaining;
    if (limit < totalRounds) totalRounds = limit < 0 ? 0 : limit;
  }

  void _endRound({required bool struggled}) {
    if (struggled) {
      struggledRounds++;
      consecutiveStruggledRounds++;
    } else {
      consecutiveStruggledRounds = 0;
    }
    roundIndex++;
    errorsThisRound = 0;
    _hintThisRound = false;
    hintsThisRound = 0;
    _markActive = activeTime;
  }

  int? get medianLatencyMs {
    if (latenciesMs.isEmpty) return null;
    final sorted = [...latenciesMs]..sort();
    final mid = sorted.length ~/ 2;
    return sorted.length.isOdd
        ? sorted[mid]
        : (sorted[mid - 1] + sorted[mid]) ~/ 2;
  }

  Duration get activeTime {
    final end = _pausedAt ?? _clock();
    return end.difference(startedAt) - _paused;
  }

  /// Converts the run into what the server stores. Abandoned runs have no
  /// score: a partly played game says nothing meaningful.
  ActivityOutcome toOutcome({
    required String activityId,
    required int difficulty,
    required bool abandoned,
    bool scored = true,
    bool fatigueReported = false,
    String? recommendationId,
  }) {
    resume();
    final completedAt = _clock();
    final score = !scored || abandoned
        ? null
        : (totalRounds == 0 ? 0.0 : solved / totalRounds);
    return ActivityOutcome(
      activityId: activityId,
      difficultyLevel: difficulty,
      startedAt: startedAt,
      completedAt: completedAt.isBefore(startedAt) ? startedAt : completedAt,
      score: score,
      correctCount: correct,
      attemptCount: attempts,
      hintCount: hints,
      durationMs: activeTime.inMilliseconds.clamp(0, 6 * 60 * 60 * 1000),
      abandoned: abandoned,
      fatigueReported: fatigueReported,
      recommendationId: recommendationId,
      metrics: {
        // Mean active time per answer: used only to notice when answering
        // becomes much slower than usual (comfort), never as a grade.
        if (attempts > 0)
          'mean_response_ms': activeTime.inMilliseconds ~/ attempts,
        'rounds_total': totalRounds,
        'rounds_solved': solved,
        'rounds_skipped': skipped,
        'rounds_first_try': solvedFirstTry,
        'paused_ms': _paused.inMilliseconds,
        'rounds_planned': roundsPlanned,
        'rounds_struggled': struggledRounds,
        'hints_automatic': hintsAutomatic,
        'instructions_repeated': instructionsRepeated,
        if (shortened) 'shortened': 1,
        // Per-answer latency (pauses excluded). Recorded for the session
        // timeline; analytics keeps using mean_response_ms so earlier
        // baselines stay comparable.
        'median_answer_ms': ?medianLatencyMs,
      },
    );
  }
}
