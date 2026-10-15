// Shared test harness. All data here is SYNTHETIC.
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sneha_patient/app.dart';
import 'package:sneha_patient/app_services.dart';
import 'package:sneha_patient/data/api/api_client.dart';
import 'package:sneha_patient/data/local/local_database.dart';
import 'package:sneha_patient/data/repositories/media_cache.dart';
import 'package:sneha_patient/data/repositories/settings_repository.dart';
import 'package:sneha_patient/data/repositories/sync_service.dart';
import 'package:sneha_patient/speech/speech.dart';
import 'package:sneha_patient/speech/voice_input.dart';
import 'package:sneha_patient/data/repositories/token_store.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

const patientId = '11111111-1111-4111-8111-111111111111';
const userId = '22222222-2222-4222-8222-222222222222';
const pairsId = '4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0001';
const objectId = '4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0009';
const storyId = '4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0007';
const validCode = 'ABCD-2345';

Map<String, dynamic> catalogJson(
  String id,
  String slug, {
  bool memory = false,
  int min = 1,
  int max = 3,
}) => {
  'id': id,
  'slug': slug,
  'version': 1,
  'title': 'Synthetic $slug',
  'description': 'Synthetic description for $slug.',
  'activity_type': 'attention',
  'cognitive_domains': ['attention'],
  'min_difficulty': min,
  'max_difficulty': max,
  'default_duration_seconds': 120,
  'supports_offline': true,
  'uses_memory_bank': memory,
};

/// A scriptable stand-in for the SNEHA API.
class FakeServer {
  bool online = true;
  int pullCalls = 0;
  final List<Map<String, dynamic>> pushedMutations = [];
  final List<List<String>> pushedBatches = [];

  /// Status per entity type for push responses (default applied).
  final Map<String, String> pushStatus = {};

  /// Like the real server: replays of a mutation_id, or the same record id
  /// pushed again, are `duplicate` and are not stored twice.
  final Set<String> seenMutations = {};
  final Map<String, Set<String>> stored = {};

  /// Respond to the next N pushes with HTTP 500 (nothing applied).
  int failPushes = 0;

  /// Apply the next push, then lose the response (as if the connection
  /// dropped or the app was killed mid-sync).
  bool dropNextPushResponse = false;

  /// GET /patients/{id}/preferences body; null → 404 (older server).
  Map<String, dynamic>? preferences;
  int pairStatus = 200;
  int authStatus = 200;

  // ----- Stage 7 endpoints (null handler → 404, like an older server) -----

  /// POST /activities/next → RecommendationOut body.
  Map<String, dynamic> Function(Map<String, dynamic> body)? onNext;
  final List<Map<String, dynamic>> nextRequests = [];

  /// GET /activities/catalog → list of CatalogEntry.
  List<Map<String, dynamic>>? catalogSpecs;

  /// POST /conversation/analyze → AnalyzeResponse body (or set analyzeStatus).
  Map<String, dynamic> Function(Map<String, dynamic> body)? onAnalyze;
  int analyzeStatus = 200;
  final List<Map<String, dynamic>> analyzeRequests = [];

  /// POST /patients/{id}/memories (patient proposals).
  final List<Map<String, dynamic>> memoryProposals = [];

  /// GET /speech/status body; POST /speech/transcribe response.
  Map<String, dynamic>? speechStatus;
  (int, Map<String, dynamic>) transcribeResponse = (
    503,
    {
      'error': {'code': 'model_missing', 'message': 'missing'},
    },
  );
  final List<http.Request> transcribeRequests = [];

  /// Pages returned by /sync/pull, in order; afterwards empty pages.
  final List<Map<String, dynamic>> pullPages = [];
  final List<int> pullSince = [];
  Map<String, String?> consents = {
    'data_processing': 'granted',
    'clinician_sharing': null,
    'cloud_ai': 'withdrawn',
    'voice_processing': null,
  };

  http.Response _json(Object body, [int status = 200]) => http.Response(
    jsonEncode(body),
    status,
    headers: {'content-type': 'application/json'},
  );

  http.Response _error(int status, String code) => _json({
    'error': {'code': code, 'message': code},
  }, status);

