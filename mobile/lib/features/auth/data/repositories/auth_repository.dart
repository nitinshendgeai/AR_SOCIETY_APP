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
      final userModel = await _remote.getMe();
      return AuthSuccess(userModel.toEntity());
    } on DioException catch (e) {
      return AuthFailure(parseApiError(e));
    } catch (e) {
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

  /// Logout: clear all stored tokens.
  Future<void> logout() async {
    await TokenStorage.clearTokens();
  }
}
