import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/features/users/data/models/user_admin_models.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';

class UserDetailScreen extends ConsumerWidget {
  final String userId;
  const UserDetailScreen({super.key, required this.userId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userAsync = ref.watch(userDetailProvider(userId));

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('User Details'),
        actions: [
          userAsync.whenOrNull(
            data: (user) => PopupMenuButton<String>(
              icon: const Icon(Icons.more_vert_rounded),
              onSelected: (v) => _handleMenu(context, ref, v, user),
              itemBuilder: (_) => const [
                PopupMenuItem(value: 'edit',  child: Text('Edit profile')),
                PopupMenuItem(value: 'roles', child: Text('Manage roles')),
                PopupMenuItem(value: 'reset', child: Text('Reset password')),
                PopupMenuItem(
                  value: 'delete',
                  child: Text('Delete user',
                      style: TextStyle(color: AppTheme.error)),
                ),
              ],
            ),
          ) ?? const SizedBox.shrink(),
        ],
      ),
      body: userAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded,
                  color: AppTheme.error, size: 40),
              const SizedBox(height: 12),
              Text(e.toString(),
                  style: const TextStyle(color: AppTheme.textSecondary)),
              TextButton(
                onPressed: () =>
                    ref.read(userDetailProvider(userId).notifier).refresh(),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
        data: (user) => _UserDetailBody(user: user, userId: userId),
      ),
    );
  }

  Future<void> _handleMenu(
      BuildContext context, WidgetRef ref, String action, AdminUserModel user) async {
    switch (action) {
      case 'edit':
        final changed = await context.push(
          AppRoutes.usersEdit.replaceFirst(':userId', userId),
          extra: user,
        );
        if (changed == true) {
          ref.read(userDetailProvider(userId).notifier).refresh();
        }
        break;
      case 'roles':
        await context.push(
          AppRoutes.usersRoles.replaceFirst(':userId', userId),
          extra: user,
        );
        ref.read(userDetailProvider(userId).notifier).refresh();
        break;
      case 'reset':
        final ok = await _confirmDialog(
          context,
          title: 'Reset Password',
          content:
              'A new temporary password will be generated. The user must change it on next login.',
          confirmLabel: 'Reset',
        );
        if (ok && context.mounted) {
          final result =
              await ref.read(userDetailProvider(userId).notifier).resetPassword();
          if (context.mounted) _showTempPassword(context, result.temporaryPassword);
        }
        break;
      case 'delete':
        final ok = await _confirmDialog(
          context,
          title: 'Delete User',
          content:
              'This will permanently deactivate ${user.fullName}. This cannot be undone.',
          confirmLabel: 'Delete',
          destructive: true,
        );
        if (ok) {
          await ref.read(usersListProvider.notifier).deleteUser(userId);
          if (context.mounted) context.pop();
        }
        break;
    }
  }

  Future<bool> _confirmDialog(
    BuildContext context, {
    required String title,
    required String content,
    required String confirmLabel,
    bool destructive = false,
  }) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(content),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: destructive
                ? ElevatedButton.styleFrom(backgroundColor: AppTheme.error)
                : null,
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(confirmLabel),
          ),
        ],
      ),
    );
    return result ?? false;
  }

  void _showTempPassword(BuildContext context, String pwd) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Temporary Password'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Share this with the user. They must change it on login.',
                style: TextStyle(
                    fontSize: 13, color: AppTheme.textSecondary)),
            const SizedBox(height: 12),
            GestureDetector(
              onTap: () {
                Clipboard.setData(ClipboardData(text: pwd));
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Copied to clipboard')),
                );
              },
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppTheme.border),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(pwd,
                          style: const TextStyle(
                              fontFamily: 'monospace',
                              fontWeight: FontWeight.w700,
                              fontSize: 16)),
                    ),
                    const Icon(Icons.copy_rounded,
                        size: 16, color: AppTheme.primary),
                  ],
                ),
              ),
            ),
          ],
        ),
        actions: [
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Done'),
          ),
        ],
      ),
    );
  }
}

class _UserDetailBody extends StatelessWidget {
  final AdminUserModel user;
  final String userId;
  const _UserDetailBody({required this.user, required this.userId});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _ProfileHeader(user: user),
          const SizedBox(height: 20),
          _InfoCard(user: user),
          const SizedBox(height: 16),
          _RolesCard(user: user, userId: userId),
        ],
      ),
    );
  }
}

