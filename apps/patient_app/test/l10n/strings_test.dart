import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/l10n/strings.dart';

void main() {
  test('every string key used in lib/ exists in English', () {
    final used = <String>{};
    final pattern = RegExp(r"""\.t\(\s*'([a-z0-9_]+)'""");
    for (final f in Directory(
      'lib',
    ).listSync(recursive: true).whereType<File>()) {
      if (!f.path.endsWith('.dart')) continue;
      used.addAll(
        pattern.allMatches(f.readAsStringSync()).map((m) => m.group(1)!),
      );
    }
    // Keys built dynamically.
    used.addAll(['story_prompt_1', 'story_prompt_2', 'story_prompt_3']);
    for (final k in [
      'data_processing',
      'clinician_sharing',
      'cloud_ai',
      'voice_processing',
    ]) {
      used.add('consent_$k');
    }
    final missing = used
        .where((k) => !AppStrings.english.containsKey(k))
        .toList();
    expect(missing, isEmpty);
  });

  test('draft tables only contain keys that exist in English', () {
    for (final table in AppStrings.draftTables.values) {
      expect(
        table.keys.where((k) => !AppStrings.english.containsKey(k)),
        isEmpty,
      );
    }
  });

  test('falls back to English and substitutes arguments', () {
    expect(AppStrings('kha').t('home_play'), 'Play an activity');
    expect(AppStrings('hi').t('home_play'), 'कोई खेल खेलें');
    expect(
      AppStrings('en').t('home_greeting', {'name': 'Aita'}),
      'Namaste, Aita',
    );
  });

  test('result and activity strings avoid clinical or alarming words', () {
    final banned = RegExp(
      r'\b(poor|fail|failed|decline|impair|dementia|score|wrong|bad)\b',
      caseSensitive: false,
    );
    final offending = AppStrings.english.entries
        .where(
          (e) =>
              e.key.startsWith('result_') ||
              e.key.startsWith('runner_') ||
              e.key.startsWith('game_'),
        )
        .where((e) => banned.hasMatch(e.value))
        .map((e) => e.key);
    expect(offending, isEmpty);
  });

  test('every supported language has a translation status', () {
    expect(supportedLanguages.map((l) => l.code).toSet().length, 11);
    expect(translationStatus('en'), TranslationStatus.complete);
    expect(translationStatus('as'), TranslationStatus.draft);
    expect(translationStatus('lus'), TranslationStatus.englishFallback);
  });
}
