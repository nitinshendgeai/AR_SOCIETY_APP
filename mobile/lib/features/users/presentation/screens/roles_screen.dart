import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show HeaderActionButton, StatusPill;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The roles a society can give its users. The standard roles (Manager, Security Staff, Resident...) are shared by every
/// society and are listed for reference; the society's own roles can be added, renamed and deleted here. A new role starts
/// with nothing (or with what another role may do) and is then given its permissions in the Permission Matrix and its
/// menu screens in the Forms Matrix. A role can be deleted once nobody holds it.
class RolesScreen extends ConsumerWidget {
  const RolesScreen({super.key});

  Future<void> _add(BuildContext context, WidgetRef ref, List<RoleModel> roles) async {
    final made = await showAppSheet<RoleModel>(context: context, builder: (_) => RoleSheet(roles: roles));
    if (made == null) return;
    ref.invalidate(rolesListProvider);
    if (context.mounted) AppToast.success(context, '${made.name} added. Now choose what it may do.');
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(rolesListProvider);
    final roles = async.valueOrNull ?? const <RoleModel>[];
    final desktop = isDesktopLayout(context);
    return AppPage(
      title: 'Roles',
      actions: [
        if (desktop) HeaderActionButton(icon: Icons.add_rounded, label: 'New role', onPressed: () => _add(context, ref, roles)),
      ],
      floatingActionButton: desktop
          ? null
          : FloatingActionButton.extended(
              key: const Key('role-add'),
              onPressed: () => _add(context, ref, roles),
              icon: const Icon(Icons.add_rounded),
              label: const Text('New role')),
      body: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => ListView(children: [
          Padding(padding: const EdgeInsets.all(24), child: Text(friendlyErrorMessage(e), style: TextStyle(color: AppTheme.error)))
        ]),
        data: (all) {
          final mine = all.where((r) => r.isCustom).toList();
          final standard = all.where((r) => !r.isCustom).toList();
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(rolesListProvider),
            child: ResponsiveBody(
              maxWidth: 860,
              child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
                Text(
                    'Roles decide what a user may do and which screens they see. The standard roles are shared by every society. '
                    'Add a role of your own when none of them fits, for example a gym instructor or a librarian.',
                    style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary, height: 1.35)),
                const SizedBox(height: 16),
                const _Heading('Your society\'s roles'),
                if (mine.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 12),
                    child: Text('No roles of your own yet. Tap New role to add one.', key: Key('no-custom-roles')),
                  )
                else
                  for (final r in mine) _RoleTile(role: r, all: all),
                const SizedBox(height: 16),
                const _Heading('Standard roles'),
                for (final r in standard) _RoleTile(role: r, all: all),
              ]),
            ),
          );
        },
      ),
    );
  }
}

class _Heading extends StatelessWidget {
  final String text;
  const _Heading(this.text);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(text, style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14, color: AppTheme.primary)),
      );
}

class _RoleTile extends ConsumerWidget {
  final RoleModel role;
  final List<RoleModel> all;
  const _RoleTile({required this.role, required this.all});

  Future<void> _edit(BuildContext context, WidgetRef ref) async {
    final saved = await showAppSheet<RoleModel>(context: context, builder: (_) => RoleSheet(roles: all, existing: role));
    if (saved == null) return;
    ref.invalidate(rolesListProvider);
    if (context.mounted) AppToast.success(context, 'Role saved');
  }

