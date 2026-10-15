import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Device session tokens, one per paired patient profile.
///
/// Tokens are secrets: they never go into SQLite, logs or analytics.
abstract interface class TokenStore {
  Future<String?> read(String patientId);
  Future<void> write(String patientId, String token);
  Future<void> delete(String patientId);
}

/// Production store: Android Keystore-backed encrypted storage.
class SecureTokenStore implements TokenStore {
  SecureTokenStore([FlutterSecureStorage? storage])
    : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  static String _key(String patientId) => 'device_token.$patientId';

  @override
  Future<String?> read(String patientId) => _storage.read(key: _key(patientId));

  @override
  Future<void> write(String patientId, String token) =>
      _storage.write(key: _key(patientId), value: token);

  @override
  Future<void> delete(String patientId) =>
      _storage.delete(key: _key(patientId));
}

/// For tests and previews only.
class InMemoryTokenStore implements TokenStore {
  final Map<String, String> tokens = {};

  @override
  Future<String?> read(String patientId) async => tokens[patientId];

  @override
  Future<void> write(String patientId, String token) async =>
      tokens[patientId] = token;

  @override
  Future<void> delete(String patientId) async => tokens.remove(patientId);
}
