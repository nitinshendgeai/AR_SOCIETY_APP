import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';

class RoleAssignmentScreen extends ConsumerWidget {
  final AdminUserModel user;
  const RoleAssignmentScreen({super.key, required this.user});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final rolesAsync = ref.watch(rolesListProvider);
    final userAsync  = ref.watch(userDetailProvider(user.id));
    final currentRoles =
        userAsync.valueOrNull?.roles ?? user.roles;

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text('Roles — ${user.fullName.split(' ').first}'),
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              'Tap a role to assign or remove it.',
              style: const TextStyle(
                  fontSize: 13, color: AppTheme.textSecondary),
            ),
          ),
          Expanded(
            child: rolesAsync.when(
              loading: () =>
                  const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(
                  child: Text(e.toString(),
                      style: const TextStyle(
                          color: AppTheme.error))),
              data: (roles) => ListView.separated(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: roles.length,
                separatorBuilder: (_, __) =>
                    const Divider(height: 1),
                itemBuilder: (_, i) {
                  final role = roles[i];
                  final assigned = currentRoles.contains(role.name);
                  return _RoleTile(
                    role: role,
                    assigned: assigned,
                    onToggle: () async {
                      if (assigned) {
                        await ref
                            .read(userDetailProvider(user.id).notifier)
                            .removeRole(role.name);
                      } else {
                        await ref
                            .read(userDetailProvider(user.id).notifier)
                            .assignRole(role.name);
                      }
                    },
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RoleTile extends StatefulWidget {
  final RoleModel role;
  final bool assigned;
  final Future<void> Function() onToggle;
  const _RoleTile(
      {required this.role,
      required this.assigned,
      required this.onToggle});

  @override
  State<_RoleTile> createState() => _RoleTileState();
}

class _RoleTileState extends State<_RoleTile> {
  bool _loading = false;

  Future<void> _toggle() async {
    setState(() => _loading = true);
    try {
      await widget.onToggle();
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Container(
        width: 36,
        height: 36,
        decoration: BoxDecoration(
          color: (widget.assigned ? AppTheme.success : AppTheme.textSecondary)
              .withOpacity(0.1),
          shape: BoxShape.circle,
        ),
        child: Icon(
          widget.assigned
              ? Icons.check_circle_rounded
              : Icons.radio_button_unchecked_rounded,
          size: 20,
          color: widget.assigned
              ? AppTheme.success
              : AppTheme.textSecondary,
        ),
      ),
      title: Text(widget.role.name,
          style: const TextStyle(
              fontWeight: FontWeight.w600,
              fontSize: 14,
              color: AppTheme.textPrimary)),
      subtitle: widget.role.description != null
          ? Text(widget.role.description!,
              style: const TextStyle(
                  fontSize: 11, color: AppTheme.textSecondary))
          : null,
      trailing: _loading
          ? const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2))
          : Switch(
              value: widget.assigned,
              activeColor: AppTheme.success,
              onChanged: (_) => _toggle(),
            ),
      onTap: _loading ? null : _toggle,
    );
  }
}
