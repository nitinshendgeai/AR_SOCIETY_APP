import 'package:flutter/foundation.dart' show kIsWeb, debugPrint;
import 'package:local_auth/local_auth.dart';

/// Thin wrapper around local_auth. Biometric unlock is Android/iOS only —
/// guarded off on web, where local_auth has no meaningful support and this
/// app also runs (see build/web testing elsewhere in this codebase).
class BiometricService {
  final _auth = LocalAuthentication();

  Future<bool> isAvailable() async {
    if (kIsWeb) return false;
    try {
      final supported = await _auth.isDeviceSupported();
      final canCheck = await _auth.canCheckBiometrics;
      return supported && canCheck;
    } catch (e) {
      debugPrint('[BIOMETRIC] isAvailable check failed: $e');
      return false;
    }
  }

  /// Prompts for fingerprint/face (falling back to device PIN/pattern if
  /// biometrics aren't enrolled — biometricOnly is deliberately false so a
  /// user isn't locked out entirely just because they haven't enrolled a
  /// fingerprint). Returns false on any failure or cancellation rather than
  /// throwing, since callers treat "not unlocked" as the only signal that
  /// matters.
  Future<bool> authenticate(String reason) async {
    if (kIsWeb) return false;
    try {
      return await _auth.authenticate(
        localizedReason: reason,
        options: const AuthenticationOptions(
          biometricOnly: false,
          stickyAuth: true,
        ),
      );
    } catch (e) {
      debugPrint('[BIOMETRIC] authenticate failed: $e');
      return false;
    }
  }
}
