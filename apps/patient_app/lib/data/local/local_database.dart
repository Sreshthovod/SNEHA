import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';
import 'package:uuid/uuid.dart';

/// On-device SQLite database. This is the patient app's source of truth for
/// everything that must work offline. It does NOT synchronise with the server
/// by itself; see docs/offline-strategy.md and data/repositories/sync_service.dart.
class LocalDatabase {
  LocalDatabase._(this.db);

  static const String fileName = 'sneha_local.db';

  /// Bump when adding a migration below. Migrations are append-only.
  static const int schemaVersion = 6;

  static const String _installIdKey = 'install_id';

  final Database db;

  /// Opens (and migrates) the database. Pass [factory] and [path] in tests,
  /// e.g. `databaseFactoryFfi` and `inMemoryDatabasePath`.
  static Future<LocalDatabase> open({
    DatabaseFactory? factory,
    String? path,
    int version = schemaVersion,
  }) async {
    final dbFactory = factory ?? databaseFactory;
    final dbPath = path ?? p.join(await dbFactory.getDatabasesPath(), fileName);
    final db = await dbFactory.openDatabase(
      dbPath,
      options: OpenDatabaseOptions(
        version: version,
        onConfigure: (db) => db.execute('PRAGMA foreign_keys = ON'),
        onCreate: (db, version) => _migrate(db, 0, version),
        onUpgrade: _migrate,
      ),
    );
    final local = LocalDatabase._(db);
    await local._ensureInstallId();
    return local;
  }

  static Future<void> _migrate(Database db, int from, int to) async {
    for (var version = from + 1; version <= to; version++) {
      final statements = migrations[version];
      if (statements == null) {
        throw StateError(
          'Missing local database migration for version $version',
        );
      }
      final batch = db.batch();
      statements.forEach(batch.execute);
      await batch.commit(noResult: true);
    }
  }

