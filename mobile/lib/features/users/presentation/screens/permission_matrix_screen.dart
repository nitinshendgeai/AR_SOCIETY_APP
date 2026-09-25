import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
import 'package:ar_society_app/shared/widgets/role_matrix.dart';

/// Admin-only editor for the dynamic RBAC permission matrix: which of the
/// fixed access tiers (Admin, Admin + Committee, ...) each role is granted.
/// Every protected endpoint in the backend checks this matrix at request
/// time, so a toggle here takes effect immediately — no app update needed.
class PermissionMatrixScreen extends ConsumerWidget {
  const PermissionMatrixScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final permissionsAsync = ref.watch(permissionsListProvider);
    final matrixAsync = ref.watch(permissionMatrixProvider);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Permission Matrix'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: () => ref.read(permissionMatrixProvider.notifier).refresh(),
          ),
        ],
      ),
      body: permissionsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
            child: Text(friendlyErrorMessage(e),
                style: const TextStyle(color: AppTheme.error))),
        data: (permissions) => matrixAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(
              child: Text(friendlyErrorMessage(e),
                  style: const TextStyle(color: AppTheme.error))),
          data: (rows) => _MatrixTable(permissions: permissions, rows: rows),
        ),
      ),
    );
  }
}

class _MatrixTable extends ConsumerWidget {
  final List<PermissionModel> permissions;
  final List<RolePermissionMatrixRow> rows;
  const _MatrixTable({required this.permissions, required this.rows});

  @override
  Widget build(BuildContext context, WidgetRef ref) => RoleMatrix(
        description: 'Each column is an access tier used across the app. Ticking a box grants that '
            'tier to the role in its row — changes apply immediately.',
        columnNoun: 'tiers',
        columns: [
          for (final p in permissions) MatrixColumn(key: p.code, label: p.name, tooltip: p.description),
        ],
        rows: [
          for (final r in rows) MatrixRow(roleId: r.roleId, roleName: r.roleName, granted: r.permissionCodes.toSet()),
        ],
        onToggle: (roleId, code, value) =>
            ref.read(permissionMatrixProvider.notifier).togglePermission(roleId, code, value),
      );
}
