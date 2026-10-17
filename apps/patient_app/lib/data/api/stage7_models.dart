/// Typed models for the Stage 3–5 endpoints the patient app uses.
///
/// Source of truth: packages/api_contracts/openapi.json (CatalogEntry,
/// RecommendationOut, AnalyzeResponse, SpeechStatus, TranscriptionOut).
/// Parsing is strict about required fields and lenient about extra ones.
library;

import 'models.dart';

// ---------------------------------------------------------------- catalog

/// GET /activities/catalog → CatalogEntry: per-level parameters and the
/// plain-language instructions, hint and stop rules for one activity.
class ActivitySpec {
  const ActivitySpec({
    required this.activityId,
    required this.slug,
    required this.instructions,
    required this.hint,
    required this.stop,
    required this.levels,
  });

  final String activityId;
  final String slug;
  final String instructions;
  final String hint;
  final String stop;

  /// level → parameters, e.g. {2: {"pairs": 4}}.
  final Map<int, Map<String, Object?>> levels;

  factory ActivitySpec.fromJson(Map<String, dynamic> j) => ActivitySpec(
    activityId: j['id'] as String,
    slug: j['slug'] as String,
    instructions: j['instructions'] as String,
    hint: j['hint'] as String,
    stop: j['stop'] as String,
    levels: {
      for (final l in j['levels'] as List<dynamic>)
        (l as Map<String, dynamic>)['level'] as int: Map<String, Object?>.from(
          l['parameters'] as Map,
        ),
    },
  );

  Map<String, dynamic> toJson() => {
    'id': activityId,
    'slug': slug,
    'instructions': instructions,
    'hint': hint,
    'stop': stop,
    'levels': [
      for (final e in levels.entries) {'level': e.key, 'parameters': e.value},
    ],
  };
}

// ---------------------------------------------------------------- recommendations

/// RecommendationOut (server engine). Only the fields the app shows or
/// sends back are kept.
class ServerRecommendation {
  const ServerRecommendation({
    required this.id,
    required this.action,
    required this.activityId,
    required this.activitySlug,
    required this.activityTitle,
    required this.difficulty,
    required this.reasonCodes,
    required this.breakMinutes,
    required this.hintsEnabled,
    this.memoryItemIds = const [],
    this.readAloudFirst = false,
  });

  final String id;

  /// activity | break | stop | none
  final String action;
  final String? activityId;
  final String? activitySlug;
  final String? activityTitle;
  final int? difficulty;
  final List<String> reasonCodes;
  final int? breakMinutes;
  final bool hintsEnabled;

  /// `content_refs.memory_item_ids`: approved memories chosen for this
  /// activity, most relevant first.
  final List<String> memoryItemIds;

  /// Read each question aloud when it appears (engine 1.2.0).
  final bool readAloudFirst;

  factory ServerRecommendation.fromJson(Map<String, dynamic> j) =>
      ServerRecommendation(
        id: j['id'] as String,
        action: j['action'] as String,
        activityId: j['activity_id'] as String?,
        activitySlug: j['activity_slug'] as String?,
        activityTitle: j['activity_title'] as String?,
        difficulty: j['difficulty'] as int?,
        reasonCodes: [
          for (final c in j['reason_codes'] as List<dynamic>) c as String,
        ],
        breakMinutes: j['break_minutes'] as int?,
        hintsEnabled: j['hints_enabled'] as bool? ?? false,
        readAloudFirst: j['read_aloud_first'] as bool? ?? false,
        memoryItemIds: [
          for (final id
              in ((j['content_refs']
                          as Map<String, dynamic>?)?['memory_item_ids']
                      as List<dynamic>? ??
                  const []))
            id as String,
        ],
      );
}

// ---------------------------------------------------------------- conversation

/// A mention of a person, place or routine. Only `stored_fact` mentions are
/// backed by caregiver-approved data; `uncertain` ones are never shown as
/// facts.
class Mention {
  const Mention({
    required this.mention,
    required this.storedFact,
    this.memoryId,
    this.routineId,
  });