  /// version -> SQL statements. Never edit a released migration; add a new one.
  /// Timestamps are ISO-8601 UTC strings, e.g. 2026-01-01T10:00:00.000Z.
  static const Map<int, List<String>> migrations = {
    1: [
      '''
      CREATE TABLE app_meta (
        key TEXT PRIMARY KEY NOT NULL,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL -- ISO-8601 UTC, e.g. 2026-01-01T10:00:00.000Z
      )
      ''',
    ],
    2: [
      // User preferences (language, text size, contrast, motion, active profile).
      '''
      CREATE TABLE settings (
        key TEXT PRIMARY KEY NOT NULL,
        value TEXT NOT NULL
      )
      ''',
      // One row per patient paired on this phone. Tokens are NOT stored here
      // (they live in secure storage, see TokenStore).
      '''
      CREATE TABLE profiles (
        patient_id TEXT PRIMARY KEY NOT NULL,
        user_id TEXT NOT NULL,
        display_name TEXT NOT NULL,
        preferred_name TEXT,
        preferred_language TEXT NOT NULL,
        timezone TEXT NOT NULL,
        paired_at TEXT NOT NULL,
        needs_repair INTEGER NOT NULL DEFAULT 0,
        consents_json TEXT,
        consents_fetched_at TEXT
      )
      ''',
      // Global activity catalog (pulled; patient_id NULL on the server).
      '''
      CREATE TABLE catalog (
        id TEXT PRIMARY KEY NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        version INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        activity_type TEXT NOT NULL,
        min_difficulty INTEGER NOT NULL,
        max_difficulty INTEGER NOT NULL,
        default_duration_seconds INTEGER NOT NULL,
        uses_memory_bank INTEGER NOT NULL,
        is_active INTEGER NOT NULL
      )
      ''',
      // Approved memories only (the server never sends anything else).
      '''
      CREATE TABLE memories (
        id TEXT PRIMARY KEY NOT NULL,
        patient_id TEXT NOT NULL REFERENCES profiles(patient_id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        approx_year INTEGER,
        tags_json TEXT NOT NULL,
        media_file_id TEXT,
        version INTEGER NOT NULL,
        local_photo_path TEXT
      )
      ''',
      '''
      CREATE TABLE memory_links (
        id TEXT PRIMARY KEY NOT NULL,
        patient_id TEXT NOT NULL REFERENCES profiles(patient_id) ON DELETE CASCADE,
        from_memory_id TEXT NOT NULL,
        to_memory_id TEXT NOT NULL,
        relation_type TEXT NOT NULL
      )
      ''',
      '''
      CREATE TABLE routines (
        id TEXT PRIMARY KEY NOT NULL,
        patient_id TEXT NOT NULL REFERENCES profiles(patient_id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        local_time TEXT NOT NULL,
        days_of_week INTEGER NOT NULL,
        is_active INTEGER NOT NULL
      )
      ''',
      '''
      CREATE TABLE personalization (
        patient_id TEXT NOT NULL REFERENCES profiles(patient_id) ON DELETE CASCADE,
        activity_id TEXT NOT NULL,
        current_difficulty INTEGER NOT NULL,
        rules_version TEXT NOT NULL,
        state_json TEXT NOT NULL,
        state_updated_at TEXT NOT NULL,
        PRIMARY KEY (patient_id, activity_id)
      )
      ''',
      '''
      CREATE TABLE sessions (
        id TEXT PRIMARY KEY NOT NULL,
        patient_id TEXT NOT NULL REFERENCES profiles(patient_id) ON DELETE CASCADE,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        status TEXT NOT NULL,
        end_reason TEXT
      )
      ''',
      '''
      CREATE TABLE results (
        id TEXT PRIMARY KEY NOT NULL,
        session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        patient_id TEXT NOT NULL REFERENCES profiles(patient_id) ON DELETE CASCADE,
        activity_id TEXT NOT NULL,
        difficulty_level INTEGER NOT NULL,
        started_at TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        score REAL,
        correct_count INTEGER NOT NULL,
        attempt_count INTEGER NOT NULL,
        hint_count INTEGER NOT NULL,
        duration_ms INTEGER NOT NULL,
        abandoned INTEGER NOT NULL,
        metrics_json TEXT NOT NULL
      )
      ''',
      // Mutations waiting to be pushed, in creation order (seq).
      // last_status NULL = pending; 'conflict'/'rejected' = needs attention.
      '''
      CREATE TABLE outbox (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        mutation_id TEXT NOT NULL UNIQUE,
        patient_id TEXT NOT NULL REFERENCES profiles(patient_id) ON DELETE CASCADE,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        last_status TEXT,
        last_detail TEXT
      )
      ''',
      'CREATE INDEX ix_outbox_patient_pending ON outbox (patient_id, last_status, seq)',
      '''
      CREATE TABLE sync_state (
        patient_id TEXT PRIMARY KEY NOT NULL REFERENCES profiles(patient_id) ON DELETE CASCADE,
        cursor INTEGER NOT NULL DEFAULT 0,
        last_attempt_at TEXT,
        last_success_at TEXT,
        last_error TEXT
      )
      ''',
    ],
    3: [
      // Stage 5: explicit feedback on results (engagement NULL = not answered).
      'ALTER TABLE results ADD COLUMN engagement TEXT',
      'ALTER TABLE results ADD COLUMN fatigue_reported INTEGER NOT NULL DEFAULT 0',
      'ALTER TABLE results ADD COLUMN recommendation_id TEXT',
      // Retry with exponential backoff. last_status: NULL pending,
      // 'conflict' | 'rejected' | 'failed' (gave up after max attempts) =
      // needs attention. Rows are never deleted until the server accepts them.
      'ALTER TABLE outbox ADD COLUMN next_attempt_at TEXT',
      // Caregiver-approved preferences fetched from the server (best effort).
      '''
      CREATE TABLE preferences (
        patient_id TEXT PRIMARY KEY NOT NULL REFERENCES profiles(patient_id) ON DELETE CASCADE,
        interests_json TEXT NOT NULL,
        disliked_json TEXT NOT NULL,
        fetched_at TEXT NOT NULL
      )
      ''',
    ],
    4: [
      // Stage 7: activity specs from GET /activities/catalog (levels with
      // parameters, instructions, hint and stop text). Until a spec has been
      // fetched, games use their bundled defaults.
      '''
      CREATE TABLE catalog_specs (
        activity_id TEXT PRIMARY KEY NOT NULL,
        slug TEXT NOT NULL,
        spec_json TEXT NOT NULL,
        fetched_at TEXT NOT NULL
      )
      ''',
    ],
    5: [
      // Alignment work: what happened inside each activity run (answers with
      // latency, hints, pauses, tiredness, stop requests, and every
      // in-session adaptation decision). Written as it happens and pushed as
      // `activity_event` mutations.
      '''
      CREATE TABLE activity_events (
        id TEXT PRIMARY KEY NOT NULL,
        patient_id TEXT NOT NULL REFERENCES profiles(patient_id) ON DELETE CASCADE,
        session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        activity_id TEXT NOT NULL,
        seq INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        round_index INTEGER,
        data_json TEXT NOT NULL
      )
      ''',
      'CREATE INDEX ix_activity_events_session ON activity_events (session_id, seq)',
      // Tiredness reports with a level: made on this phone (by the person or
      // a caregiver) or pulled from caregiver observations on the dashboard.
      // Never any note text.
      '''
      CREATE TABLE fatigue_reports (
        id TEXT PRIMARY KEY NOT NULL,
        patient_id TEXT NOT NULL REFERENCES profiles(patient_id) ON DELETE CASCADE,
        level TEXT NOT NULL,
        source TEXT NOT NULL,
        reported_at TEXT NOT NULL
      )
      ''',
      'CREATE INDEX ix_fatigue_reports_patient ON fatigue_reports (patient_id, reported_at)',
    ],
    6: [
      // Memory-based activities: how a person is related to the patient, as
      // the caregiver entered it (server migration 0012).
      'ALTER TABLE memories ADD COLUMN relationship TEXT',
    ],
  };

  Future<void> _ensureInstallId() async {
    if (await getMeta(_installIdKey) == null) {
      await setMeta(_installIdKey, const Uuid().v4());
    }
  }

  /// A stable random ID for this installation, sent as `device_install_id`
  /// during sync. It contains no personal data.
  Future<String> installId() async => (await getMeta(_installIdKey))!;

  Future<String?> getMeta(String key) async {
    final rows = await db.query(
      'app_meta',
      columns: ['value'],
      where: 'key = ?',
      whereArgs: [key],
    );
    return rows.isEmpty ? null : rows.first['value'] as String;
  }

  Future<void> setMeta(String key, String value) async {
    await db.insert('app_meta', {
      'key': key,
      'value': value,
      'updated_at': DateTime.now().toUtc().toIso8601String(),
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> close() => db.close();
}
