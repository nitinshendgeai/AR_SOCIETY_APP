import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';

class UserRemoteDataSource {
  final Dio _dio;
  UserRemoteDataSource({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<List<AdminUserModel>> listUsers({int skip = 0, int limit = 100}) async {
    final r = await _dio.get('/users/', queryParameters: {'skip': skip, 'limit': limit});
    return (r.data as List)
        .map((e) => AdminUserModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<AdminUserModel> getUser(String id) async {
    final r = await _dio.get('/users/$id');
    return AdminUserModel.fromJson(r.data as Map<String, dynamic>);
  }

  Future<AdminUserModel> createUser({
    required String email,
    required String fullName,
    String? phone,
    String? roleName,
    bool mustChangePassword = true,
  }) async {
    final r = await _dio.post('/users/', data: {
      'email': email,
      'full_name': fullName,
      if (phone != null) 'phone': phone,
      if (roleName != null) 'role_name': roleName,
      'must_change_password': mustChangePassword,
    });
    return AdminUserModel.fromJson(r.data as Map<String, dynamic>);
  }

  Future<AdminUserModel> updateUser(
      String id, Map<String, dynamic> data) async {
    final r = await _dio.patch('/users/$id', data: data);
    return AdminUserModel.fromJson(r.data as Map<String, dynamic>);
  }

  Future<AdminUserModel> assignRole(String userId, String roleName) async {
    final r = await _dio.post('/users/$userId/roles',
        data: {'role_name': roleName});
    return AdminUserModel.fromJson(r.data as Map<String, dynamic>);
  }

  Future<AdminUserModel> removeRole(String userId, String roleName) async {
    final r = await _dio.delete('/users/$userId/roles/$roleName');
    return AdminUserModel.fromJson(r.data as Map<String, dynamic>);
  }

  Future<PasswordResetResult> resetPassword(String userId) async {
    final r = await _dio.post('/users/$userId/reset-password');
    return PasswordResetResult.fromJson(r.data as Map<String, dynamic>);
  }

  Future<void> deleteUser(String id) async {
    await _dio.delete('/users/$id');
  }

  Future<List<RoleModel>> listRoles() async {
    final r = await _dio.get('/roles/');
    return (r.data as List)
        .map((e) => RoleModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
