import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart';

/// Staff home screen — navigation hub for all operational staff modules.
/// Handles async staff-profile resolution: shows loading/error/retry banners
/// and keeps operation cards visually disabled until the staffId is known.
class StaffHomeScreen extends ConsumerWidget {
  const StaffHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user       = ref.watch(currentUserProvider);
    final staffAsync = ref.watch(currentStaffProvider); // AsyncValue<StaffEntity?>
    final staffId    = ref.watch(staffIdProvider);
    final societyId  = user?.societyId;
    final isReady    = staffId != null;

    // Role detection for supervisor/manager management section
    final roles = user?.roles ?? [];
    final isSupervisor = roles.any((r) => r.contains('Supervisor'));
    final isManager = roles.any((r) =>
        r.contains('Manager') ||
        r.contains('Committee') || r == 'Super Admin' || r == 'Society Admin');
    final showManagement = (isSupervisor || isManager) && societyId != null;

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Staff Portal'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout_rounded),
            onPressed: () => _logout(context, ref),
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async => ref.invalidate(currentStaffProvider),
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              // ── Greeting card ─────────────────────────────────────────────
              Container(
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [AppTheme.primary, AppTheme.primaryDark],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Icon(Icons.person_rounded,
                          color: Colors.white, size: 26),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Hello, ${user?.fullName.split(' ').first ?? 'Staff'}',
                            style: const TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                                fontWeight: FontWeight.w700),
                          ),
                          Text(
                            user?.roleLabel ?? 'Staff Member',
                            style: const TextStyle(
                                color: Colors.white70, fontSize: 13),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 20),

              // ── Profile resolution status ─────────────────────────────────
              _StaffProfileStatus(staffAsync: staffAsync, staffId: staffId),

              // ── My Operations ─────────────────────────────────────────────
              const SectionHeader(title: 'My Operations'),
              const SizedBox(height: 14),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 1.1,
                children: [
                  _ModuleCard(
                    icon: Icons.fingerprint_rounded,
                    label: 'Attendance',
                    subtitle: isReady ? 'Check in / out' : 'Loading…',
                    color: AppTheme.success,
                    disabled: !isReady,
                    onTap: isReady
                        ? () => context.push('/staff/attendance/$staffId')
                        : null,
                  ),
                  _ModuleCard(
                    icon: Icons.assignment_rounded,
                    label: 'My Duties',
                    subtitle: isReady ? 'View & complete' : 'Loading…',
                    color: AppTheme.primary,
                    disabled: !isReady,
                    onTap: isReady
                        ? () => context.push('/staff/duties/$staffId')
                        : null,
                  ),
                  _ModuleCard(
                    icon: Icons.swap_horiz_rounded,
                    label: 'Handover',
                    subtitle: isReady ? 'Create & accept' : 'Loading…',
                    color: AppTheme.warning,
                    disabled: !isReady,
                    onTap: isReady
                        ? () => context.push(
                            '/staff/handover/$staffId',
                            extra: societyId ?? '',
                          )
                        : null,
                  ),
                  const _ModuleCard(
                    icon: Icons.task_alt_rounded,
                    label: 'Tasks',
                    subtitle: 'Coming soon',
                    color: AppTheme.textSecondary,
                    disabled: true,
                    onTap: null,
                  ),
                ],
              ),

              // ── Management (supervisors / managers only) ───────────────────
              if (showManagement) ...[
                const SizedBox(height: 24),
                const SectionHeader(title: 'Management'),
                const SizedBox(height: 14),
                GridView.count(
                  crossAxisCount: 2,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  mainAxisSpacing: 12,
                  crossAxisSpacing: 12,
                  childAspectRatio: 1.1,
                  children: [
                    _ModuleCard(
                      icon: Icons.approval_rounded,
                      label: 'Approvals',
                      subtitle: 'Punch-in & out',
                      color: AppTheme.error,
                      onTap: () =>
                          context.push('/staff/approvals', extra: societyId),
                    ),
                    _ModuleCard(
                      icon: Icons.badge_rounded,
                      label: 'My Staff',
                      subtitle: 'View team',
                      color: AppTheme.secondary,
                      onTap: () => context.push('/staff/list'),
                    ),
                    _ModuleCard(
                      icon: Icons.assignment_turned_in_rounded,
                      label: 'Assign Duty',
                      subtitle: 'To staff member',
                      color: AppTheme.primary,
                      onTap: () => context.push(
                        '/staff/assign-duty',
                        extra: {'societyId': societyId},
                      ),
                    ),
                    if (isManager)
                      _ModuleCard(
                        icon: Icons.report_problem_rounded,
                        label: 'Complaints',
                        subtitle: 'Assign to dept',
                        color: AppTheme.warning,
                        onTap: () => context.push('/complaints'),
                      ),
                  ],
                ),
              ],

              const SizedBox(height: 20),
            ],
          ),
        ),
      ),
    );
  }

  void _logout(BuildContext context, WidgetRef ref) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Sign out?'),
        content: const Text('You will be returned to the login screen.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () {
              Navigator.pop(ctx);
              ref.read(authProvider.notifier).logout();
            },
            child: const Text('Sign out'),
          ),
        ],
      ),
    );
  }
}

