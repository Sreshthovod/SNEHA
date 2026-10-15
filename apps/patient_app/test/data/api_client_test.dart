import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sneha_patient/data/api/api_client.dart';

SnehaApiClient clientWith(MockClientHandler handler) => SnehaApiClient(
  baseUrl: Uri.parse('http://api.test'),
  httpClient: MockClient(handler),
);

void main() {
  test('getHealth parses the contract and normalises to UTC', () async {
    final client = clientWith(
      (r) async => http.Response(
        jsonEncode({
          'status': 'ok',
          'service': 'SNEHA API',
          'version': '0.1.0',
          'environment': 'test',
          'server_time': '2026-01-01T10:00:00+05:30',
        }),
        200,
      ),
    );
    final health = await client.getHealth();
    expect(health.serverTime, DateTime.utc(2026, 1, 1, 4, 30));
  });

  test('pairDevice posts the code and parses the token response', () async {
    late http.Request seen;
    final client = clientWith((r) async {
      seen = r;
      return http.Response(
        jsonEncode({
          'access_token': 't',
          'token_type': 'bearer',
          'expires_at': '2027-01-01T00:00:00Z',
          'user': {
            'id': 'u',
            'email': null,
            'full_name': 'P',
            'role': 'patient',
          },
          'patient_id': 'p',
        }),
        200,
      );
    });
    final token = await client.pairDevice(
      code: 'ABCD-2345',
      deviceName: 'Phone',
    );
    expect(seen.url.path, '/api/v1/auth/device/pair');
    expect(jsonDecode(seen.body), {
      'code': 'ABCD-2345',
      'device_name': 'Phone',
    });
    expect(token.patientId, 'p');
  });

  test('authenticated calls send the bearer token and query', () async {
    late http.Request seen;
    final client = clientWith((r) async {
      seen = r;
      return http.Response(
        jsonEncode({'changes': [], 'next_since': 7, 'has_more': false}),
        200,
      );
    });
    final page = await client.syncPull('tok', since: 7);
    expect(seen.headers['Authorization'], 'Bearer tok');
    expect(seen.url.queryParameters, {'since': '7', 'limit': '500'});
    expect(page.nextSince, 7);
  });

  test('maps the backend error envelope, including 401', () async {
    final client = clientWith(
      (_) async => http.Response(
        jsonEncode({
          'error': {'code': 'unauthorized', 'message': 'expired'},
        }),
        401,
      ),
    );
    expect(
      client.getMe('t'),
      throwsA(
        isA<ApiException>()
            .having((e) => e.isUnauthorized, 'isUnauthorized', isTrue)
            .having((e) => e.code, 'code', 'unauthorized'),
      ),
    );
  });

  test('network failures are ApiException(network_error)', () async {
    final client = clientWith((_) async => throw http.ClientException('down'));
    expect(
      client.getHealth(),
      throwsA(
        isA<ApiException>().having((e) => e.isNetwork, 'isNetwork', isTrue),
      ),
    );
  });

  test('malformed success bodies are rejected', () async {
    final client = clientWith((_) async => http.Response('<html>', 200));
    expect(
      client.getHealth(),
      throwsA(
        isA<ApiException>().having((e) => e.code, 'code', 'invalid_response'),
      ),
    );
  });

  test('downloadFile returns bytes or throws on 404', () async {
    final ok = clientWith((_) async => http.Response.bytes([1, 2, 3], 200));
    expect(await ok.downloadFile('t', 'f'), [1, 2, 3]);
    final missing = clientWith((_) async => http.Response('', 404));
    expect(missing.downloadFile('t', 'f'), throwsA(isA<ApiException>()));
  });
}
