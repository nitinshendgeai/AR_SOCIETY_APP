import 'package:shared_preferences/shared_preferences.dart';

/// Per-device biometric app-unlock preference. Not a secret — just a UX
/// toggle — so plain SharedPreferences is enough (unlike TokenStorage,
/// which holds the actual JWTs in encrypted storage).
class BiometricPreference {
  static const _enabledKey = 'biometric_unlock_enabled';
  static const _promptPendingKey = 'biometric_prompt_pending';

  /// Whether the device should be gated by a biometric prompt on cold-start
  /// session restore (see AuthNotifier.checkSession()).
  static Future<bool> isEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_enabledKey) ?? false;
  }

  static Future<void> setEnabled(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_enabledKey, value);
  }

  /// Set right after a forced password change succeeds, so the next screen
  /// the user lands on can offer to enable biometric unlock exactly once.
  static Future<void> setPromptPending(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_promptPendingKey, value);
  }

  /// Reads and immediately clears the pending flag so the offer is only
  /// ever shown once, however many times the dashboard shell rebuilds.
  static Future<bool> consumePromptPending() async {
    final prefs = await SharedPreferences.getInstance();
    final pending = prefs.getBool(_promptPendingKey) ?? false;
    if (pending) await prefs.setBool(_promptPendingKey, false);
    return pending;
  }
}
