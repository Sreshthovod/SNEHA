import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/activities/run_tracker.dart';

void main() {
  late DateTime now;
  RunTracker make(int rounds) {
    now = DateTime.utc(2026, 10, 15, 10);
    return RunTracker(totalRounds: rounds, clock: () => now);
  }

  test('counts attempts, hints, skips and first-try solves', () {
    final t = make(3);
    t.attempt(correct: true);
    t.solveRound(); // first try
    t.attempt(correct: false);
    t.attempt(correct: true);
    t.solveRound(); // with a mistake
    t.hint();
    t.skipRound();
    expect(t.finished, isTrue);
    final o = t.toOutcome(activityId: 'a', difficulty: 2, abandoned: false);
    expect(o.attemptCount, 3);
    expect(o.correctCount, 2);
    expect(o.hintCount, 1);
    expect(o.score, closeTo(2 / 3, 1e-9));
    expect(o.metrics['rounds_first_try'], 1);
    expect(o.metrics['rounds_skipped'], 1);
    expect(o.correctCount <= o.attemptCount, isTrue);
  });

  test('paused time is excluded from duration', () {
    final t = make(1);
    now = now.add(const Duration(seconds: 30));
    t.pause();
    now = now.add(const Duration(minutes: 5));
    t.resume();
    now = now.add(const Duration(seconds: 30));
    expect(t.activeTime, const Duration(minutes: 1));
    final o = t.toOutcome(activityId: 'a', difficulty: 1, abandoned: false);
    expect(o.durationMs, 60000);
    expect(o.metrics['paused_ms'], 300000);
  });

  test('abandoned and unscored runs have no score', () {
    final t = make(4)..attempt(correct: true);
    expect(
      t.toOutcome(activityId: 'a', difficulty: 1, abandoned: true).score,
      isNull,
    );
    expect(
      t
          .toOutcome(
            activityId: 'a',
            difficulty: 1,
            abandoned: false,
            scored: false,
          )
          .score,
      isNull,
    );
  });

  test('hints are counted per round and reset on the next round', () {
    final t = make(2)
      ..hint()
      ..hint();
    expect(t.hintsThisRound, 2);
    t.skipRound();
    expect(t.hintsThisRound, 0);
    expect(t.hints, 2);
  });
}
