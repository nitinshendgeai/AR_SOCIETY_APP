import 'package:flutter/foundation.dart';
import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/auth/data/models/auth_models.dart';
import 'package:ar_society_app/features/auth/domain/entities/device_session.dart';
import 'package:ar_society_app/features/auth/domain/entities/society_choice.dart';

/// Calls FastAPI auth endpoints.
class AuthRemoteDataSource {
  final Dio _dio;

  AuthRemoteDataSource({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  /// POST /auth/login — either the tokens, or (when this login belongs to several societies) the societies to
  /// choose from; send the same credentials again with [societyId].
  Future<({TokenModel? tokens, List<SocietyChoice>? choices})> login({
    required String email,
    required String password,
    String? societyId,
  }) async {
    debugPrint('[LOGIN_REQUEST] POST /auth/login  email=$email');
    final response = await _dio.post('/auth/login', data: {
      'email': email,
      'password': password,
      if (societyId != null) 'society_id': societyId,
    });
    debugPrint('[LOGIN_RESPONSE] status=${response.statusCode}  '
        'keys=${(response.data as Map?)?.keys.toList()}');
    final data = response.data as Map<String, dynamic>;
    if (data['requires_society_choice'] == true) {
      return (
        tokens: null,
        choices: (data['choices'] as List<dynamic>)
            .map((e) => SocietyChoice.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
    }
    return (tokens: TokenModel.fromJson(data), choices: null);
  }

  /// POST /auth/switch-society — move to this person's login in another society, no password needed.
  Future<TokenModel> switchSociety(String societyId) async {
    final response = await _dio.post('/auth/switch-society', data: {'society_id': societyId});
    return TokenModel.fromJson(response.data as Map<String, dynamic>);
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

  /// POST /auth/logout — ends this device's session on the server.
  Future<void> logout() => _dio.post('/auth/logout',
      options: Options(sendTimeout: const Duration(seconds: 4), receiveTimeout: const Duration(seconds: 4)));

  /// GET /auth/sessions — the devices signed in to this account.
  Future<List<DeviceSession>> listSessions() async {
    final r = await _dio.get('/auth/sessions');
    return (r.data as List).map((e) => DeviceSession.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// DELETE /auth/sessions/{id}
  Future<void> signOutDevice(String id) => _dio.delete('/auth/sessions/$id');

  /// POST /auth/sessions/revoke-others
  Future<void> signOutOtherDevices() => _dio.post('/auth/sessions/revoke-others');

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

  /// POST /auth/accept-terms
  Future<void> acceptTerms() async {
    await _dio.post('/auth/accept-terms', data: {'terms_accepted': true});
  }
}