class _ProfileHeader extends StatelessWidget {
  final AdminUserModel user;
  const _ProfileHeader({required this.user});

  @override
  Widget build(BuildContext context) {
    final isActive = user.status == 'active';
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppTheme.primary, AppTheme.primaryDark],
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.2),
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(user.initials,
                  style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 20)),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(user.fullName,
                    style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                        fontSize: 18)),
                const SizedBox(height: 2),
                Text(user.email,
                    style: TextStyle(
                        color: Colors.white.withOpacity(0.8),
                        fontSize: 13)),
                const SizedBox(height: 6),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: (isActive ? AppTheme.success : Colors.grey)
                        .withOpacity(0.2),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    isActive ? 'Active' : user.status,
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  final AdminUserModel user;
  const _InfoCard({required this.user});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Profile',
              style: TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 14,
                  color: AppTheme.textPrimary)),
          const SizedBox(height: 12),
          _InfoRow(
              icon: Icons.email_outlined,
              label: 'Email',
              value: user.email),
          if (user.phone != null) ...[
            const Divider(height: 20),
            _InfoRow(
                icon: Icons.phone_outlined,
                label: 'Phone',
                value: user.phone!),
          ],
          if (user.mustChangePassword) ...[
            const Divider(height: 20),
            _InfoRow(
              icon: Icons.warning_amber_rounded,
              label: 'Password',
              value: 'Must change on next login',
              valueColor: AppTheme.warning,
            ),
          ],
          if (user.createdAt != null) ...[
            const Divider(height: 20),
            _InfoRow(
                icon: Icons.calendar_today_outlined,
                label: 'Joined',
                value: user.createdAt!.split('T').first),
          ],
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color? valueColor;
  const _InfoRow(
      {required this.icon,
      required this.label,
      required this.value,
      this.valueColor});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 16, color: AppTheme.textSecondary),
        const SizedBox(width: 10),
        SizedBox(
          width: 72,
          child: Text(label,
              style: const TextStyle(
                  fontSize: 12, color: AppTheme.textSecondary)),
        ),
        Expanded(
          child: Text(value,
              style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: valueColor ?? AppTheme.textPrimary)),
        ),
      ],
    );
  }
}

class _RolesCard extends ConsumerWidget {
  final AdminUserModel user;
  final String userId;
  const _RolesCard({required this.user, required this.userId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text('Assigned Roles',
                    style: TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 14,
                        color: AppTheme.textPrimary)),
              ),
              TextButton.icon(
                onPressed: () async {
                  await context.push(
                    AppRoutes.usersRoles.replaceFirst(':userId', userId),
                    extra: user,
                  );
                  ref.read(userDetailProvider(userId).notifier).refresh();
                },
                icon: const Icon(Icons.edit_rounded, size: 14),
                label: const Text('Manage'),
                style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (user.roles.isEmpty)
            const Text('No roles assigned',
                style: TextStyle(
                    color: AppTheme.textSecondary, fontSize: 13))
          else
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: user.roles
                  .map((r) => _RoleChip(role: r, userId: userId))
                  .toList(),
            ),
        ],
      ),
    );
  }
}

class _RoleChip extends ConsumerWidget {
  final String role;
  final String userId;
  const _RoleChip({required this.role, required this.userId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Chip(
      label: Text(role,
          style: const TextStyle(
              fontSize: 12,
              color: AppTheme.primary,
              fontWeight: FontWeight.w600)),
      backgroundColor: AppTheme.primary.withOpacity(0.08),
      side: BorderSide(color: AppTheme.primary.withOpacity(0.3)),
      deleteIcon: const Icon(Icons.close_rounded, size: 14),
      deleteIconColor: AppTheme.primary,
      onDeleted: () async {
        final ok = await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Remove Role'),
            content: Text('Remove "$role" from this user?'),
            actions: [
              TextButton(
                  onPressed: () => Navigator.pop(ctx, false),
                  child: const Text('Cancel')),
              ElevatedButton(
                  style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.error),
                  onPressed: () => Navigator.pop(ctx, true),
                  child: const Text('Remove')),
            ],
          ),
        );
        if (ok == true) {
          await ref.read(userDetailProvider(userId).notifier).removeRole(role);
        }
      },
    );
  }
}