  Future<void> _delete(BuildContext context, WidgetRef ref) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('Delete ${role.name}?'),
        content: const Text('Its permissions and screens are removed with it. This can\'t be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Delete')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(userAdminRepoProvider).deleteRole(role.id);
      ref.invalidate(rolesListProvider);
      if (context.mounted) AppToast.success(context, '${role.name} deleted');
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = role;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(r.name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15))),
            StatusPill(r.isCustom ? 'Yours' : 'Standard', r.isCustom ? AppTheme.primary : AppTheme.textSecondary),
          ]),
          if ((r.description ?? '').isNotEmpty)
            Padding(padding: const EdgeInsets.only(top: 2), child: Text(r.description!, style: const TextStyle(fontSize: 13))),
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(r.userCount == 1 ? '1 user' : '${r.userCount} users',
                style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          ),
          if (r.isCustom) ...[
            const SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 8, children: [
              OutlinedButton.icon(
                onPressed: () => context.push(AppRoutes.permissionMatrix),
                icon: const Icon(Icons.rule_rounded, size: 18),
                label: const Text('What it may do'),
              ),
              OutlinedButton.icon(
                onPressed: () => context.push(AppRoutes.formsMatrix),
                icon: const Icon(Icons.dashboard_customize_rounded, size: 18),
                label: const Text('Its screens'),
              ),
              TextButton.icon(
                onPressed: () => _edit(context, ref),
                icon: const Icon(Icons.edit_outlined, size: 18),
                label: const Text('Rename'),
              ),
              TextButton.icon(
                key: Key('role-delete-${r.id}'),
                onPressed: r.userCount > 0 ? null : () => _delete(context, ref),
                icon: const Icon(Icons.delete_outline_rounded, size: 18),
                label: Text(r.userCount > 0 ? 'In use' : 'Delete'),
              ),
            ]),
          ],
        ]),
      ),
    );
  }
}

/// Add a role, or rename / re-describe one of the society's own. Pops the saved [RoleModel].
class RoleSheet extends ConsumerStatefulWidget {
  final List<RoleModel> roles;
  final RoleModel? existing;
  const RoleSheet({super.key, required this.roles, this.existing});

  @override
  ConsumerState<RoleSheet> createState() => _RoleSheetState();
}

class _RoleSheetState extends ConsumerState<RoleSheet> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(text: widget.existing?.name ?? '');
  late final _description = TextEditingController(text: widget.existing?.description ?? '');
  String? _copyFrom;
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    _description.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _busy = true);
    final repo = ref.read(userAdminRepoProvider);
    try {
      final saved = widget.existing == null
          ? await repo.createRole(_name.text.trim(), description: _description.text, copyFromRoleId: _copyFrom)
          : await repo.updateRole(widget.existing!.id, name: _name.text.trim(), description: _description.text.trim());
      if (mounted) Navigator.of(context).pop(saved);
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final editing = widget.existing != null;
    return AppSheetFrame(
      title: editing ? 'Rename role' : 'New role',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          FormFieldBox(
            label: 'Role name',
            required: true,
            child: TextFormField(
              key: const Key('role-name'),
              controller: _name,
              maxLength: 60,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(counterText: '', hintText: 'e.g. Gym Instructor'),
              validator: (v) {
                final t = (v ?? '').trim();
                return t.length < 3 ? 'At least 3 characters' : null;
              },
            ),
          ),
          FormFieldBox(
            label: 'What the role is for (optional)',
            child: TextFormField(
                key: const Key('role-description'),
                controller: _description,
                maxLength: 500,
                minLines: 2,
                maxLines: 3,
                decoration: const InputDecoration(counterText: '', alignLabelWithHint: true)),
          ),
          if (!editing)
            FormFieldBox(
              label: 'Start from',
              child: DropdownButtonFormField<String?>(
                key: const Key('role-copy-from'),
                initialValue: _copyFrom,
                isExpanded: true,
                decoration: const InputDecoration(helperText: 'Copies that role\'s permissions and screens; you can change them after'),
                items: [
                  const DropdownMenuItem<String?>(value: null, child: Text('Nothing: start empty')),
                  for (final r in widget.roles) DropdownMenuItem<String?>(value: r.id, child: Text(r.name)),
                ],
                onChanged: (v) => setState(() => _copyFrom = v),
              ),
            ),
          const SizedBox(height: 8),
          FilledButton(onPressed: _busy ? null : _save, child: Text(editing ? 'Save' : 'Add role')),
        ]),
      ),
    );
  }
}
