import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';

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
            'Each column is a navigation screen. Toggling a switch grants '
            'or revokes that screen for the role in its row — changes '
            'apply the next time that role\'s users open the app menu.',
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
                  for (final f in forms)
                    DataColumn(
                      label: Tooltip(
                        message: f.description ?? f.name,
                        child: Text(f.name,
                            style: const TextStyle(fontWeight: FontWeight.w700)),
                      ),
                    ),
                ],
                rows: [
                  for (final row in rows)
                    DataRow(cells: [
                      DataCell(Text(row.roleName,
                          style: const TextStyle(fontWeight: FontWeight.w600))),
                      for (final f in forms)
                        DataCell(_FormSwitch(
                          roleId: row.roleId,
                          code: f.code,
                          granted: row.formCodes.contains(f.code),
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

class _FormSwitch extends ConsumerStatefulWidget {
  final String roleId;
  final String code;
  final bool granted;
  const _FormSwitch(
      {required this.roleId, required this.code, required this.granted});

  @override
  ConsumerState<_FormSwitch> createState() => _FormSwitchState();
}

class _FormSwitchState extends ConsumerState<_FormSwitch> {
  bool _saving = false;

  Future<void> _toggle(bool value) async {
    setState(() => _saving = true);
    try {
      await ref
          .read(formMatrixProvider.notifier)
          .toggleForm(widget.roleId, widget.code, value);
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
