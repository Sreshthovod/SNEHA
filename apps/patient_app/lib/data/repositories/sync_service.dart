import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:sqflite/sqflite.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../local/local_database.dart';
import 'clock.dart';
import 'media_cache.dart';
import 'profile_repository.dart';

enum SyncOutcome { success, offline, needsRepair, failed }

class SyncReport {
  const SyncReport(
    this.outcome, {
    this.pushed = 0,
    this.needsAttention = 0,
    this.pulled = 0,
    this.message,
  });

  final SyncOutcome outcome;
  final int pushed;
  final int needsAttention;
  final int pulled;
  final String? message;
}

/// Per-profile sync status shown on the sync screen.
class SyncStatus {
  const SyncStatus({
    required this.pending,
    required this.needsAttention,
    this.lastSuccessAt,
    this.lastAttemptAt,
    this.lastError,
  });

  final int pending;
  final int needsAttention;
  final DateTime? lastSuccessAt;
  final DateTime? lastAttemptAt;
  final String? lastError;
}

/// An outbox entry the server did not accept. Always kept on the phone.
class AttentionItem {
  const AttentionItem({
    required this.mutationId,
    required this.entityType,
    required this.status,
    required this.attempts,
    required this.createdAt,
    this.detail,
  });

  final String mutationId;
  final String entityType;

  /// conflict | rejected | failed
  final String status;
  final int attempts;
  final DateTime createdAt;
  final String? detail;

  /// A conflict means the server already holds a different copy; retrying
  /// cannot change that. Rejected/failed items may succeed later.
  bool get retryable => status != 'conflict';
}

/// Exponential backoff for entries the server did not acknowledge or that hit
/// a server error. Network failures do NOT count: being offline for days is
/// normal and must never exhaust retries.
class RetryPolicy {
  const RetryPolicy({
    this.maxAttempts = 8,
    this.baseDelay = const Duration(seconds: 30),
    this.maxDelay = const Duration(hours: 6),
  });

  final int maxAttempts;
  final Duration baseDelay;
  final Duration maxDelay;

  Duration delayAfter(int attempts) {
    final factor = 1 << (attempts - 1).clamp(0, 20);
    final ms = baseDelay.inMilliseconds * factor;
    return ms > maxDelay.inMilliseconds ? maxDelay : Duration(milliseconds: ms);
  }
}

/// Explicit device ⇄ server sync (docs/offline-strategy.md):
/// 1. push the outbox in creation order, 200 at a time;
/// 2. remove `applied`/`duplicate`; keep `conflict`/`rejected` for attention;
/// 3. pull the change log from the stored cursor until `has_more` is false,
///    applying each page and its new cursor in one transaction;
/// 4. refresh profile + consent and download missing memory photos.
class SyncService extends ChangeNotifier {
  SyncService({
    required LocalDatabase local,
    required SnehaApiClient api,
    required ProfileRepository profiles,
    required MediaCache media,
    Clock clock = systemClock,
    this.retry = const RetryPolicy(),
  }) : _local = local,
       _api = api,
       _profiles = profiles,
       _media = media,
       _clock = clock;

  static const int pushBatchSize = 200;
  final RetryPolicy retry;

  final LocalDatabase _local;
  final SnehaApiClient _api;
  final ProfileRepository _profiles;
  final MediaCache _media;
  final Clock _clock;

  bool _running = false;
  bool get isRunning => _running;

  Future<SyncStatus> status(String patientId) async {
    final db = _local.db;
    final pending =
        Sqflite.firstIntValue(
          await db.rawQuery(
            'SELECT COUNT(*) FROM outbox WHERE patient_id = ? AND last_status IS NULL',
            [patientId],
          ),
        ) ??
        0;
    final attention =
        Sqflite.firstIntValue(
          await db.rawQuery(
            'SELECT COUNT(*) FROM outbox WHERE patient_id = ? AND last_status IS NOT NULL',
            [patientId],
          ),
        ) ??
        0;
    final rows = await db.query(
      'sync_state',
      where: 'patient_id = ?',
      whereArgs: [patientId],
    );
    final row = rows.isEmpty ? const <String, Object?>{} : rows.first;
    DateTime? date(Object? v) => v == null ? null : DateTime.parse(v as String);
    return SyncStatus(
      pending: pending,
      needsAttention: attention,
      lastSuccessAt: date(row['last_success_at']),
      lastAttemptAt: date(row['last_attempt_at']),
      lastError: row['last_error'] as String?,
    );
  }

