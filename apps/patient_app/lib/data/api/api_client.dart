import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import 'models.dart';
import 'stage7_models.dart';

/// Liveness information from `GET /api/v1/health`.
/// Contract: packages/api_contracts/openapi.json (HealthResponse).
class ServerHealth {
  const ServerHealth({
    required this.service,
    required this.version,
    required this.environment,
    required this.serverTime,
  });

  final String service;
  final String version;
  final String environment;
  final DateTime serverTime;

  factory ServerHealth.fromJson(Map<String, dynamic> json) {
    if (json['status'] != 'ok') {
      throw const FormatException('Health response status is not "ok"');
    }
    return ServerHealth(
      service: json['service'] as String,
      version: json['version'] as String,
      environment: json['environment'] as String,
      serverTime: DateTime.parse(json['server_time'] as String).toUtc(),
    );
  }
}

/// A failure talking to the backend, with a message safe to log.
class ApiException implements Exception {
  const ApiException(this.code, this.message, {this.statusCode});

  final String code;
  final String message;
  final int? statusCode;

  /// True when the server could not be reached at all.
  bool get isNetwork => code == 'network_error' || code == 'timeout';

  /// True when the device session is no longer valid (re-pairing needed).
  bool get isUnauthorized => statusCode == 401;

  @override
  String toString() => 'ApiException($code, $statusCode): $message';
}

/// HTTP client for the SNEHA API. Only the data layer uses this; the UI talks
/// to repositories. The app must keep working when every call here fails.
class SnehaApiClient {
  SnehaApiClient({
    required Uri baseUrl,
    http.Client? httpClient,
    this.timeout = const Duration(seconds: 8),
  }) : _baseUrl = baseUrl,
       _http = httpClient ?? http.Client();

  static const String apiPrefix = '/api/v1';

  final Uri _baseUrl;
  final http.Client _http;
  final Duration timeout;

  Uri _url(String path, [Map<String, String>? query]) => _baseUrl.replace(
    path: '${_baseUrl.path}$apiPrefix$path',
    queryParameters: query,
  );

  Map<String, String> _headers(String? token, {bool json = false}) => {
    'Accept': 'application/json',
    if (json) 'Content-Type': 'application/json',
    if (token != null) 'Authorization': 'Bearer $token',
  };

  // ---------- endpoints ----------

  Future<ServerHealth> getHealth() async {
    final json = await _send('GET', '/health');
    return _parse(() => ServerHealth.fromJson(json), 'health');
  }

  /// POST /auth/device/pair: exchange a caregiver-issued code for a device session.
  Future<TokenResponse> pairDevice({
    required String code,
    required String deviceName,
  }) async {
    final json = await _send(
      'POST',
      '/auth/device/pair',
      body: {'code': code, 'device_name': deviceName},
    );
    return _parse(() => TokenResponse.fromJson(json), 'pairing');
  }

  Future<UserOut> getMe(String token) async {
    final json = await _send('GET', '/auth/me', token: token);
    return _parse(() => UserOut.fromJson(json), 'me');
  }

  Future<PatientOut> getPatient(String token, String patientId) async {
    final json = await _send('GET', '/patients/$patientId', token: token);
    return _parse(() => PatientOut.fromJson(json), 'patient');
  }

  Future<ConsentSummary> getConsents(String token, String patientId) async {
    final json = await _send(
      'GET',
      '/patients/$patientId/consents',
      token: token,
    );
    return _parse(() => ConsentSummary.fromJson(json), 'consents');
  }

  /// GET /patients/{id}/preferences (caregiver-approved interests).
  Future<PatientPreferences> getPreferences(
    String token,
    String patientId,
  ) async {
    final json = await _send(
      'GET',
      '/patients/$patientId/preferences',
      token: token,
    );
    return _parse(() => PatientPreferences.fromJson(json), 'preferences');
  }

  /// GET /activities/catalog: specs (levels, instructions, hints, stop).
  Future<List<ActivitySpec>> getCatalogSpecs(String token) async {
    final response = await _request(
      () => _http
          .get(_url('/activities/catalog'), headers: _headers(token))
          .timeout(timeout),
    );
    if (response.statusCode != 200) {
      throw _errorFrom(response, '/activities/catalog');
    }
    final decoded = _decode(response);
    return _parse(
      () => [
        for (final e in decoded as List<dynamic>)
          ActivitySpec.fromJson(e as Map<String, dynamic>),
      ],
      'catalog',
    );
  }

  /// POST /conversation/analyze.
  Future<ConversationTurn> analyzeConversation(
    String token, {
    required String patientId,
    required String text,
    required String language,
    String? conversationId,
    String? sessionId,
    List<String>? availableSlugs,
  }) async {
    final json = await _send(
      'POST',
      '/conversation/analyze',
      token: token,
      body: {
        'patient_id': patientId,
        'text': text,
        'language': language,
        'conversation_id': ?conversationId,
        'session_id': ?sessionId,
        'available_slugs': ?availableSlugs,
      },
    );
    return _parse(() => ConversationTurn.fromJson(json), 'conversation');
  }

  /// POST /patients/{id}/memories. From a patient device this creates a
  /// PROPOSAL (pending_approval) that the family must approve.
  Future<Map<String, dynamic>> proposeMemory(
    String token, {
    required String patientId,
    required String id,
    required String kind,
    required String title,
    String? description,
  }) => _send(
    'POST',
    '/patients/$patientId/memories',
    token: token,
    body: {'id': id, 'kind': kind, 'title': title, 'description': ?description},
  );

