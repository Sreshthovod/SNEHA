/// Engagement-rule thresholds for the on-device personalization engine.
///
/// MIRRORS services/api/config/personalization.toml exactly. A test
/// (test/personalization/config_parity_test.dart) reads that file and fails if
/// any value here drifts. Change the TOML first, then update this file.
///
/// These are ENGAGEMENT rules for choosing a comfortable activity, not
/// clinical thresholds.
library;

class DifficultyRules {
  const DifficultyRules({
    required this.successScore,
    required this.maxHintsForSuccess,
    required this.slowResponseFactor,
    required this.struggleScore,
    required this.increaseAfterSuccesses,
    required this.decreaseAfterStruggles,
    required this.minResultsBetweenChanges,
    required this.hintsAfterStruggles,
    required this.historyWindow,
  });

  final double successScore;
  final int maxHintsForSuccess;
  final double slowResponseFactor;
  final double struggleScore;
  final int increaseAfterSuccesses;
  final int decreaseAfterStruggles;
  final int minResultsBetweenChanges;
  final int hintsAfterStruggles;
  final int historyWindow;
}

class SelectionRules {
  const SelectionRules({
    required this.recentWindow,
    required this.repeatLastPenalty,
    required this.repeatRecentPenalty,
    required this.interestMatchBonus,
    required this.interestBonusCap,
    required this.contextMatchBonus,
    required this.enjoyedBonus,
    required this.notEnjoyedPenalty,
    required this.interruptionPenalty,
    required this.familiarBonus,
    required this.lowEngagementWindow,
    required this.lowEngagementThreshold,
    required this.coldStartOrder,
  });

  final int recentWindow;
  final int repeatLastPenalty;
  final int repeatRecentPenalty;
  final int interestMatchBonus;
  final int interestBonusCap;

  /// Per tag from the current conversation (weaker than approved interests).
  final int contextMatchBonus;
  final int enjoyedBonus;
  final int notEnjoyedPenalty;
  final int interruptionPenalty;
  final int familiarBonus;
  final int lowEngagementWindow;
  final int lowEngagementThreshold;
  final List<String> coldStartOrder;
}

class FatigueRules {
  const FatigueRules({
    required this.feedbackWindowHours,
    required this.observationWindowHours,
    required this.lowEffortSlugs,
    required this.breakMinutes,
    required this.caregiverSevereAction,
  });

  final double feedbackWindowHours;
  final double observationWindowHours;
  final List<String> lowEffortSlugs;
  final int breakMinutes;

  /// What a "very tired" report does to a running activity:
  /// `end_session` or `offer_break`.
  final String caregiverSevereAction;
}

/// Thresholds for the in-activity comfort policy (adaptation/session_policy.dart).
class InSessionRules {
  const InSessionRules({
    required this.autoHintAfterErrors,
    required this.autoHintAfterErrorsAssisted,
    required this.struggledRoundErrors,
    required this.shortenAfterStruggledRounds,
    required this.breakAfterStruggledRounds,
    required this.mildFatigueMaxRemainingRounds,
  });

  final int autoHintAfterErrors;
  final int autoHintAfterErrorsAssisted;
  final int struggledRoundErrors;
  final int shortenAfterStruggledRounds;
  final int breakAfterStruggledRounds;
  final int mildFatigueMaxRemainingRounds;
}

/// 1.2.0: support that follows what the person needed last time.
class SupportRules {
  const SupportRules({
    required this.hintWindow,
    required this.hintHeavyMinHints,
    required this.hintHeavyResults,
    required this.struggleAtEasiestResults,
    required this.struggleAtEasiestPenalty,
    required this.instructionWindow,
    required this.readAloudAfterRepeats,
  });

  final int hintWindow;
  final int hintHeavyMinHints;
  final int hintHeavyResults;
  final int struggleAtEasiestResults;
  final int struggleAtEasiestPenalty;
  final int instructionWindow;
  final int readAloudAfterRepeats;
}

class MemoryRules {
  const MemoryRules({
    required this.minPhotoMemories,
    required this.minPersonPhotoMemories,
    required this.minStoryMemories,
    required this.minRoutineItems,
    required this.itemsPerActivity,
    required this.recentUseRecommendations,
  });

