import 'package:uuid/uuid.dart';

import '../../personalization/recommendation_source.dart';
import '../api/api_client.dart';
import '../api/stage7_models.dart';
import 'profile_repository.dart';

/// Online conversation understanding (POST /conversation/analyze).
///
/// The server validates everything the language model says against the
/// family-approved Memory Bank and only returns a patient-safe reply. When
/// this throws (offline, not paired, no consent, server problem) the screen
/// uses the simple helper on this phone instead.
class ConversationRepository {
  ConversationRepository(this._api, this._profiles, this._facts);

  final SnehaApiClient _api;
  final ProfileRepository _profiles;
  final LocalFacts _facts;

  Future<String> _token(String patientId) async {
    final profile = await _profiles.get(patientId);
    final token = await _profiles.token(patientId);
    if (profile == null || token == null || profile.needsRepair) {
      throw const ApiException(
        'not_paired',
        'This phone needs a new pairing code.',
        statusCode: 401,
      );
    }
    return token;
  }

  Future<ConversationTurn> analyze(
    String patientId, {
    required String text,
    required String language,
    required String conversationId,
    String? sessionId,
  }) async {
    final token = await _token(patientId);
    return _api.analyzeConversation(
      token,
      patientId: patientId,
      text: text,
      language: language,
      conversationId: conversationId,
      sessionId: sessionId,
      availableSlugs: await _facts.availableSlugs(patientId),
    );
  }

  /// Sends a possible memory to the family as a PROPOSAL. The server stores
  /// it as `pending_approval`; it reaches this phone only after approval.
  Future<void> proposeMemory(String patientId, MemoryCandidate c) async {
    final token = await _token(patientId);
    await _api.proposeMemory(
      token,
      patientId: patientId,
      id: const Uuid().v4(),
      kind: c.kind,
      title: c.title,
      description: c.description,
    );
  }
}
