// Reading aloud never carries on after the person pauses, stops, says they are
// tired or leaves, and it can always be stopped. Hints, stories and helper
// replies can be heard as well as read. All data is SYNTHETIC.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/features/memories/story_time_screen.dart';
import 'package:sneha_patient/speech/speech.dart';

import '../helpers.dart';
import '../stage7/conversation_and_e2e_test.dart' show openTalk, say;
import '../widgets/runner_test.dart' show openObjectGame;
import '../widgets/stage5_widgets_test.dart' show FakeSpeech, enableReadAloud;

Finder readAloud() => find.widgetWithText(OutlinedButton, 'Read aloud');
Finder stopReading() => find.widgetWithText(OutlinedButton, 'Stop reading');

Future<(Harness, FakeSpeech)> gameReadingAloud(WidgetTester tester) async {
  final speech = FakeSpeech(SpeechAvailability.available);
  final h = await pairedHarness(tester, speech: speech);
  await enableReadAloud(tester, h);
  await openObjectGame(tester, h);
  await tapVisible(tester, readAloud());
  expect(speech.speaking.value, isTrue);
  return (h, speech);
}

void main() {
  testWidgets('while reading, the button becomes "Stop reading" and stops it', (
    tester,
  ) async {
    final (h, speech) = await gameReadingAloud(tester);
    addTearDown(h.dispose);
    expect(stopReading(), findsOneWidget);
    await tapVisible(tester, stopReading());
    expect(speech.speaking.value, isFalse);
    expect(speech.stops, 1);
    expect(readAloud(), findsOneWidget);
  });

  testWidgets('when the voice finishes, the button goes back to "Read aloud"', (
    tester,
  ) async {
    final (h, speech) = await gameReadingAloud(tester);
    addTearDown(h.dispose);
    speech.finish();
    await tester.pump();
    expect(readAloud(), findsOneWidget);
    expect(stopReading(), findsNothing);
  });

  testWidgets('pausing silences the voice', (tester) async {
    final (h, speech) = await gameReadingAloud(tester);
    addTearDown(h.dispose);
    await tapVisible(tester, find.text('Pause'));
    expect(speech.speaking.value, isFalse);
  });

  testWidgets('asking to stop silences the voice before the question', (
    tester,
  ) async {
    final (h, speech) = await gameReadingAloud(tester);
    addTearDown(h.dispose);
    await tapVisible(tester, find.text('Stop'));
    expect(find.byKey(const ValueKey('stop_confirm')), findsOneWidget);
    expect(speech.speaking.value, isFalse);
  });

  testWidgets("\"I'm tired\" silences the voice", (tester) async {
    final (h, speech) = await gameReadingAloud(tester);
    addTearDown(h.dispose);
    await tapVisible(tester, find.text("I'm tired"));
    expect(speech.speaking.value, isFalse);
  });

  testWidgets('leaving the app silences the voice', (tester) async {
    final (h, speech) = await gameReadingAloud(tester);
    addTearDown(h.dispose);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    await tester.pump();
    expect(speech.speaking.value, isFalse);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
  });

  testWidgets('a hint can be heard, and only offers it when a voice exists', (
    tester,
  ) async {
    final speech = FakeSpeech(SpeechAvailability.available);
    final h = await pairedHarness(tester, speech: speech);
    addTearDown(h.dispose);
    await openObjectGame(tester, h);
    // Read aloud is off in Settings: the hint shows no extra button.
    await tapVisible(tester, find.text('Hint'));
    final hint = find.byKey(const ValueKey('runner_hint_message'));
    expect(
      find.descendant(of: hint, matching: find.byType(OutlinedButton)),
      findsNothing,
    );
    expect(speech.spoken, isEmpty);

    await enableReadAloud(tester, h);
    await settle(tester);
    final hintButton = find.descendant(
      of: hint,
      matching: find.widgetWithText(OutlinedButton, 'Read aloud'),
    );
    expect(hintButton, findsOneWidget);
    expect(speech.spoken, isEmpty); // never speaks by itself here
    await tapVisible(tester, hintButton);
    final hintText = tester
        .widgetList<Text>(
          find.descendant(of: hint, matching: find.byType(Text)),
        )
        .first
        .data;
    expect(speech.spoken.single.$1, hintText);
  });

  testWidgets('story time can be heard, and moving on stops the voice', (
    tester,
  ) async {
    final speech = FakeSpeech(SpeechAvailability.available);
    final h = await pairedHarness(tester, speech: speech);
    addTearDown(h.dispose);
    await real(tester, () async {
      for (var i = 0; i < 2; i++) {
        await h.local.db.insert('memories', {
          'id': 'mem-$i',
          'patient_id': patientId,
          'kind': 'place',
          'title': 'Synthetic story place $i',
          'description': i == 0 ? 'Synthetic: the river at dawn.' : null,
          'approx_year': null,
          'relationship': null,
          'tags_json': '[]',
          'media_file_id': null,
          'version': 1,
          'local_photo_path': null,
        });
      }
    });
    await enableReadAloud(tester, h);
    final profile = await real(
      tester,
      () => h.services.profiles.get(patientId),
    );
    await tester.pumpWidget(h.app());
    await settle(tester);
    tester
        .state<NavigatorState>(find.byType(Navigator).first)
        .push(
          MaterialPageRoute<void>(
            builder: (_) => StoryTimeScreen(profile: profile!),
          ),
        );
    await settle(tester);
    await tapVisible(tester, readAloud());
    final said = speech.spoken.single.$1;
    expect(said, startsWith('Synthetic story place'));
    expect(speech.speaking.value, isTrue);
    await tapVisible(tester, find.text('Next memory'));
    expect(speech.speaking.value, isFalse);
  });

  testWidgets('helper replies have a small "Read aloud" button', (
    tester,
  ) async {
    final speech = FakeSpeech(SpeechAvailability.available);
    final h = await pairedHarness(tester, speech: speech);
    addTearDown(h.dispose);
    await enableReadAloud(tester, h);
    await openTalk(tester, h);
    await say(tester, 'I remember the tea garden');
    final speaker = find.byTooltip('Read aloud');
    expect(speaker, findsWidgets);
    await tapVisible(tester, speaker.last);
    expect(speech.spoken, isNotEmpty);
    // Only the helper's words get a button, never the person's own.
    expect(
      speech.spoken.any((s) => s.$1 == 'I remember the tea garden'),
      isFalse,
    );
  });

  testWidgets('without a voice, helper replies show no speaker button', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await enableReadAloud(tester, h);
    await openTalk(tester, h);
    await say(tester, 'I remember the tea garden');
    expect(find.byTooltip('Read aloud'), findsNothing);
  });
}
