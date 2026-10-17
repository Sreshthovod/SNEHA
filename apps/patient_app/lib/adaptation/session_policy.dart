import '../personalization/engine_config.dart';

/// What the runner should do next inside an activity.
enum SessionAction {
  continueRun('continue'),
  showHint('show_hint'),
  shorten('shorten'),
  offerBreak('offer_break'),
  endSession('end_session');

  const SessionAction(this.code);

  /// Stored in `adaptation` events (schemas/events.py AdaptationAction).
  final String code;
}

/// How tired someone seems. `mild` = "a little tired", `severe` = "very tired".
enum FatigueLevel {
  mild('mild'),
  severe('severe');

  const FatigueLevel(this.code);
  final String code;

  static FatigueLevel? fromCode(String? code) {
    for (final l in values) {
      if (l.code == code) return l;
    }
    return null;
  }
}

/// Reason codes for in-session decisions (documented in
/// packages/shared_docs/personalization-rules.md).
abstract final class SessionReason {
  static const stopRequested = 'STOP_REQUESTED';
  static const severeFatigueEnd = 'SEVERE_FATIGUE_END_SESSION';
  static const severeFatigueBreak = 'SEVERE_FATIGUE_OFFER_BREAK';
  static const mildFatigueShorten = 'MILD_FATIGUE_SHORTEN';
  static const mildFatigueMoreHints = 'MILD_FATIGUE_MORE_HINTS';
  static const repeatedErrorsInRound = 'REPEATED_ERRORS_IN_ROUND';
  static const hintsAdvisedByEngine = 'HINTS_ADVISED_BY_ENGINE';
  static const repeatedStruggleShorten = 'REPEATED_STRUGGLE_SHORTEN';
  static const repeatedStruggleBreak = 'REPEATED_STRUGGLE_OFFER_BREAK';
  static const caregiverReport = 'CAREGIVER_REPORT';
  static const patientReport = 'PATIENT_REPORT';
}

/// Everything the policy may look at. All values are counted on the phone
/// during this run; nothing is estimated.
class SessionSignals {
  const SessionSignals({
    this.stopRequested = false,
    this.fatigue,
    this.fatigueFromCaregiver = false,
    this.errorsThisRound = 0,
    this.hintsThisRound = 0,
    this.maxHintsThisRound = 0,
    this.consecutiveStruggledRounds = 0,
    this.struggledRounds = 0,
    this.roundsRemaining = 0,
    this.hintsAdvised = false,
    this.breakAlreadyOffered = false,
  });

  final bool stopRequested;
  final FatigueLevel? fatigue;
  final bool fatigueFromCaregiver;

  /// Wrong answers in the round on screen.
  final int errorsThisRound;

  /// Hints already shown in the round on screen (asked for or automatic).
  final int hintsThisRound;
  final int maxHintsThisRound;

  /// Rounds just finished that were struggled, counted backwards from the
  /// latest one.
  final int consecutiveStruggledRounds;

  /// Struggled rounds in the whole run.
  final int struggledRounds;

  /// Rounds still to play, counting the one on screen if it is unfinished.
  final int roundsRemaining;

  /// The engine asked for hints (recent struggle or tiredness).
  final bool hintsAdvised;

  /// A rest was already offered in this run (offered at most once).
  final bool breakAlreadyOffered;
}

class SessionDecision {
  const SessionDecision(this.action, this.reasons, {this.roundsRemaining});

  final SessionAction action;
  final List<String> reasons;

  /// For [SessionAction.shorten]: how many rounds are left after shortening
  /// (including the one on screen if unfinished).
  final int? roundsRemaining;

  static const keepGoing = SessionDecision(SessionAction.continueRun, []);

  @override
  String toString() => 'SessionDecision(${action.code}, $reasons)';
}

/// When the policy is consulted.
enum Checkpoint {
  /// Right after a wrong answer.
  afterWrongAnswer,

  /// After a round was solved or skipped (before the next one is shown).
  afterRound,

  /// The person or a caregiver reported tiredness, or asked to stop.
  onReport,
}

/// The in-activity comfort policy. Pure and deterministic.
///
/// Priority (first match wins):
/// 1. stop request → end the session;
/// 2. "very tired" → end the session (or offer a rest, per config);
/// 3. "a little tired" → shorten to at most N more rounds;
/// 4. repeated struggling rounds → offer a rest once, otherwise shorten;
/// 5. repeated wrong answers in a round → show a hint automatically;
/// 6. otherwise carry on.
///
/// It can only make an activity easier, shorter or stop it. Nothing here
/// lengthens an activity or keeps someone playing.
SessionDecision decideInSession(
  Checkpoint at,
  SessionSignals s, {
  EngineConfig config = engineConfig,
}) {
  final rules = config.inSession;
  final who = s.fatigueFromCaregiver
      ? SessionReason.caregiverReport
      : SessionReason.patientReport;

  if (s.stopRequested) {
    return const SessionDecision(SessionAction.endSession, [
      SessionReason.stopRequested,
    ]);
  }

  if (s.fatigue == FatigueLevel.severe) {
    final end = config.fatigue.caregiverSevereAction == 'end_session';
    // A rest that was already offered and turned down is not offered again.
    if (end || s.breakAlreadyOffered) {
      return SessionDecision(SessionAction.endSession, [
        SessionReason.severeFatigueEnd,
        who,
      ]);
    }
    return SessionDecision(SessionAction.offerBreak, [
      SessionReason.severeFatigueBreak,
      who,
    ]);
  }

  if (s.fatigue == FatigueLevel.mild &&
      at != Checkpoint.afterWrongAnswer &&
      s.roundsRemaining > rules.mildFatigueMaxRemainingRounds) {
    return SessionDecision(SessionAction.shorten, [
      SessionReason.mildFatigueShorten,
      who,
    ], roundsRemaining: rules.mildFatigueMaxRemainingRounds);
  }

  if (at == Checkpoint.afterRound && s.roundsRemaining > 0) {
    if (s.struggledRounds >= rules.breakAfterStruggledRounds &&
        !s.breakAlreadyOffered) {
      return const SessionDecision(SessionAction.offerBreak, [
        SessionReason.repeatedStruggleBreak,
      ]);
    }
    if (s.consecutiveStruggledRounds >= rules.shortenAfterStruggledRounds &&
        s.roundsRemaining > 1) {
      return const SessionDecision(SessionAction.shorten, [
        SessionReason.repeatedStruggleShorten,
      ], roundsRemaining: 1);
    }
  }

  if (at == Checkpoint.afterWrongAnswer &&
      s.hintsThisRound < s.maxHintsThisRound) {
    final assisted = s.hintsAdvised || s.fatigue == FatigueLevel.mild;
    final threshold = assisted
        ? rules.autoHintAfterErrorsAssisted
        : rules.autoHintAfterErrors;
    // One automatic hint per `threshold` wrong answers, so hints keep pace
    // with difficulty instead of all arriving at once.
    if (s.errorsThisRound >= threshold * (s.hintsThisRound + 1)) {
      return SessionDecision(SessionAction.showHint, [
        SessionReason.repeatedErrorsInRound,
        if (s.hintsAdvised) SessionReason.hintsAdvisedByEngine,
        if (s.fatigue == FatigueLevel.mild) SessionReason.mildFatigueMoreHints,
      ]);
    }
  }

  return SessionDecision.keepGoing;
}
