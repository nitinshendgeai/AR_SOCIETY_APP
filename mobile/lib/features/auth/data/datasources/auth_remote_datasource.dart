import 'package:flutter/foundation.dart';
import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/auth/data/models/auth_models.dart';

/// Calls FastAPI auth endpoints.
class AuthRemoteDataSource {
  final Dio _dio;

  AuthRemoteDataSource({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  /// POST /auth/login
  Future<TokenModel> login({
    required String email,
    required String password,
  }) async {
    debugPrint('[LOGIN_REQUEST] POST /auth/login  email=$email');
    final response = await _dio.post('/auth/login', data: {
      'email': email,
      'password': password,
    });
    debugPrint('[LOGIN_RESPONSE] status=${response.statusCode}  '
        'keys=${(response.data as Map?)?.keys.toList()}');
    final token = TokenModel.fromJson(response.data as Map<String, dynamic>);
    debugPrint('[ACCESS_TOKEN_RECEIVED] ${token.accessToken.substring(0, 20)}...');
    debugPrint('[REFRESH_TOKEN_RECEIVED] ${token.refreshToken.substring(0, 20)}...');
    return token;
  }

  /// GET /auth/me
  Future<UserModel> getMe() async {
    debugPrint('[USER_PROFILE_FETCH] GET /auth/me');
    final response = await _dio.get('/auth/me');
    debugPrint('[USER_PROFILE_FETCH] status=${response.statusCode}  '
        'data=${response.data}');
    return UserModel.fromJson(response.data as Map<String, dynamic>);
  }

  /// POST /auth/refresh
  Future<TokenModel> refreshTokens(String refreshToken) async {
    final response = await _dio.post('/auth/refresh', data: {
      'refresh_token': refreshToken,
    });
    return TokenModel.fromJson(response.data as Map<String, dynamic>);
  }

  /// POST /auth/change-password
  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    await _dio.post('/auth/change-password', data: {
      'current_password': currentPassword,
      'new_password': newPassword,
    });
  }
}