  final int minPhotoMemories;
  final int minPersonPhotoMemories;
  final int minStoryMemories;
  final int minRoutineItems;
  final int itemsPerActivity;
  final int recentUseRecommendations;
}

class EngineConfig {
  const EngineConfig({
    required this.configVersion,
    required this.difficulty,
    required this.selection,
    required this.fatigue,
    required this.inSession,
    required this.support,
    required this.memory,
    required this.activityInterestTags,
    required this.contentLanguages,
  });

  final String configVersion;
  final DifficultyRules difficulty;
  final SelectionRules selection;
  final FatigueRules fatigue;
  final InSessionRules inSession;
  final SupportRules support;
  final MemoryRules memory;
  final Map<String, List<String>> activityInterestTags;
  final Map<String, List<String>> contentLanguages;
}

const engineConfig = EngineConfig(
  configVersion: '2026.10.3',
  difficulty: DifficultyRules(
    successScore: 0.8,
    maxHintsForSuccess: 1,
    slowResponseFactor: 1.5,
    struggleScore: 0.5,
    increaseAfterSuccesses: 3,
    decreaseAfterStruggles: 2,
    minResultsBetweenChanges: 3,
    hintsAfterStruggles: 1,
    historyWindow: 40,
  ),
  selection: SelectionRules(
    recentWindow: 5,
    repeatLastPenalty: 60,
    repeatRecentPenalty: 15,
    interestMatchBonus: 20,
    interestBonusCap: 40,
    contextMatchBonus: 10,
    enjoyedBonus: 15,
    notEnjoyedPenalty: 25,
    interruptionPenalty: 10,
    familiarBonus: 10,
    lowEngagementWindow: 3,
    lowEngagementThreshold: 2,
    coldStartOrder: [
      'picture-pairs',
      'name-the-object',
      'sort-into-groups',
      'daily-sequence',
      'photo-recall',
      'familiar-faces',
      'story-time',
    ],
  ),
  fatigue: FatigueRules(
    feedbackWindowHours: 3,
    observationWindowHours: 8,
    lowEffortSlugs: ['story-time', 'picture-pairs', 'name-the-object'],
    breakMinutes: 10,
    caregiverSevereAction: 'end_session',
  ),
  inSession: InSessionRules(
    autoHintAfterErrors: 2,
    autoHintAfterErrorsAssisted: 1,
    struggledRoundErrors: 2,
    shortenAfterStruggledRounds: 2,
    breakAfterStruggledRounds: 3,
    mildFatigueMaxRemainingRounds: 1,
  ),
  support: SupportRules(
    hintWindow: 3,
    hintHeavyMinHints: 2,
    hintHeavyResults: 2,
    struggleAtEasiestResults: 2,
    struggleAtEasiestPenalty: 50,
    instructionWindow: 3,
    readAloudAfterRepeats: 3,
  ),
  memory: MemoryRules(
    minPhotoMemories: 3,
    minPersonPhotoMemories: 2,
    minStoryMemories: 1,
    minRoutineItems: 3,
    itemsPerActivity: 6,
    recentUseRecommendations: 3,
  ),
  activityInterestTags: {
    'picture-pairs': ['animals', 'nature', 'flowers', 'festivals', 'birds'],
    'name-the-object': ['household', 'cooking', 'tools', 'market', 'farming'],
    'sort-into-groups': [
      'cooking',
      'food',
      'clothes',
      'gardening',
      'household',
      'market',
    ],
    'daily-sequence': [
      'cooking',
      'tea',
      'prayer',
      'gardening',
      'routine',
      'weaving',
    ],
  },
  contentLanguages: {
    'picture-pairs': ['*'],
    'photo-recall': ['*'],
    'familiar-faces': ['*'],
    'story-time': ['*'],
    'name-the-object': ['en', 'hi', 'as', 'bn'],
    'sort-into-groups': ['en', 'hi', 'as', 'bn'],
    'daily-sequence': ['en', 'hi', 'as', 'bn'],
  },
);
