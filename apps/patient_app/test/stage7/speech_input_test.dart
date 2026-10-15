// Stage 7: server speech recognition is gated and never invents text.
// Audio here is SYNTHETIC (a few bytes standing in for a WAV recording).
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/data/api/api_client.dart';
import 'package:sneha_patient/speech/speech.dart';
import 'package:sneha_patient/speech/voice_input.dart';

import '../helpers.dart';

class FakeRecorder implements VoiceRecorder {
  bool permission = true;
  bool recording = false;
  Uint8List? audio = Uint8List.fromList(List.filled(64, 1));
  int starts = 0;

  @override
  Future<bool> hasPermission() async => permission;

  @override
  Future<void> start() async {
    starts++;
    recording = true;
  }

  @override
  Future<Uint8List?> stop() async {
    recording = false;
    return audio;
  }

  @override
  Future<void> cancel() async => recording = false;
}

Map<String, dynamic> statusJson({List<String> recognition = const ['as']}) => {
  'asr': {
    'name': 'faster_whisper',
    'configured': true,
    'available': true,
    'model': 'synthetic',
    'languages': ['as', 'bn', 'en', 'hi', 'ne'],
    'detail': 'ready',
  },
  'tts': {
    'name': 'indic_parler',
    'configured': false,
    'available': false,
    'model': null,
    'languages': [],
    'detail': 'not installed',
  },
  'languages': [
    for (final l in ['as', 'en', 'kha'])
      {
        'language': l,
        'speech_recognition': recognition.contains(l),
        'speech_synthesis': false,
      },
  ],
  'touch_alternative': 'Synthetic.',
};

SpeechContext ctx({bool consent = true, String language = 'as'}) =>
    SpeechContext(
      patientId: patientId,
      language: language,
      consents: {'voice_processing': consent ? 'granted' : null},
    );

