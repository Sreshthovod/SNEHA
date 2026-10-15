import 'dart:convert';

import 'package:sqflite/sqflite.dart';
import 'package:uuid/uuid.dart';

import '../local/local_database.dart';
import 'clock.dart';

/// Outcome of one activity run, in the shape the server validates
/// (schemas/activities.py ResultCreate).
class ActivityOutcome {
  const ActivityOutcome({
    required this.activityId,
    required this.difficultyLevel,
    required this.startedAt,
    required this.completedAt,
    required this.correctCount,
    required this.attemptCount,
    required this.hintCount,
    required this.durationMs,
    required this.abandoned,
    this.score,
    this.metrics = const {},
    this.fatigueReported = false,
    this.engagement,
    this.recommendationId,
  }) : assert(correctCount <= attemptCount);

  final String activityId;
  final int difficultyLevel;
  final DateTime startedAt;
  final DateTime completedAt;

  /// 0..1, or null for unscored activities (e.g. story time).
  final double? score;
  final int correctCount;
  final int attemptCount;
  final int hintCount;
  final int durationMs;
  final bool abandoned;

  /// Numeric only, snake_case keys, at most 20 entries.
  final Map<String, num> metrics;

  /// The person said they were tired (explicit fatigue report).
  final bool fatigueReported;

  /// enjoyed | neutral | not_enjoyed; null = not asked / not answered.
  final String? engagement;

  /// Only for SERVER recommendations (it references a server record).
  final String? recommendationId;
}

const engagementValues = {'enjoyed', 'neutral', 'not_enjoyed'};

/// Conversation METADATA only. There is deliberately no field for words spoken
/// or typed: transcripts are never stored or synced.
class ConversationSummary {
  const ConversationSummary({
    required this.startedAt,
    required this.endedAt,
    required this.language,
    required this.turnCount,
    required this.intents,
  });

  final DateTime startedAt;
  final DateTime endedAt;
  final String language;
  final int turnCount;
  final List<String> intents;
}

/// Writes local records AND their outbox mutations in one SQLite transaction,
/// so nothing recorded offline can be lost or pushed twice.
class ActivityRecorder {
  ActivityRecorder(this._local, {Clock clock = systemClock, Uuid? uuid})
    : _clock = clock,
      _uuid = uuid ?? const Uuid();

  final LocalDatabase _local;
  final Clock _clock;
  final Uuid _uuid;

  static final _metricKey = RegExp(r'^[a-z][a-z0-9_]{0,39}$');

  Future<void> _enqueue(
    Transaction txn, {
    required String patientId,
    required String entityType,
    required String entityId,
    required Map<String, dynamic> data,
  }) => txn.insert('outbox', {
    'mutation_id': _uuid.v4(),
    'patient_id': patientId,
    'entity_type': entityType,
    'entity_id': entityId,
    'payload_json': jsonEncode(data),
    'created_at': isoUtc(_clock()),
  });

  /// Starts a session now. Returns (sessionId, startedAt).
  Future<(String, DateTime)> startSession(String patientId) async {
    final id = _uuid.v4();
    final startedAt = _clock();
    await _local.db.transaction((txn) async {
      await txn.insert('sessions', {
        'id': id,
        'patient_id': patientId,
        'started_at': isoUtc(startedAt),
        'status': 'in_progress',
      });
      await _enqueue(
        txn,
        patientId: patientId,
        entityType: 'activity_session',
        entityId: id,
        data: {
          'id': id,
          'started_at': isoUtc(startedAt),
          'status': 'in_progress',
        },
      );
    });
    return (id, startedAt);
  }

  Future<String> recordResult(
    String patientId,
    String sessionId,
    ActivityOutcome o,
  ) async {
    if (o.metrics.length > 20 ||
        o.metrics.keys.any((k) => !_metricKey.hasMatch(k))) {
      throw ArgumentError('Metrics must be ≤20 snake_case numeric values');
    }
    final score = o.score?.clamp(0.0, 1.0);
    final id = _uuid.v4();
    final data = {
      'id': id,
      'session_id': sessionId,
      'activity_id': o.activityId,
      'difficulty_level': o.difficultyLevel,
      'started_at': isoUtc(o.startedAt),
      'completed_at': isoUtc(o.completedAt),
      'score': score,
      'correct_count': o.correctCount,
      'attempt_count': o.attemptCount,
      'hint_count': o.hintCount,
      'duration_ms': o.durationMs,
      'abandoned': o.abandoned,
      'metrics': o.metrics,
      // Optional feedback fields are only sent when set.
      if (o.fatigueReported) 'fatigue_reported': true,
      if (o.engagement != null) 'engagement': o.engagement,
      if (o.recommendationId != null) 'recommendation_id': o.recommendationId,
    };
    if (o.engagement != null && !engagementValues.contains(o.engagement)) {
      throw ArgumentError.value(o.engagement, 'engagement');
    }
    await _local.db.transaction((txn) async {
      await txn.insert(
        'results',
        {
          ...data,
          'patient_id': patientId,
          'abandoned': o.abandoned ? 1 : 0,
          'metrics_json': jsonEncode(o.metrics),
          'fatigue_reported': o.fatigueReported ? 1 : 0,
        }..remove('metrics'),
      );
      await _enqueue(
        txn,
        patientId: patientId,
        entityType: 'activity_result',
        entityId: id,
        data: data,
      );
    });
    return id;
  }

