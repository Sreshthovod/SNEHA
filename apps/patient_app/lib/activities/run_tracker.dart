import '../data/repositories/activity_recorder.dart';
import '../data/repositories/clock.dart';

/// Counts attempts, hints, skips and active time for one activity run.
/// Pure logic (no widgets) so scoring rules are unit-tested.
class RunTracker {
  RunTracker({required this.totalRounds, required Clock clock})
    : _clock = clock,
      startedAt = clock();

  final int totalRounds;
  final Clock _clock;
  final DateTime startedAt;

  int roundIndex = 0;
  int attempts = 0;
  int correct = 0;
  int hints = 0;
  int skipped = 0;
  int solved = 0;
  int solvedFirstTry = 0;
  bool _mistakeThisRound = false;
  bool _hintThisRound = false;
  int hintsThisRound = 0;

  DateTime? _pausedAt;
  Duration _paused = Duration.zero;

  bool get isPaused => _pausedAt != null;
  bool get finished => roundIndex >= totalRounds;

  /// Rounds the person reached (solved or skipped).
  int get roundsPlayed => solved + skipped;

  void pause() => _pausedAt ??= _clock();

  void resume() {
    if (_pausedAt != null) {
      _paused += _clock().difference(_pausedAt!);
      _pausedAt = null;
    }
  }

  void attempt({required bool correct}) {
    attempts++;
    if (correct) {
      this.correct++;
    } else {
      _mistakeThisRound = true;
    }
  }

  void hint() {
    hints++;
    hintsThisRound++;
    _hintThisRound = true;
  }

  void solveRound() {
    solved++;
    if (!_mistakeThisRound && !_hintThisRound) solvedFirstTry++;
    _nextRound();
  }

  void skipRound() {
    skipped++;
    _nextRound();
  }

  void _nextRound() {
    roundIndex++;
    _mistakeThisRound = false;
    _hintThisRound = false;
    hintsThisRound = 0;
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
      },
    );
  }
}
