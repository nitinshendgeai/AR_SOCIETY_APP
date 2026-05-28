import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/config/constants.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

/// Temporary home screen for each role.
/// Replace with real dashboards as modules are built.
class HomePlaceholderScreen extends ConsumerWidget {
  final String role;
  const HomePlaceholderScreen({super.key, required this.role});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text('${_roleEmoji(role)} ${_roleTitle(role)}'),
        centerTitle: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.logout_rounded),
            tooltip: 'Sign out',
            onPressed: () => _confirmLogout(context, ref),
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // User greeting card
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [AppTheme.primary, AppTheme.primaryDark],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Hello, ${user?.fullName.split(' ').first ?? 'User'}! 👋',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      user?.roleLabel ?? role,
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.8),
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      user?.email ?? '',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.6),
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 32),

              // Under construction notice
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: AppTheme.cardBg,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppTheme.border),
                ),
                child: Column(
                  children: [
                    Icon(
                      Icons.construction_rounded,
                      size: 48,
                      color: AppTheme.warning,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      '${_roleTitle(role)} Dashboard',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'This dashboard is being built.\nAuth & navigation foundation is ready.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                    const SizedBox(height: 16),
                    // Role capabilities preview
                    _RoleCapabilities(role: role),
                  ],
                ),
              ),

              const Spacer(),

              // Session info (dev mode)
              if (user != null)
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.success.withOpacity(0.08),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppTheme.success.withOpacity(0.2)),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.check_circle_outline,
                          color: AppTheme.success, size: 16),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Authenticated · JWT valid · Roles: ${user.roles.join(", ")}',
                          style: TextStyle(
                            fontSize: 11,
                            color: AppTheme.success,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _confirmLogout(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Sign out?'),
        content: const Text('You will be returned to the login screen.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.error,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Sign out'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await ref.read(authProvider.notifier).logout();
      // GoRouter redirect handles navigation to login
    }
  }

  String _roleEmoji(String role) {
    switch (role) {
      case AppConstants.roleAdmin:        return '🛡️';
      case AppConstants.roleCommittee:    return '🏛️';
      case AppConstants.roleSecurity:     return '🔒';
      case AppConstants.roleStaff:        return '🔧';
      default:                            return '🏠';
    }
  }

  String _roleTitle(String role) {
    switch (role) {
      case AppConstants.roleAdmin:        return 'Admin';
      case AppConstants.roleCommittee:    return 'Committee';
      case AppConstants.roleSecurity:     return 'Security';
      case AppConstants.roleStaff:        return 'Staff';
      default:                            return 'Resident';
    }
  }
}

class _RoleCapabilities extends StatelessWidget {
  final String role;
  const _RoleCapabilities({required this.role});

  List<String> get _modules {
    switch (role) {
      case AppConstants.roleAdmin:
        return ['Society Management', 'User & Role Management', 'All Modules', 'Reports & Analytics'];
      case AppConstants.roleCommittee:
        return ['Society Management', 'Complaint Approvals', 'Billing', 'Notice Board'];
      case AppConstants.roleSecurity:
        return ['Visitor Management', 'Gate Operations', 'Parking', 'Handover/Takeover'];
      case AppConstants.roleStaff:
        return ['Attendance', 'My Duties', 'Tasks', 'Leave Requests'];
      default:
        return ['My Flat', 'Complaints', 'Amenity Bookings', 'Notices & Bills'];
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Modules you\'ll have access to:',
          style: TextStyle(
            fontSize: 12,
            color: AppTheme.textSecondary,
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: _modules.map((m) => Chip(
            label: Text(m, style: const TextStyle(fontSize: 11)),
            backgroundColor: AppTheme.primary.withOpacity(0.08),
            side: BorderSide(color: AppTheme.primary.withOpacity(0.2)),
            padding: EdgeInsets.zero,
          )).toList(),
        ),
      ],
    );
  }
}