  /// Record "Did you enjoy this?" for an already-recorded result.
  ///
  /// Results are immutable on the server, so the answer can only travel with
  /// the result while it is still waiting in the outbox. Returns true if it
  /// will be shared; false if the result was already shared (kept locally).
  Future<bool> setEngagement(String resultId, String? engagement) async {
    if (engagement != null && !engagementValues.contains(engagement)) {
      throw ArgumentError.value(engagement, 'engagement');
    }
    return _local.db.transaction((txn) async {
      await txn.update(
        'results',
        {'engagement': engagement},
        where: 'id = ?',
        whereArgs: [resultId],
      );
      final rows = await txn.query(
        'outbox',
        where:
            "entity_type = 'activity_result' AND entity_id = ? AND last_status IS NULL",
        whereArgs: [resultId],
      );
      if (rows.isEmpty) return false;
      final payload =
          jsonDecode(rows.first['payload_json'] as String)
              as Map<String, dynamic>;
      if (engagement == null) {
        payload.remove('engagement');
      } else {
        payload['engagement'] = engagement;
      }
      await txn.update(
        'outbox',
        {'payload_json': jsonEncode(payload)},
        where: 'seq = ?',
        whereArgs: [rows.first['seq']],
      );
      return true;
    });
  }

  /// [endReason]: completed | user_stopped | fatigue_detected | timeout.
  Future<void> finishSession(
    String patientId,
    String sessionId, {
    required String endReason,
  }) async {
    final endedAt = _clock();
    final status = endReason == 'completed' ? 'completed' : 'abandoned';
    await _local.db.transaction((txn) async {
      final rows = await txn.query(
        'sessions',
        where: 'id = ?',
        whereArgs: [sessionId],
      );
      if (rows.isEmpty) throw StateError('Unknown session $sessionId');
      await txn.update(
        'sessions',
        {
          'ended_at': isoUtc(endedAt),
          'status': status,
          'end_reason': endReason,
        },
        where: 'id = ?',
        whereArgs: [sessionId],
      );
      await _enqueue(
        txn,
        patientId: patientId,
        entityType: 'activity_session',
        entityId: sessionId,
        data: {
          'id': sessionId,
          'started_at': rows.first['started_at'],
          'ended_at': isoUtc(endedAt),
          'status': status,
          'end_reason': endReason,
        },
      );
    });
  }

  Future<void> recordConversation(
    String patientId,
    ConversationSummary c,
  ) async {
    final id = _uuid.v4();
    final intents = c.intents.toSet().take(50).toList();
    await _local.db.transaction(
      (txn) => _enqueue(
        txn,
        patientId: patientId,
        entityType: 'conversation',
        entityId: id,
        data: {
          'id': id,
          'started_at': isoUtc(c.startedAt),
          'ended_at': isoUtc(c.endedAt),
          'language': c.language,
          'provider': 'deterministic',
          'fallback_used': false,
          'turn_count': c.turnCount,
          'intents': intents,
        },
      ),
    );
  }
}

/// Helpers for adjusting an outcome before recording.
extension ActivityOutcomeCopy on ActivityOutcome {
  static ActivityOutcome withMetrics(
    ActivityOutcome o,
    Map<String, num> extra,
  ) => ActivityOutcome(
    activityId: o.activityId,
    difficultyLevel: o.difficultyLevel,
    startedAt: o.startedAt,
    completedAt: o.completedAt,
    score: o.score,
    correctCount: o.correctCount,
    attemptCount: o.attemptCount,
    hintCount: o.hintCount,
    durationMs: o.durationMs,
    abandoned: o.abandoned,
    metrics: {...o.metrics, ...extra},
    fatigueReported: o.fatigueReported,
    engagement: o.engagement,
    recommendationId: o.recommendationId,
  );
}
