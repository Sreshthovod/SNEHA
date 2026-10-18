import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';

/// Why reading aloud is or is not possible. Shown to the user honestly:
/// the app never pretends audio played.
enum SpeechAvailability {
  available,

  /// The phone's speech engine has no voice for this language.
  languageUnsupported,

  /// No speech engine on this phone (or it failed to start).
  engineUnavailable,
}

/// Text-to-speech. Text always stays on screen; this is an addition, never a
/// replacement for reading and touch controls.
abstract interface class SpeechOutput {
  Future<SpeechAvailability> availability(String languageCode);

  /// Returns true only if the engine accepted the text for speaking.
  Future<bool> speak(String text, String languageCode);

  /// Silence the voice at once (pause, stop, "I'm tired", leaving a screen).
  Future<void> stop();

  /// True while the voice is speaking, so the person can be offered "Stop".
  ValueListenable<bool> get speaking;
}

/// Shared "never speaking" value for outputs that cannot speak.
final ValueListenable<bool> notSpeaking = ValueNotifier<bool>(false);

/// Speech-to-text. See voice_input.dart for the server-backed implementation.
///
/// Implementations NEVER invent a transcription: when recognition is not
/// possible they say why (a string-table key) and the person types or taps.
abstract interface class SpeechInput {
  /// Whether voice can be used right now for this person, and if not, why.
  Future<VoiceAvailability> availability(SpeechContext context);

  /// Start listening. Returns a reason key if it could not start.
  Future<String?> start();

  /// Stop listening and turn the recording into text for the person to
  /// check. Never sends anything on its own.
  Future<VoiceResult> stop(SpeechContext context);

  /// Stop listening and throw the recording away.
  Future<void> cancel();
}

/// Who is speaking, in which language (SNEHA language code).
class SpeechContext {
  const SpeechContext({
    required this.patientId,
    required this.language,
    required this.consents,
  });

  final String patientId;
  final String language;

  /// Cached consent summary for the profile (may be stale or missing).
  final Map<String, String?>? consents;

  bool get voiceConsent => consents?['voice_processing'] == 'granted';
}

class VoiceAvailability {
  const VoiceAvailability.available() : reasonKey = null;
  const VoiceAvailability.unavailable(String this.reasonKey);

  /// String-table key explaining why voice cannot be used, or null.
  final String? reasonKey;
  bool get isAvailable => reasonKey == null;
}

class VoiceResult {
  const VoiceResult.text(String this.text) : errorKey = null;
  const VoiceResult.error(String this.errorKey) : text = null;

  final String? text;
  final String? errorKey;
}

/// Used when no recorder / server recognition is wired (and in tests). Never
/// returns a transcription, so nothing is ever invented.
class UnavailableSpeechInput implements SpeechInput {
  const UnavailableSpeechInput();

  @override
  Future<VoiceAvailability> availability(SpeechContext context) async =>
      const VoiceAvailability.unavailable('speech_input_unavailable');

  @override
  Future<String?> start() async => 'speech_input_unavailable';

  @override
  Future<VoiceResult> stop(SpeechContext context) async =>
      const VoiceResult.error('speech_input_unavailable');

  @override
  Future<void> cancel() async {}
}

/// No speech at all (tests, or phones without a speech engine).
class UnavailableSpeechOutput implements SpeechOutput {
  const UnavailableSpeechOutput();

  @override
  Future<SpeechAvailability> availability(String languageCode) async =>
      SpeechAvailability.engineUnavailable;

  @override
  Future<bool> speak(String text, String languageCode) async => false;

  @override
  Future<void> stop() async {}

  @override
  ValueListenable<bool> get speaking => notSpeaking;
}

/// BCP-47 locales to try on Android for each SNEHA language code. Several NE
/// languages usually have no system voice; they then report
/// [SpeechAvailability.languageUnsupported].
const ttsLocales = <String, List<String>>{
  'as': ['as-IN'],
  'bn': ['bn-IN', 'bn-BD'],
  'brx': ['brx-IN'],
  'en': ['en-IN', 'en-GB', 'en-US'],
  'grt': ['grt-IN'],
  'hi': ['hi-IN'],
  'kha': ['kha-IN'],
  'mni': ['mni-IN'],
  'lus': ['lus-IN'],
  'nag': ['nag-IN'],
  'ne': ['ne-NP', 'ne-IN'],
};

/// Android system text-to-speech via flutter_tts (on-device, no network
/// needed once the voice is installed on the phone).
class SystemSpeechOutput implements SpeechOutput {
  SystemSpeechOutput([FlutterTts? tts]) : _tts = tts ?? FlutterTts() {
    // The engine reports when speech starts and ends (finished, stopped or
    // failed), so the app never shows "Stop reading" when nothing is playing.
    _tts.setStartHandler(() => _speaking.value = true);
    _tts.setCompletionHandler(() => _speaking.value = false);
    _tts.setCancelHandler(() => _speaking.value = false);
    _tts.setErrorHandler((_) => _speaking.value = false);
  }

  final FlutterTts _tts;
  final ValueNotifier<bool> _speaking = ValueNotifier<bool>(false);
  final Map<String, String?> _resolved = {};

  @override
  ValueListenable<bool> get speaking => _speaking;

  Future<String?> _locale(String languageCode) async {
    if (_resolved.containsKey(languageCode)) return _resolved[languageCode];
    String? found;
    for (final locale in ttsLocales[languageCode] ?? const <String>[]) {
      final ok = await _tts.isLanguageAvailable(locale);
      if (ok == true || ok == 1) {
        found = locale;
        break;
      }
    }
    return _resolved[languageCode] = found;
  }

  @override
  Future<SpeechAvailability> availability(String languageCode) async {
    try {
      return await _locale(languageCode) == null
          ? SpeechAvailability.languageUnsupported
          : SpeechAvailability.available;
    } on Object catch (e) {
      debugPrint('TTS unavailable: $e');
      return SpeechAvailability.engineUnavailable;
    }
  }

  @override
  Future<bool> speak(String text, String languageCode) async {
    try {
      final locale = await _locale(languageCode);
      if (locale == null) return false;
      await _tts.setLanguage(locale);
      await _tts.setSpeechRate(0.4); // slower, clearer speech
      final result = await _tts.speak(text);
      final ok = result == 1 || result == true;
      if (ok) _speaking.value = true;
      return ok;
    } on Object catch (e) {
      debugPrint('TTS failed: $e');
      return false;
    }
  }

  @override
  Future<void> stop() async {
    _speaking.value = false;
    try {
      await _tts.stop();
    } on Object catch (_) {}
  }
}