  Future<http.Response> handle(http.Request r) async {
    if (!online) throw http.ClientException('Connection refused');
    final path = r.url.path.replaceFirst('/api/v1', '');
    if (path == '/health') {
      return _json({
        'status': 'ok',
        'service': 'SNEHA API',
        'version': '0.1.0',
        'environment': 'test',
        'server_time': '2026-10-15T10:00:00Z',
      });
    }
    if (path == '/auth/device/pair') {
      if (pairStatus != 200) return _error(pairStatus, 'invalid_pairing_code');
      final body = jsonDecode(r.body) as Map<String, dynamic>;
      if (body['code'] != validCode) return _error(401, 'invalid_pairing_code');
      return _json({
        'access_token': 'synthetic-token',
        'token_type': 'bearer',
        'expires_at': '2027-01-01T00:00:00Z',
        'user': {
          'id': userId,
          'email': null,
          'full_name': 'Synthetic Patient',
          'role': 'patient',
          'is_verified': true,
          'created_at': '2026-10-01T00:00:00Z',
        },
        'patient_id': patientId,
      });
    }
    if (authStatus != 200) return _error(authStatus, 'unauthorized');
    if (path == '/patients/$patientId') {
      return _json({
        'id': patientId,
        'display_name': 'Synthetic Patient',
        'preferred_name': 'Aita',
        'birth_year': null,
        'preferred_language': 'as',
        'region': null,
        'timezone': 'Asia/Kolkata',
        'is_synthetic': true,
        'has_paired_device': true,
        'created_at': '2026-10-01T00:00:00Z',
        'updated_at': '2026-10-01T00:00:00Z',
      });
    }
    if (path == '/patients/$patientId/consents') {
      return _json({'current': consents, 'history': []});
    }
    if (path == '/sync/push') {
      if (failPushes > 0) {
        failPushes--;
        return _error(500, 'internal_error');
      }
      final body = jsonDecode(r.body) as Map<String, dynamic>;
      final mutations = (body['mutations'] as List)
          .cast<Map<String, dynamic>>();
      pushedMutations.addAll(mutations);
      pushedBatches.add([
        for (final m in mutations) m['entity_type'] as String,
      ]);
      final results = [for (final m in mutations) _applyMutation(m)];
      if (dropNextPushResponse) {
        dropNextPushResponse = false;
        throw http.ClientException('Connection reset');
      }
      return _json({'results': results});
    }
    if (path == '/patients/$patientId/preferences') {
      if (preferences == null) return _error(404, 'not_found');
      return _json(preferences!);
    }
    if (path == '/sync/pull') {
      pullCalls++;
      final since = int.parse(r.url.queryParameters['since']!);
      pullSince.add(since);
      if (pullPages.isNotEmpty) return _json(pullPages.removeAt(0));
      return _json({'changes': [], 'next_since': since, 'has_more': false});
    }
    if (path == '/activities/next' && r.method == 'POST') {
      final body = jsonDecode(r.body) as Map<String, dynamic>;
      nextRequests.add(body);
      if (onNext == null) return _error(404, 'not_found');
      return _json(onNext!(body));
    }
    if (path == '/activities/catalog') {
      if (catalogSpecs == null) return _error(404, 'not_found');
      return _json(catalogSpecs!);
    }
    if (path == '/conversation/analyze') {
      final body = jsonDecode(r.body) as Map<String, dynamic>;
      analyzeRequests.add(body);
      if (analyzeStatus != 200) return _error(analyzeStatus, 'provider_error');
      if (onAnalyze == null) return _error(404, 'not_found');
      return _json(onAnalyze!(body));
    }
    if (path == '/patients/$patientId/memories' && r.method == 'POST') {
      final body = jsonDecode(r.body) as Map<String, dynamic>;
      memoryProposals.add(body);
      return _json({...body, 'status': 'pending_approval'}, 201);
    }
    if (path == '/speech/status') {
      if (speechStatus == null) return _error(404, 'not_found');
      return _json(speechStatus!);
    }
    if (path == '/speech/transcribe') {
      transcribeRequests.add(r);
      final (status, body) = transcribeResponse;
      return _json(body, status);
    }
    if (path.startsWith('/files/')) return http.Response('not found', 404);
    return _error(404, 'not_found');
  }
}

