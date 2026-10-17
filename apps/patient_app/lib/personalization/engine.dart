/// On-device port of the deterministic personalization engine.
///
/// Source of truth: services/api/app/personalization/engine.py
/// (ALGORITHM_VERSION 1.2.0). This file must give the SAME decisions for the
/// same inputs; test/personalization/engine_parity_test.dart replays scenarios
/// whose expected outputs were produced by the Python engine
/// (tool/engine_parity/generate.py → test/fixtures/engine_parity.json).
///
/// Pure functions: no database, no network, no randomness. These are
/// ENGAGEMENT rules for choosing a comfortable, enjoyable activity; nothing
/// here measures or implies any medical condition.
library;

import 'engine_config.dart';

const algorithmVersion = '1.2.0';

enum Reason {
  stopRequested('STOP_REQUESTED'),
  fatigueReportedBreak('FATIGUE_REPORTED_BREAK'),
  recentFatigueFeedback('RECENT_FATIGUE_FEEDBACK'),
  recentFatigueObservation('RECENT_FATIGUE_OBSERVATION'),
  caregiverSevereFatigue('CAREGIVER_REPORTED_SEVERE_FATIGUE'),
  lowEffortForFatigue('LOW_EFFORT_FOR_FATIGUE'),
  coldStartDefault('COLD_START_DEFAULT'),
  interestMatch('INTEREST_MATCH'),
  conversationContextMatch('CONVERSATION_CONTEXT_MATCH'),
  enjoyedBefore('ENJOYED_BEFORE'),
  familiarActivity('FAMILIAR_ACTIVITY'),
  lowEngagementSwitch('LOW_ENGAGEMENT_SWITCH'),
  avoidRepetition('AVOID_REPETITION'),
  onlyAvailableActivity('ONLY_AVAILABLE_ACTIVITY'),
  difficultyIncreased('DIFFICULTY_INCREASED_AFTER_COMFORTABLE_SUCCESS'),
  difficultyDecreased('DIFFICULTY_DECREASED_AFTER_REPEATED_ERRORS'),
  difficultyHeldCooldown('DIFFICULTY_HELD_TO_AVOID_OSCILLATION'),
  difficultyUnchanged('DIFFICULTY_UNCHANGED'),
  difficultyStartingLevel('DIFFICULTY_STARTING_LEVEL'),
  hintsOffered('HINTS_OFFERED_AFTER_ERRORS'),
  missingDataIgnored('MISSING_DATA_NOT_COUNTED_AS_ERROR'),
  memoryContentUsed('APPROVED_MEMORIES_USED'),
  personalRoutinesUsed('PERSONAL_ROUTINES_USED'),
  dislikedExcluded('DISLIKED_ACTIVITY_EXCLUDED'),
  offlineContentFilter('LIMITED_TO_AVAILABLE_OFFLINE_CONTENT'),
  languageContentFallback('LANGUAGE_CONTENT_FALLBACK'),
  noAvailableActivity('NO_AVAILABLE_ACTIVITY'),
  // 1.2.0: support that follows what the person needed last time.
  hintSupport('HINT_SUPPORT_AFTER_HINT_USE'),
  easierAlternative('EASIER_ALTERNATIVE_AFTER_STRUGGLE'),
  readAloudFirst('INSTRUCTIONS_READ_ALOUD_FIRST');

  const Reason(this.code);
  final String code;
}

enum EngineAction {
  activity('activity'),
  breakTime('break'),
  stop('stop'),
  none('none');

  const EngineAction(this.code);
  final String code;
}

enum Outcome { success, struggle, neutral, interruption }

// ---------------------------------------------------------------- facts

class ActivityFact {
  const ActivityFact({
    required this.id,
    required this.slug,
    required this.minDifficulty,
    required this.maxDifficulty,
    required this.usesMemoryBank,
  });

  final String id;
  final String slug;
  final int minDifficulty;
  final int maxDifficulty;
  final bool usesMemoryBank;
}

class ResultFact {
  const ResultFact({
    required this.id,
    required this.activityId,
    required this.completedAt,
    required this.difficulty,
    required this.score,
    required this.hints,
    required this.abandoned,
    this.engagement,
    this.fatigueReported = false,
    this.meanResponseMs,
    this.instructionsRepeated,
  });

