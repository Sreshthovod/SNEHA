import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:record/record.dart';

import '../data/api/api_client.dart';
import '../data/repositories/profile_repository.dart';
import 'speech.dart';

/// Captures 16 kHz mono 16-bit PCM WAV (what POST /speech/transcribe accepts).
abstract interface class VoiceRecorder {
  Future<bool> hasPermission();
  Future<void> start();

  /// The WAV bytes, or null if nothing was recorded.
  Future<Uint8List?> stop();
  Future<void> cancel();
}

/// Android microphone via the `record` package. Audio is kept in a temporary
/// file only until it has been sent, then deleted.
class RecordPackageRecorder implements VoiceRecorder {
  RecordPackageRecorder({AudioRecorder? recorder, Directory? tempDir})
    : _recorder = recorder ?? AudioRecorder(),
      _tempDir = tempDir ?? Directory.systemTemp;

  final AudioRecorder _recorder;
  final Directory _tempDir;
  String? _path;

  static const config = RecordConfig(
    encoder: AudioEncoder.wav,
    sampleRate: 16000,
    numChannels: 1,
  );

  @override
  Future<bool> hasPermission() => _recorder.hasPermission();

  @override
  Future<void> start() async {
    _path = p.join(
      _tempDir.path,
      'sneha_voice_${DateTime.now().microsecondsSinceEpoch}.wav',
    );
    await _recorder.start(config, path: _path!);
  }

  @override
  Future<Uint8List?> stop() async {
    final path = await _recorder.stop() ?? _path;
    _path = null;
    if (path == null) return null;
    final file = File(path);
    if (!file.existsSync()) return null;
    try {
      return await file.readAsBytes();
    } finally {
      file.deleteSync();
    }
  }

  @override
  Future<void> cancel() async {
    await _recorder.cancel();
    final path = _path;
    _path = null;
    if (path != null && File(path).existsSync()) File(path).deleteSync();
  }
}

/// Speech-to-text through the SNEHA server (POST /speech/transcribe).
///
/// Available only when ALL hold: the server reports recognition ready for the
/// language (GET /speech/status), voice-processing consent is granted, and
/// the microphone can be used. Otherwise the reason is shown and touch/typing
/// stays the way to answer. The transcript only fills the text box.
class ServerSpeechInput implements SpeechInput {
  ServerSpeechInput(this._api, this._profiles, this._recorder);

  final SnehaApiClient _api;
  final ProfileRepository _profiles;
  final VoiceRecorder _recorder;

  @override
  Future<VoiceAvailability> availability(SpeechContext context) async {
    if (!context.voiceConsent) {
      return const VoiceAvailability.unavailable('speech_no_consent');
    }
    final token = await _profiles.token(context.patientId);
    if (token == null) {
      return const VoiceAvailability.unavailable('speech_input_unavailable');
    }
    try {
      final status = await _api.speechStatus(token);
      if (!status.recognition.contains(context.language)) {
        return const VoiceAvailability.unavailable('speech_lang_no_asr');
      }
    } on ApiException catch (e) {
      return VoiceAvailability.unavailable(
        e.isNetwork ? 'speech_offline' : 'speech_input_unavailable',
      );
    }
    return const VoiceAvailability.available();
  }

  @override
  Future<String?> start() async {
    try {
      if (!await _recorder.hasPermission()) return 'speech_no_mic_permission';
      await _recorder.start();
      return null;
    } on Object catch (e) {
      debugPrint('Voice: could not start recording ($e)');
      return 'speech_failed';
    }
  }

  @override
  Future<VoiceResult> stop(SpeechContext context) async {
    final Uint8List? wav;
    try {
      wav = await _recorder.stop();
    } on Object catch (e) {
      debugPrint('Voice: could not stop recording ($e)');
      return const VoiceResult.error('speech_failed');
    }
    if (wav == null || wav.isEmpty) {
      return const VoiceResult.error('speech_bad_audio');
    }
    final token = await _profiles.token(context.patientId);
    if (token == null) return const VoiceResult.error('speech_failed');
    try {
      final result = await _api.transcribe(
        token,
        patientId: context.patientId,
        language: context.language,
        wav: wav,
      );
      if (result.noSpeech || result.text.trim().isEmpty) {
        return const VoiceResult.error('speech_nothing_heard');
      }
      return VoiceResult.text(result.text.trim());
    } on ApiException catch (e) {
      return VoiceResult.error(errorKeyFor(e));
    }
  }

  @override
  Future<void> cancel() => _recorder.cancel();

  /// Server error → plain message key.
  static String errorKeyFor(ApiException e) {
    if (e.isNetwork) return 'speech_offline';
    return switch (e.code) {
      'model_missing' || 'speech_unavailable' => 'speech_server_missing',
      'language_unsupported' => 'speech_lang_no_asr',
      'invalid_audio' => 'speech_bad_audio',
      'consent_required' => 'speech_no_consent',
      'file_too_large' || 'content_too_large' => 'speech_bad_audio',
      _ => 'speech_failed',
    };
  }
}
