import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/auth/biometric_service.dart';

final biometricServiceProvider = Provider<BiometricService>((_) => BiometricService());

/// True while a cold-start-restored session is waiting on biometric
/// re-confirmation. Set by AuthNotifier.checkSession() (never by an
/// interactive login() — the user just typed their password, re-confirming
/// immediately would be redundant); cleared once the user passes the
/// biometric prompt on BiometricLockScreen, or logs out instead.
class BiometricLockNotifier extends StateNotifier<bool> {
  BiometricLockNotifier() : super(false);
  void lock() => state = true;
  void unlock() => state = false;
}

final biometricLockProvider =
    StateNotifierProvider<BiometricLockNotifier, bool>((_) => BiometricLockNotifier());
