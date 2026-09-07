import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';

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
  Widget build(BuildContext context, WidgetRef ref) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          color: AppTheme.cardBg,
          child: const Text(
            'Each column is an access tier used across the app. Toggling a '
            'switch grants or revokes that tier for the role in its row — '
            'changes apply immediately.',
            style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
          ),
        ),
        Expanded(
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SingleChildScrollView(
              child: DataTable(
                headingRowColor:
                    WidgetStateProperty.all(AppTheme.cardBg),
                columns: [
                  const DataColumn(
                    label: Text('Role',
                        style: TextStyle(fontWeight: FontWeight.w700)),
                  ),
                  for (final p in permissions)
                    DataColumn(
                      label: Tooltip(
                        message: p.description ?? p.name,
                        child: Text(p.name,
                            style: const TextStyle(fontWeight: FontWeight.w700)),
                      ),
                    ),
                ],
                rows: [
                  for (final row in rows)
                    DataRow(cells: [
                      DataCell(Text(row.roleName,
                          style: const TextStyle(fontWeight: FontWeight.w600))),
                      for (final p in permissions)
                        DataCell(_PermissionSwitch(
                          roleId: row.roleId,
                          code: p.code,
                          granted: row.permissionCodes.contains(p.code),
                        )),
                    ]),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _PermissionSwitch extends ConsumerStatefulWidget {
  final String roleId;
  final String code;
  final bool granted;
  const _PermissionSwitch(
      {required this.roleId, required this.code, required this.granted});

  @override
  ConsumerState<_PermissionSwitch> createState() => _PermissionSwitchState();
}

class _PermissionSwitchState extends ConsumerState<_PermissionSwitch> {
  bool _saving = false;

  Future<void> _toggle(bool value) async {
    setState(() => _saving = true);
    try {
      await ref
          .read(permissionMatrixProvider.notifier)
          .togglePermission(widget.roleId, widget.code, value);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(friendlyErrorMessage(e)),
          backgroundColor: AppTheme.error,
        ));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_saving) {
      return const SizedBox(
        width: 20,
        height: 20,
        child: CircularProgressIndicator(strokeWidth: 2),
      );
    }
    return Switch(
      value: widget.granted,
      activeColor: AppTheme.success,
      onChanged: _toggle,
    );
  }
}