  /// Entries that could not be shared, oldest first. Never deleted silently.
  Future<List<AttentionItem>> attentionItems(String patientId) async {
    final rows = await _local.db.query(
      'outbox',
      where: 'patient_id = ? AND last_status IS NOT NULL',
      whereArgs: [patientId],
      orderBy: 'seq',
    );
    return [
      for (final r in rows)
        AttentionItem(
          mutationId: r['mutation_id'] as String,
          entityType: r['entity_type'] as String,
          status: r['last_status'] as String,
          attempts: r['attempts'] as int,
          createdAt: DateTime.parse(r['created_at'] as String),
          detail: r['last_detail'] as String?,
        ),
    ];
  }

  /// Put a needs-attention entry back in the queue (user pressed "Try again").
  Future<void> retryItem(String mutationId) => _local.db.update(
    'outbox',
    {
      'last_status': null,
      'last_detail': null,
      'attempts': 0,
      'next_attempt_at': null,
    },
    where:
        "mutation_id = ? AND last_status IS NOT NULL AND last_status != 'conflict'",
    whereArgs: [mutationId],
  );

  /// Entries waiting for a later retry because of earlier server errors.
  Future<int> backedOffCount(String patientId) async =>
      Sqflite.firstIntValue(
        await _local.db.rawQuery(
          'SELECT COUNT(*) FROM outbox WHERE patient_id = ? AND last_status IS NULL '
          'AND next_attempt_at IS NOT NULL AND next_attempt_at > ?',
          [patientId, isoUtc(_clock())],
        ),
      ) ??
      0;

  Future<SyncReport> syncProfile(String patientId) async {
    if (_running) {
      return const SyncReport(
        SyncOutcome.failed,
        message: 'A sync is already running.',
      );
    }
    _running = true;
    notifyListeners();
    try {
      final report = await _sync(patientId);
      await _local.db.update(
        'sync_state',
        {
          'last_attempt_at': isoUtc(_clock()),
          if (report.outcome == SyncOutcome.success)
            'last_success_at': isoUtc(_clock()),
          'last_error': report.outcome == SyncOutcome.success
              ? null
              : report.message,
        },
        where: 'patient_id = ?',
        whereArgs: [patientId],
      );
      return report;
    } finally {
      _running = false;
      notifyListeners();
    }
  }

  Future<SyncReport> _sync(String patientId) async {
    final profile = await _profiles.get(patientId);
    final token = await _profiles.token(patientId);
    if (profile == null || token == null || profile.needsRepair) {
      return const SyncReport(
        SyncOutcome.needsRepair,
        message: 'This phone needs a new pairing code to share progress.',
      );
    }
    try {
      final (pushed, attention) = await _push(patientId, token);
      final pulled = await _pull(patientId, token);
      await _refreshProfile(patientId, token);
      await _refreshCatalogSpecs(token);
      await _downloadPhotos(patientId, token);
      return SyncReport(
        SyncOutcome.success,
        pushed: pushed,
        needsAttention: attention,
        pulled: pulled,
      );
    } on ApiException catch (e) {
      if (e.isUnauthorized) {
        await _profiles.markNeedsRepair(patientId);
        return const SyncReport(
          SyncOutcome.needsRepair,
          message:
              'This phone was signed out. Ask your caregiver for a new code.',
        );
      }
      if (e.isNetwork) {
        return const SyncReport(
          SyncOutcome.offline,
          message:
              'No internet connection. Your progress is safe on this phone.',
        );
      }
      return SyncReport(SyncOutcome.failed, message: e.message);
    }
  }