  final String mention;
  final bool storedFact;
  final String? memoryId;
  final String? routineId;

  factory Mention.fromJson(Map<String, dynamic> j) => Mention(
    mention: j['mention'] as String,
    storedFact: j['status'] == 'stored_fact',
    memoryId: j['memory_id'] as String?,
    routineId: j['routine_id'] as String?,
  );
}

/// A possible new memory heard in the conversation. Never saved
/// automatically: the person may choose to send it to their family, who
/// approve it first.
class MemoryCandidate {
  const MemoryCandidate({
    required this.title,
    required this.kind,
    this.description,
  });

  final String title;
  final String kind;
  final String? description;

  factory MemoryCandidate.fromJson(Map<String, dynamic> j) => MemoryCandidate(
    title: j['title'] as String,
    kind: j['kind'] as String,
    description: j['description'] as String?,
  );
}

/// POST /conversation/analyze → AnalyzeResponse. The app shows only the
/// server's patient-safe `reply` (never model output), approved memories,
/// the safety message and the suggestion.
class ConversationTurn {
  const ConversationTurn({
    required this.conversationId,
    required this.provider,
    required this.fallbackUsed,
    required this.reply,
    required this.memories,
    required this.candidates,
    required this.distress,
    required this.safetyMessage,
    required this.suggestion,
    required this.people,
    required this.places,
  });

  final String conversationId;
  final String provider;
  final bool fallbackUsed;
  final String reply;
  final List<MemoryItem> memories;
  final List<MemoryCandidate> candidates;
  final bool distress;
  final String? safetyMessage;
  final ServerRecommendation? suggestion;
  final List<Mention> people;
  final List<Mention> places;

  factory ConversationTurn.fromJson(Map<String, dynamic> j) {
    final understanding = j['understanding'] as Map<String, dynamic>;
    final safety = j['safety'] as Map<String, dynamic>;
    final fallback = j['fallback'] as Map<String, dynamic>;
    final suggestion = j['suggestion'] as Map<String, dynamic>?;
    return ConversationTurn(
      conversationId: j['conversation_id'] as String,
      provider: j['provider'] as String,
      fallbackUsed: fallback['used'] as bool,
      reply: j['reply'] as String,
      memories: [
        for (final m in j['memories'] as List<dynamic>)
          MemoryItem.fromJson(m as Map<String, dynamic>),
      ],
      candidates: [
        for (final c in j['memory_candidates'] as List<dynamic>)
          MemoryCandidate.fromJson(c as Map<String, dynamic>),
      ],
      distress: safety['distress_detected'] as bool,
      safetyMessage: safety['message'] as String?,
      suggestion: suggestion == null
          ? null
          : ServerRecommendation.fromJson(suggestion),
      people: [
        for (final p in understanding['people'] as List<dynamic>)
          Mention.fromJson(p as Map<String, dynamic>),
      ],
      places: [
        for (final p in understanding['places'] as List<dynamic>)
          Mention.fromJson(p as Map<String, dynamic>),
      ],
    );
  }
}

// ---------------------------------------------------------------- speech

/// GET /speech/status, reduced to what the phone needs.
class ServerSpeechStatus {
  const ServerSpeechStatus({required this.recognition});

  /// Languages for which server speech recognition is ready right now.
  final Set<String> recognition;

  factory ServerSpeechStatus.fromJson(Map<String, dynamic> j) =>
      ServerSpeechStatus(
        recognition: {
          for (final l in j['languages'] as List<dynamic>)
            if ((l as Map<String, dynamic>)['speech_recognition'] == true)
              l['language'] as String,
        },
      );
}

/// TranscriptionOut. The text is only ever placed in the input box for the
/// person to check; it is never sent automatically or stored.
class Transcription {
  const Transcription({required this.text, required this.noSpeech});

  final String text;
  final bool noSpeech;

  factory Transcription.fromJson(Map<String, dynamic> j) => Transcription(
    text: j['text'] as String,
    noSpeech: j['no_speech'] as bool,
  );
}
