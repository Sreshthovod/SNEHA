import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import 'app.dart';
import 'app_services.dart';
import 'config/app_config.dart';
import 'data/api/api_client.dart';
import 'data/local/local_database.dart';
import 'data/repositories/media_cache.dart';
import 'data/repositories/token_store.dart';
import 'speech/speech.dart';
import 'speech/voice_input.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  try {
    final config = AppConfig.fromEnvironment();
    // Local storage opens first: the app must work without the server.
    final local = await LocalDatabase.open();
    final docs = await getApplicationDocumentsDirectory();
    final services = AppServices(
      local: local,
      api: SnehaApiClient(baseUrl: config.apiBaseUrl),
      tokens: SecureTokenStore(),
      media: MediaCache(Directory(p.join(docs.path, 'memory_photos'))),
      speechOutput: SystemSpeechOutput(),
      voiceRecorder: RecordPackageRecorder(),
    );
    await services.controller.load();
    runApp(SnehaApp(services: services));
  } on Object catch (error) {
    debugPrint('SNEHA startup failed: $error');
    runApp(StartupErrorApp(message: error.toString()));
  }
}
