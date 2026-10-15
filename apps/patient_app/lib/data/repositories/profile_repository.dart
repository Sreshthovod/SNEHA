import 'dart:convert';

import 'package:sqflite/sqflite.dart';

import '../api/models.dart';
import '../local/local_database.dart';
import 'clock.dart';
import 'media_cache.dart';
import 'token_store.dart';

/// A patient paired on this phone.
class Profile {
  const Profile({
    required this.patientId,
    required this.userId,
    required this.displayName,
    required this.preferredLanguage,
    required this.timezone,
    required this.pairedAt,
    this.preferredName,
    this.needsRepair = false,
    this.consents,
    this.consentsFetchedAt,
  });

  final String patientId;
  final String userId;
  final String displayName;
  final String? preferredName;
  final String preferredLanguage;
  final String timezone;
  final DateTime pairedAt;

  /// The device session was rejected by the server (e.g. a caregiver signed
  /// this phone out). Local use continues; syncing needs a new pairing code.
  final bool needsRepair;

  /// Last consent state fetched from the server (read-only on the device).
  final Map<String, String?>? consents;
  final DateTime? consentsFetchedAt;

  String get greetingName => preferredName ?? displayName;

  static Profile fromRow(Map<String, Object?> r) => Profile(
    patientId: r['patient_id'] as String,
    userId: r['user_id'] as String,
    displayName: r['display_name'] as String,
    preferredName: r['preferred_name'] as String?,
    preferredLanguage: r['preferred_language'] as String,
    timezone: r['timezone'] as String,
    pairedAt: DateTime.parse(r['paired_at'] as String),
    needsRepair: (r['needs_repair'] as int) == 1,
    consents: r['consents_json'] == null
        ? null
        : (jsonDecode(r['consents_json'] as String) as Map<String, dynamic>)
              .map((k, v) => MapEntry(k, v as String?)),
    consentsFetchedAt: r['consents_fetched_at'] == null
        ? null
        : DateTime.parse(r['consents_fetched_at'] as String),
  );
}

class ProfileRepository {
  ProfileRepository(
    this._local,
    this._tokens,
    this._media, {
    Clock clock = systemClock,
  }) : _clock = clock;

  final LocalDatabase _local;
  final TokenStore _tokens;
  final MediaCache _media;
  final Clock _clock;

  Future<List<Profile>> list() async {
    final rows = await _local.db.query('profiles', orderBy: 'display_name');
    return rows.map(Profile.fromRow).toList();
  }

  Future<Profile?> get(String patientId) async {
    final rows = await _local.db.query(
      'profiles',
      where: 'patient_id = ?',
      whereArgs: [patientId],
    );
    return rows.isEmpty ? null : Profile.fromRow(rows.first);
  }

  Future<String?> token(String patientId) => _tokens.read(patientId);

  /// Save a newly paired profile (or re-pair an existing one).
  Future<Profile> savePaired(TokenResponse token, PatientOut patient) async {
    await _tokens.write(patient.id, token.accessToken);
    await _local.db.transaction((txn) async {
      final existing = await txn.query(
        'profiles',
        where: 'patient_id = ?',
        whereArgs: [patient.id],
      );
      final row = {
        'patient_id': patient.id,
        'user_id': token.user.id,
        'display_name': patient.displayName,
        'preferred_name': patient.preferredName,
        'preferred_language': patient.preferredLanguage,
        'timezone': patient.timezone,
        'needs_repair': 0,
      };
      if (existing.isEmpty) {
        await txn.insert('profiles', {...row, 'paired_at': isoUtc(_clock())});
        await txn.insert('sync_state', {'patient_id': patient.id});
      } else {
        await txn.update(
          'profiles',
          row,
          where: 'patient_id = ?',
          whereArgs: [patient.id],
        );
      }
    });
    return (await get(patient.id))!;
  }

  Future<void> updateFromServer(PatientOut patient) => _local.db.update(
    'profiles',
    {
      'display_name': patient.displayName,
      'preferred_name': patient.preferredName,
      'preferred_language': patient.preferredLanguage,
      'timezone': patient.timezone,
    },
    where: 'patient_id = ?',
    whereArgs: [patient.id],
  );

  Future<void> saveConsents(String patientId, ConsentSummary consents) =>
      _local.db.update(
        'profiles',
        {
          'consents_json': jsonEncode(consents.current),
          'consents_fetched_at': isoUtc(_clock()),
        },
        where: 'patient_id = ?',
        whereArgs: [patientId],
      );

  Future<void> markNeedsRepair(String patientId) => _local.db.update(
    'profiles',
    {'needs_repair': 1},
    where: 'patient_id = ?',
    whereArgs: [patientId],
  );

  /// Number of records not yet shared with the server for this profile.
  Future<int> unsyncedCount(String patientId) async =>
      Sqflite.firstIntValue(
        await _local.db.rawQuery(
          'SELECT COUNT(*) FROM outbox WHERE patient_id = ?',
          [patientId],
        ),
      ) ??
      0;

  /// Remove the profile and ALL its data from this phone (not from the server).
  Future<void> remove(String patientId) async {
    await _local.db.transaction((txn) async {
      // Child tables cascade from profiles(patient_id).
      await txn.delete(
        'profiles',
        where: 'patient_id = ?',
        whereArgs: [patientId],
      );
    });
    await _media.deleteForPatient(patientId);
    await _tokens.delete(patientId);
  }
}