  /// Count one failed attempt for [ids]: back off, or give up after
  /// [RetryPolicy.maxAttempts] (kept as 'failed', never deleted).
  Future<int> _countFailure(
    DatabaseExecutor db,
    List<String> ids,
    String detail,
  ) async {
    var gaveUp = 0;
    for (final id in ids) {
      final rows = await db.query(
        'outbox',
        columns: ['attempts'],
        where: 'mutation_id = ?',
        whereArgs: [id],
      );
      if (rows.isEmpty) continue;
      final attempts = (rows.first['attempts'] as int) + 1;
      if (attempts >= retry.maxAttempts) {
        gaveUp++;
        await db.update(
          'outbox',
          {
            'attempts': attempts,
            'last_status': 'failed',
            'last_detail': detail,
            'next_attempt_at': null,
          },
          where: 'mutation_id = ?',
          whereArgs: [id],
        );
      } else {
        await db.update(
          'outbox',
          {
            'attempts': attempts,
            'last_detail': detail,
            'next_attempt_at': isoUtc(_clock().add(retry.delayAfter(attempts))),
          },
          where: 'mutation_id = ?',
          whereArgs: [id],
        );
      }
    }
    return gaveUp;
  }

  Future<(int, int)> _push(String patientId, String token) async {
    final installId = await _local.installId();
    var pushed = 0;
    var attention = 0;
    final tried = <String>{};
    while (true) {
      // Pending entries that are due now, in creation order. Entries already
      // tried in this run are skipped so one sync never loops on them.
      final rows =
          (await _local.db.query(
                'outbox',
                where:
                    'patient_id = ? AND last_status IS NULL AND '
                    '(next_attempt_at IS NULL OR next_attempt_at <= ?)',
                whereArgs: [patientId, isoUtc(_clock())],
                orderBy: 'seq',
              ))
              .where((r) => !tried.contains(r['mutation_id']))
              .take(pushBatchSize)
              .toList();
      if (rows.isEmpty) break;
      final ids = [for (final r in rows) r['mutation_id'] as String];
      tried.addAll(ids);
      final mutations = [
        for (final r in rows)
          {
            'mutation_id': r['mutation_id'],
            'entity_type': r['entity_type'],
            'operation': 'upsert',
            'data': jsonDecode(r['payload_json'] as String),
          },
      ];
      final List<MutationResult> results;
      try {
        results = await _api.syncPush(
          token,
          deviceInstallId: installId,
          mutations: mutations,
        );
      } on ApiException catch (e) {
        // Offline / signed out: nothing is counted, entries stay pending.
        if (e.isNetwork || e.isUnauthorized) rethrow;
        // A server-side failure (5xx, malformed reply…): back off and retry
        // later; the whole batch was not processed.
        attention += await _countFailure(_local.db, ids, e.message);
        rethrow;
      }
      final byId = {for (final r in results) r.mutationId: r};
      await _local.db.transaction((txn) async {
        final unacknowledged = <String>[];
        for (final id in ids) {
          final result = byId[id];
          if (result == null) {
            unacknowledged.add(id);
            continue;
          }
          if (result.status == 'applied' || result.status == 'duplicate') {
            await txn.delete(
              'outbox',
              where: 'mutation_id = ?',
              whereArgs: [id],
            );
            pushed++;
          } else {
            await txn.rawUpdate(
              'UPDATE outbox SET attempts = attempts + 1, last_status = ?, '
              'last_detail = ?, next_attempt_at = NULL WHERE mutation_id = ?',
              [result.status, result.detail, id],
            );
            attention++;
          }
        }
        if (unacknowledged.isNotEmpty) {
          attention += await _countFailure(
            txn,
            unacknowledged,
            'The server did not confirm this item.',
          );
        }
      });
    }
    return (pushed, attention);
  }

  Future<int> _pull(String patientId, String token) async {
    var pulled = 0;
    while (true) {
      final cursorRows = await _local.db.query(
        'sync_state',
        columns: ['cursor'],
        where: 'patient_id = ?',
        whereArgs: [patientId],
      );
      final since = cursorRows.isEmpty ? 0 : cursorRows.first['cursor'] as int;
      final page = await _api.syncPull(token, since: since);
      final orphanedPhotos = <String>[];
      await _local.db.transaction((txn) async {
        for (final change in page.changes) {
          orphanedPhotos.addAll(await _apply(txn, patientId, change));
        }
        await txn.update(
          'sync_state',
          {'cursor': page.nextSince},
          where: 'patient_id = ?',
          whereArgs: [patientId],
        );
      });
      for (final fileId in orphanedPhotos) {
        await _media.delete(patientId, fileId);
      }
      pulled += page.changes.length;
      if (!page.hasMore || page.nextSince == since) break;
    }
    return pulled;
  }