  final String id;
  final String activityId;
  final DateTime completedAt;
  final int difficulty;
  final double? score;
  final int hints;
  final bool abandoned;

  /// enjoyed | neutral | not_enjoyed | null (not asked / not answered).
  final String? engagement;
  final bool fatigueReported;
  final double? meanResponseMs;

  /// Times "Read aloud" was pressed during the run (1.2.0); null = not recorded.
  final int? instructionsRepeated;
}

class ObservationFact {
  const ObservationFact({
    required this.id,
    required this.category,
    required this.observedAt,
    this.fatigueLevel,
  });

  final String id;
  final String category;
  final DateTime observedAt;

  /// Fatigue observations only: `mild` | `severe` | null (not given).
  final String? fatigueLevel;
}

class SessionEndFact {
  const SessionEndFact({
    required this.id,
    required this.endedAt,
    required this.endReason,
  });

  final String id;
  final DateTime endedAt;
  final String? endReason;
}

class ContentAvailability {
  const ContentAvailability({
    required this.sufficient,
    this.memoryItemIds = const [],
    this.routineItemIds = const [],
    this.matchedInterests = const [],
  });

  final bool sufficient;
  final List<String> memoryItemIds;
  final List<String> routineItemIds;
  final List<String> matchedInterests;
}

class EngineInput {
  const EngineInput({
    required this.now,
    required this.language,
    required this.activities,
    required this.results,
    this.interests = const [],
    this.contextTags = const [],
    this.dislikedSlugs = const {},
    this.observations = const [],
    this.sessionEnds = const [],
    this.content = const {},
    this.stopRequested = false,
    this.fatigueReported = false,
    this.availableSlugs,
  });

  final DateTime now;
  final String language;
  final List<ActivityFact> activities;

  /// Oldest first.
  final List<ResultFact> results;
  final List<String> interests;

  /// Topics from the current conversation (transient; may be empty).
  final List<String> contextTags;
  final Set<String> dislikedSlugs;
  final List<ObservationFact> observations;
  final List<SessionEndFact> sessionEnds;
  final Map<String, ContentAvailability> content;
  final bool stopRequested;
  final bool fatigueReported;

  /// Null = no device restriction.
  final Set<String>? availableSlugs;
}

/// A stored record that supports a decision. [detail] never contains notes.
class Support {
  const Support(this.kind, this.id, this.detail);

  final String kind;
  final String id;
  final String detail;

  @override
  bool operator ==(Object other) =>
      other is Support &&
      other.kind == kind &&
      other.id == id &&
      other.detail == detail;

  @override
  int get hashCode => Object.hash(kind, id, detail);

  @override
  String toString() => 'Support($kind, $id, $detail)';
}

class DifficultyDecision {
  DifficultyDecision(
    this.level,
    this.reasons,
    this.supporting,
    this.hints, [
    this.trailingStruggles = 0,
  ]);

  /// Consecutive struggles at the end of the history (1.2.0).
  final int trailingStruggles;

  final int level;
  final List<Reason> reasons;
  final List<Support> supporting;
  final bool hints;
}

class EngineRecommendation {
  EngineRecommendation({
    required this.action,
    required this.activity,
    required this.difficulty,
    required this.reasons,
    required this.supporting,
    this.hintsEnabled = false,
    this.memoryItemIds = const [],
    this.routineItemIds = const [],
    this.fallbackUsed = false,
    this.fallbackReason,
    this.breakMinutes,
    this.readAloudFirst = false,
  });

  final EngineAction action;
  final ActivityFact? activity;
  final int? difficulty;
  final List<Reason> reasons;
  final List<Support> supporting;
  final bool hintsEnabled;
  final List<String> memoryItemIds;
  final List<String> routineItemIds;
  final bool fallbackUsed;
  final String? fallbackReason;
  final int? breakMinutes;

  /// 1.2.0: read each question aloud when it appears (if read-aloud is on).
  final bool readAloudFirst;

  /// Reason codes in first-seen order, without duplicates.
  List<String> get reasonCodes {
    final seen = <String>[];
    for (final r in reasons) {
      if (!seen.contains(r.code)) seen.add(r.code);
    }
    return seen;
  }
}

// ---------------------------------------------------------------- difficulty

