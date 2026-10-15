/// Build-time configuration, supplied with `--dart-define` (never secrets).
///
/// Example:
///   flutter run --dart-define=SNEHA_API_BASE_URL=http://10.0.2.2:8000
///
/// `10.0.2.2` is how the Android emulator reaches the host machine's localhost.
class AppConfig {
  const AppConfig({required this.apiBaseUrl, required this.environment});

  static const String defaultApiBaseUrl = 'http://10.0.2.2:8000';

  /// Base URL of the SNEHA backend, without a trailing slash.
  final Uri apiBaseUrl;

  /// `development`, `staging` or `production`.
  final String environment;

  bool get isProduction => environment == 'production';

  factory AppConfig.fromEnvironment() => AppConfig.parse(
    apiBaseUrl: const String.fromEnvironment(
      'SNEHA_API_BASE_URL',
      defaultValue: defaultApiBaseUrl,
    ),
    environment: const String.fromEnvironment(
      'SNEHA_ENV',
      defaultValue: 'development',
    ),
  );

  factory AppConfig.parse({
    required String apiBaseUrl,
    required String environment,
  }) {
    const environments = {'development', 'staging', 'production'};
    if (!environments.contains(environment)) {
      throw ArgumentError.value(
        environment,
        'SNEHA_ENV',
        'must be one of ${environments.join(', ')}',
      );
    }

    final trimmed = apiBaseUrl.trim().replaceAll(RegExp(r'/+$'), '');
    final uri = Uri.tryParse(trimmed);
    if (uri == null ||
        !uri.hasAuthority ||
        !(uri.scheme == 'http' || uri.scheme == 'https')) {
      throw ArgumentError.value(
        apiBaseUrl,
        'SNEHA_API_BASE_URL',
        'must be an absolute http(s) URL such as $defaultApiBaseUrl',
      );
    }
    if (environment == 'production' && uri.scheme != 'https') {
      throw ArgumentError.value(
        apiBaseUrl,
        'SNEHA_API_BASE_URL',
        'must use https in production',
      );
    }
    return AppConfig(apiBaseUrl: uri, environment: environment);
  }
}
