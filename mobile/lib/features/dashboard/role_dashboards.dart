import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/onboarding/presentation/providers/trial_status_provider.dart';

// ── Shared scaffold wrapper ───────────────────────────────────────────────────

class _DashboardShell extends ConsumerWidget {
  final String title;
  final List<Widget> children;

  const _DashboardShell({required this.title, required this.children});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final menuItems = <_MenuItem>[
      _MenuItem('Users & Roles', Icons.people_rounded, AppRoutes.usersList),
      _MenuItem('Society Settings', Icons.apartment_rounded, AppRoutes.societySettings),
      _MenuItem('Visitors', Icons.meeting_room_rounded, AppRoutes.visitorsMy),
      _MenuItem('Complaints', Icons.report_problem_rounded, AppRoutes.complaints),
      _MenuItem('Staff', Icons.badge_rounded, AppRoutes.staffHome),
      _MenuItem('Setup Wizard', Icons.checklist_rounded, AppRoutes.setupWizard),
    ];

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.menu_rounded),
          tooltip: 'Open menu',
          onPressed: () => Scaffold.of(context).openDrawer(),
        ),
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
      drawer: Drawer(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.symmetric(vertical: 12),
            children: [
              const Padding(
                padding: EdgeInsets.fromLTRB(16, 8, 16, 8),
                child: Text('Navigation', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              ),
              const Divider(),
              ...menuItems.map((item) => ListTile(
                    leading: Icon(item.icon, color: AppTheme.primary),
                    title: Text(item.label),
                    onTap: () {
                      Navigator.pop(context);
                      if (item.route != null) context.push(item.route!);
                    },
                  )),
            ],
          ),
        ),
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

class _MenuItem {
  final String label;
  final IconData icon;
  final String? route;

  const _MenuItem(this.label, this.icon, this.route);
}

class _GreetingCard extends StatelessWidget {
  final UserEntity? user;
  final String subtitle;

  const _GreetingCard({required this.user, required this.subtitle});

  @override
  Widget build(BuildContext context) {
    final today = DateTime.now();
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppTheme.primary, AppTheme.primaryDark],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Welcome back', style: TextStyle(color: Colors.white.withOpacity(0.9), fontSize: 12)),
          const SizedBox(height: 2),
          Text(user?.fullName ?? 'Society User', style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text(subtitle, style: TextStyle(color: Colors.white.withOpacity(0.88), fontSize: 13)),
          const SizedBox(height: 6),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _chip('Society Name', 'Airtel Society'),
              _chip('Role', user?.roles.firstOrNull ?? 'Member'),
              _chip('Date', '${today.day}/${today.month}/${today.year}'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _chip(String label, String value) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(color: Colors.white.withOpacity(0.12), borderRadius: BorderRadius.circular(999)),
        child: Text('$label: $value', style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w600)),
      );
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
  final String? route;
  const _ActionItem({
    required this.icon,
    required this.label,
    required this.color,
    this.badge,
    this.route,
  });
}

class _SummaryCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  const _SummaryCard({required this.icon, required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Container(width: 36, height: 36, decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(10)), child: Icon(icon, color: color, size: 18)),
            const Spacer(),
            Icon(Icons.trending_up_rounded, color: color.withOpacity(0.8), size: 14),
          ]),
          const SizedBox(height: 10),
          Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ],
      ),
    );
  }
}

class _QuickActionChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? route;

  const _QuickActionChip({required this.icon, required this.label, this.route});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: InkWell(
        onTap: route == null ? null : () => context.push(route!),
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppTheme.border)),
          child: Column(children: [Icon(icon, color: AppTheme.primary), const SizedBox(height: 6), Text(label, textAlign: TextAlign.center, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.textPrimary))]),
        ),
      ),
    );
  }
}

class _OperationalPanel extends StatelessWidget {
  final String title;
  final List<Widget> children;
  const _OperationalPanel({required this.title, required this.children});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(16), border: Border.all(color: AppTheme.border)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
        const SizedBox(height: 10),
        ...children,
      ]),
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

// ── Trial Status Widget ───────────────────────────────────────────────────────

