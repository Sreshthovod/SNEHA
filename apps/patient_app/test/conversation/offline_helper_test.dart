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

  test(
    'feeling unwell or scared while asking to stop gets the safety reply',
    () {
      for (final text in ['Please stop, I feel dizzy', "Stop, I'm scared"]) {
        final r = helper.reply(text, ctx);
        expect(r.intent, isNot(HelperIntent.unknown), reason: text);
        expect(r.intent, isNot(HelperIntent.stop), reason: text);
        expect(r.text, contains('112'), reason: text);
      }
    },
  );

  test('stop always wins, in English and the draft Indic forms', () {
    for (final text in [
      'stop',
      'No, stop',
      'no no stop it',
      "I'm tired, stop",
      'enough',
      'I want to stop',
      "I don't want to do this anymore",
      'रुकिए',
      'रुको',
      'बस करो',
      'बस',
      'থামুন',
      'থামো',
      'বন্ধ করুন',
      'ৰখক',
      'ৰখা',
      'বন্ধ কৰক',
    ]) {
      final r = helper.reply(text, ctx);
      expect(r.intent, HelperIntent.stop, reason: text);
      expect(r.text, contains('stop now'), reason: text);
      expect(r.intent.label, 'request_stop');
    }
    expect(helper.classify('बस्ती'), isNot(HelperIntent.stop));
    expect(
      OfflineHelper(AppStrings('hi')).reply('रुको', ctx).text,
      contains('रुक'),
    );
  });

  test('tiredness gets a rest suggestion, but "not tired" does not', () {
    for (final text in [
      "I'm tired",
      'No, I am so tired',
      'I am sleepy',
      'मैं थक गया हूँ',
      'আমি ক্লান্ত',
    ]) {
      final r = helper.reply(text, ctx);
      expect(r.intent, HelperIntent.tired, reason: text);
      expect(r.text, contains('rest'), reason: text);
    }
    expect(helper.classify("I'm not tired"), isNot(HelperIntent.tired));
    expect(helper.classify('मैं थका नहीं हूँ'), isNot(HelperIntent.tired));
  });

  test('fear and being lost get a calm reply with family and 112', () {
    for (final text in [
      "I'm scared",
      'I am afraid',
      'I am lost',
      'where am I?',
      'मुझे डर लग रहा है',
      'আমার ভয় করছে',
    ]) {
      final r = helper.reply(text, ctx);
      expect(r.intent, HelperIntent.scaredOrLost, reason: text);
      expect(r.text, contains('112'), reason: text);
      expect(r.text.toLowerCase(), contains('family'), reason: text);
    }
  });

  test('nothing safety-related falls through to "did not understand"', () {
    final unknown = helper.replyTo(HelperIntent.unknown, ctx).text;
    for (final text in ['stop', "I'm tired", "I'm scared", 'I am lost']) {
      expect(helper.reply(text, ctx).text, isNot(unknown), reason: text);
    }
  });

  test('intent labels match the server pattern', () {
    for (final i in HelperIntent.values) {
      expect(i.label, matches(RegExp(r'^[a-z][a-z0-9_]{0,39}$')));
    }
  });
}
