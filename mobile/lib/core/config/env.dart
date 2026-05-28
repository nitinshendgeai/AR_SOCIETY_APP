import 'package:flutter_dotenv/flutter_dotenv.dart';

/// Centralised environment configuration.
/// Values read from .env file at startup.
class Env {
  static String get apiBaseUrl =>
      dotenv.env['API_BASE_URL'] ??
      'https://arsocietyapp-production.up.railway.app/api/v1';
  static String get appName => dotenv.env['APP_NAME'] ?? 'AR Society';
  static String get appEnv => dotenv.env['APP_ENV'] ?? 'development';
  static bool get isProduction => appEnv == 'production';
}
