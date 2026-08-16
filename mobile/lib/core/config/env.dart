import 'package:flutter_dotenv/flutter_dotenv.dart';

/// Centralised environment configuration.
///
/// Priority order:
///   1. Compile-time `--dart-define=KEY=value` (baked in at build time)
///   2. `.env` file bundled as an asset (loaded at startup, may be empty)
///   3. Hard-coded production fallback
///
/// All dotenv.env accesses are guarded with try/catch because flutter_dotenv
/// 5.x throws StateError when env is accessed before a successful load().
/// In production, the .env asset is intentionally empty and load() silently
/// fails, so every access must have a fallback.
class Env {
  static const String _compiledApiUrl =
      String.fromEnvironment('API_BASE_URL');
  static const String _compiledAppEnv =
      String.fromEnvironment('APP_ENV');

  static const String _productionUrl =
      'https://arsocietyapp-production.up.railway.app/api/v1';

  static String _dotenvGet(String key) {
    try {
      return dotenv.env[key] ?? '';
    } catch (_) {
      return '';
    }
  }

  static String get apiBaseUrl {
    if (_compiledApiUrl.isNotEmpty) return _compiledApiUrl;
    final v = _dotenvGet('API_BASE_URL');
    return v.isNotEmpty ? v : _productionUrl;
  }

  static String get appName {
    final v = _dotenvGet('APP_NAME');
    return v.isNotEmpty ? v : 'AR Society';
  }

  static String get appEnv {
    if (_compiledAppEnv.isNotEmpty) return _compiledAppEnv;
    final v = _dotenvGet('APP_ENV');
    return v.isNotEmpty ? v : 'production';
  }

  static bool get isProduction => appEnv == 'production';
}