  /// Applies one change. Returns media file IDs whose photo should be deleted.
  Future<List<String>> _apply(
    Transaction txn,
    String patientId,
    SyncChange c,
  ) async {
    final data = c.data;
    switch (c.entityType) {
      case 'activity_definition':
        if (c.isDelete) {
          await txn.delete('catalog', where: 'id = ?', whereArgs: [c.entityId]);
        } else {
          final a = CatalogActivity.fromJson(data!);
          await txn.insert('catalog', {
            'id': a.id,
            'slug': a.slug,
            'version': a.version,
            'title': a.title,
            'description': a.description,
            'activity_type': a.activityType,
            'min_difficulty': a.minDifficulty,
            'max_difficulty': a.maxDifficulty,
            'default_duration_seconds': a.defaultDurationSeconds,
            'uses_memory_bank': a.usesMemoryBank ? 1 : 0,
            'is_active': 1,
          }, conflictAlgorithm: ConflictAlgorithm.replace);
        }
      case 'memory_item':
        final old = await txn.query(
          'memories',
          columns: ['media_file_id', 'local_photo_path', 'version'],
          where: 'id = ? AND patient_id = ?',
          whereArgs: [c.entityId, patientId],
        );
        final oldFile = old.isEmpty
            ? null
            : old.first['media_file_id'] as String?;
        // Defence in depth: the server only sends approved memories of this
        // patient. Anything else is treated as a delete, never stored.
        final unusable =
            !c.isDelete &&
            (data!['status'] != 'approved' || data['patient_id'] != patientId);
        if (unusable) debugPrint('Sync: refused a non-approved memory');
        if (c.isDelete || unusable) {
          await txn.delete(
            'memories',
            where: 'id = ? AND patient_id = ?',
            whereArgs: [c.entityId, patientId],
          );
          return [?oldFile];
        }
        final m = MemoryItem.fromJson(data!);
        // Never silently replace an approved memory with an OLDER version
        // (e.g. a stale page replayed after a restart).
        if (old.isNotEmpty && (old.first['version'] as int) > m.version) {
          debugPrint('Sync: kept newer local copy of memory ${m.id}');
          return const [];
        }
        final keepPhoto = oldFile != null && oldFile == m.mediaFileId;
        await txn.insert('memories', {
          'id': m.id,
          'patient_id': patientId,
          'kind': m.kind,
          'title': m.title,
          'description': m.description,
          'approx_year': m.approxYear,
          'relationship': m.relationship,
          'tags_json': jsonEncode(m.tags),
          'media_file_id': m.mediaFileId,
          'version': m.version,
          'local_photo_path': keepPhoto ? old.first['local_photo_path'] : null,
        }, conflictAlgorithm: ConflictAlgorithm.replace);
        return [if (oldFile != null && !keepPhoto) oldFile];
      case 'memory_relationship':
        if (c.isDelete) {
          await txn.delete(
            'memory_links',
            where: 'id = ?',
            whereArgs: [c.entityId],
          );
        } else {
          await txn.insert('memory_links', {
            'id': c.entityId,
            'patient_id': patientId,
            'from_memory_id': data!['from_memory_id'],
            'to_memory_id': data['to_memory_id'],
            'relation_type': data['relation_type'],
          }, conflictAlgorithm: ConflictAlgorithm.replace);
        }
      case 'routine_item':
        if (c.isDelete) {
          await txn.delete(
            'routines',
            where: 'id = ?',
            whereArgs: [c.entityId],
          );
        } else {
          final r = RoutineItem.fromJson(data!);
          await txn.insert('routines', {
            'id': r.id,
            'patient_id': patientId,
            'title': r.title,
            'local_time': r.localTime,
            'days_of_week': r.daysOfWeek,
            'is_active': r.isActive ? 1 : 0,
          }, conflictAlgorithm: ConflictAlgorithm.replace);
        }
      case 'personalization_state':
        if (!c.isDelete) {
          await txn.insert('personalization', {
            'patient_id': patientId,
            'activity_id': data!['activity_id'],
            'current_difficulty': data['current_difficulty'],
            'rules_version': data['rules_version'],
            'state_json': jsonEncode(data['state']),
            'state_updated_at': data['state_updated_at'],
          }, conflictAlgorithm: ConflictAlgorithm.replace);
        }
      case 'fatigue_report':
        // A caregiver's tiredness report (level and time only). Replaces a
        // report made on this phone with the same ID: same record.
        if (c.isDelete) {
          await txn.delete(
            'fatigue_reports',
            where: 'id = ? AND patient_id = ?',
            whereArgs: [c.entityId, patientId],
          );
        } else {
          final local = await txn.query(
            'fatigue_reports',
            columns: ['source'],
            where: 'id = ?',
            whereArgs: [c.entityId],
          );
          await txn.insert('fatigue_reports', {
            'id': c.entityId,
            'patient_id': patientId,
            // No level given on the dashboard = treat as "a little tired".
            'level': data!['level'] as String? ?? 'mild',
            'source': local.isEmpty
                ? (data['source'] == 'device'
                      ? 'caregiver_phone'
                      : 'caregiver_dashboard')
                : local.first['source'],
            'reported_at': data['observed_at'],
          }, conflictAlgorithm: ConflictAlgorithm.replace);
        }
      default:
        // Unknown entity types from a newer server are skipped, not fatal.
        debugPrint('Sync: ignoring unknown entity type ${c.entityType}');
    }
    return const [];
  }