extension on FakeServer {
  Map<String, dynamic> _applyMutation(Map<String, dynamic> m) {
    final type = m['entity_type'] as String;
    final data = m['data'] as Map;
    final entityId = (data['id'] ?? data['activity_id'] ?? 'x') as String;
    String status;
    if (seenMutations.contains(m['mutation_id'])) {
      status = 'duplicate';
    } else if (pushStatus.containsKey(type)) {
      status = pushStatus[type]!;
    } else if (type == 'activity_result' &&
        (stored[type]?.contains(entityId) ?? false)) {
      status = 'duplicate';
    } else {
      status = 'applied';
      stored.putIfAbsent(type, () => {}).add(entityId);
    }
    if (status == 'applied' || status == 'duplicate') {
      seenMutations.add(m['mutation_id'] as String);
    }
    return {
      'mutation_id': m['mutation_id'],
      'entity_type': type,
      'entity_id': entityId,
      'status': status,
      'detail': status == 'applied' || status == 'duplicate'
          ? null
          : 'Synthetic $status',
    };
  }
}

int _dbCounter = 0;

class Harness {
  Harness._(this.services, this.server, this.tokens, this.local, this.mediaDir);

  final AppServices services;
  final FakeServer server;
  final InMemoryTokenStore tokens;
  final LocalDatabase local;
  final Directory mediaDir;

  /// [now] is the fixed starting time; the clock advances 1s per call so
  /// durations are positive and deterministic.
  static Future<Harness> create({
    DateTime? now,
    FakeServer? server,
    SpeechOutput speech = const UnavailableSpeechOutput(),
    RetryPolicy retry = const RetryPolicy(),
    VoiceRecorder? voiceRecorder,
  }) async {
    sqfliteFfiInit();
    final local = await LocalDatabase.open(
      factory: databaseFactoryFfiNoIsolate,
      path:
          '${Directory.systemTemp.createTempSync('sneha_db').path}/t${_dbCounter++}.db',
    );
    final fake = server ?? FakeServer();
    final tokens = InMemoryTokenStore();
    var t = (now ?? DateTime.utc(2026, 10, 15, 4, 30)).toUtc();
    DateTime clock() => t = t.add(const Duration(seconds: 1));
    final mediaDir = Directory.systemTemp.createTempSync('sneha_media');
    final services = AppServices(
      local: local,
      api: SnehaApiClient(
        baseUrl: Uri.parse('http://api.test'),
        httpClient: MockClient(fake.handle),
      ),
      tokens: tokens,
      media: MediaCache(mediaDir),
      clock: clock,
      random: Random(42),
      speechOutput: speech,
      retry: retry,
      voiceRecorder: voiceRecorder,
    );
    return Harness._(services, fake, tokens, local, mediaDir);
  }

  Future<void> dispose() => local.close();

  /// Pair the synthetic patient (via the real controller) and finish onboarding.
  Future<void> pairAndOnboard({bool withCatalog = true}) async {
    final c = services.controller;
    await c.load();
    await c.updateSettings(
      const AppSettings(onboardingComplete: true, languageChosen: true),
    );
    await c.pair(code: validCode, deviceName: 'Test phone');
    if (withCatalog) await seedCatalog();
  }

  Future<void> seedCatalog() async {
    for (final a in [
      catalogJson(pairsId, 'picture-pairs', max: 5),
      catalogJson(objectId, 'name-the-object'),
      catalogJson('4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0002', 'word-partners'),
      catalogJson(storyId, 'story-time', memory: true, max: 1),
      catalogJson(
        '4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0006',
        'photo-recall',
        memory: true,
      ),
    ]) {
      await local.db.insert('catalog', {
        'id': a['id'],
        'slug': a['slug'],
        'version': 1,
        'title': a['title'],
        'description': a['description'],
        'activity_type': a['activity_type'],
        'min_difficulty': a['min_difficulty'],
        'max_difficulty': a['max_difficulty'],
        'default_duration_seconds': 120,
        'uses_memory_bank': a['uses_memory_bank'] == true ? 1 : 0,
        'is_active': 1,
      });
    }
  }

  Future<List<Map<String, Object?>>> outbox() =>
      local.db.query('outbox', orderBy: 'seq');

  Widget app() => SnehaApp(services: services);
}

