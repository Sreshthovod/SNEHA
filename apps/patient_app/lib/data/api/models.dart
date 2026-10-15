/// Typed models for the SNEHA API.
///
/// Source of truth: packages/api_contracts/openapi.json (generated from the
/// backend). Field names mirror the JSON exactly. Keep in sync with
/// docs/api-contracts.md.
library;

DateTime _date(Object? v) => DateTime.parse(v as String).toUtc();
DateTime? _dateOrNull(Object? v) => v == null ? null : _date(v);

class UserOut {
  const UserOut({
    required this.id,
    required this.fullName,
    required this.role,
    this.email,
  });

  final String id;
  final String? email;
  final String fullName;
  final String role;

  factory UserOut.fromJson(Map<String, dynamic> j) => UserOut(
    id: j['id'] as String,
    email: j['email'] as String?,
    fullName: j['full_name'] as String,
    role: j['role'] as String,
  );
}

/// Response of POST /auth/device/pair (and /auth/login).
class TokenResponse {
  const TokenResponse({
    required this.accessToken,
    required this.expiresAt,
    required this.user,
    this.patientId,
  });

  final String accessToken;
  final DateTime expiresAt;
  final UserOut user;
  final String? patientId;

  factory TokenResponse.fromJson(Map<String, dynamic> j) => TokenResponse(
    accessToken: j['access_token'] as String,
    expiresAt: _date(j['expires_at']),
    user: UserOut.fromJson(j['user'] as Map<String, dynamic>),
    patientId: j['patient_id'] as String?,
  );
}

class PatientOut {
  const PatientOut({
    required this.id,
    required this.displayName,
    required this.preferredLanguage,
    required this.timezone,
    this.preferredName,
  });

  final String id;
  final String displayName;
  final String? preferredName;
  final String preferredLanguage;
  final String timezone;

  factory PatientOut.fromJson(Map<String, dynamic> j) => PatientOut(
    id: j['id'] as String,
    displayName: j['display_name'] as String,
    preferredName: j['preferred_name'] as String?,
    preferredLanguage: j['preferred_language'] as String,
    timezone: j['timezone'] as String,
  );
}

/// GET /patients/{id}/consents → `current` map (type → granted/withdrawn/null).
class ConsentSummary {
  const ConsentSummary(this.current);

  final Map<String, String?> current;

  factory ConsentSummary.fromJson(Map<String, dynamic> j) => ConsentSummary(
    (j['current'] as Map<String, dynamic>).map(
      (k, v) => MapEntry(k, v as String?),
    ),
  );

  Map<String, dynamic> toJson() => {'current': current};
}

/// ActivityDefinitionOut.
class CatalogActivity {
  const CatalogActivity({
    required this.id,
    required this.slug,
    required this.version,
    required this.title,
    required this.description,
    required this.activityType,
    required this.minDifficulty,
    required this.maxDifficulty,
    required this.defaultDurationSeconds,
    required this.usesMemoryBank,
    this.isActive = true,
  });

  final String id;
  final String slug;
  final int version;
  final String title;
  final String description;
  final String activityType;
  final int minDifficulty;
  final int maxDifficulty;
  final int defaultDurationSeconds;
  final bool usesMemoryBank;
  final bool isActive;

  factory CatalogActivity.fromJson(Map<String, dynamic> j) => CatalogActivity(
    id: j['id'] as String,
    slug: j['slug'] as String,
    version: j['version'] as int,
    title: j['title'] as String,
    description: j['description'] as String,
    activityType: j['activity_type'] as String,
    minDifficulty: j['min_difficulty'] as int,
    maxDifficulty: j['max_difficulty'] as int,
    defaultDurationSeconds: j['default_duration_seconds'] as int,
    usesMemoryBank: j['uses_memory_bank'] as bool,
    isActive: j['is_active'] as bool? ?? true,
  );
}

/// MemoryOut (only APPROVED memories ever reach the device).
class MemoryItem {
  const MemoryItem({
    required this.id,
    required this.patientId,
    required this.kind,
    required this.title,
    this.description,
    this.approxYear,
    this.tags = const [],
    this.mediaFileId,
    this.version = 1,
    this.localPhotoPath,
  });

  final String id;
  final String patientId;
  final String kind;
  final String title;
  final String? description;
  final int? approxYear;
  final List<String> tags;
  final String? mediaFileId;
  final int version;