double? _median(List<double> values) {
  if (values.isEmpty) return null;
  final sorted = [...values]..sort();
  final mid = sorted.length ~/ 2;
  return sorted.length.isOdd
      ? sorted[mid]
      : (sorted[mid - 1] + sorted[mid]) / 2;
}

Outcome classify(ResultFact r, double? baselineMs, EngineConfig cfg) {
  final rules = cfg.difficulty;
  if (r.abandoned) {
    // Fatigue is handled by the fatigue rules, never as an error.
    return r.fatigueReported ? Outcome.neutral : Outcome.interruption;
  }
  final score = r.score;
  if (score == null) return Outcome.neutral; // missing data is not a failure
  final comfortable =
      r.meanResponseMs == null ||
      baselineMs == null ||
      r.meanResponseMs! <= baselineMs * rules.slowResponseFactor;
  if (score >= rules.successScore &&
      r.hints <= rules.maxHintsForSuccess &&
      comfortable) {
    return Outcome.success;
  }
  if (score < rules.struggleScore) return Outcome.struggle;
  return Outcome.neutral;
}

String _date(DateTime t) {
  final u = t.toUtc();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${u.year.toString().padLeft(4, '0')}-${two(u.month)}-${two(u.day)}';
}

/// Replay this activity's results through the step rules (with hysteresis).
DifficultyDecision decideDifficulty(
  ActivityFact activity,
  List<ResultFact> results,
  EngineConfig cfg,
) {
  final rules = cfg.difficulty;
  final history = results.length > rules.historyWindow
      ? results.sublist(results.length - rules.historyWindow)
      : results;
  var level = activity.minDifficulty;
  if (history.isEmpty) {
    return DifficultyDecision(
      level,
      [Reason.difficultyStartingLevel],
      [],
      false,
    );
  }

  var successes = 0;
  var struggles = 0;
  // Consecutive struggles at the end of the history (not reset by steps).
  var trailingStruggles = 0;
  var sinceChange = rules.minResultsBetweenChanges;
  final responseTimes = <double>[];
  (String, ResultFact)? lastChange;
  var pendingBlocked = false;

  for (final r in history) {
    final outcome = classify(r, _median(responseTimes), cfg);
    sinceChange++;
    if (outcome == Outcome.success) {
      successes++;
      struggles = 0;
    } else if (outcome == Outcome.struggle) {
      struggles++;
      successes = 0;
    }
    // neutral and interruption leave streaks untouched.
    if (outcome == Outcome.struggle) {
      trailingStruggles++;
    } else if (outcome == Outcome.success) {
      trailingStruggles = 0;
    }

    pendingBlocked = false;
    if (successes >= rules.increaseAfterSuccesses &&
        level < activity.maxDifficulty) {
      if (sinceChange >= rules.minResultsBetweenChanges) {
        level++;
        successes = 0;
        sinceChange = 0;
        lastChange = ('up', r);
      } else {
        pendingBlocked = true;
      }
    } else if (struggles >= rules.decreaseAfterStruggles &&
        level > activity.minDifficulty) {
      if (sinceChange >= rules.minResultsBetweenChanges) {
        level--;
        struggles = 0;
        sinceChange = 0;
        lastChange = ('down', r);
      } else {
        pendingBlocked = true;
      }
    }

    if (r.meanResponseMs != null && !r.abandoned) {
      responseTimes.add(r.meanResponseMs!);
    }
  }

  level = level.clamp(activity.minDifficulty, activity.maxDifficulty);
  final latest = history.last;
  final reasons = <Reason>[];
  final supporting = [
    for (final r
        in history.length > 3 ? history.sublist(history.length - 3) : history)
      Support(
        'activity_result',
        r.id,
        'difficulty ${r.difficulty}, completed ${_date(r.completedAt)}',
      ),
  ];
  if (lastChange != null && identical(lastChange.$2, latest)) {
    reasons.add(
      lastChange.$1 == 'up'
          ? Reason.difficultyIncreased
          : Reason.difficultyDecreased,
    );
  } else if (pendingBlocked) {
    reasons.add(Reason.difficultyHeldCooldown);
  } else {
    reasons.add(Reason.difficultyUnchanged);
  }
  if (latest.score == null && !latest.abandoned) {
    reasons.add(Reason.missingDataIgnored);
  }
  final hints = trailingStruggles >= rules.hintsAfterStruggles;
  if (hints) reasons.add(Reason.hintsOffered);
  return DifficultyDecision(
    level,
    reasons,
    supporting,
    hints,
    trailingStruggles,
  );
}

