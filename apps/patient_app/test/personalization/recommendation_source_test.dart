import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sneha_patient/data/api/api_client.dart';
import 'package:sneha_patient/personalization/engine.dart';
import 'package:sneha_patient/personalization/recommendation_source.dart';

import '../helpers.dart';

void main() {
  test('server recommendations are ON since Stage 7 (local fallback)', () {
    expect(serverRecommendationsEnabled, isTrue);
  });

  test(
    'server-first source parses the server and falls back offline',
    () async {
      final h = await Harness.create();
      addTearDown(h.dispose);
      await h.pairAndOnboard();
      var online = true;
      final api = SnehaApiClient(
        baseUrl: Uri.parse('http://api.test'),
        httpClient: MockClient((r) async {
          if (!online) throw http.ClientException('offline');
          expect(r.url.path, '/api/v1/activities/next');
          final body = jsonDecode(r.body) as Map<String, dynamic>;
          expect(body['patient_id'], patientId);
          expect(body['available_slugs'], contains('picture-pairs'));
          return http.Response(
            jsonEncode(recommendationJson(id: 'rec-1')),
            200,
            headers: {'content-type': 'application/json'},
          );
        }),
      );
      final source = ServerFirstRecommendationSource(
        api,
        h.services.profiles,
        LocalRecommendationSource(h.services.facts, h.services.profiles),
        h.services.facts,
      );
      final server = await source.next(patientId);
      expect(server.chosenOnDevice, isFalse);
      expect(server.recommendationId, 'rec-1');
      expect(server.difficulty, 2);

      online = false;
      final local = await source.next(patientId);
      expect(local.chosenOnDevice, isTrue);
      expect(local.recommendationId, isNull);
      expect(local.action, EngineAction.activity);
    },
  );
}
