import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/data/local/local_database.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  setUpAll(sqfliteFfiInit);

  String tempPath() =>
      '${Directory.systemTemp.createTempSync('sneha_db').path}/local.db';

  test('fresh install creates the current schema', () async {
    final local = await LocalDatabase.open(
      factory: databaseFactoryFfi,
      path: inMemoryDatabasePath,
    );
    addTearDown(local.close);
    expect(await local.db.getVersion(), LocalDatabase.schemaVersion);
    expect(LocalDatabase.schemaVersion, 4);
    final tables = (await local.db.rawQuery(
      "SELECT name FROM sqlite_master WHERE type = 'table'",
    )).map((r) => r['name']).toSet();
    expect(
      tables,
      containsAll([
        'app_meta',
        'settings',
        'profiles',
        'catalog',
        'memories',
        'memory_links',
        'routines',
        'personalization',
        'sessions',
        'results',
        'outbox',
        'sync_state',
        'preferences',
        'catalog_specs',
      ]),
    );
  });

  test('v2 database upgrades to v3, keeping results and outbox', () async {
    final path = tempPath();
    final v2 = await LocalDatabase.open(
      factory: databaseFactoryFfi,
      path: path,
      version: 2,
    );
    await v2.db.insert('profiles', {
      'patient_id': 'p',
      'user_id': 'u',
      'display_name': 'Synthetic',
      'preferred_language': 'en',
      'timezone': 'Asia/Kolkata',
      'paired_at': '2026-10-15T00:00:00.000Z',
    });
    await v2.db.insert('outbox', {
      'mutation_id': 'm-1',
      'patient_id': 'p',
      'entity_type': 'activity_result',
      'entity_id': 'r-1',
      'payload_json': '{}',
      'created_at': '2026-10-15T00:00:00.000Z',
    });
    await v2.close();

    final v3 = await LocalDatabase.open(
      factory: databaseFactoryFfi,
      path: path,
      version: 3,
    );
    addTearDown(v3.close);
    expect(await v3.db.getVersion(), 3);
    final row = (await v3.db.query('outbox')).single;
    expect(row['mutation_id'], 'm-1');
    expect(row['next_attempt_at'], isNull);
    final cols = (await v3.db.rawQuery(
      'PRAGMA table_info(results)',
    )).map((r) => r['name']).toSet();
    expect(
      cols,
      containsAll(['engagement', 'fatigue_reported', 'recommendation_id']),
    );
  });

  test('v1 database upgrades to current and keeps the install id', () async {
    final path = tempPath();
    final v1 = await LocalDatabase.open(
      factory: databaseFactoryFfi,
      path: path,
      version: 1,
    );
    final id = await v1.installId();
    await v1.close();

    final v2 = await LocalDatabase.open(
      factory: databaseFactoryFfi,
      path: path,
    );
    addTearDown(v2.close);
    expect(await v2.db.getVersion(), LocalDatabase.schemaVersion);
    expect(await v2.installId(), id);
    expect(await v2.db.query('outbox'), isEmpty);
  });

  test('install id is a stable UUIDv4', () async {
    final local = await LocalDatabase.open(
      factory: databaseFactoryFfi,
      path: inMemoryDatabasePath,
    );
    addTearDown(local.close);
    final id = await local.installId();
    expect(id, matches(RegExp(r'^[0-9a-f-]{36}$')));
    expect(await local.installId(), id);
  });

  test('released migrations are append-only (v1 unchanged)', () {
    expect(LocalDatabase.migrations[1], hasLength(1));
    expect(
      LocalDatabase.migrations[1]!.single,
      contains('CREATE TABLE app_meta'),
    );
  });

  test('v3 database upgrades to v4 (catalog specs), keeping results', () async {
    final path =
        '${Directory.systemTemp.createTempSync('sneha_v4').path}/up.db';
    final v3 = await LocalDatabase.open(
      factory: databaseFactoryFfi,
      path: path,
      version: 3,
    );
    await v3.db.insert('settings', {'key': 'k', 'value': 'v'});
    await v3.close();
    final v4 = await LocalDatabase.open(
      factory: databaseFactoryFfi,
      path: path,
    );
    addTearDown(v4.close);
    expect(await v4.db.getVersion(), 4);
    expect((await v4.db.query('settings')).single['value'], 'v');
    expect(await v4.db.query('catalog_specs'), isEmpty);
  });
}