/// This activity's recent results that needed many hints, if they form a
/// pattern (1.2.0).
List<ResultFact> hintHeavy(List<ResultFact> results, EngineConfig cfg) {
  final rules = cfg.support;
  final finished = results.where((r) => !r.abandoned).toList();
  final recent = finished.length > rules.hintWindow
      ? finished.sublist(finished.length - rules.hintWindow)
      : finished;
  final heavy = recent
      .where((r) => r.hints >= rules.hintHeavyMinHints)
      .toList();
  return heavy.length >= rules.hintHeavyResults ? heavy : const [];
}

/// The latest struggles if the person is struggling at this activity's
/// easiest level (1.2.0).
List<ResultFact> strugglingAtEasiest(
  ActivityFact activity,
  List<ResultFact> results,
  EngineConfig cfg,
) {
  final decision = decideDifficulty(activity, results, cfg);
  final needed = cfg.support.struggleAtEasiestResults;
  if (decision.level == activity.minDifficulty &&
      decision.trailingStruggles >= needed) {
    final scored = results
        .where((r) => r.score != null && !r.abandoned)
        .toList();
    return scored.sublist(scored.length - needed);
  }
  return const [];
}

/// Recent results where "Read aloud" was pressed often enough to read
/// questions first (1.2.0).
List<ResultFact> readAloudFirstResults(
  List<ResultFact> results,
  EngineConfig cfg,
) {
  final rules = cfg.support;
  final recent = results.length > rules.instructionWindow
      ? results.sublist(results.length - rules.instructionWindow)
      : results;
  final pressed = recent
      .where((r) => (r.instructionsRepeated ?? 0) > 0)
      .toList();
  final total = recent.fold<int>(
    0,
    (sum, r) => sum + (r.instructionsRepeated ?? 0),
  );
  return total >= rules.readAloudAfterRepeats ? pressed : const [];
}

// ---------------------------------------------------------------- selection

bool _within(DateTime now, DateTime moment, double hours) {
  final from = now.subtract(Duration(microseconds: (hours * 3.6e9).round()));
  final to = now.add(const Duration(minutes: 5));
  return !moment.isBefore(from) && !moment.isAfter(to);
}

String _hhmm(DateTime t) {
  final u = t.toUtc();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(u.hour)}:${two(u.minute)}';
}

({bool explicitNow, List<Reason> reasons, List<Support> supporting})
_fatigueSignals(EngineInput inp, EngineConfig cfg) {
  final rules = cfg.fatigue;
  final reasons = <Reason>[];
  final supporting = <Support>[];
  final latest = inp.results.isEmpty ? null : inp.results.last;
  var explicitNow =
      inp.fatigueReported ||
      (latest != null &&
          latest.fatigueReported &&
          _within(inp.now, latest.completedAt, rules.feedbackWindowHours));
  if (inp.fatigueReported) {
    supporting.add(
      const Support(
        'request',
        'fatigue_reported',
        'tiredness reported just now',
      ),
    );
  }
  if (latest != null && latest.fatigueReported && explicitNow) {
    supporting.add(
      Support(
        'activity_result',
        latest.id,
        'tiredness reported after this activity',
      ),
    );
  }
  for (final r in inp.results) {
    if (r.fatigueReported &&
        _within(inp.now, r.completedAt, rules.feedbackWindowHours)) {
      if (!(latest != null && r.id == latest.id)) {
        reasons.add(Reason.recentFatigueFeedback);
        supporting.add(
          Support('activity_result', r.id, 'tiredness reported recently'),
        );
      }
    }
  }
  for (final s in inp.sessionEnds) {
    if (s.endReason == 'fatigue_detected' &&
        _within(inp.now, s.endedAt, rules.feedbackWindowHours)) {
      reasons.add(Reason.recentFatigueFeedback);
      supporting.add(
        Support('activity_session', s.id, 'session ended early for tiredness'),
      );
    }
  }
  for (final o in inp.observations) {
    if (o.category == 'fatigue' &&
        _within(inp.now, o.observedAt, rules.observationWindowHours)) {
      if (o.fatigueLevel == 'severe') {
        // A caregiver said "very tired": a rest, not another activity.
        explicitNow = true;
        reasons.add(Reason.caregiverSevereFatigue);
      } else {
        reasons.add(Reason.recentFatigueObservation);
      }
      final level = o.fatigueLevel == null ? '' : ' (${o.fatigueLevel})';
      supporting.add(
        Support(
          'caregiver_observation',
          o.id,
          'caregiver noted tiredness at ${_hhmm(o.observedAt)} UTC$level',
        ),
      );
    }
  }
  return (explicitNow: explicitNow, reasons: reasons, supporting: supporting);
}

