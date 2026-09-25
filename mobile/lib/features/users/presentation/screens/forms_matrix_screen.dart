import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/shared/widgets/role_matrix.dart';

/// Admin-only editor for the forms matrix: which top-level navigation
/// screens each role sees. Independent of the Permission Matrix (which
/// gates backend API access by tier) — this instead controls what the
/// mobile app's drawer renders, so an Admin can grant/revoke individual
/// screens per role without touching any of the broader access tiers.
class FormsMatrixScreen extends ConsumerWidget {
  const FormsMatrixScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final formsAsync = ref.watch(formsListProvider);
    final matrixAsync = ref.watch(formMatrixProvider);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Forms Matrix'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: () => ref.read(formMatrixProvider.notifier).refresh(),
          ),
        ],
      ),
      body: formsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
            child: Text(friendlyErrorMessage(e),
                style: const TextStyle(color: AppTheme.error))),
        data: (forms) => matrixAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(
              child: Text(friendlyErrorMessage(e),
                  style: const TextStyle(color: AppTheme.error))),
          data: (rows) => _MatrixTable(forms: forms, rows: rows),
        ),
      ),
    );
  }
}

class _MatrixTable extends ConsumerWidget {
  final List<FormModel> forms;
  final List<RoleFormMatrixRow> rows;
  const _MatrixTable({required this.forms, required this.rows});

  /// Screens in the same order and groups as the app menu, so the matrix
  /// reads like the sidebar; screens not in the menu go last.
  List<MatrixColumn> get _columns {
    final byCode = {for (final f in forms) f.code: f};
    final columns = <MatrixColumn>[];
    for (final category in appMenuCategories) {
      for (final item in category.items) {
        final f = byCode.remove(item.formCode);
        if (f != null) {
          columns.add(MatrixColumn(key: f.code, label: f.name, tooltip: f.description, group: category.label));
        }
      }
    }
    for (final f in byCode.values) {
      columns.add(MatrixColumn(key: f.code, label: f.name, tooltip: f.description, group: 'Other'));
    }
    return columns;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) => RoleMatrix(
        description: 'Each column is a screen in the app menu. Ticking a box shows that screen to the '
            'role in its row — users see the change next time they open the menu.',
        columnNoun: 'screens',
        columns: _columns,
        rows: [
          for (final r in rows) MatrixRow(roleId: r.roleId, roleName: r.roleName, granted: r.formCodes.toSet()),
        ],
        onToggle: (roleId, code, value) => ref.read(formMatrixProvider.notifier).toggleForm(roleId, code, value),
      );
}
