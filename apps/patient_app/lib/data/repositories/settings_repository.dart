import 'package:sqflite/sqflite.dart';

import '../local/local_database.dart';

enum TextSizeOption {
  normal(1.0),
  large(1.2),
  extraLarge(1.4);

  const TextSizeOption(this.scale);
  final double scale;
}

/// User preferences. Immutable; change with [copyWith] and save.
class AppSettings {
  const AppSettings({
    this.languageCode = 'en',
    this.languageChosen = false,
    this.onboardingComplete = false,
    this.textSize = TextSizeOption.normal,
    this.highContrast = false,
    this.reduceMotion = false,
    this.readAloud = false,
    this.activePatientId,
  });

  final String languageCode;
  final bool languageChosen;
  final bool onboardingComplete;
  final TextSizeOption textSize;
  final bool highContrast;
  final bool reduceMotion;

  /// Read instructions and questions aloud (when the phone has a voice).
  final bool readAloud;
  final String? activePatientId;

  AppSettings copyWith({
    String? languageCode,
    bool? languageChosen,
    bool? onboardingComplete,
    TextSizeOption? textSize,
    bool? highContrast,
    bool? reduceMotion,
    bool? readAloud,
    String? activePatientId,
    bool clearActivePatient = false,
  }) => AppSettings(
    languageCode: languageCode ?? this.languageCode,
    languageChosen: languageChosen ?? this.languageChosen,
    onboardingComplete: onboardingComplete ?? this.onboardingComplete,
    textSize: textSize ?? this.textSize,
    highContrast: highContrast ?? this.highContrast,
    reduceMotion: reduceMotion ?? this.reduceMotion,
    readAloud: readAloud ?? this.readAloud,
    activePatientId: clearActivePatient
        ? null
        : activePatientId ?? this.activePatientId,
  );
}

class SettingsRepository {
  SettingsRepository(this._local);

  final LocalDatabase _local;

  Future<AppSettings> load() async {
    final rows = await _local.db.query('settings');
    final m = {for (final r in rows) r['key'] as String: r['value'] as String};
    return AppSettings(
      languageCode: m['language'] ?? 'en',
      languageChosen: m['language_chosen'] == '1',
      onboardingComplete: m['onboarding_complete'] == '1',
      textSize: TextSizeOption.values.firstWhere(
        (t) => t.name == m['text_size'],
        orElse: () => TextSizeOption.normal,
      ),
      highContrast: m['high_contrast'] == '1',
      reduceMotion: m['reduce_motion'] == '1',
      readAloud: m['read_aloud'] == '1',
      activePatientId: m['active_patient_id'],
    );
  }

  Future<void> save(AppSettings s) async {
    final values = <String, String?>{
      'language': s.languageCode,
      'language_chosen': s.languageChosen ? '1' : '0',
      'onboarding_complete': s.onboardingComplete ? '1' : '0',
      'text_size': s.textSize.name,
      'high_contrast': s.highContrast ? '1' : '0',
      'reduce_motion': s.reduceMotion ? '1' : '0',
      'read_aloud': s.readAloud ? '1' : '0',
      'active_patient_id': s.activePatientId,
    };
    final batch = _local.db.batch();
    values.forEach((key, value) {
      if (value == null) {
        batch.delete('settings', where: 'key = ?', whereArgs: [key]);
      } else {
        batch.insert('settings', {
          'key': key,
          'value': value,
        }, conflictAlgorithm: ConflictAlgorithm.replace);
      }
    });
    await batch.commit(noResult: true);
  }
}