bool _languageOk(String slug, String language, EngineConfig cfg) {
  final langs = cfg.contentLanguages[slug] ?? const ['*'];
  return langs.contains('*') || langs.contains(language);
}

EngineRecommendation recommend(EngineInput inp, [EngineConfig? config]) {
  final cfg = config ?? engineConfig;

  // 1. A direct stop request always wins.
  if (inp.stopRequested) {
    return EngineRecommendation(
      action: EngineAction.stop,
      activity: null,
      difficulty: null,
      reasons: [Reason.stopRequested],
      supporting: const [
        Support('request', 'stop_requested', 'the patient asked to stop'),
      ],
    );
  }

  final reasons = <Reason>[];
  final supporting = <Support>[];

  // 2. Candidate filtering.
  var candidates = [...inp.activities];
  final available = inp.availableSlugs;
  if (available != null) {
    final narrowed = candidates
        .where((a) => available.contains(a.slug))
        .toList();
    if (narrowed.length < candidates.length) {
      reasons.add(Reason.offlineContentFilter);
    }
    candidates = narrowed;
  }
  if (inp.dislikedSlugs.isNotEmpty) {
    final narrowed = candidates
        .where((a) => !inp.dislikedSlugs.contains(a.slug))
        .toList();
    if (narrowed.length < candidates.length && narrowed.isNotEmpty) {
      reasons.add(Reason.dislikedExcluded);
      supporting.add(
        Support(
          'preference',
          'disliked_activity_slugs',
          (inp.dislikedSlugs.toList()..sort()).join(', '),
        ),
      );
      candidates = narrowed;
    }
  }
  candidates = candidates
      .where((a) => inp.content[a.slug]?.sufficient ?? true)
      .toList();
  String? fallbackReason;
  final languageOk = candidates
      .where((a) => _languageOk(a.slug, inp.language, cfg))
      .toList();
  if (languageOk.isNotEmpty) {
    candidates = languageOk;
  } else if (candidates.isNotEmpty) {
    reasons.add(Reason.languageContentFallback);
    fallbackReason = 'language_content_unavailable';
  }

  if (candidates.isEmpty) {
    return EngineRecommendation(
      action: EngineAction.none,
      activity: null,
      difficulty: null,
      reasons: [...reasons, Reason.noAvailableActivity],
      supporting: supporting,
      fallbackUsed: true,
      fallbackReason: 'no_available_activity',
    );
  }

  final byId = {for (final a in inp.activities) a.id: a};

  // 3. Fatigue.
  final fatigue = _fatigueSignals(inp, cfg);
  final tired = fatigue.explicitNow || fatigue.reasons.isNotEmpty;
  if (tired) {
    final easy = candidates
        .where((a) => cfg.fatigue.lowEffortSlugs.contains(a.slug))
        .toList();
    if (easy.isNotEmpty) candidates = easy;
    reasons.addAll(fatigue.reasons);
    supporting.addAll(fatigue.supporting);
  }

  // 4. Low engagement.
  final sel = cfg.selection;
  final recentAll = inp.results.length > sel.lowEngagementWindow
      ? inp.results.sublist(inp.results.length - sel.lowEngagementWindow)
      : inp.results;
  final unhappy = recentAll
      .where(
        (r) =>
            (r.abandoned && !r.fatigueReported) ||
            r.engagement == 'not_enjoyed',
      )
      .toList();
  var avoid = <String>{};
  if (unhappy.length >= sel.lowEngagementThreshold) {
    avoid = {for (final r in unhappy) r.activityId};
    if (candidates.any((a) => !avoid.contains(a.id))) {
      reasons.add(Reason.lowEngagementSwitch);
      supporting.addAll([
        for (final r in unhappy)
          Support('activity_result', r.id, 'interrupted or not enjoyed'),
      ]);
    } else {
      avoid = {};
    }
  }

  // 5. Score candidates.
  final coldStart = inp.results.isEmpty;
  final lastActivity = inp.results.isEmpty ? null : inp.results.last.activityId;
  final recentIds = [
    for (final r
        in inp.results.length > sel.recentWindow
            ? inp.results.sublist(inp.results.length - sel.recentWindow)
            : inp.results)
      r.activityId,
  ];
  final lastPlayed = <String, DateTime>{};
  for (final r in inp.results) {
    lastPlayed[r.activityId] = r.completedAt;
  }
  final interests = {for (final t in inp.interests) t.toLowerCase()};

  // Repeated struggles at an activity's easiest level: prefer another one.
  final hardAtEasiest = {
    for (final a in candidates)
      a.id: strugglingAtEasiest(
        a,
        inp.results.where((r) => r.activityId == a.id).toList(),
        cfg,
      ),
  };

  ({int score, List<Reason> why, List<Support> sup}) score(ActivityFact a) {
    var s = 0;
    final why = <Reason>[];
    final sup = <Support>[];
    if (coldStart && sel.coldStartOrder.contains(a.slug)) {
      s += sel.coldStartOrder.length - sel.coldStartOrder.indexOf(a.slug);
    }
    final content = inp.content[a.slug];
    final tags = {...?cfg.activityInterestTags[a.slug]};
    if (content != null) tags.addAll(content.matchedInterests);
    final matched = interests.intersection(tags).toList()..sort();
    if (matched.isNotEmpty) {
      final bonus = sel.interestMatchBonus * matched.length;
      s += bonus < sel.interestBonusCap ? bonus : sel.interestBonusCap;
      why.add(Reason.interestMatch);
      sup.add(
        Support(
          'preference',
          'interests',
          'approved interests: ${matched.join(', ')}',
        ),
      );
    }
    final context = {
      for (final t in inp.contextTags) t.toLowerCase(),
    }.intersection(tags).difference(matched.toSet()).toList()..sort();
    if (context.isNotEmpty) {
      final bonus = sel.contextMatchBonus * context.length;
      s += bonus < sel.interestBonusCap ? bonus : sel.interestBonusCap;
      why.add(Reason.conversationContextMatch);
      sup.add(
        Support(
          'conversation',
          'context_tags',
          'talked about: ${context.join(', ')}',
        ),
      );
    }
    final all = inp.results.where((r) => r.activityId == a.id).toList();
    final mine = all.length > 5 ? all.sublist(all.length - 5) : all;
    final enjoyed = mine.where((r) => r.engagement == 'enjoyed').length;
    if (enjoyed > 0) {
      s += sel.enjoyedBonus * enjoyed;
      why.add(Reason.enjoyedBefore);
      final e = [
        for (final r in mine)
          if (r.engagement == 'enjoyed')
            Support('activity_result', r.id, 'enjoyed'),
      ];
      sup.addAll(e.length > 2 ? e.sublist(e.length - 2) : e);
    }
    s -=
        sel.notEnjoyedPenalty *
        mine.where((r) => r.engagement == 'not_enjoyed').length;
    s -=
        sel.interruptionPenalty *
        mine.where((r) => r.abandoned && !r.fatigueReported).length;
    if (mine.any((r) => !r.abandoned)) {
      s += sel.familiarBonus;
      why.add(Reason.familiarActivity);
    }
    if (a.id == lastActivity) s -= sel.repeatLastPenalty;
    s -= sel.repeatRecentPenalty * recentIds.where((id) => id == a.id).length;
    if (avoid.contains(a.id)) s -= 10000;
    if (hardAtEasiest[a.id]!.isNotEmpty) {
      s -= cfg.support.struggleAtEasiestPenalty;
    }
    return (score: s, why: why, sup: sup);
  }

  final epoch = DateTime.utc(1);
  final scored = [for (final a in candidates) (activity: a, result: score(a))];
  int compare(
    ({
      ActivityFact activity,
      ({int score, List<Reason> why, List<Support> sup}) result,
    })
    x,
    ({
      ActivityFact activity,
      ({int score, List<Reason> why, List<Support> sup}) result,
    })
    y,
  ) {
    var c = y.result.score.compareTo(x.result.score); // higher score first
    if (c != 0) return c;
    final xPlayed = lastPlayed.containsKey(x.activity.id);
    final yPlayed = lastPlayed.containsKey(y.activity.id);
    if (xPlayed != yPlayed) return xPlayed ? 1 : -1; // never played first
    c = (lastPlayed[x.activity.id] ?? epoch).compareTo(
      lastPlayed[y.activity.id] ?? epoch,
    );
    if (c != 0) return c;
    int order(String slug) {
      final i = sel.coldStartOrder.indexOf(slug);
      return i < 0 ? 99 : i;
    }

    c = order(x.activity.slug).compareTo(order(y.activity.slug));
    if (c != 0) return c;
    return x.activity.slug.compareTo(y.activity.slug);
  }

  scored.sort(compare);
  final chosen = scored.first.activity;
  reasons.addAll(scored.first.result.why);
  supporting.addAll(scored.first.result.sup);

  if (candidates.length == 1) {
    reasons.add(Reason.onlyAvailableActivity);
  } else if (lastActivity != null &&
      chosen.id != lastActivity &&
      candidates.any((a) => a.id == lastActivity)) {
    reasons.add(Reason.avoidRepetition);
  }
  if (coldStart) {
    reasons.add(Reason.coldStartDefault);
    fallbackReason ??= 'no_history';
  }
  final avoided = candidates
      .where((a) => hardAtEasiest[a.id]!.isNotEmpty && a.id != chosen.id)
      .toList();
  if (avoided.isNotEmpty) {
    reasons.add(Reason.easierAlternative);
    supporting.addAll([
      for (final a in avoided)
        for (final r in hardAtEasiest[a.id]!)
          Support('activity_result', r.id, 'struggled at the easiest level'),
    ]);
  }

  // 6. Difficulty.
  final decision = decideDifficulty(
    chosen,
    inp.results.where((r) => r.activityId == chosen.id).toList(),
    cfg,
  );
  var difficulty = decision.level;
  reasons.addAll(decision.reasons);
  supporting.addAll(decision.supporting);
  if (tired) {
    difficulty = chosen.minDifficulty;
    reasons.add(Reason.lowEffortForFatigue);
  }
  final heavy = hintHeavy(
    inp.results.where((r) => r.activityId == chosen.id).toList(),
    cfg,
  );
  if (heavy.isNotEmpty) {
    reasons.add(Reason.hintSupport);
    supporting.addAll([
      for (final r in heavy)
        Support('activity_result', r.id, '${r.hints} hints used'),
    ]);
  }
  final repeated = readAloudFirstResults(inp.results, cfg);
  if (repeated.isNotEmpty) {
    reasons.add(Reason.readAloudFirst);
    supporting.addAll([
      for (final r in repeated)
        Support(
          'activity_result',
          r.id,
          'question read aloud ${r.instructionsRepeated}x',
        ),
    ]);
  }

  final content =
      inp.content[chosen.slug] ?? const ContentAvailability(sufficient: true);
  if (content.memoryItemIds.isNotEmpty) {
    reasons.add(Reason.memoryContentUsed);
    supporting.addAll([
      for (final id in content.memoryItemIds)
        Support('memory_item', id, 'approved memory'),
    ]);
  }
  if (content.routineItemIds.isNotEmpty) {
    reasons.add(Reason.personalRoutinesUsed);
    supporting.addAll([
      for (final id in content.routineItemIds)
        Support('routine_item', id, "patient's own routine"),
    ]);
  }

  final unique = <Support>[];
  for (final item in supporting) {
    if (!unique.contains(item)) unique.add(item);
  }

  return EngineRecommendation(
    action: fatigue.explicitNow
        ? EngineAction.breakTime
        : EngineAction.activity,
    activity: byId[chosen.id],
    difficulty: difficulty,
    reasons: reasons,
    supporting: unique,
    hintsEnabled: decision.hints || tired || heavy.isNotEmpty,
    memoryItemIds: content.memoryItemIds,
    routineItemIds: content.routineItemIds,
    fallbackUsed: fallbackReason != null,
    fallbackReason: fallbackReason,
    breakMinutes: fatigue.explicitNow ? cfg.fatigue.breakMinutes : null,
    readAloudFirst: repeated.isNotEmpty,
  );
}
