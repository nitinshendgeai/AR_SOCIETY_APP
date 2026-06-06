import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/data/repositories/user_admin_repository.dart';

// ── Repository provider ───────────────────────────────────────────────────────

final userAdminRepoProvider = Provider<UserAdminRepository>(
  (_) => UserAdminRepository(),
);

// ── Users list ────────────────────────────────────────────────────────────────

final usersListProvider =
    AsyncNotifierProvider<UsersListNotifier, List<AdminUserModel>>(
        UsersListNotifier.new);

class UsersListNotifier extends AsyncNotifier<List<AdminUserModel>> {
  @override
  Future<List<AdminUserModel>> build() =>
      ref.read(userAdminRepoProvider).listUsers();

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
        () => ref.read(userAdminRepoProvider).listUsers());
  }

  Future<void> deleteUser(String id) async {
    await ref.read(userAdminRepoProvider).deleteUser(id);
    state = AsyncData(
      state.valueOrNull?.where((u) => u.id != id).toList() ?? [],
    );
  }
}

// ── Roles list ────────────────────────────────────────────────────────────────

final rolesListProvider =
    AsyncNotifierProvider<RolesListNotifier, List<RoleModel>>(
        RolesListNotifier.new);

class RolesListNotifier extends AsyncNotifier<List<RoleModel>> {
  @override
  Future<List<RoleModel>> build() =>
      ref.read(userAdminRepoProvider).listRoles();
}

// ── Single user detail ────────────────────────────────────────────────────────

final userDetailProvider = AsyncNotifierProviderFamily<UserDetailNotifier,
    AdminUserModel, String>(UserDetailNotifier.new);

class UserDetailNotifier
    extends FamilyAsyncNotifier<AdminUserModel, String> {
  @override
  Future<AdminUserModel> build(String arg) =>
      ref.read(userAdminRepoProvider).getUser(arg);

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
        () => ref.read(userAdminRepoProvider).getUser(arg));
  }

  Future<void> assignRole(String roleName) async {
    final updated =
        await ref.read(userAdminRepoProvider).assignRole(arg, roleName);
    state = AsyncData(updated);
  }

  Future<void> removeRole(String roleName) async {
    final updated =
        await ref.read(userAdminRepoProvider).removeRole(arg, roleName);
    state = AsyncData(updated);
  }

  Future<PasswordResetResult> resetPassword() async {
    final result =
        await ref.read(userAdminRepoProvider).resetPassword(arg);
    final updated = await ref.read(userAdminRepoProvider).getUser(arg);
    state = AsyncData(updated);
    return result;
  }
}
