import 'package:ar_society_app/features/users/data/datasources/user_remote_datasource.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';

class UserAdminRepository {
  final UserRemoteDataSource _ds;
  UserAdminRepository({UserRemoteDataSource? ds})
      : _ds = ds ?? UserRemoteDataSource();

  Future<List<AdminUserModel>> listUsers({int skip = 0, int limit = 100}) =>
      _ds.listUsers(skip: skip, limit: limit);

  Future<AdminUserModel> getUser(String id) => _ds.getUser(id);

  Future<AdminUserModel> createUser({
    required String email,
    required String fullName,
    String? phone,
    String? roleName,
    bool mustChangePassword = true,
  }) =>
      _ds.createUser(
        email: email,
        fullName: fullName,
        phone: phone,
        roleName: roleName,
        mustChangePassword: mustChangePassword,
      );

  Future<AdminUserModel> updateUser(String id, Map<String, dynamic> data) =>
      _ds.updateUser(id, data);

  Future<AdminUserModel> assignRole(String userId, String roleName) =>
      _ds.assignRole(userId, roleName);

  Future<AdminUserModel> removeRole(String userId, String roleName) =>
      _ds.removeRole(userId, roleName);

  Future<PasswordResetResult> resetPassword(String userId) =>
      _ds.resetPassword(userId);

  Future<void> deleteUser(String id) => _ds.deleteUser(id);

  Future<List<RoleModel>> listRoles() => _ds.listRoles();
}
