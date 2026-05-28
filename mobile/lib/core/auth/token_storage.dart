import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:ar_society_app/core/config/constants.dart';

/// Manages JWT token storage using device secure storage.
/// Tokens persist across app restarts.
class TokenStorage {
  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );

  // ── Write ──────────────────────────────────────────────────────────────────

  static Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await Future.wait([
      _storage.write(key: AppConstants.accessTokenKey, value: accessToken),
      _storage.write(key: AppConstants.refreshTokenKey, value: refreshToken),
    ]);
  }

  static Future<void> saveAccessToken(String token) async {
    await _storage.write(key: AppConstants.accessTokenKey, value: token);
  }

  // ── Read ───────────────────────────────────────────────────────────────────

  static Future<String?> getAccessToken() async {
    return _storage.read(key: AppConstants.accessTokenKey);
  }

  static Future<String?> getRefreshToken() async {
    return _storage.read(key: AppConstants.refreshTokenKey);
  }

  static Future<bool> hasValidTokens() async {
    final access = await getAccessToken();
    final refresh = await getRefreshToken();
    return access != null && refresh != null;
  }

  // ── Clear ──────────────────────────────────────────────────────────────────

  static Future<void> clearTokens() async {
    await Future.wait([
      _storage.delete(key: AppConstants.accessTokenKey),
      _storage.delete(key: AppConstants.refreshTokenKey),
    ]);
  }
}
