import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';

// ── Shared scaffold wrapper ───────────────────────────────────────────────────

class _DashboardShell extends ConsumerWidget {
  final String title;
  final List<Widget> children;

  const _DashboardShell({required this.title, required this.children});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text(title),
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
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: children,
        ),
      ),
    );
  }

  Future<void> _confirmLogout(BuildContext context, WidgetRef ref) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Sign out?'),
        content: const Text('You will be returned to the login screen.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Sign out'),
          ),
        ],
      ),
    );
    if (ok == true) ref.read(authProvider.notifier).logout();
  }
}

// ── Shared components ─────────────────────────────────────────────────────────

class _GreetingCard extends StatelessWidget {
  final UserEntity? user;
  final String subtitle;

  const _GreetingCard({required this.user, required this.subtitle});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
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
            'Hello, ${user?.fullName.split(' ').first ?? 'User'}!',
            style: const TextStyle(
                color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(subtitle,
              style: TextStyle(
                  color: Colors.white.withOpacity(0.85), fontSize: 13)),
          const SizedBox(height: 2),
          Text(user?.email ?? '',
              style: TextStyle(
                  color: Colors.white.withOpacity(0.6), fontSize: 12)),
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(text,
        style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: AppTheme.textSecondary));
  }
}

class _ActionItem {
  final IconData icon;
  final String label;
  final Color color;
  final String? badge;
  const _ActionItem(
      {required this.icon,
      required this.label,
      required this.color,
      this.badge});
}

class _ModuleGrid extends StatelessWidget {
  final List<_ActionItem> items;
  const _ModuleGrid({required this.items});

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisSpacing: 12,
        crossAxisSpacing: 12,
        childAspectRatio: 1.15,
      ),
      itemCount: items.length,
      itemBuilder: (_, i) {
        final item = items[i];
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.cardBg,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppTheme.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: item.color.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(item.icon, color: item.color, size: 20),
                  ),
                  if (item.badge != null) ...[
                    const Spacer(),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppTheme.error,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(item.badge!,
                          style: const TextStyle(
                              color: Colors.white,
                              fontSize: 10,
                              fontWeight: FontWeight.w600)),
                    ),
                  ],
                ],
              ),
              const Spacer(),
              Text(item.label,
                  style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary)),
            ],
          ),
        );
      },
    );
  }
}