class _TrialStatusWidget extends StatelessWidget {
  final int daysRemaining;
  final bool isExpired;
  final bool isWarning;
  final bool isCritical;

  const _TrialStatusWidget({
    required this.daysRemaining,
    required this.isExpired,
    required this.isWarning,
    required this.isCritical,
  });

  @override
  Widget build(BuildContext context) {
    Color bannerColor;
    IconData bannerIcon;
    String bannerTitle;
    String bannerSubtitle;

    if (isExpired) {
      bannerColor = AppTheme.error;
      bannerIcon  = Icons.warning_amber_rounded;
      bannerTitle = 'Trial Expired';
      bannerSubtitle = 'Contact support to continue using AR Society.';
    } else if (isCritical) {
      bannerColor = AppTheme.error;
      bannerIcon  = Icons.timer_rounded;
      bannerTitle = '$daysRemaining days left in trial';
      bannerSubtitle = 'Your trial ends soon — upgrade now to avoid disruption.';
    } else if (isWarning) {
      bannerColor = AppTheme.warning;
      bannerIcon  = Icons.access_time_rounded;
      bannerTitle = '$daysRemaining days left in trial';
      bannerSubtitle = 'Consider upgrading to a paid plan.';
    } else {
      bannerColor = AppTheme.success;
      bannerIcon  = Icons.check_circle_outline_rounded;
      bannerTitle = 'Trial Active — $daysRemaining days remaining';
      bannerSubtitle = 'Enjoy full access during your free trial.';
    }

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: bannerColor.withOpacity(0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: bannerColor.withOpacity(0.25)),
      ),
      child: Row(
        children: [
          Icon(bannerIcon, color: bannerColor, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  bannerTitle,
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                    color: bannerColor,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  bannerSubtitle,
                  style: TextStyle(
                      fontSize: 11, color: AppTheme.textSecondary),
                ),
              ],
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
    final societyId = user?.societyId;

    Widget trialBanner = const SizedBox.shrink();
    if (societyId != null) {
      final trialAsync = ref.watch(trialStatusProvider(societyId));
      trialBanner = trialAsync.when(
        data: (trial) => trial.isTrial || trial.trialExpired
            ? Column(children: [
                _TrialStatusWidget(
                  daysRemaining: trial.trialDaysRemaining,
                  isExpired: trial.trialExpired,
                  isWarning: trial.expiryWarning,
                  isCritical: trial.expiryCritical,
                ),
                const SizedBox(height: 16),
              ])
            : const SizedBox.shrink(),
        loading: () => const SizedBox.shrink(),
        error: (_, __) => const SizedBox.shrink(),
      );
    }

    return _DashboardShell(
      title: 'Society Overview',
      children: [
        _GreetingCard(user: user, subtitle: 'Society Admin · Operational dashboard'),
        const SizedBox(height: 18),
        trialBanner,
        const _SectionLabel('Summary'),
        const SizedBox(height: 10),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.12,
          children: const [
            _SummaryCard(icon: Icons.apartment_rounded, label: 'Total Flats', value: '128', color: AppTheme.primary),
            _SummaryCard(icon: Icons.home_rounded, label: 'Occupied Flats', value: '96', color: AppTheme.success),
            _SummaryCard(icon: Icons.people_rounded, label: 'Residents', value: '324', color: AppTheme.secondary),
            _SummaryCard(icon: Icons.badge_rounded, label: 'Active Staff', value: '24', color: AppTheme.warning),
            _SummaryCard(icon: Icons.meeting_room_rounded, label: 'Visitors Today', value: '18', color: AppTheme.primary),
            _SummaryCard(icon: Icons.report_problem_rounded, label: 'Open Complaints', value: '7', color: AppTheme.error),
            _SummaryCard(icon: Icons.approval_rounded, label: 'Pending Approvals', value: '3', color: AppTheme.warning),
            _SummaryCard(icon: Icons.campaign_rounded, label: 'Notice Count', value: '5', color: AppTheme.secondary),
          ],
        ),
        const SizedBox(height: 18),
        const _SectionLabel('Quick Actions'),
        const SizedBox(height: 10),
        Row(children: const [
          _QuickActionChip(icon: Icons.person_add_rounded, label: 'Add Visitor', route: AppRoutes.visitorsCreate),
          SizedBox(width: 8),
          _QuickActionChip(icon: Icons.report_problem_rounded, label: 'Create Complaint', route: AppRoutes.complaints),
          SizedBox(width: 8),
          _QuickActionChip(icon: Icons.badge_rounded, label: 'Add Staff', route: AppRoutes.staffHome),
          SizedBox(width: 8),
          _QuickActionChip(icon: Icons.campaign_rounded, label: 'Add Notice', route: AppRoutes.complaintsCreate),
        ]),
        const SizedBox(height: 18),
        _OperationalPanel(title: 'Recent Complaints', children: const [
          _InfoTile(icon: Icons.receipt_long_rounded, title: 'CMP-1042', value: 'Water leakage · In progress', color: AppTheme.warning),
          SizedBox(height: 8),
          _InfoTile(icon: Icons.electric_bolt_rounded, title: 'CMP-1040', value: 'Power issue · Open', color: AppTheme.error),
        ]),
        const SizedBox(height: 12),
        _OperationalPanel(title: 'Today\'s Visitors', children: const [
          _InfoTile(icon: Icons.person_rounded, title: 'Ravi Sharma', value: 'Flat A-204 · Approved', color: AppTheme.primary),
          SizedBox(height: 8),
          _InfoTile(icon: Icons.person_outline_rounded, title: 'Neha Verma', value: 'Flat B-110 · Checked In', color: AppTheme.success),
        ]),
        const SizedBox(height: 12),
        _OperationalPanel(title: 'Staff On Duty', children: const [
          _InfoTile(icon: Icons.badge_rounded, title: 'A. Khan', value: 'Security · Night Shift', color: AppTheme.secondary),
          SizedBox(height: 8),
          _InfoTile(icon: Icons.cleaning_services_rounded, title: 'M. Rao', value: 'Housekeeping · Morning Shift', color: AppTheme.warning),
        ]),
        const SizedBox(height: 18),
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
      title: 'Chairman Dashboard',
      children: [
        _GreetingCard(user: user, subtitle: 'Committee Chairman · Governance overview'),
        const SizedBox(height: 18),
        const _SectionLabel('Overview'),
        const SizedBox(height: 10),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.12,
          children: const [
            _SummaryCard(icon: Icons.report_problem_rounded, label: 'Complaints', value: '7', color: AppTheme.error),
            _SummaryCard(icon: Icons.campaign_rounded, label: 'Notices', value: '5', color: AppTheme.primary),
            _SummaryCard(icon: Icons.approval_rounded, label: 'Approvals', value: '3', color: AppTheme.warning),
            _SummaryCard(icon: Icons.people_rounded, label: 'Staff', value: '24', color: AppTheme.secondary),
          ],
        ),
        const SizedBox(height: 18),
        const _SectionLabel('Quick Actions'),
        const SizedBox(height: 10),
        Row(children: const [
          _QuickActionChip(icon: Icons.report_problem_rounded, label: 'Complaints', route: AppRoutes.complaints),
          SizedBox(width: 8),
          _QuickActionChip(icon: Icons.campaign_rounded, label: 'Updates', route: AppRoutes.societySettings),
          SizedBox(width: 8),
          _QuickActionChip(icon: Icons.people_rounded, label: 'Staff', route: AppRoutes.staffHome),
          SizedBox(width: 8),
          _QuickActionChip(icon: Icons.meeting_room_rounded, label: 'Visitors', route: AppRoutes.visitorsMy),
        ]),
        const SizedBox(height: 18),
        _OperationalPanel(title: 'Open actions', children: const [
          _InfoTile(icon: Icons.pending_actions_rounded, title: 'Pending approvals', value: '3 items need review', color: AppTheme.warning),
          SizedBox(height: 8),
          _InfoTile(icon: Icons.gpp_good_rounded, title: 'Society status', value: 'All core services running', color: AppTheme.success),
        ]),
        const SizedBox(height: 18),
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
      title: 'Security Supervisor',
      children: [
        _GreetingCard(user: user, subtitle: 'Security Supervisor · Gate and visitor operations'),
        const SizedBox(height: 18),
        const _SectionLabel('Today'),
        const SizedBox(height: 10),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.12,
          children: const [
            _SummaryCard(icon: Icons.people_rounded, label: 'Visitors Today', value: '18', color: AppTheme.primary),
            _SummaryCard(icon: Icons.login_rounded, label: 'Check-ins', value: '12', color: AppTheme.success),
            _SummaryCard(icon: Icons.local_parking_rounded, label: 'Parking Entries', value: '9', color: AppTheme.secondary),
            _SummaryCard(icon: Icons.shield_rounded, label: 'Duty Status', value: 'On Duty', color: AppTheme.warning),
          ],
        ),
        const SizedBox(height: 18),
        const _SectionLabel('Quick Actions'),
        const SizedBox(height: 10),
        Row(children: const [
          _QuickActionChip(icon: Icons.person_add_rounded, label: 'Log Visitor', route: AppRoutes.visitorsCreate),
          SizedBox(width: 8),
          _QuickActionChip(icon: Icons.login_rounded, label: 'Check In', route: AppRoutes.visitorsPending),
          SizedBox(width: 8),
          _QuickActionChip(icon: Icons.logout_rounded, label: 'Check Out', route: AppRoutes.visitorsMy),
          SizedBox(width: 8),
          _QuickActionChip(icon: Icons.list_alt_rounded, label: 'Visitor Log', route: AppRoutes.visitorsMy),
        ]),
        const SizedBox(height: 18),
        _OperationalPanel(title: 'Shift Notes', children: const [
          _InfoTile(icon: Icons.swap_horiz_rounded, title: 'Handover', value: 'Shift handover confirmed', color: AppTheme.warning),
          SizedBox(height: 8),
          _InfoTile(icon: Icons.gpp_good_rounded, title: 'Security status', value: 'All gates monitored', color: AppTheme.success),
        ]),
        const SizedBox(height: 18),
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
        _GreetingCard(user: user, subtitle: 'Resident · Day-to-day services'),
        const SizedBox(height: 18),
        const _SectionLabel('Summary'),
        const SizedBox(height: 10),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.12,
          children: const [
            _SummaryCard(icon: Icons.report_problem_rounded, label: 'Open Complaints', value: '2', color: AppTheme.error),
            _SummaryCard(icon: Icons.campaign_rounded, label: 'Notices', value: '3', color: AppTheme.primary),
            _SummaryCard(icon: Icons.receipt_long_rounded, label: 'Bills', value: '1 pending', color: AppTheme.warning),
            _SummaryCard(icon: Icons.home_rounded, label: 'My Flat', value: 'A-204', color: AppTheme.success),
          ],
        ),
        const SizedBox(height: 18),
        const _SectionLabel('Quick Actions'),
        const SizedBox(height: 10),
        Row(children: const [
          _QuickActionChip(icon: Icons.report_problem_rounded, label: 'Complaint', route: AppRoutes.complaints),
          SizedBox(width: 8),
          _QuickActionChip(icon: Icons.campaign_rounded, label: 'Updates', route: AppRoutes.societySettings),
          SizedBox(width: 8),
          _QuickActionChip(icon: Icons.person_rounded, label: 'Visitors', route: AppRoutes.visitorsMy),
          SizedBox(width: 8),
          _QuickActionChip(icon: Icons.receipt_long_rounded, label: 'Settings', route: AppRoutes.societySettings),
        ]),
        const SizedBox(height: 18),
        _OperationalPanel(title: 'Recent updates', children: const [
          _InfoTile(icon: Icons.info_outline_rounded, title: 'Notice board', value: 'Community meeting scheduled', color: AppTheme.primary),
          SizedBox(height: 8),
          _InfoTile(icon: Icons.pending_actions_rounded, title: 'Pending approvals', value: 'Visitor entry approval', color: AppTheme.warning),
        ]),
        const SizedBox(height: 18),
        _StatusBar(user: user),
      ],
    );
  }
}
