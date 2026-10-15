import 'dart:math';

import 'package:flutter/widgets.dart';

import 'app_controller.dart';
import 'core/connectivity/server_status.dart';
import 'data/api/api_client.dart';
import 'data/local/local_database.dart';
import 'data/repositories/activity_recorder.dart';
import 'data/repositories/clock.dart';
import 'data/repositories/content_repository.dart';
import 'data/repositories/conversation_repository.dart';
import 'data/repositories/media_cache.dart';
import 'data/repositories/progress_repository.dart';
import 'data/repositories/profile_repository.dart';
import 'data/repositories/settings_repository.dart';
import 'data/repositories/sync_service.dart';
import 'data/repositories/token_store.dart';
import 'personalization/recommendation_source.dart';
import 'speech/speech.dart';
import 'speech/voice_input.dart';

/// Composition root. Everything the UI needs, created once at startup (or
/// with fakes in tests). Widgets never construct repositories themselves.
class AppServices {
  AppServices({
    required this.local,
    required this.api,
    required TokenStore tokens,
    required MediaCache media,
    this.clock = systemClock,
    Random? random,
    this.speechOutput = const UnavailableSpeechOutput(),
    VoiceRecorder? voiceRecorder,
    RetryPolicy retry = const RetryPolicy(),
  }) : random = random ?? Random() {
    profiles = ProfileRepository(local, tokens, media, clock: clock);
    settings = SettingsRepository(local);
    content = ContentRepository(local);
    recorder = ActivityRecorder(local, clock: clock);
    sync = SyncService(
      local: local,
      api: api,
      profiles: profiles,
      media: media,
      clock: clock,
      retry: retry,
    );
    facts = LocalFacts(local, clock: clock);
    progress = ProgressRepository(facts);
    final onDevice = LocalRecommendationSource(facts, profiles);
    recommendations = serverRecommendationsEnabled
        ? ServerFirstRecommendationSource(api, profiles, onDevice, facts)
        : onDevice;
    conversation = ConversationRepository(api, profiles, facts);
    // Voice input needs a microphone recorder AND server recognition; without
    // a recorder it is unavailable (never faked).
    speechInput = voiceRecorder == null
        ? const UnavailableSpeechInput()
        : ServerSpeechInput(api, profiles, voiceRecorder);
    serverStatus = ServerStatusController(api);
    controller = AppController(this);
  }

  final LocalDatabase local;
  final SnehaApiClient api;
  final Clock clock;
  final Random random;
  final SpeechOutput speechOutput;
  late final SpeechInput speechInput;

  late final ProfileRepository profiles;
  late final SettingsRepository settings;
  late final ContentRepository content;
  late final ActivityRecorder recorder;
  late final SyncService sync;
  late final LocalFacts facts;
  late final ProgressRepository progress;
  late final RecommendationSource recommendations;
  late final ConversationRepository conversation;
  late final ServerStatusController serverStatus;
  late final AppController controller;
}

/// Gives widgets access to [AppServices] and rebuilds them when the
/// [AppController] changes (settings, active profile).
class AppScope extends InheritedNotifier<AppController> {
  AppScope({super.key, required this.services, required super.child})
    : super(notifier: services.controller);

  final AppServices services;

  static AppServices of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<AppScope>()!.services;
}