  /// GET /speech/status.
  Future<ServerSpeechStatus> speechStatus(String token) async {
    final json = await _send('GET', '/speech/status', token: token);
    return _parse(() => ServerSpeechStatus.fromJson(json), 'speech status');
  }

  /// POST /speech/transcribe (multipart WAV). Longer timeout: recognition
  /// runs on the server.
  Future<Transcription> transcribe(
    String token, {
    required String patientId,
    required String language,
    required Uint8List wav,
  }) async {
    final request = http.MultipartRequest('POST', _url('/speech/transcribe'))
      ..headers.addAll(_headers(token))
      ..fields['patient_id'] = patientId
      ..fields['language'] = language
      ..files.add(
        http.MultipartFile.fromBytes('audio', wav, filename: 'speech.wav'),
      );
    final response = await _request(
      () async => http.Response.fromStream(
        await _http.send(request).timeout(timeout * 4),
      ),
    );
    if (response.statusCode != 200) {
      throw _errorFrom(response, '/speech/transcribe');
    }
    final decoded = _decode(response);
    return _parse(
      () => Transcription.fromJson(decoded as Map<String, dynamic>),
      'transcription',
    );
  }

  /// POST /activities/next (server engine).
  Future<Map<String, dynamic>> nextActivity(
    String token, {
    required String patientId,
    bool stopRequested = false,
    bool fatigueReported = false,
    List<String>? availableSlugs,
  }) => _send(
    'POST',
    '/activities/next',
    token: token,
    body: {
      'patient_id': patientId,
      'stop_requested': stopRequested,
      'fatigue_reported': fatigueReported,
      'available_slugs': ?availableSlugs,
    },
  );

  /// POST /sync/push. [mutations] are already-encoded outbox payloads.
  Future<List<MutationResult>> syncPush(
    String token, {
    required String deviceInstallId,
    required List<Map<String, dynamic>> mutations,
  }) async {
    final json = await _send(
      'POST',
      '/sync/push',
      token: token,
      body: {'device_install_id': deviceInstallId, 'mutations': mutations},
    );
    return _parse(
      () => (json['results'] as List<dynamic>)
          .map((r) => MutationResult.fromJson(r as Map<String, dynamic>))
          .toList(),
      'sync push',
    );
  }

  Future<SyncPullResponse> syncPull(
    String token, {
    required int since,
    int limit = 500,
  }) async {
    final json = await _send(
      'GET',
      '/sync/pull',
      token: token,
      query: {'since': '$since', 'limit': '$limit'},
    );
    return _parse(() => SyncPullResponse.fromJson(json), 'sync pull');
  }

  /// GET /files/{id}/content: protected media bytes (approved memory photos).
  Future<Uint8List> downloadFile(String token, String fileId) async {
    final response = await _request(
      () => _http
          .get(
            _url('/files/$fileId/content'),
            headers: _headers(token)..remove('Accept'),
          )
          .timeout(timeout),
    );
    if (response.statusCode == 200) return response.bodyBytes;
    throw _errorFrom(response, '/files/$fileId/content');
  }

  void close() => _http.close();

  // ---------- plumbing ----------

  T _parse<T>(T Function() parse, String what) {
    try {
      return parse();
    } on Object catch (e) {
      throw ApiException('invalid_response', 'Unexpected $what response: $e');
    }
  }

  Future<http.Response> _request(Future<http.Response> Function() run) async {
    try {
      return await run();
    } on TimeoutException {
      throw const ApiException('timeout', 'The server did not respond in time');
    } on SocketException catch (e) {
      throw ApiException(
        'network_error',
        'Cannot reach the server: ${e.message}',
      );
    } on http.ClientException catch (e) {
      throw ApiException(
        'network_error',
        'Cannot reach the server: ${e.message}',
      );
    }
  }

  Future<Map<String, dynamic>> _send(
    String method,
    String path, {
    String? token,
    Object? body,
    Map<String, String>? query,
  }) async {
    final url = _url(path, query);
    final response = await _request(() {
      final headers = _headers(token, json: body != null);
      final future = switch (method) {
        'GET' => _http.get(url, headers: headers),
        'POST' => _http.post(url, headers: headers, body: jsonEncode(body)),
        _ => throw ArgumentError.value(method, 'method'),
      };
      return future.timeout(timeout);
    });

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final decoded = _decode(response);
      if (decoded is Map<String, dynamic>) return decoded;
      throw ApiException(
        'invalid_response',
        'Expected a JSON object from $path',
        statusCode: response.statusCode,
      );
    }
    throw _errorFrom(response, path);
  }

  Object? _decode(http.Response response) {
    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      return null;
    }
  }

  ApiException _errorFrom(http.Response response, String path) {
    final body = _decode(response);
    // Backend error envelope: {"error": {"code", "message", ...}}
    if (body is Map<String, dynamic> && body['error'] is Map<String, dynamic>) {
      final error = body['error'] as Map<String, dynamic>;
      return ApiException(
        error['code'] as String? ?? 'http_error',
        error['message'] as String? ?? 'Request failed',
        statusCode: response.statusCode,
      );
    }
    return ApiException(
      'http_error',
      'Request to $path failed',
      statusCode: response.statusCode,
    );
  }
}