void main() {
  late Harness h;
  late FakeRecorder recorder;
  late ServerSpeechInput input;

  setUp(() async {
    h = await Harness.create();
    await h.pairAndOnboard();
    recorder = FakeRecorder();
    input = ServerSpeechInput(h.services.api, h.services.profiles, recorder);
  });
  tearDown(() => h.dispose());

  test(
    'availability: consent, language and connection are all required',
    () async {
      h.server.speechStatus = statusJson();
      expect((await input.availability(ctx())).isAvailable, isTrue);
      expect(
        (await input.availability(ctx(consent: false))).reasonKey,
        'speech_no_consent',
      );
      expect(
        (await input.availability(ctx(language: 'kha'))).reasonKey,
        'speech_lang_no_asr',
      );
      h.server.online = false;
      expect((await input.availability(ctx())).reasonKey, 'speech_offline');
      h.server.online = true;
      h.server.speechStatus = null; // older server
      expect(
        (await input.availability(ctx())).reasonKey,
        'speech_input_unavailable',
      );
    },
  );

  test('a successful transcription only returns text', () async {
    h.server.transcribeResponse = (
      200,
      {
        'text': 'Synthetic words',
        'language': 'as',
        'provider': 'faster_whisper',
        'model': 'synthetic',
        'confidence': 0.8,
        'duration_seconds': 1.0,
        'no_speech': false,
      },
    );
    expect(await input.start(), isNull);
    final result = await input.stop(ctx());
    expect(result.text, 'Synthetic words');
    final sent = h.server.transcribeRequests.single;
    expect(sent.headers['content-type'], startsWith('multipart/form-data'));
    final body = String.fromCharCodes(sent.bodyBytes);
    expect(body, contains('name="language"'));
    expect(body, contains('name="patient_id"'));
  });

  test('server errors map to plain messages; nothing is invented', () async {
    final cases = <(int, String, String)>[
      (503, 'model_missing', 'speech_server_missing'),
      (422, 'language_unsupported', 'speech_lang_no_asr'),
      (422, 'invalid_audio', 'speech_bad_audio'),
      (409, 'consent_required', 'speech_no_consent'),
      (500, 'internal_error', 'speech_failed'),
    ];
    for (final (status, code, key) in cases) {
      h.server.transcribeResponse = (
        status,
        {
          'error': {'code': code, 'message': code},
        },
      );
      await input.start();
      final result = await input.stop(ctx());
      expect(result.text, isNull, reason: code);
      expect(result.errorKey, key, reason: code);
    }
    h.server.transcribeResponse = (
      200,
      {
        'text': '',
        'language': 'as',
        'provider': 'faster_whisper',
        'model': 'synthetic',
        'confidence': null,
        'duration_seconds': 1.0,
        'no_speech': true,
      },
    );
    await input.start();
    expect((await input.stop(ctx())).errorKey, 'speech_nothing_heard');
    h.server.online = false;
    await input.start();
    expect((await input.stop(ctx())).errorKey, 'speech_offline');
  });

  test('no microphone permission or empty recording', () async {
    recorder.permission = false;
    expect(await input.start(), 'speech_no_mic_permission');
    expect(recorder.starts, 0);
    recorder
      ..permission = true
      ..audio = null;
    await input.start();
    expect((await input.stop(ctx())).errorKey, 'speech_bad_audio');
    expect(h.server.transcribeRequests, isEmpty);
  });

  test('error-key mapping covers network failures', () {
    expect(
      ServerSpeechInput.errorKeyFor(const ApiException('timeout', 't')),
      'speech_offline',
    );
  });

  testWidgets('mic button: disabled with reason, or records into the text '
      'box without sending', (tester) async {
    final fake = FakeServer()
      ..speechStatus = statusJson(recognition: ['as', 'en'])
      ..consents = {
        'data_processing': 'granted',
        'clinician_sharing': null,
        'cloud_ai': 'withdrawn',
        'voice_processing': 'granted',
      }
      ..transcribeResponse = (
        200,
        {
          'text': 'Synthetic spoken words',
          'language': 'as',
          'provider': 'faster_whisper',
          'model': 'synthetic',
          'confidence': 0.9,
          'duration_seconds': 1.0,
          'no_speech': false,
        },
      );
    final wh = await real(tester, () async {
      final x = await Harness.create(
        server: fake,
        voiceRecorder: FakeRecorder(),
      );
      await x.pairAndOnboard();
      return x;
    });
    addTearDown(wh.dispose);
    await tester.pumpWidget(wh.app());
    await settle(tester);
    await tapVisible(tester, find.text('Talk with the helper'));
    await settle(tester);

    final mic = find.byKey(const ValueKey('mic_button'));
    expect(tester.widget<IconButton>(mic).onPressed, isNotNull);
    await tester.tap(mic);
    await settle(tester);
    expect(find.textContaining('Listening'), findsOneWidget);
    await tester.tap(mic);
    await settle(tester);
    expect(
      tester.widget<TextField>(find.byType(TextField)).controller!.text,
      'Synthetic spoken words',
    );
    expect(find.text('Please check the words, then tap Send.'), findsOneWidget);
    // Not sent automatically.
    expect(fake.analyzeRequests, isEmpty);
  });

  testWidgets('mic disabled when voice consent is missing', (tester) async {
    final fake = FakeServer()
      ..speechStatus = statusJson(recognition: ['as', 'en']);
    final wh = await real(tester, () async {
      final x = await Harness.create(
        server: fake,
        voiceRecorder: FakeRecorder(),
      );
      await x.pairAndOnboard();
      return x;
    });
    addTearDown(wh.dispose);
    await tester.pumpWidget(wh.app());
    await settle(tester);
    await tapVisible(tester, find.text('Talk with the helper'));
    await settle(tester);
    final mic = find.byKey(const ValueKey('mic_button'));
    expect(tester.widget<IconButton>(mic).onPressed, isNull);
    expect(
      find.byTooltip(
        'Talking by voice needs permission from your family first. '
        'Please type or tap a reply.',
      ),
      findsOneWidget,
    );
  });
}