  /// Set when the photo has been downloaded to this phone.
  final String? localPhotoPath;

  bool get hasPhoto => localPhotoPath != null;

  factory MemoryItem.fromJson(Map<String, dynamic> j) => MemoryItem(
    id: j['id'] as String,
    patientId: j['patient_id'] as String,
    kind: j['kind'] as String,
    title: j['title'] as String,
    description: j['description'] as String?,
    approxYear: j['approx_year'] as int?,
    tags: (j['tags'] as List<dynamic>? ?? const []).cast<String>(),
    mediaFileId: j['media_file_id'] as String?,
    version: j['version'] as int? ?? 1,
  );
}

/// RoutineOut.
class RoutineItem {
  const RoutineItem({
    required this.id,
    required this.patientId,
    required this.title,
    required this.localTime,
    required this.daysOfWeek,
    required this.isActive,
  });

  final String id;
  final String patientId;
  final String title;

  /// "HH:MM" in the patient's timezone.
  final String localTime;

  /// Bitmask Mon=1 … Sun=64.
  final int daysOfWeek;
  final bool isActive;

  bool occursOn(DateTime day) => daysOfWeek & (1 << (day.weekday - 1)) != 0;

  factory RoutineItem.fromJson(Map<String, dynamic> j) => RoutineItem(
    id: j['id'] as String,
    patientId: j['patient_id'] as String,
    title: j['title'] as String,
    localTime: j['local_time'] as String,
    daysOfWeek: j['days_of_week'] as int,
    isActive: j['is_active'] as bool,
  );
}

class MutationResult {
  const MutationResult({
    required this.mutationId,
    required this.entityType,
    required this.entityId,
    required this.status,
    this.detail,
  });

  final String mutationId;
  final String entityType;
  final String entityId;

  /// applied | duplicate | conflict | rejected
  final String status;
  final String? detail;

  factory MutationResult.fromJson(Map<String, dynamic> j) => MutationResult(
    mutationId: j['mutation_id'] as String,
    entityType: j['entity_type'] as String,
    entityId: j['entity_id'] as String,
    status: j['status'] as String,
    detail: j['detail'] as String?,
  );
}

class SyncChange {
  const SyncChange({
    required this.seq,
    required this.entityType,
    required this.entityId,
    required this.operation,
    required this.changedAt,
    this.data,
  });

  final int seq;
  final String entityType;
  final String entityId;

  /// upsert | delete
  final String operation;
  final DateTime changedAt;
  final Map<String, dynamic>? data;

  bool get isDelete => operation == 'delete' || data == null;

  factory SyncChange.fromJson(Map<String, dynamic> j) => SyncChange(
    seq: j['seq'] as int,
    entityType: j['entity_type'] as String,
    entityId: j['entity_id'] as String,
    operation: j['operation'] as String,
    changedAt: _date(j['changed_at']),
    data: j['data'] as Map<String, dynamic>?,
  );
}

class SyncPullResponse {
  const SyncPullResponse({
    required this.changes,
    required this.nextSince,
    required this.hasMore,
  });

  final List<SyncChange> changes;
  final int nextSince;
  final bool hasMore;

  factory SyncPullResponse.fromJson(Map<String, dynamic> j) => SyncPullResponse(
    changes: (j['changes'] as List<dynamic>)
        .map((c) => SyncChange.fromJson(c as Map<String, dynamic>))
        .toList(),
    nextSince: j['next_since'] as int,
    hasMore: j['has_more'] as bool,
  );
}

/// Exposed for parsing nullable timestamps elsewhere in the data layer.
DateTime? parseApiDate(Object? v) => _dateOrNull(v);

/// Caregiver-approved preferences (GET /patients/{id}/preferences). Parsed
/// defensively: unknown fields are ignored, missing lists become empty.
class PatientPreferences {
  const PatientPreferences({
    this.interests = const [],
    this.dislikedActivitySlugs = const [],
  });

  final List<String> interests;
  final List<String> dislikedActivitySlugs;

  factory PatientPreferences.fromJson(Map<String, dynamic> json) =>
      PatientPreferences(
        interests: [
          for (final t in json['interests'] as List? ?? const [])
            if (t is String) t,
        ],
        dislikedActivitySlugs: [
          for (final t in json['disliked_activity_slugs'] as List? ?? const [])
            if (t is String) t,
        ],
      );
}
