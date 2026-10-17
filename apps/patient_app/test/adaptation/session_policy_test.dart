// In-session comfort policy: different observed interactions lead to
// different, explained decisions; stop and tiredness always win.
import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/adaptation/session_policy.dart';
import 'package:sneha_patient/personalization/engine_config.dart';

EngineConfig withSevereAction(String action) => EngineConfig(
  configVersion: engineConfig.configVersion,
  difficulty: engineConfig.difficulty,
  selection: engineConfig.selection,
  fatigue: FatigueRules(
    feedbackWindowHours: engineConfig.fatigue.feedbackWindowHours,
    observationWindowHours: engineConfig.fatigue.observationWindowHours,
    lowEffortSlugs: engineConfig.fatigue.lowEffortSlugs,
    breakMinutes: engineConfig.fatigue.breakMinutes,
    caregiverSevereAction: action,
  ),
  inSession: engineConfig.inSession,
  support: engineConfig.support,
  memory: engineConfig.memory,
  activityInterestTags: engineConfig.activityInterestTags,
  contentLanguages: engineConfig.contentLanguages,
);

void main() {
  const going = SessionSignals(roundsRemaining: 3, maxHintsThisRound: 2);

  test('a calm run carries on', () {
    expect(
      decideInSession(Checkpoint.afterRound, going).action,
      SessionAction.continueRun,
    );
    expect(
      decideInSession(
        Checkpoint.afterWrongAnswer,
        const SessionSignals(
          errorsThisRound: 1,
          maxHintsThisRound: 2,
          roundsRemaining: 3,
        ),
      ).action,
      SessionAction.continueRun,
      reason: 'one wrong answer is not a reason to step in',
    );
  });

  test('repeated wrong answers in a round bring a hint, at a steady pace', () {
    SessionDecision after(int errors, int hints, {bool advised = false}) =>
        decideInSession(
          Checkpoint.afterWrongAnswer,
          SessionSignals(
            errorsThisRound: errors,
            hintsThisRound: hints,
            maxHintsThisRound: 2,
            roundsRemaining: 2,
            hintsAdvised: advised,
          ),
        );
    expect(after(2, 0).action, SessionAction.showHint);
    expect(after(2, 0).reasons, [SessionReason.repeatedErrorsInRound]);
    expect(after(3, 1).action, SessionAction.continueRun);
    expect(after(4, 1).action, SessionAction.showHint);
    expect(
      after(4, 2).action,
      SessionAction.continueRun,
      reason: 'no hints left',
    );
    // When the engine advised hints, the first wrong answer is enough.
    expect(after(1, 0, advised: true).action, SessionAction.showHint);
    expect(
      after(1, 0, advised: true).reasons,
      contains(SessionReason.hintsAdvisedByEngine),
    );
  });

  test('struggling rounds shorten the activity, or offer a rest once', () {
    final shorten = decideInSession(
      Checkpoint.afterRound,
      const SessionSignals(
        consecutiveStruggledRounds: 2,
        struggledRounds: 2,
        roundsRemaining: 3,
      ),
    );
    expect(shorten.action, SessionAction.shorten);
    expect(shorten.roundsRemaining, 1);
    expect(shorten.reasons, [SessionReason.repeatedStruggleShorten]);

    const struggling = SessionSignals(
      consecutiveStruggledRounds: 1,
      struggledRounds: 3,
      roundsRemaining: 2,
    );
    final rest = decideInSession(Checkpoint.afterRound, struggling);
    expect(rest.action, SessionAction.offerBreak);
    expect(rest.reasons, [SessionReason.repeatedStruggleBreak]);
    expect(
      decideInSession(
        Checkpoint.afterRound,
        const SessionSignals(
          consecutiveStruggledRounds: 1,
          struggledRounds: 3,
          roundsRemaining: 2,
          breakAlreadyOffered: true,
        ),
      ).action,
      SessionAction.continueRun,
      reason: 'a declined rest is not offered again and again',
    );
  });

  test('a little tired: shorter, with hints sooner', () {
    final d = decideInSession(
      Checkpoint.onReport,
      const SessionSignals(
        fatigue: FatigueLevel.mild,
        fatigueFromCaregiver: true,
        roundsRemaining: 4,
      ),
    );
    expect(d.action, SessionAction.shorten);
    expect(
      d.roundsRemaining,
      engineConfig.inSession.mildFatigueMaxRemainingRounds,
    );
    expect(d.reasons, [
      SessionReason.mildFatigueShorten,
      SessionReason.caregiverReport,
    ]);
    final hint = decideInSession(
      Checkpoint.afterWrongAnswer,
      const SessionSignals(
        fatigue: FatigueLevel.mild,
        errorsThisRound: 1,
        maxHintsThisRound: 1,
        roundsRemaining: 1,
      ),
    );
    expect(hint.action, SessionAction.showHint);
    expect(hint.reasons, contains(SessionReason.mildFatigueMoreHints));
  });

  test('very tired ends the session (default) or offers a rest (config)', () {
    const severe = SessionSignals(
      fatigue: FatigueLevel.severe,
      fatigueFromCaregiver: true,
      roundsRemaining: 3,
    );
    final end = decideInSession(Checkpoint.onReport, severe);
    expect(end.action, SessionAction.endSession);
    expect(end.reasons, [
      SessionReason.severeFatigueEnd,
      SessionReason.caregiverReport,
    ]);

    final cfg = withSevereAction('offer_break');
    expect(
      decideInSession(Checkpoint.onReport, severe, config: cfg).action,
      SessionAction.offerBreak,
    );
    expect(
      decideInSession(
        Checkpoint.afterRound,
        const SessionSignals(
          fatigue: FatigueLevel.severe,
          roundsRemaining: 2,
          breakAlreadyOffered: true,
        ),
        config: cfg,
      ).action,
      SessionAction.endSession,
      reason: 'a declined rest while very tired still ends the session',
    );
  });

  test('stop beats everything, including signals that would continue', () {
    for (final s in [
      const SessionSignals(stopRequested: true, roundsRemaining: 5),
      const SessionSignals(
        stopRequested: true,
        fatigue: FatigueLevel.mild,
        errorsThisRound: 5,
        maxHintsThisRound: 2,
        roundsRemaining: 5,
      ),
      const SessionSignals(
        stopRequested: true,
        consecutiveStruggledRounds: 3,
        struggledRounds: 3,
        roundsRemaining: 5,
      ),
    ]) {
      for (final at in Checkpoint.values) {
        final d = decideInSession(at, s);
        expect(d.action, SessionAction.endSession);
        expect(d.reasons.first, SessionReason.stopRequested);
      }
    }
  });

  test('the policy never lengthens an activity', () {
    for (final errors in [0, 1, 2, 5]) {
      for (final struggled in [0, 1, 2, 3, 4]) {
        for (final remaining in [0, 1, 2, 5]) {
          for (final fatigue in [null, ...FatigueLevel.values]) {
            final d = decideInSession(
              Checkpoint.afterRound,
              SessionSignals(
                errorsThisRound: errors,
                consecutiveStruggledRounds: struggled,
                struggledRounds: struggled,
                roundsRemaining: remaining,
                fatigue: fatigue,
                maxHintsThisRound: 2,
              ),
            );
            if (d.action == SessionAction.shorten) {
              expect(d.roundsRemaining, lessThan(remaining));
            }
          }
        }
      }
    }
  });
}
