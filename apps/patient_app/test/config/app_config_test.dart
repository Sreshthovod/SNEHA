import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/config/app_config.dart';

void main() {
  group('AppConfig.parse', () {
    test('accepts the emulator default and strips trailing slashes', () {
      final config = AppConfig.parse(
        apiBaseUrl: 'http://10.0.2.2:8000/',
        environment: 'development',
      );
      expect(config.apiBaseUrl.toString(), 'http://10.0.2.2:8000');
      expect(config.isProduction, isFalse);
    });

    test('rejects relative or non-http URLs', () {
      for (final bad in ['10.0.2.2:8000', '/api', 'ftp://host', '']) {
        expect(
          () => AppConfig.parse(apiBaseUrl: bad, environment: 'development'),
          throwsArgumentError,
          reason: bad,
        );
      }
    });

    test('requires https in production', () {
      expect(
        () => AppConfig.parse(
          apiBaseUrl: 'http://api.example.test',
          environment: 'production',
        ),
        throwsA(
          isA<ArgumentError>().having(
            (e) => e.message,
            'message',
            contains('https'),
          ),
        ),
      );
      expect(
        AppConfig.parse(
          apiBaseUrl: 'https://api.example.test',
          environment: 'production',
        ).isProduction,
        isTrue,
      );
    });

    test('rejects unknown environments', () {
      expect(
        () => AppConfig.parse(apiBaseUrl: 'http://x.test', environment: 'prod'),
        throwsArgumentError,
      );
    });
  });
}
