import 'package:flutter_dotenv/flutter_dotenv.dart';

/// Centralised environment configuration.
///
/// Priority order:
///   1. Compile-time `--dart-define=API_BASE_URL=…` (baked in at build time)
///   2. `.env` file bundled as an asset (loaded at startup)
///   3. Hard-coded fallback (production Railway URL)
class Env {
  // Compile-time constants — empty string when not set via --dart-define
  static const String _compiledApiUrl =
      String.fromEnvironment('API_BASE_URL');
  static const String _compiledAppEnv =
      String.fromEnvironment('APP_ENV');

  static const String _productionUrl =
      'https://arsocietyapp-production.up.railway.app/api/v1';

  static String get apiBaseUrl {
    if (_compiledApiUrl.isNotEmpty) return _compiledApiUrl;
    return dotenv.env['API_BASE_URL'] ?? _productionUrl;
  }

  static String get appName => dotenv.env['APP_NAME'] ?? 'AR Society';

  static String get appEnv {
    if (_compiledAppEnv.isNotEmpty) return _compiledAppEnv;
    return dotenv.env['APP_ENV'] ?? 'production';
  }

  static bool get isProduction => appEnv == 'production';
}
