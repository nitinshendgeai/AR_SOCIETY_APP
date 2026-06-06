import 'package:flutter/foundation.dart' show kIsWeb, debugPrint;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ar_society_app/core/config/constants.dart';

/// Manages JWT token storage.
///
/// On native (Android / iOS): flutter_secure_storage (encrypted keychain/keystore).
/// On web: SharedPreferences (backed by localStorage). The browser's same-origin
/// policy and HTTPS provide the equivalent security boundary; Web Crypto AES-GCM
/// (used by flutter_secure_storage's web backend) throws OperationError on some
/// Chrome builds when running on localhost, so we avoid it on the web target.
class TokenStorage {
  static const _secure = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );

  // ── Write ──────────────────────────────────────────────────────────────────

  static Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    if (kIsWeb) {
      final prefs = await SharedPreferences.getInstance();
      await Future.wait([
        prefs.setString(AppConstants.accessTokenKey, accessToken),
        prefs.setString(AppConstants.refreshTokenKey, refreshToken),
      ]);
      debugPrint('[TOKEN_SAVED] web: written to SharedPreferences');
    } else {
      await Future.wait([
        _secure.write(key: AppConstants.accessTokenKey, value: accessToken),
        _secure.write(key: AppConstants.refreshTokenKey, value: refreshToken),
      ]);
      debugPrint('[TOKEN_SAVED] native: written to FlutterSecureStorage');
    }
  }

  static Future<void> saveAccessToken(String token) async {
    if (kIsWeb) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(AppConstants.accessTokenKey, token);
    } else {
      await _secure.write(key: AppConstants.accessTokenKey, value: token);
    }
  }

  // ── Read ───────────────────────────────────────────────────────────────────

  static Future<String?> getAccessToken() async {
    if (kIsWeb) {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getString(AppConstants.accessTokenKey);
    }
    return _secure.read(key: AppConstants.accessTokenKey);
  }

  static Future<String?> getRefreshToken() async {
    if (kIsWeb) {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getString(AppConstants.refreshTokenKey);
    }
    return _secure.read(key: AppConstants.refreshTokenKey);
  }

  static Future<bool> hasValidTokens() async {
    final access  = await getAccessToken();
    final refresh = await getRefreshToken();
    return access != null && refresh != null;
  }

  // ── Clear ──────────────────────────────────────────────────────────────────

  static Future<void> clearTokens() async {
    if (kIsWeb) {
      final prefs = await SharedPreferences.getInstance();
      await Future.wait([
        prefs.remove(AppConstants.accessTokenKey),
        prefs.remove(AppConstants.refreshTokenKey),
      ]);
    } else {
      await Future.wait([
        _secure.delete(key: AppConstants.accessTokenKey),
        _secure.delete(key: AppConstants.refreshTokenKey),
      ]);
    }
  }
}