class _InfoTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String value;
  final Color color;

  const _InfoTile(
      {required this.icon,
      required this.title,
      required this.value,
      required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: color.withOpacity(0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: color, size: 18),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                  style: const TextStyle(
                      fontSize: 11, color: AppTheme.textSecondary)),
              const SizedBox(height: 2),
              Text(value,
                  style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary)),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatusBar extends StatelessWidget {
  final UserEntity? user;
  const _StatusBar({required this.user});

  @override
  Widget build(BuildContext context) {
    if (user == null) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppTheme.success.withOpacity(0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.success.withOpacity(0.2)),
      ),
      child: Row(
        children: [
          Icon(Icons.check_circle_outline, color: AppTheme.success, size: 14),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              'Authenticated · Roles: ${user!.roles.join(", ")}',
              style: TextStyle(fontSize: 10, color: AppTheme.success),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Admin Dashboard ───────────────────────────────────────────────────────────

class AdminDashboardScreen extends ConsumerWidget {
  const AdminDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    return _DashboardShell(
      title: 'Admin Dashboard',
      children: [
        _GreetingCard(user: user, subtitle: 'Administrator · Full Access'),
        const SizedBox(height: 20),
        const _SectionLabel('Society Management'),
        const SizedBox(height: 12),
        _ModuleGrid(items: const [
          _ActionItem(icon: Icons.people_rounded,
              label: 'Users & Roles', color: AppTheme.primary),
          _ActionItem(icon: Icons.apartment_rounded,
              label: 'Society Settings', color: AppTheme.secondary),
          _ActionItem(icon: Icons.receipt_long_rounded,
              label: 'Billing', color: AppTheme.success),
          _ActionItem(icon: Icons.bar_chart_rounded,
              label: 'Reports', color: AppTheme.warning),
        ]),
        const SizedBox(height: 20),
        const _SectionLabel('Operations'),
        const SizedBox(height: 12),
        _ModuleGrid(items: const [
          _ActionItem(icon: Icons.badge_rounded,
              label: 'Staff', color: AppTheme.primary),
          _ActionItem(icon: Icons.meeting_room_rounded,
              label: 'Visitors', color: AppTheme.secondary),
          _ActionItem(icon: Icons.inventory_2_rounded,
              label: 'Inventory', color: AppTheme.warning),
          _ActionItem(icon: Icons.campaign_rounded,
              label: 'Notices', color: AppTheme.success),
        ]),
        const SizedBox(height: 20),
        _StatusBar(user: user),
      ],
    );
  }
}

// ── Committee Dashboard ───────────────────────────────────────────────────────

class CommitteeDashboardScreen extends ConsumerWidget {
  const CommitteeDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    return _DashboardShell(
      title: 'Committee Dashboard',
      children: [
        _GreetingCard(user: user, subtitle: 'Committee Member'),
        const SizedBox(height: 20),
        const _SectionLabel('Approvals & Governance'),
        const SizedBox(height: 12),
        _ModuleGrid(items: const [
          _ActionItem(icon: Icons.approval_rounded,
              label: 'Complaints', color: AppTheme.error),
          _ActionItem(icon: Icons.campaign_rounded,
              label: 'Notices', color: AppTheme.primary),
          _ActionItem(icon: Icons.receipt_long_rounded,
              label: 'Billing', color: AppTheme.success),
          _ActionItem(icon: Icons.people_rounded,
              label: 'Staff', color: AppTheme.warning),
        ]),
        const SizedBox(height: 20),
        const _SectionLabel('Gate & Facility'),
        const SizedBox(height: 12),
        _ModuleGrid(items: const [
          _ActionItem(icon: Icons.meeting_room_rounded,
              label: 'Visitors', color: AppTheme.secondary),
          _ActionItem(icon: Icons.local_parking_rounded,
              label: 'Parking', color: AppTheme.primary),
          _ActionItem(icon: Icons.sports_tennis_rounded,
              label: 'Amenities', color: AppTheme.success),
          _ActionItem(icon: Icons.inventory_2_rounded,
              label: 'Inventory', color: AppTheme.warning),
        ]),
        const SizedBox(height: 20),
        _StatusBar(user: user),
      ],
    );
  }
}

// ── Security Dashboard ────────────────────────────────────────────────────────

class SecurityDashboardScreen extends ConsumerWidget {
  const SecurityDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    return _DashboardShell(
      title: 'Security Dashboard',
      children: [
        _GreetingCard(user: user, subtitle: 'Security Officer · Gate Operations'),
        const SizedBox(height: 20),
        const _SectionLabel('Gate Operations'),
        const SizedBox(height: 12),
        _ModuleGrid(items: const [
          _ActionItem(icon: Icons.person_add_rounded,
              label: 'Log Visitor', color: AppTheme.primary),
          _ActionItem(icon: Icons.login_rounded,
              label: 'Check In', color: AppTheme.success),
          _ActionItem(icon: Icons.logout_rounded,
              label: 'Check Out', color: AppTheme.warning),
          _ActionItem(icon: Icons.list_alt_rounded,
              label: 'Visitor Log', color: AppTheme.secondary),
        ]),
        const SizedBox(height: 20),
        const _SectionLabel('Shift Management'),
        const SizedBox(height: 12),
        Row(
          children: const [
            Expanded(
              child: _InfoTile(
                icon: Icons.swap_horiz_rounded,
                title: 'Handover',
                value: 'Shift Takeover',
                color: AppTheme.warning,
              ),
            ),
            SizedBox(width: 12),
            Expanded(
              child: _InfoTile(
                icon: Icons.local_parking_rounded,
                title: 'Parking',
                value: 'Gate Entry',
                color: AppTheme.primary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 20),
        _StatusBar(user: user),
      ],
    );
  }
}

// ── Resident Dashboard ────────────────────────────────────────────────────────

class ResidentDashboardScreen extends ConsumerWidget {
  const ResidentDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    return _DashboardShell(
      title: 'Resident Dashboard',
      children: [
        _GreetingCard(user: user, subtitle: 'Resident'),
        const SizedBox(height: 20),
        const _SectionLabel('My Services'),
        const SizedBox(height: 12),
        _ModuleGrid(items: const [
          _ActionItem(icon: Icons.report_problem_rounded,
              label: 'Complaints', color: AppTheme.error),
          _ActionItem(icon: Icons.campaign_rounded,
              label: 'Notices', color: AppTheme.primary),
          _ActionItem(icon: Icons.receipt_long_rounded,
              label: 'My Bills', color: AppTheme.warning),
          _ActionItem(icon: Icons.sports_tennis_rounded,
              label: 'Amenities', color: AppTheme.success),
        ]),
        const SizedBox(height: 20),
        const _SectionLabel('Visitors & Parking'),
        const SizedBox(height: 12),
        _ModuleGrid(items: const [
          _ActionItem(icon: Icons.person_rounded,
              label: 'My Visitors', color: AppTheme.secondary),
          _ActionItem(icon: Icons.pending_actions_rounded,
              label: 'Pending Approvals', color: AppTheme.warning),
          _ActionItem(icon: Icons.local_parking_rounded,
              label: 'My Parking', color: AppTheme.primary),
          _ActionItem(icon: Icons.home_rounded,
              label: 'My Flat', color: AppTheme.success),
        ]),
        const SizedBox(height: 20),
        _StatusBar(user: user),
      ],
    );
  }
}
