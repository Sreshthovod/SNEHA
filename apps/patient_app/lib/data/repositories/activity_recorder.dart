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

const fatigueLevels = {'mild', 'severe'};

/// Must match ActivityEventType in services/api/app/models/enums.py.
const activityEventTypes = {
  'activity_started',
  'attempt',
  'hint_requested',
  'hint_auto',
  'round_solved',
  'round_skipped',
  'paused',
  'resumed',
  'fatigue_reported',
  'stop_requested',
  'adaptation',
  'break_taken',
  'break_declined',
  'activity_ended',
  'instructions_repeated',
};

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
  ///
  /// Ending is once only: if the session has already ended (a double tap, a
  /// retry, a stop that raced a completion), nothing is written or queued, so
  /// the first ending, e.g. a stop, always stands.
  /// [endedAt] defaults to now.
  Future<void> finishSession(
    String patientId,
    String sessionId, {
    required String endReason,
    DateTime? endedAt,
  }) async {
    endedAt ??= _clock();
    final status = endReason == 'completed' ? 'completed' : 'abandoned';
    await _local.db.transaction((txn) async {
      final rows = await txn.query(
        'sessions',
        where: 'id = ?',
        whereArgs: [sessionId],
      );
      if (rows.isEmpty) throw StateError('Unknown session $sessionId');
      if (rows.first['ended_at'] != null) return;
      await txn.update(
        'sessions',
        {
          'ended_at': isoUtc(endedAt!),
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

  /// Appends one in-activity event (schemas/events.py). Stored on the phone
  /// and queued for sync in one transaction, so it is never held only in
  /// screen state. [data] must contain only the small typed values the server
  /// accepts: no free text.
  Future<String> recordEvent(
    String patientId, {
    required String sessionId,
    required String activityId,
    required int seq,
    required String eventType,
    int? roundIndex,
    Map<String, Object> data = const {},
  }) async {
    if (!activityEventTypes.contains(eventType)) {
      throw ArgumentError.value(eventType, 'eventType');
    }
    final id = _uuid.v4();
    final occurredAt = isoUtc(_clock());
    final payload = {
      'id': id,
      'session_id': sessionId,
      'activity_id': activityId,
      'seq': seq,
      'event_type': eventType,
      'occurred_at': occurredAt,
      'round_index': ?roundIndex,
      'data': data,
    };
    await _local.db.transaction((txn) async {
      await txn.insert('activity_events', {
        'id': id,
        'patient_id': patientId,
        'session_id': sessionId,
        'activity_id': activityId,
        'seq': seq,
        'event_type': eventType,
        'occurred_at': occurredAt,
        'round_index': roundIndex,
        'data_json': jsonEncode(data),
      });
      await _enqueue(
        txn,
        patientId: patientId,
        entityType: 'activity_event',
        entityId: id,
        data: payload,
      );
    });
    return id;
  }

  /// A caregiver's tiredness report made on this phone. Kept locally so the
  /// phone's engine and any running activity respect it offline, and synced as
  /// a fatigue observation (level and time only; the server writes a fixed
  /// note). The person's own "I'm tired" is recorded on the result and the
  /// session instead, so it is never counted twice.
  Future<String> reportCaregiverFatigue(
    String patientId, {
    required String level,
  }) async {
    if (!fatigueLevels.contains(level)) {
      throw ArgumentError.value(level, 'level');
    }
    final id = _uuid.v4();
    final at = isoUtc(_clock());
    await _local.db.transaction((txn) async {
      await txn.insert('fatigue_reports', {
        'id': id,
        'patient_id': patientId,
        'level': level,
        'source': 'caregiver_phone',
        'reported_at': at,
      });
      await _enqueue(
        txn,
        patientId: patientId,
        entityType: 'fatigue_report',
        entityId: id,
        data: {'id': id, 'level': level, 'reported_at': at},
      );
    });
    return id;
  }

  /// Sessions this phone left running (the app was closed or killed during an
  /// activity) are ended as `timeout`, i.e. interrupted, at the time of their
  /// last recorded step, never "now", so durations stay honest. Call only when
  /// no activity is open (at app start). Returns how many were closed.
  Future<int> closeInterruptedSessions(String patientId) async {
    final open = await _local.db.query(
      'sessions',
      where: 'patient_id = ? AND ended_at IS NULL',
      whereArgs: [patientId],
    );
    for (final row in open) {
      final id = row['id'] as String;
      final last = await _local.db.rawQuery(
        '''SELECT MAX(t) AS t FROM (
             SELECT MAX(occurred_at) AS t FROM activity_events WHERE session_id = ?
             UNION ALL
             SELECT MAX(completed_at) AS t FROM results WHERE session_id = ?)''',
        [id, id],
      );
      final at = last.first['t'] as String? ?? row['started_at'] as String;
      await finishSession(
        patientId,
        id,
        endReason: 'timeout',
        endedAt: DateTime.parse(at).toUtc(),
      );
    }
    return open.length;
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
