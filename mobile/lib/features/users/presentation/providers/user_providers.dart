import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
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

// ── Permission matrix ─────────────────────────────────────────────────────────

final permissionsListProvider =
    AsyncNotifierProvider<PermissionsListNotifier, List<PermissionModel>>(
        PermissionsListNotifier.new);

class PermissionsListNotifier extends AsyncNotifier<List<PermissionModel>> {
  @override
  Future<List<PermissionModel>> build() =>
      ref.read(userAdminRepoProvider).listPermissions();
}

final permissionMatrixProvider = AsyncNotifierProvider<PermissionMatrixNotifier,
    List<RolePermissionMatrixRow>>(PermissionMatrixNotifier.new);

class PermissionMatrixNotifier
    extends AsyncNotifier<List<RolePermissionMatrixRow>> {
  @override
  Future<List<RolePermissionMatrixRow>> build() =>
      ref.read(userAdminRepoProvider).getPermissionMatrix();

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
        () => ref.read(userAdminRepoProvider).getPermissionMatrix());
  }

  Future<void> togglePermission(
      String roleId, String permissionCode, bool grant) async {
    final rows = state.valueOrNull;
    if (rows == null) return;
    final idx = rows.indexWhere((r) => r.roleId == roleId);
    if (idx == -1) return;

    final current = rows[idx];
    final updatedCodes = Set<String>.from(current.permissionCodes);
    if (grant) {
      updatedCodes.add(permissionCode);
    } else {
      updatedCodes.remove(permissionCode);
    }

    final saved = await ref
        .read(userAdminRepoProvider)
        .updateRolePermissions(roleId, updatedCodes.toList());

    final newRows = [...rows];
    newRows[idx] = saved;
    state = AsyncData(newRows);
  }
}

// ── Forms matrix ──────────────────────────────────────────────────────────────

final formsListProvider =
    AsyncNotifierProvider<FormsListNotifier, List<FormModel>>(
        FormsListNotifier.new);

class FormsListNotifier extends AsyncNotifier<List<FormModel>> {
  @override
  Future<List<FormModel>> build() =>
      ref.read(userAdminRepoProvider).listForms();
}

final formMatrixProvider =
    AsyncNotifierProvider<FormMatrixNotifier, List<RoleFormMatrixRow>>(
        FormMatrixNotifier.new);

class FormMatrixNotifier extends AsyncNotifier<List<RoleFormMatrixRow>> {
  @override
  Future<List<RoleFormMatrixRow>> build() =>
      ref.read(userAdminRepoProvider).getFormMatrix();

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
        () => ref.read(userAdminRepoProvider).getFormMatrix());
  }

  Future<void> toggleForm(String roleId, String formCode, bool grant) async {
    final rows = state.valueOrNull;
    if (rows == null) return;
    final idx = rows.indexWhere((r) => r.roleId == roleId);
    if (idx == -1) return;

    final current = rows[idx];
    final updatedCodes = Set<String>.from(current.formCodes);
    if (grant) {
      updatedCodes.add(formCode);
    } else {
      updatedCodes.remove(formCode);
    }

    final saved = await ref
        .read(userAdminRepoProvider)
        .updateRoleForms(roleId, updatedCodes.toList());

    final newRows = [...rows];
    newRows[idx] = saved;
    state = AsyncData(newRows);

    // The edit may have changed the CURRENT user's own visible navigation
    // (e.g. an Admin editing their own role) — refetch so the drawer
    // reflects it without requiring a re-login.
    ref.invalidate(myFormCodesProvider);
  }
}

// ── Current user's own visible forms (drives drawer navigation) ────────────────
//
// Watches currentUserProvider so a login, logout, or account switch within
// the same app session automatically re-fetches — no manual invalidation
// wiring needed at the call site.
final myFormCodesProvider = FutureProvider<List<String>>((ref) async {
  final user = ref.watch(currentUserProvider);
  if (user == null) return const [];
  return ref.read(userAdminRepoProvider).getMyForms();
});
