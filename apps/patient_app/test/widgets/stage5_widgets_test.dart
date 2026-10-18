// Stage 5 UI: suggestion card, "I'm tired", engagement question, progress,
// sync problems list, read aloud. All data is SYNTHETIC.
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/data/repositories/activity_recorder.dart';
import 'package:sneha_patient/data/repositories/settings_repository.dart';
import 'package:sneha_patient/speech/speech.dart';

import '../helpers.dart';
import 'runner_test.dart' show answerCorrectly, openObjectGame;

class FakeSpeech implements SpeechOutput {
  FakeSpeech(this.result);

  final SpeechAvailability result;
  final spoken = <(String, String)>[];

  @override
  Future<SpeechAvailability> availability(String languageCode) async => result;

  /// How many times the app asked the voice to stop.
  int stops = 0;
  final ValueNotifier<bool> _speaking = ValueNotifier<bool>(false);

  @override
  ValueListenable<bool> get speaking => _speaking;

  @override
  Future<bool> speak(String text, String languageCode) async {
    if (result != SpeechAvailability.available) return false;
    spoken.add((text, languageCode));
    _speaking.value = true;
    return true;
  }

  @override
  Future<void> stop() async {
    stops++;
    _speaking.value = false;
  }

  /// The voice reached the end by itself.
  void finish() => _speaking.value = false;
}

Future<void> enableReadAloud(WidgetTester tester, Harness h) => real(
  tester,
  () => h.services.controller.updateSettings(
    h.services.controller.settings.copyWith(readAloud: true),
  ),
);

