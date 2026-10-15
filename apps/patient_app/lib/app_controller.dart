import 'package:flutter/foundation.dart';

import 'app_services.dart';
import 'data/api/api_client.dart';
import 'data/repositories/profile_repository.dart';
import 'data/repositories/settings_repository.dart';
import 'l10n/strings.dart';

enum PairingError { invalidCode, offline, rateLimited, other }

class PairingException implements Exception {
  const PairingException(this.error);
  final PairingError error;
}

/// App-wide state: settings, paired profiles and the active profile.
class AppController extends ChangeNotifier {
  AppController(this._services);

  final AppServices _services;

  bool _ready = false;
  AppSettings _settings = const AppSettings();
  List<Profile> _profiles = const [];

  bool get ready => _ready;
  AppSettings get settings => _settings;
  List<Profile> get profiles => _profiles;
  AppStrings get strings => AppStrings(_settings.languageCode);

  Profile? get activeProfile {
    final id = _settings.activePatientId;
    for (final p in _profiles) {
      if (p.patientId == id) return p;
    }
    return null;
  }

  Future<void> load() async {
    _settings = await _services.settings.load();
    _profiles = await _services.profiles.list();
    _ready = true;
    notifyListeners();
  }

  Future<void> updateSettings(AppSettings next) async {
    _settings = next;
    notifyListeners();
    await _services.settings.save(next);
  }

  Future<void> chooseLanguage(String code) => updateSettings(
    _settings.copyWith(languageCode: code, languageChosen: true),
  );

  Future<void> completeOnboarding() =>
      updateSettings(_settings.copyWith(onboardingComplete: true));

  Future<void> selectProfile(String? patientId) => updateSettings(
    patientId == null
        ? _settings.copyWith(clearActivePatient: true)
        : _settings.copyWith(activePatientId: patientId),
  );

  Future<void> refreshProfiles() async {
    _profiles = await _services.profiles.list();
    notifyListeners();
  }

  /// Pair this phone with a patient using a caregiver-issued code, then make
  /// that profile active. A first sync is attempted but is not required.
  Future<Profile> pair({
    required String code,
    required String deviceName,
  }) async {
    final api = _services.api;
    try {
      final token = await api.pairDevice(code: code, deviceName: deviceName);
      final patientId = token.patientId;
      if (patientId == null) throw const PairingException(PairingError.other);
      final patient = await api.getPatient(token.accessToken, patientId);
      final profile = await _services.profiles.savePaired(token, patient);
      await refreshProfiles();
      await selectProfile(profile.patientId);
      return profile;
    } on ApiException catch (e) {
      if (e.isNetwork) throw const PairingException(PairingError.offline);
      if (e.statusCode == 401) {
        throw const PairingException(PairingError.invalidCode);
      }
      if (e.statusCode == 429) {
        throw const PairingException(PairingError.rateLimited);
      }
      if (e.statusCode == 422) {
        throw const PairingException(PairingError.invalidCode);
      }
      throw const PairingException(PairingError.other);
    }
  }

  Future<void> removeProfile(String patientId) async {
    // Sign this phone out on the server first so the token stops working there too.
    // Best effort: removing the profile must also work offline.
    final token = await _services.tokens.read(patientId);
    if (token != null) {
      try {
        await _services.api.logout(token);
      } on Object {
        // Offline or server error: the session still expires on its own.
      }
    }
    await _services.profiles.remove(patientId);
    if (_settings.activePatientId == patientId) {
      await selectProfile(null);
    }
    await refreshProfiles();
  }
}
