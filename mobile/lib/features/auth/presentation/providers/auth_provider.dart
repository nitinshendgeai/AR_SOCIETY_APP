import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/auth/data/repositories/auth_repository.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';

// ── Auth State ────────────────────────────────────────────────────────────────

sealed class AuthState {}

class AuthInitial extends AuthState {}

class AuthLoading extends AuthState {}

class AuthAuthenticated extends AuthState {
  final UserEntity user;
  AuthAuthenticated(this.user);
}

class AuthUnauthenticated extends AuthState {}

class AuthError extends AuthState {
  final String message;
  AuthError(this.message);
}

// ── Repository Provider ───────────────────────────────────────────────────────

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository();
});

// ── Auth Notifier ─────────────────────────────────────────────────────────────

class AuthNotifier extends StateNotifier<AuthState> {
  final AuthRepository _repo;

  AuthNotifier(this._repo) : super(AuthInitial());

  /// Called on app startup — validates existing session.
  Future<void> checkSession() async {
    debugPrint('[AUTH_STATE] checkSession → AuthLoading');
    state = AuthLoading();
    final result = await _repo.validateSession();
    switch (result) {
      case AuthSuccess(:final data):
        debugPrint('[AUTH_STATE] checkSession → AuthAuthenticated(${data.email})');
        state = AuthAuthenticated(data);
      case AuthFailure(:final message):
        debugPrint('[AUTH_STATE] checkSession → AuthUnauthenticated ($message)');
        state = AuthUnauthenticated();
    }
  }

  /// Called from login screen.
  Future<void> login({required String email, required String password}) async {
    debugPrint('[AUTH_STATE] login($email) → AuthLoading');
    state = AuthLoading();
    final result = await _repo.login(email: email, password: password);
    switch (result) {
      case AuthSuccess(:final data):
        debugPrint('[AUTH_STATE] login → AuthAuthenticated(${data.email}) '
            'roles=${data.roles} mustChange=${data.mustChangePassword}');
        state = AuthAuthenticated(data);
      case AuthFailure(:final message):
        debugPrint('[AUTH_STATE] login → AuthError($message)');
        state = AuthError(message);
    }
  }

  /// Change password. On success, clears the mustChangePassword flag on the user.
  Future<AuthResult<void>> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    final result = await _repo.changePassword(
      currentPassword: currentPassword,
      newPassword: newPassword,
    );
    if (result is AuthSuccess && state is AuthAuthenticated) {
      final user = (state as AuthAuthenticated).user;
      state = AuthAuthenticated(user.copyWith(mustChangePassword: false));
    }
    return result;
  }

  /// Accept terms of service. Does not update local state — call refreshUser() after wizard completes.
  Future<AuthResult<void>> acceptTerms() async {
    return await _repo.acceptTerms();
  }

  /// Re-fetch user from /auth/me and update local state.
  Future<void> refreshUser() async {
    final result = await _repo.validateSession();
    if (result is AuthSuccess<UserEntity>) {
      state = AuthAuthenticated(result.data);
    }
    // On failure, keep existing auth state — don't log the user out.
  }

  /// Logout — clears tokens and redirects to login.
  Future<void> logout() async {
    await _repo.logout();
    state = AuthUnauthenticated();
  }

  /// Clear error state (e.g., when user dismisses error).
  void clearError() {
    if (state is AuthError) state = AuthUnauthenticated();
  }

  /// Convenience getter for current user.
  UserEntity? get currentUser {
    final s = state;
    return s is AuthAuthenticated ? s.user : null;
  }
}

// ── Provider ──────────────────────────────────────────────────────────────────

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  final repo = ref.watch(authRepositoryProvider);
  return AuthNotifier(repo);
});

/// Convenience provider — returns current user or null.
final currentUserProvider = Provider<UserEntity?>((ref) {
  final state = ref.watch(authProvider);
  return state is AuthAuthenticated ? state.user : null;
});

/// Convenience provider — true when authenticated.
final isAuthenticatedProvider = Provider<bool>((ref) {
  return ref.watch(authProvider) is AuthAuthenticated;
});