/// Lets real async work (SQLite, mock HTTP) progress, then pumps frames.
/// Bounded, because some screens legitimately show spinners.
Future<void> settle(WidgetTester tester, {int rounds = 12}) async {
  for (var i = 0; i < rounds; i++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 5)),
    );
    await tester.pump(const Duration(milliseconds: 50));
  }
}

/// Runs [body] with real async (for setup and direct DB checks in widget tests).
Future<T> real<T>(WidgetTester tester, Future<T> Function() body) async =>
    (await tester.runAsync(body)) as T;

/// Scroll a target into view inside the first scrollable, then tap it.
Future<void> tapVisible(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pump();
  await tester.tap(finder);
  await settle(tester);
}

/// Harness that is paired, onboarded and has a catalog — created with real async.
Future<Harness> pairedHarness(
  WidgetTester tester, {
  FakeServer? server,
  SpeechOutput speech = const UnavailableSpeechOutput(),
}) => real(tester, () async {
  final h = await Harness.create(server: server, speech: speech);
  await h.pairAndOnboard();
  return h;
});

/// A RecommendationOut body exactly as the server returns it (SYNTHETIC).
Map<String, dynamic> recommendationJson({
  String id = '33333333-3333-4333-8333-333333333333',
  String action = 'activity',
  String? activityId = objectId,
  String? slug = 'name-the-object',
  int? difficulty = 2,
  List<String> reasons = const ['INTEREST_MATCH'],
  int? breakMinutes,
}) => {
  'id': id,
  'patient_id': patientId,
  'session_id': null,
  'action': action,
  'activity_id': activityId,
  'activity_slug': slug,
  'activity_title': slug == null ? null : 'Synthetic $slug',
  'difficulty': difficulty,
  'level_parameters': difficulty == null ? null : {'options': 3},
  'instructions': 'Synthetic instructions.',
  'hints_enabled': false,
  'break_minutes': breakMinutes,
  'reason_codes': reasons,
  'supporting': [],
  'content_refs': {'memory_item_ids': [], 'routine_item_ids': []},
  'algorithm_version': '1.0.0',
  'config_version': '2026.10.1',
  'fallback': {'used': false, 'reason': null},
  'created_at': '2026-10-15T10:00:00Z',
  'disclaimer': 'Synthetic disclaimer.',
};

/// A CatalogEntry body (SYNTHETIC) with explicit per-level parameters.
Map<String, dynamic> specJson(
  String id,
  String slug,
  Map<int, Map<String, Object>> levels, {
  String instructions = 'Synthetic catalog instructions.',
}) => {
  ...catalogJson(id, slug),
  'instructions': instructions,
  'hint': 'Synthetic hint.',
  'evaluation': 'Synthetic evaluation.',
  'stop': 'Synthetic stop.',
  'accessibility': 'Synthetic accessibility.',
  'levels': [
    for (final e in levels.entries) {'level': e.key, 'parameters': e.value},
  ],
  'content_languages': ['*'],
  'interest_tags': <String>[],
};

/// An AnalyzeResponse body (SYNTHETIC).
Map<String, dynamic> analyzeJson({
  String reply = 'Synthetic safe reply.',
  List<Map<String, dynamic>> memories = const [],
  List<Map<String, dynamic>> candidates = const [],
  bool distress = false,
  Map<String, dynamic>? suggestion,
  String provider = 'deterministic',
}) => {
  'conversation_id': '44444444-4444-4444-8444-444444444444',
  'provider': provider,
  'fallback': {'used': provider == 'deterministic', 'reason': null},
  'understanding': {
    'topic': 'synthetic',
    'intents': ['other'],
    'people': [],
    'places': [],
    'routines': [],
    'topic_tags': [],
    'fatigue_expressed': false,
    'distress_expressed': distress,
    'stop_requested': false,
    'uncertain': false,
    'clarification': {'needed': false, 'question': null},
    'uncertain_interpretations': [],
  },
  'memories': memories,
  'memory_candidates': candidates,
  'safety': {
    'distress_detected': distress,
    'message': distress
        ? 'Synthetic safety message: please call your family or 112.'
        : null,
  },
  'suggestion': suggestion,
  'reply': reply,
  'disclaimer': 'Synthetic disclaimer.',
};
