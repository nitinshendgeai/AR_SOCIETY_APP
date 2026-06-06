import 'package:flutter/foundation.dart';
import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/auth/token_storage.dart';
import 'package:ar_society_app/features/auth/data/datasources/auth_remote_datasource.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';

sealed class AuthResult<T> {}

class AuthSuccess<T> extends AuthResult<T> {
  final T data;
  AuthSuccess(this.data);
}

class AuthFailure<T> extends AuthResult<T> {
  final String message;
  AuthFailure(this.message);
}

/// Auth repository: coordinates remote API + local token storage.
class AuthRepository {
  final AuthRemoteDataSource _remote;

  AuthRepository({AuthRemoteDataSource? remote})
      : _remote = remote ?? AuthRemoteDataSource();

  /// Login: call API, store tokens, return user entity.
  Future<AuthResult<UserEntity>> login({
    required String email,
    required String password,
  }) async {
    try {
      final tokens = await _remote.login(email: email, password: password);
      await TokenStorage.saveTokens(
        accessToken: tokens.accessToken,
        refreshToken: tokens.refreshToken,
      );
      debugPrint('[TOKEN_SAVED] access and refresh tokens written to storage');
      // Verify the token was actually stored
      final stored = await TokenStorage.getAccessToken();
      debugPrint('[TOKEN_SAVED] read-back: ${stored != null ? "OK (${stored.substring(0, 20)}...)" : "NULL — storage failed!"}');
      final userModel = await _remote.getMe();
      final entity = userModel.toEntity();
      debugPrint('[AUTH_STATE_UPDATED] user=${entity.email} '
          'roles=${entity.roles} mustChangePassword=${entity.mustChangePassword}');
      return AuthSuccess(entity);
    } on DioException catch (e) {
      debugPrint('[LOGIN_ERROR] DioException: ${e.response?.statusCode} '
          '${e.response?.data} ${e.message}');
      return AuthFailure(parseApiError(e));
    } catch (e) {
      debugPrint('[LOGIN_ERROR] Unexpected: $e');
      return AuthFailure('Unexpected error: $e');
    }
  }

  /// Validate existing session by fetching /auth/me.
  Future<AuthResult<UserEntity>> validateSession() async {
    try {
      final hasTokens = await TokenStorage.hasValidTokens();
      if (!hasTokens) return AuthFailure('No session');
      final userModel = await _remote.getMe();
      return AuthSuccess(userModel.toEntity());
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        await TokenStorage.clearTokens();
        return AuthFailure('Session expired');
      }
      return AuthFailure(parseApiError(e));
    } catch (e) {
      return AuthFailure('Session validation failed');
    }
  }

  /// Change password for the currently authenticated user.
  Future<AuthResult<void>> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    try {
      await _remote.changePassword(
        currentPassword: currentPassword,
        newPassword: newPassword,
      );
      return AuthSuccess(null);
    } on DioException catch (e) {
      return AuthFailure(parseApiError(e));
    } catch (e) {
      return AuthFailure('Unexpected error: $e');
    }
  }

  /// Logout: clear all stored tokens.
  Future<void> logout() async {
    await TokenStorage.clearTokens();
  }
}