// ── Staff profile resolution banner ──────────────────────────────────────────

/// Shows a contextual banner while the staff profile is loading, errored, or
/// not found. Disappears once the staffId is successfully resolved.
class _StaffProfileStatus extends ConsumerWidget {
  final AsyncValue<StaffEntity?> staffAsync;
  final String? staffId;

  const _StaffProfileStatus({
    required this.staffAsync,
    required this.staffId,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (staffId != null) return const SizedBox.shrink();

    final Color color;
    final IconData icon;
    final String title;
    final String subtitle;
    final Widget? trailing;

    if (staffAsync.isLoading) {
      color    = AppTheme.primary;
      icon     = Icons.sync_rounded;
      title    = 'Loading your staff profile…';
      subtitle = 'Operational modules will be ready in a moment.';
      trailing = const SizedBox(
        width: 18,
        height: 18,
        child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.primary),
      );
    } else if (staffAsync.hasError) {
      color    = AppTheme.error;
      icon     = Icons.error_outline_rounded;
      title    = 'Could not load staff profile';
      subtitle = 'Check your connection, then pull down to retry.';
      trailing = TextButton(
        onPressed: () => ref.invalidate(currentStaffProvider),
        style: TextButton.styleFrom(
          foregroundColor: AppTheme.primary,
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        ),
        child: const Text('Retry', style: TextStyle(fontSize: 12)),
      );
    } else {
      // Resolved but staff returned null — no staff record linked to this user
      color    = AppTheme.warning;
      icon     = Icons.person_off_rounded;
      title    = 'No staff profile linked';
      subtitle = 'Ask your administrator to link your account to a staff record.';
      trailing = null;
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Row(
          children: [
            Icon(icon, color: color, size: 18),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title,
                      style: TextStyle(
                          fontWeight: FontWeight.w600,
                          fontSize: 13,
                          color: color)),
                  const SizedBox(height: 2),
                  Text(subtitle,
                      style: const TextStyle(
                          fontSize: 11, color: AppTheme.textSecondary)),
                ],
              ),
            ),
            if (trailing != null) ...[const SizedBox(width: 8), trailing],
          ],
        ),
      ),
    );
  }
}

// ── Module card ───────────────────────────────────────────────────────────────

class _ModuleCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String subtitle;
  final Color color;
  final VoidCallback? onTap;
  final bool disabled;

  const _ModuleCard({
    required this.icon,
    required this.label,
    required this.subtitle,
    required this.color,
    this.onTap,
    this.disabled = false,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: disabled ? null : onTap,
      child: AnimatedOpacity(
        duration: const Duration(milliseconds: 250),
        opacity: disabled ? 0.45 : 1.0,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.cardBg,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: disabled ? AppTheme.border : AppTheme.border,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: color.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: color, size: 22),
              ),
              const Spacer(),
              Text(label,
                  style: const TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                      color: AppTheme.textPrimary)),
              const SizedBox(height: 2),
              Text(subtitle,
                  style: const TextStyle(
                      fontSize: 11, color: AppTheme.textSecondary)),
            ],
          ),
        ),
      ),
    );
  }
}