  Future<void> _refreshProfile(String patientId, String token) async {
    final patient = await _api.getPatient(token, patientId);
    await _profiles.updateFromServer(patient);
    final consents = await _api.getConsents(token, patientId);
    await _profiles.saveConsents(patientId, consents);
    await _refreshPreferences(patientId, token);
  }

  /// Caregiver-approved interests feed the on-device engine. Best effort: an
  /// older server without the endpoint, or no permission, is not an error.
  Future<void> _refreshPreferences(String patientId, String token) async {
    try {
      final prefs = await _api.getPreferences(token, patientId);
      await _local.db.insert('preferences', {
        'patient_id': patientId,
        'interests_json': jsonEncode(prefs.interests),
        'disliked_json': jsonEncode(prefs.dislikedActivitySlugs),
        'fetched_at': isoUtc(_clock()),
      }, conflictAlgorithm: ConflictAlgorithm.replace);
    } on ApiException catch (e) {
      if (e.isUnauthorized || e.isNetwork) rethrow;
      debugPrint('Sync: preferences not available (${e.code})');
    }
  }

  /// Activity specs (per-level parameters, instructions, hints). Global, so
  /// one refresh serves every profile. Best effort like preferences.
  Future<void> _refreshCatalogSpecs(String token) async {
    try {
      final specs = await _api.getCatalogSpecs(token);
      await _local.db.transaction((txn) async {
        for (final spec in specs) {
          await txn.insert('catalog_specs', {
            'activity_id': spec.activityId,
            'slug': spec.slug,
            'spec_json': jsonEncode(spec.toJson()),
            'fetched_at': isoUtc(_clock()),
          }, conflictAlgorithm: ConflictAlgorithm.replace);
        }
      });
    } on ApiException catch (e) {
      if (e.isUnauthorized || e.isNetwork) rethrow;
      debugPrint('Sync: activity specs not available (${e.code})');
    }
  }

  Future<void> _downloadPhotos(String patientId, String token) async {
    final rows = await _local.db.query(
      'memories',
      columns: ['id', 'media_file_id'],
      where:
          'patient_id = ? AND media_file_id IS NOT NULL AND local_photo_path IS NULL',
      whereArgs: [patientId],
    );
    for (final r in rows) {
      final fileId = r['media_file_id'] as String;
      try {
        final bytes = await _api.downloadFile(token, fileId);
        final path = await _media.save(patientId, fileId, bytes);
        await _local.db.update(
          'memories',
          {'local_photo_path': path},
          where: 'id = ?',
          whereArgs: [r['id']],
        );
      } on ApiException catch (e) {
        // A missing photo must not block sync; retried next time.
        if (e.isUnauthorized || e.isNetwork) rethrow;
        debugPrint('Sync: photo $fileId not downloaded (${e.code})');
      }
    }
  }

  /// Fetch consent only (privacy screen refresh). Requires the internet.
  Future<void> refreshConsents(String patientId) async {
    final token = await _profiles.token(patientId);
    if (token == null) {
      throw const ApiException('unauthorized', 'Not paired', statusCode: 401);
    }
    final consents = await _api.getConsents(token, patientId);
    await _profiles.saveConsents(patientId, consents);
  }
}