void main() {
  testWidgets('home suggestion is chosen on this phone and can be started', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.online = false;
    await tester.pumpWidget(h.app());
    await settle(tester);

    expect(find.text('Suggested for you'), findsOneWidget);
    expect(find.text('Chosen on this phone'), findsOneWidget);
    expect(find.text('Synthetic picture-pairs'), findsOneWidget);
    expect(find.text('A good one to start with.'), findsOneWidget);
    expect(find.textContaining('COLD_START'), findsNothing, reason: 'no codes');
    await tapVisible(tester, find.text('Start'));
    // The generic runner opened the suggested game.
    expect(find.text("I'm tired"), findsOneWidget);
    expect(
      find.descendant(
        of: find.byType(AppBar),
        matching: find.text('Synthetic picture-pairs'),
      ),
      findsOneWidget,
    );
  });

  testWidgets("I'm tired records tiredness, ends gently and offers rest", (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await openObjectGame(tester, h);
    await answerCorrectly(tester);
    await tapVisible(tester, find.text("I'm tired"));

    expect(find.text("Let's take a rest"), findsOneWidget);
    expect(find.text('Rest now'), findsOneWidget);
    final rows = await real(tester, h.outbox);
    final result = jsonDecode(
      rows.firstWhere(
            (r) => r['entity_type'] == 'activity_result',
          )['payload_json']
          as String,
    );
    expect(result['fatigue_reported'], isTrue);
    expect(result['abandoned'], isTrue);
    expect(result['score'], isNull, reason: 'tiredness is never a mistake');
    final end = jsonDecode(rows.last['payload_json'] as String);
    expect(end['end_reason'], 'fatigue_detected');

    // "Try something easy" uses the engine: an easy activity at its minimum.
    await tapVisible(tester, find.text('Try something easy'));
    expect(
      find.descendant(
        of: find.byType(AppBar),
        matching: find.text('Synthetic picture-pairs'),
      ),
      findsOneWidget,
      reason: 'a different, low-effort activity',
    );
    await tapVisible(tester, find.text('Stop'));
    await tapVisible(tester, find.text('Yes, stop'));
    await tapVisible(tester, find.text('Go home'));
    expect(find.text('Time for a rest'), findsOneWidget);
  });

  testWidgets('"Did you enjoy this?" is optional and saved with the result', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await openObjectGame(tester, h);
    for (var r = 0; r < 3; r++) {
      await answerCorrectly(tester);
    }
    expect(find.text('Did you enjoy this?'), findsOneWidget);
    expect(find.text('Skip this question'), findsOneWidget);
    await tapVisible(tester, find.text('Enjoyed it'));
    expect(find.text('Thank you for telling us.'), findsOneWidget);

    final rows = await real(tester, h.outbox);
    final result = jsonDecode(
      rows.firstWhere(
            (r) => r['entity_type'] == 'activity_result',
          )['payload_json']
          as String,
    );
    expect(result['engagement'], 'enjoyed');
  });

  testWidgets('progress screen is descriptive and works offline', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.online = false;
    await openObjectGame(tester, h);
    for (var r = 0; r < 3; r++) {
      await answerCorrectly(tester);
    }
    await tapVisible(tester, find.text('Go home'));
    await tapVisible(tester, find.text('For caregivers'));
    await tapVisible(tester, find.text('What I have done'));
    expect(find.text('Synthetic name-the-object'), findsOneWidget);
    expect(find.text('Level 1 of 3'), findsOneWidget);
    expect(find.text('Played 1 time'), findsOneWidget);
    expect(find.textContaining('not a test'), findsOneWidget);
    expect(find.textContaining('%'), findsNothing);
  });

  testWidgets('sync screen lists items that could not be shared', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.pushStatus['activity_result'] = 'conflict';
    h.server.pushStatus['activity_session'] = 'rejected';
    await real(tester, () async {
      final (sid, start) = await h.services.recorder.startSession(patientId);
      await h.services.recorder.recordConversation(
        patientId,
        ConversationSummaryFixture.make(start),
      );
      await h.services.sync.syncProfile(patientId);
      return sid;
    });
    await tester.pumpWidget(h.app());
    await settle(tester);
    await tapVisible(tester, find.text('For caregivers'));
    await tapVisible(tester, find.text('Sharing and offline'));

    expect(find.text('Could not be shared'), findsWidgets);
    // The session start and, because no activity was open when the app came
    // back, its "interrupted" ending: both wait for the server.
    expect(find.textContaining('An activity session'), findsNWidgets(2));
    expect(
      find.text(
        'The server could not accept this yet. Your copy is kept on this phone.',
      ),
      findsNWidgets(2),
    );
    h.server.pushStatus.clear();
    while (find.text('Try again').evaluate().isNotEmpty) {
      await tapVisible(tester, find.text('Try again').first);
    }
    await tapVisible(tester, find.text('Sync now'));
    expect(find.textContaining('An activity session'), findsNothing);
  });

  testWidgets('read aloud speaks the question when a voice exists', (
    tester,
  ) async {
    final speech = FakeSpeech(SpeechAvailability.available);
    final h = await pairedHarness(tester, speech: speech);
    addTearDown(h.dispose);
    await enableReadAloud(tester, h);
    await openObjectGame(tester, h);
    final button = find.widgetWithText(OutlinedButton, 'Read aloud');
    expect(tester.widget<OutlinedButton>(button).onPressed, isNotNull);
    await tapVisible(tester, button);
    expect(speech.spoken.single.$1, 'What is this?');
  });

  testWidgets('read aloud is disabled with an honest reason', (tester) async {
    final speech = FakeSpeech(SpeechAvailability.languageUnsupported);
    final h = await pairedHarness(tester, speech: speech);
    addTearDown(h.dispose);
    await openObjectGame(tester, h);
    // Off in settings by default.
    expect(find.text('Read aloud is turned off in Settings.'), findsOneWidget);
    await enableReadAloud(tester, h);
    await settle(tester);
    expect(
      find.text('This phone has no voice for your language.'),
      findsOneWidget,
    );
    final button = find.widgetWithText(OutlinedButton, 'Read aloud');
    expect(tester.widget<OutlinedButton>(button).onPressed, isNull);
    expect(speech.spoken, isEmpty);
  });

  testWidgets('read-aloud setting persists', (tester) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await tester.pumpWidget(h.app());
    await settle(tester);
    await tapVisible(tester, find.text('For caregivers'));
    await tapVisible(tester, find.text('Settings'));
    await tapVisible(tester, find.text('Read aloud'));
    final saved = await real(tester, () => SettingsRepository(h.local).load());
    expect(saved.readAloud, isTrue);
  });
}

/// Builds a metadata-only conversation summary for tests.
class ConversationSummaryFixture {
  static ConversationSummary make(DateTime start) => ConversationSummary(
    startedAt: start,
    endedAt: start.add(const Duration(minutes: 1)),
    language: 'as',
    turnCount: 2,
    intents: const ['greeting'],
  );
}
