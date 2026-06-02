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
    state = AuthLoading();
    final result = await _repo.validateSession();
    switch (result) {
      case AuthSuccess(:final data):
        state = AuthAuthenticated(data);
      case AuthFailure():
        state = AuthUnauthenticated();
    }
  }

  /// Called from login screen.
  Future<void> login({required String email, required String password}) async {
    state = AuthLoading();
    final result = await _repo.login(email: email, password: password);
    switch (result) {
      case AuthSuccess(:final data):
        state = AuthAuthenticated(data);
      case AuthFailure(:final message):
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
