import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/conversation/offline_helper.dart';
import 'package:sneha_patient/data/api/models.dart';
import 'package:sneha_patient/l10n/strings.dart';

void main() {
  final helper = OfflineHelper(AppStrings('en'));
  final ctx = HelperContext(
    name: 'Aita',
    now: DateTime(2026, 10, 15, 9, 5), // Thursday
    routines: const [
      RoutineItem(
        id: 'r',
        patientId: 'p',
        title: 'Morning tea',
        localTime: '07:30',
        daysOfWeek: 127,
        isActive: true,
      ),
    ],
    memories: const [
      MemoryItem(
        id: 'm',
        patientId: 'p',
        kind: 'place',
        title: 'Synthetic tea garden',
      ),
    ],
  );

  test('classifies simple intents, including Indic greetings', () {
    expect(helper.classify('Hello there'), HelperIntent.greeting);
    expect(helper.classify('नमस्ते'), HelperIntent.greeting);
    expect(helper.classify('What time is it?'), HelperIntent.askTime);
    expect(helper.classify('what day is it'), HelperIntent.askDate);
    expect(helper.classify('What do I do today?'), HelperIntent.askRoutine);
    expect(helper.classify('show me a photo'), HelperIntent.memoryPrompt);
    expect(
      helper.classify('I want to call my son'),
      HelperIntent.contactFamily,
    );
    expect(helper.classify('thank you'), HelperIntent.thanks);
    expect(helper.classify('xyzzy'), HelperIntent.unknown);
    expect(
      helper.classify('this is nice'),
      HelperIntent.unknown,
      reason: '"hi" in "this"',
    );
  });

  test('health messages always get the safety reply, never advice', () {
    for (final text in [
      'I feel dizzy',
      'chest pain',
      'I fell down',
      "I don't feel well, hello",
    ]) {
      final r = helper.reply(text, ctx);
      expect(r.intent, HelperIntent.feelingUnwell, reason: text);
      expect(r.text, contains('112'));
    }
  });

  test('replies use local context', () {
    expect(helper.reply('hello', ctx).text, contains('Aita'));
    expect(helper.reply('what time', ctx).text, contains('9:05'));
    expect(
      helper.reply('what date', ctx).text,
      contains('Thursday, 15 October 2026'),
    );
    expect(
      helper.reply('what should i do', ctx).text,
      contains('07:30 Morning tea'),
    );
    expect(helper.reply('memory', ctx).text, contains('Synthetic tea garden'));
  });

  test('intent labels match the server pattern', () {
    for (final i in HelperIntent.values) {
      expect(i.label, matches(RegExp(r'^[a-z][a-z0-9_]{0,39}$')));
    }
  });
}
