import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/auth/biometric_preference.dart';
import 'package:ar_society_app/core/layout/app_shell.dart';
import 'package:ar_society_app/core/motion/motion.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/manager_checklist/presentation/widgets/checklist_widgets.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/auth/presentation/providers/biometric_provider.dart';
import 'package:ar_society_app/features/onboarding/presentation/providers/trial_status_provider.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/complaint/presentation/providers/complaint_providers.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart' show BillingCycle, amountOf, formatRupees;
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart' show billingCyclesProvider, myBillsProvider;
import 'package:ar_society_app/features/dashboard/admin_overview.dart';
import 'package:ar_society_app/features/dashboard/gate_summary.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart' show pendingVisitorApprovalsProvider;
import 'package:ar_society_app/features/visitor/presentation/widgets/pending_visitors_banner.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart' show flatByIdProvider;
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart' show ResidentModel;
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart' show myResidentProvider, myFlatsProvider, selectedFlatIdProvider;
import 'package:ar_society_app/core/layout/app_sheet.dart';

/// Whether this society has the optional service switched on (the platform owner may switch some off).
bool _on(UserEntity? u, String key) => u == null || u.hasService(key);

/// A row of quick actions that leaves out the null ones (services switched off for this society).
Widget _chipRow(List<Widget?> chips) {
  final shown = chips.whereType<Widget>().toList();
  if (shown.isEmpty) return const SizedBox.shrink();
  return Row(children: [
    for (var i = 0; i < shown.length; i++) ...[if (i > 0) const SizedBox(width: 8), shown[i]],
  ]);
}

/// Height of a summary tile. It grows with the text size the person has chosen, so large text is not cut off.
double _cardExtent(BuildContext context) => 148 * MediaQuery.textScalerOf(context).scale(1).clamp(1.0, 2.0);

/// What a count card shows: the number once loaded, '…' while loading, and '--' if the request failed.
/// A failed request is never drawn as 0.
String _countText(AsyncValue<int> a) => a.when(data: (n) => '$n', loading: () => '…', error: (_, __) => '--');

/// A summary card for a number the server provides. While the request has not succeeded the card is neutral;
/// if it failed, the card says so and tapping it asks again.
Widget _countCard({
  required IconData icon,
  required String label,
  required AsyncValue<int> count,
  required Color Function(int n) color,
  required VoidCallback retry,
  VoidCallback? onTap,
}) {
  final failed = count.hasError && !count.hasValue;
  return _SummaryCard(
    icon: icon,
    label: label,
    value: _countText(count),
    color: count.valueOrNull == null ? AppTheme.textSecondary : color(count.value!),
    note: failed ? 'Could not load. Tap to retry' : null,
    onTap: failed ? retry : onTap,
  );
}

/// One number out of the attendance summary: loaded, failed (including a reply that lacks the number), or loading.
AsyncValue<int> _summaryCount(AsyncValue<Map<String, dynamic>> a, String key) => a.when(
      data: (m) => m[key] is num
          ? AsyncValue.data((m[key] as num).toInt())
          : AsyncValue.error(Exception('missing $key'), StackTrace.empty),
      loading: () => const AsyncValue.loading(),
      error: (e, st) => AsyncValue.error(e, st),
    );

/// Pending-approvals state as a count: loaded, failed, or still loading (including between actions).
AsyncValue<int> _approvalCount(ApprovalState s, int Function(ApprovalLoaded) pick) => switch (s) {
      ApprovalLoaded() => AsyncValue.data(pick(s)),
      ApprovalError(:final message) => AsyncValue.error(Exception(message), StackTrace.empty),
      _ => const AsyncValue.loading(),
    };

// ── Shared scaffold wrapper ───────────────────────────────────────────────────

class _DashboardShell extends ConsumerWidget {
  final String title;
  final List<Widget> children;

  const _DashboardShell({required this.title, required this.children});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final myFormsAsync = ref.watch(myFormCodesProvider);
    final menuCategories = visibleMenuCategories(
      myFormsAsync.valueOrNull?.toSet() ?? const {},
      user: ref.watch(currentUserProvider),
    );
    // On desktop widths AppShell's sidebar and account menu already provide
    // navigation and sign-out.
    final desktop = isDesktopLayout(context);

    return AppPage(
      title: title,
      showBack: false,
      actions: [
        if (!desktop)
          IconButton(
            icon: const Icon(Icons.logout_rounded),
            tooltip: 'Sign out',
            onPressed: () => _confirmLogout(context, ref),
          ),
      ],
      drawer: desktop ? null : Drawer(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.symmetric(vertical: 12),
            children: [
              const Padding(
                padding: EdgeInsets.fromLTRB(16, 8, 16, 8),
                child: Text('Navigation', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              ),
              const Divider(height: 1),
              ...menuCategories.map((category) => Theme(
                    // Suppress the default divider ExpansionTile draws around
                    // itself when expanded — the drawer already separates
                    // sections with spacing, a second line reads as clutter.
                    data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                    child: ExpansionTile(
                      initiallyExpanded: true,
                      leading: Icon(category.icon, color: AppTheme.primary),
                      title: Text(category.label,
                          style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                      childrenPadding: const EdgeInsets.only(bottom: 4),
                      children: category.items
                          .map((item) => ListTile(
                                contentPadding: const EdgeInsets.only(left: 32, right: 16),
                                leading: Icon(item.icon, size: 20, color: AppTheme.textSecondary),
                                title: Text(item.label, style: const TextStyle(fontSize: 13)),
                                onTap: () {
                                  Navigator.pop(context);
                                  if (item.route != null) context.push(item.route!);
                                },
                              ))
                          .toList(),
                    ),
                  )),
            ],
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          const _BiometricEnrollTrigger(),
          // Sections arrive one after another rather than all at once.
          for (var i = 0; i < children.length; i++) AppReveal(index: i, child: children[i]),
        ],
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

// ── Biometric enrollment offer ────────────────────────────────────────────────
//
// Zero-UI widget dropped into _DashboardShell's body: on first mount, if
// ChangePasswordScreen just flagged a pending offer (i.e. the user was an
// auto-provisioned resident/tenant who just completed their forced password
// change) AND this device actually has usable biometric hardware, ask once
// whether to enable fingerprint/face unlock. A ConsumerWidget can't use
// initState, so this is its own tiny StatefulWidget rather than living
// directly in _DashboardShell.build(), which reruns on every rebuild.
class _BiometricEnrollTrigger extends ConsumerStatefulWidget {
  const _BiometricEnrollTrigger();

  @override
  ConsumerState<_BiometricEnrollTrigger> createState() => _BiometricEnrollTriggerState();
}

class _BiometricEnrollTriggerState extends ConsumerState<_BiometricEnrollTrigger> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybePrompt());
  }

  Future<void> _maybePrompt() async {
    final pending = await BiometricPreference.consumePromptPending();
    if (!pending || !mounted) return;

    final available = await ref.read(biometricServiceProvider).isAvailable();
    if (!available || !mounted) return;

    final enable = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        title: const Text('Enable Biometric Unlock?'),
        content: const Text(
          'Use your fingerprint or face to unlock the app next time, '
          'instead of typing your password.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Not now'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Enable'),
          ),
        ],
      ),
    );
    if (enable != true || !mounted) return;

    final confirmed = await ref
        .read(biometricServiceProvider)
        .authenticate('Confirm to enable biometric unlock');
    if (confirmed) {
      await BiometricPreference.setEnabled(true);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Biometric unlock enabled'),
          backgroundColor: AppTheme.success,
        ));
      }
    }
  }

  @override
  Widget build(BuildContext context) => const SizedBox.shrink();
}

// ── Shared components ─────────────────────────────────────────────────────────


class _GreetingCard extends ConsumerWidget {
  final UserEntity? user;
  final String subtitle;

  const _GreetingCard({required this.user, required this.subtitle});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final today = DateTime.now();
    final societyAsync = ref.watch(societyInfoProvider);
    final societyName = societyAsync.valueOrNull?.name ?? '—';

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
              _chip('Society', societyName),
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


// Thin wrapper over the shared KpiCard — kept as its own name since every
// dashboard below already calls _SummaryCard(...); redefining it here (once)
// gets all six dashboards onto the shared shadow-based card in one place
// rather than touching 34 call sites individually.
class _SummaryCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;
  final String? note;
  final VoidCallback? onTap;

  const _SummaryCard({
    required this.icon, required this.label, required this.value, required this.color, this.note, this.onTap,
  });

  @override
  Widget build(BuildContext context) =>
      KpiCard(icon: icon, label: label, value: value, color: color, note: note, onTap: onTap);
}

class _QuickActionChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? route;
  final VoidCallback? onTap;
  final int badge;

  const _QuickActionChip({required this.icon, required this.label, this.route, this.onTap, this.badge = 0});

  @override
  Widget build(BuildContext context) {
    final action = onTap ?? (route == null ? null : () => context.push(route!));
    final enabled = action != null;
    // A chip with nowhere to go (for example no society yet) looks and reads as unavailable instead of
    // looking like a button that does nothing.
    return Expanded(
      child: Semantics(
        button: true,
        enabled: enabled,
        label: badge > 0 ? '$label, $badge waiting' : label,
        excludeSemantics: true,
        onTap: action,
        child: Opacity(
          opacity: enabled ? 1 : 0.45,
          child: PressableScale(
            enabled: enabled,
            child: InkWell(
              onTap: action,
              borderRadius: BorderRadius.circular(12),
              child: Container(
                constraints: const BoxConstraints(minHeight: 56),
                padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 4),
                decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppTheme.border)),
                child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  Badge(
                    isLabelVisible: badge > 0,
                    label: Text('$badge'),
                    backgroundColor: AppTheme.error,
                    child: Icon(icon, color: AppTheme.primary),
                  ),
                  const SizedBox(height: 6),
                  Text(label, textAlign: TextAlign.center, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
                ]),
              ),
            ),
          ),
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
          // Expanded so a long message wraps instead of running off the tile.
          Expanded(
            child: Column(
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
      bannerSubtitle = 'Contact support to continue using DUX OS.';
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

    // The overview numbers come from one server call (AdminOverview); only the
    // active-staff count is read here.
    final staffListState = ref.watch(staffListProvider);
    if (societyId != null && _on(user, 'staff') && staffListState is StaffListInitial) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        ref.read(staffListProvider.notifier).load(societyId);
      });
    }
    final activeStaff = !_on(user, 'staff') ? null : (staffListState is StaffListLoaded ? '${staffListState.staff.length}' : '--');
    final societyComplaints = societyId == null ? AppRoutes.complaints : AppRoutes.complaintsSociety.replaceFirst(':societyId', societyId);

    return _DashboardShell(
      title: 'Society Overview',
      children: [
        _GreetingCard(user: user, subtitle: 'Society Admin · Operational dashboard'),
        const SizedBox(height: 18),
        trialBanner,
        if (societyId != null) AdminOverview(societyId: societyId, activeStaff: activeStaff),
        const SizedBox(height: 18),
        const _SectionLabel('Quick Actions'),
        const SizedBox(height: 10),
        _chipRow([
          if (_on(user, 'visitors'))
            _QuickActionChip(
              icon: Icons.person_add_rounded, label: 'Add Visitor',
              onTap: societyId != null
                  ? () => context.push(AppRoutes.visitorsCreate, extra: societyId)
                  : null,
            ),
          if (_on(user, 'complaints'))
            _QuickActionChip(icon: Icons.report_problem_rounded, label: 'Complaints', route: societyComplaints),
          if (_on(user, 'staff')) ...const [
            _QuickActionChip(icon: Icons.person_add_alt_1_rounded, label: 'Add Staff', route: AppRoutes.staffAdd),
            _QuickActionChip(icon: Icons.badge_rounded, label: 'Staff List', route: AppRoutes.staffList),
          ],
        ]),
        const SizedBox(height: 18),
      ],
    );
  }
}

// ── Committee Dashboard ───────────────────────────────────────────────────────

class CommitteeDashboardScreen extends ConsumerWidget {
  const CommitteeDashboardScreen({super.key});

  /// "Committee Chairman" -> "Chairman"; a plain "Committee" or "Committee Member" -> "Committee".
  static String _titleFor(UserEntity? user) {
    final role = (user?.roles ?? const <String>[]).firstWhere((r) => r.startsWith('Committee'), orElse: () => 'Committee');
    final rest = role.replaceFirst('Committee', '').trim();
    return rest.isEmpty || rest == 'Member' ? 'Committee' : rest;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final societyId = user?.societyId;
    final who = _titleFor(user);

    // The committee sees the same overview as the admin: one request to the same endpoint (which already allows
    // committee), so the money, collection and "needs attention" figures are the server's, and identical.
    final staffListState = ref.watch(staffListProvider);
    if (societyId != null && _on(user, 'staff') && staffListState is StaffListInitial) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        ref.read(staffListProvider.notifier).load(societyId);
      });
    }
    final activeStaff = !_on(user, 'staff') ? null : (staffListState is StaffListLoaded ? '${staffListState.staff.length}' : '--');

    return _DashboardShell(
      title: '$who Dashboard',
      children: [
        _GreetingCard(user: user, subtitle: '${who == 'Committee' ? 'Committee Member' : 'Committee $who'} · Governance overview'),
        const SizedBox(height: 18),
        if (societyId != null) AdminOverview(societyId: societyId, activeStaff: activeStaff),
        const SizedBox(height: 18),
        const _SectionLabel('Quick Actions'),
        const SizedBox(height: 10),
        // The committee runs the society, so these open the society-wide lists, as the menu does.
        _chipRow([
          if (_on(user, 'complaints'))
            _QuickActionChip(
              icon: Icons.report_problem_rounded,
              label: 'Complaints',
              route: societyId == null ? AppRoutes.complaints : AppRoutes.complaintsSociety.replaceFirst(':societyId', societyId),
            ),
          const _QuickActionChip(icon: Icons.settings_outlined, label: 'Society Info', route: AppRoutes.societySettings),
          if (_on(user, 'staff'))
            const _QuickActionChip(icon: Icons.people_rounded, label: 'Staff', route: AppRoutes.staffList),
          if (_on(user, 'visitors'))
            _QuickActionChip(
              icon: Icons.meeting_room_rounded,
              label: 'Visitors',
              route: societyId == null ? AppRoutes.visitorsMy : AppRoutes.visitorsSociety.replaceFirst(':societyId', societyId),
            ),
        ]),
        const SizedBox(height: 18),
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
    final societyId = user?.societyId;
    // The gate works from the society's visitor log (check in / out), not the
    // resident screens that only show visitors for one's own flat.
    final visitorLog = societyId == null
        ? AppRoutes.visitorsMy
        : AppRoutes.visitorsSociety.replaceFirst(':societyId', societyId);
    // A Security Supervisor lands here (see userRoleHome) and also runs a team, so the team shortcuts are here too.
    final isSupervisor = (user?.roles ?? const <String>[]).any((r) => r.contains('Supervisor'));

    // Today's figures come from the server (visitors only: there is no source for parking entries or duty status,
    // so those are not shown). A figure the server could not work out is shown as unavailable, never as 0.
    final gate = societyId == null || !_on(user, 'visitors')
        ? AsyncValue<GateSummary>.error(Exception('no society'), StackTrace.empty)
        : ref.watch(gateSummaryProvider(societyId));
    AsyncValue<int> gateCount(int? Function(GateSummary g) pick) => gate.when(
          data: (g) {
            final v = g.failed ? null : pick(g);
            return v == null
                ? AsyncValue<int>.error(Exception('unavailable'), StackTrace.empty)
                : AsyncValue<int>.data(v);
          },
          loading: () => const AsyncValue<int>.loading(),
          error: (e, st) => AsyncValue<int>.error(e, st),
        );
    void retryGate() { if (societyId != null) ref.invalidate(gateSummaryProvider(societyId)); }
    return _DashboardShell(
      title: 'Security Supervisor',
      children: [
        _GreetingCard(user: user, subtitle: 'Security Supervisor · Gate and visitor operations'),
        const SizedBox(height: 18),
        if (_on(user, 'visitors')) ...[
          const _SectionLabel('Today'),
          const SizedBox(height: 10),
          GridView(
            gridDelegate: SliverGridDelegateWithMaxCrossAxisExtent(
              maxCrossAxisExtent: 280,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              mainAxisExtent: _cardExtent(context),
            ),
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            children: [
              _countCard(
                icon: Icons.people_rounded, label: 'Visitors Today',
                count: gateCount((g) => g.visitorsToday), color: (_) => AppTheme.primary, retry: retryGate,
                onTap: () => context.push(visitorLog),
              ),
              _countCard(
                icon: Icons.login_rounded, label: 'Let In Today',
                count: gateCount((g) => g.checkedInToday), color: (_) => AppTheme.success, retry: retryGate,
                onTap: () => context.push(visitorLog),
              ),
              _countCard(
                icon: Icons.meeting_room_rounded, label: 'Inside Now',
                count: gateCount((g) => g.inside), color: (n) => n > 0 ? AppTheme.warning : AppTheme.success,
                retry: retryGate,
                onTap: () => context.push('$visitorLog?tab=inside'),
              ),
            ],
          ),
        ],
        const SizedBox(height: 18),
        const _SectionLabel('Quick Actions'),
        const SizedBox(height: 10),
        if (_on(user, 'visitors')) ...[
          _chipRow([
            _QuickActionChip(
              icon: Icons.person_add_rounded, label: 'Log Visitor',
              onTap: societyId != null
                  ? () => context.push(AppRoutes.visitorsCreate, extra: societyId)
                  : null,
            ),
            _QuickActionChip(icon: Icons.login_rounded, label: 'Check In', route: visitorLog),
            _QuickActionChip(icon: Icons.logout_rounded, label: 'Check Out', route: '$visitorLog?tab=inside'),
          ]),
          const SizedBox(height: 8),
        ],
        _chipRow([
          if (_on(user, 'visitors')) _QuickActionChip(icon: Icons.list_alt_rounded, label: 'Visitor Log', route: visitorLog),
          if (_on(user, 'parking'))
            const _QuickActionChip(icon: Icons.local_parking_rounded, label: 'Vehicle Gate', route: AppRoutes.parkingGateCheck),
        ]),
        if (isSupervisor && societyId != null && _on(user, 'staff')) ...[
          const SizedBox(height: 18),
          const _SectionLabel('My Team'),
          const SizedBox(height: 10),
          _chipRow([
            _QuickActionChip(
              icon: Icons.approval_rounded, label: 'Approvals',
              onTap: () => context.push(AppRoutes.staffApprovals,
                  extra: {'societyId': societyId, 'department': 'security'}),
            ),
            const _QuickActionChip(icon: Icons.badge_rounded, label: 'My Team', route: AppRoutes.staffList),
            _QuickActionChip(
              icon: Icons.assignment_turned_in_rounded, label: 'Assign Duty',
              onTap: () => context.push(AppRoutes.staffAssignDuty, extra: {'societyId': societyId}),
            ),
          ]),
        ],
        const SizedBox(height: 18),
        _OperationalPanel(title: 'Shift Notes', children: const [
          _InfoTile(icon: Icons.swap_horiz_rounded, title: 'Handover', value: 'Use Staff → Handover to log shift notes', color: AppTheme.warning),
          SizedBox(height: 8),
          _InfoTile(icon: Icons.gpp_good_rounded, title: 'Visitor log', value: 'Use visitor actions above to manage entries', color: AppTheme.success),
        ]),
        const SizedBox(height: 18),
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
    final waitingAsync = _on(user, 'visitors')
        ? ref.watch(pendingVisitorApprovalsProvider).whenData((v) => v.length)
        : const AsyncValue<int>.data(0);
    final waiting = waitingAsync.valueOrNull ?? 0;     // for the badge and text below; a failure shows no badge
    final openComplaints = _on(user, 'complaints') ? ref.watch(myOpenComplaintsCountProvider) : const AsyncValue<int>.data(0);
    final myFlatId = ref.watch(myResidentProvider).valueOrNull?.flatId;
    final myFlat = myFlatId == null ? null : ref.watch(flatByIdProvider(myFlatId)).valueOrNull;
    final residentLoaded = ref.watch(myResidentProvider).hasValue;
    final myFlats = ref.watch(myFlatsProvider).valueOrNull ?? const <ResidentModel>[];
    return _DashboardShell(
      title: 'Resident Dashboard',
      children: [
        _GreetingCard(user: user, subtitle: 'Resident · Day-to-day services'),
        if (residentLoaded && myFlatId == null) ...[
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppTheme.warning.withOpacity(0.10),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.warning.withOpacity(0.35)),
            ),
            child: const Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Icon(Icons.link_off_rounded, color: AppTheme.warning, size: 20),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Your login is not linked to a flat yet. Ask the society office to link it; '
                  'until then your bills and visitor approvals will not appear here.',
                  style: TextStyle(fontSize: 13, height: 1.4, color: AppTheme.textPrimary),
                ),
              ),
            ]),
          ),
        ],
        if (_on(user, 'visitors')) const PendingVisitorsBanner(padding: EdgeInsets.only(top: 14)),
        const SizedBox(height: 18),
        const _SectionLabel('Summary'),
        const SizedBox(height: 10),
        GridView(
          gridDelegate: SliverGridDelegateWithMaxCrossAxisExtent(
            maxCrossAxisExtent: 280,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            mainAxisExtent: _cardExtent(context),
          ),
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          children: [
            if (_on(user, 'complaints'))
              _countCard(
                icon: Icons.report_problem_rounded,
                label: 'Open Complaints',
                count: openComplaints,
                color: (_) => AppTheme.error,
                retry: () => ref.invalidate(myOpenComplaintsCountProvider),
                onTap: () => context.push(AppRoutes.complaints),
              ),
            if (_on(user, 'visitors'))
              _countCard(
                icon: Icons.how_to_reg_rounded,
                label: 'Visitors Waiting',
                count: waitingAsync,
                color: (_) => AppTheme.primary,
                retry: () => ref.invalidate(pendingVisitorApprovalsProvider),
                onTap: () => context.push(AppRoutes.visitorsPending),
              ),
            _SummaryCard(
              icon: Icons.receipt_long_rounded,
              label: 'Bills Due',
              value: ref.watch(myBillsProvider).when(
                    data: (s) => formatRupees(s.totalOutstanding),
                    loading: () => '…',
                    error: (_, __) => '--',
                  ),
              color: (ref.watch(myBillsProvider).valueOrNull?.overdueCount ?? 0) > 0
                  ? AppTheme.error
                  : AppTheme.warning,
              onTap: () => context.push(AppRoutes.myBills),
            ),
            _SummaryCard(
              icon: Icons.home_rounded,
              label: myFlats.length > 1 ? 'My Flat · tap to switch' : 'My Flat',
              value: myFlat?.displayName ?? (residentLoaded && myFlatId == null ? 'Not linked' : '…'),
              color: AppTheme.success,
              onTap: myFlats.length > 1 ? () => _pickFlat(context, myFlats) : null,
            ),
          ],
        ),
        const SizedBox(height: 18),
        const _SectionLabel('Quick Actions'),
        const SizedBox(height: 10),
        _chipRow([
          if (_on(user, 'complaints'))
            const _QuickActionChip(icon: Icons.report_problem_rounded, label: 'Complaint', route: AppRoutes.complaints),
          const _QuickActionChip(icon: Icons.edit_note_rounded, label: 'Edit My Info', route: AppRoutes.editMyProfile),
          if (_on(user, 'visitors'))
            const _QuickActionChip(icon: Icons.person_rounded, label: 'Visitors', route: AppRoutes.visitorsMy),
        ]),
        const SizedBox(height: 8),
        // "Society Info" was deliberately removed here — Society Settings is
        // Admin/Committee-only (see the Forms Matrix default grants), and
        // this dashboard shortcut used to bypass that: it opened the same
        // fully-editable settings screen with no read-only mode, so a
        // Resident could see (and be shown Save controls for) fields they
        // aren't allowed to change, only failing with a 403 on tapping Save.
        _chipRow([
          if (_on(user, 'visitors'))
            _QuickActionChip(icon: Icons.pending_actions_rounded, label: 'Approvals', route: AppRoutes.visitorsPending, badge: waiting),
          const _QuickActionChip(icon: Icons.receipt_long_rounded, label: 'My Bills', route: AppRoutes.myBills),
        ]),
        const SizedBox(height: 18),
        _OperationalPanel(title: 'Recent updates', children: [
          _InfoTile(
            icon: Icons.receipt_long_rounded,
            title: 'Maintenance',
            value: ref.watch(myBillsProvider).when(
                  data: (s) => s.openCount == 0
                      ? 'All bills paid'
                      : '${formatRupees(s.totalOutstanding)} due on ${s.openCount} bill${s.openCount == 1 ? '' : 's'}',
                  loading: () => '…',
                  error: (_, __) => 'Open My Bills to check',
                ),
            color: AppTheme.primary,
          ),
          if (_on(user, 'visitors')) ...[
            const SizedBox(height: 8),
            _InfoTile(
              icon: Icons.pending_actions_rounded,
              title: 'Visitor approvals',
              value: waitingAsync.when(
                data: (n) => n == 0 ? 'No one waiting' : '$n waiting at the gate',
                loading: () => '…',
                error: (_, __) => 'Could not check. Open Approvals',
              ),
              color: AppTheme.warning,
            ),
          ],
        ]),
        const SizedBox(height: 18),
      ],
    );
  }
}

/// A resident with several flats picks which one the dashboard shows.
void _pickFlat(BuildContext context, List<ResidentModel> flats) {
  showAppSheet(
    context: context,
    builder: (_) => SafeArea(
      child: Consumer(
        builder: (context, ref, _) {
          final current = ref.watch(myResidentProvider).valueOrNull?.flatId;
          return Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 20),
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('Your flats', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              const SizedBox(height: 10),
              for (final f in flats)
                Consumer(builder: (context, ref, _) {
                  final flat = ref.watch(flatByIdProvider(f.flatId)).valueOrNull;
                  return ListTile(
                    leading: Icon(f.flatId == current ? Icons.check_circle_rounded : Icons.home_outlined,
                        color: f.flatId == current ? AppTheme.success : AppTheme.textSecondary),
                    title: Text(flat?.displayName ?? 'Flat'),
                    onTap: () {
                      ref.read(selectedFlatIdProvider.notifier).state = f.flatId;
                      Navigator.of(context).pop();
                    },
                  );
                }),
            ]),
          );
        },
      ),
    ),
  );
}

class _DeptRow extends StatelessWidget {
  final String dept;
  final int present;
  final int absent;
  const _DeptRow({required this.dept, required this.present, required this.absent});

  String get _label {
    switch (dept) {
      case 'security':     return 'Security';
      case 'housekeeping': return 'Housekeeping';
      case 'technical':    return 'Technical';
      case 'gym':          return 'Gym';
      case 'admin':        return 'Administration';
      default:             return dept[0].toUpperCase() + dept.substring(1);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          flex: 3,
          child: Text(_label,
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
        ),
        _pill('$present present', AppTheme.success),
        const SizedBox(width: 6),
        _pill('$absent absent', AppTheme.error),
      ],
    );
  }

  Widget _pill(String label, Color color) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
    decoration: BoxDecoration(
      color: color.withOpacity(0.1),
      borderRadius: BorderRadius.circular(8),
    ),
    child: Text(label, style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w600)),
  );
}

// ── Manager Dashboard ─────────────────────────────────────────────────────────

class ManagerDashboardScreen extends ConsumerWidget {
  const ManagerDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user      = ref.watch(currentUserProvider);
    final societyId = user?.societyId;

    final approvalState = ref.watch(approvalProvider);
    if (societyId != null && _on(user, 'staff') && approvalState is ApprovalInitial) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        ref.read(approvalProvider.notifier).load(societyId);
      });
    }

    final staffListState = ref.watch(staffListProvider);
    if (societyId != null && _on(user, 'staff') && staffListState is StaffListInitial) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        ref.read(staffListProvider.notifier).load(societyId);
      });
    }

    final totalStaff = staffListState is StaffListLoaded ? '${staffListState.staff.length}' : '--';

    // Every number below comes from the server. While a request is loading or has failed the card says so
    // (and a failed one can be tapped to try again); it is never shown as 0.
    final noSociety = AsyncValue<int>.error(Exception('no society'), StackTrace.empty);
    final pendingCheckin  = _approvalCount(approvalState, (l) => l.pendingCheckin.length);
    final pendingCheckout = _approvalCount(approvalState, (l) => l.pendingCheckout.length);
    void retryApprovals() { if (societyId != null) ref.read(approvalProvider.notifier).load(societyId); }

    // Attendance summary for absent + late
    final summaryAsync = societyId != null && _on(user, 'staff')
        ? ref.watch(attendanceSummaryProvider(societyId))
        : AsyncValue<Map<String, dynamic>>.error(Exception('no society'), StackTrace.empty);
    final summary = summaryAsync.valueOrNull ?? const <String, dynamic>{};
    void retrySummary() { if (societyId != null) ref.invalidate(attendanceSummaryProvider(societyId)); }

    // Open complaints count
    final openComplaints = societyId != null && _on(user, 'complaints')
        ? ref.watch(openComplaintsCountProvider(societyId))
        : noSociety;

    // Duty assignment queue
    final dutiesAsync = societyId != null && _on(user, 'staff')
        ? ref.watch(societyDutiesProvider(societyId))
        : AsyncValue<List<DutyEntity>>.error(Exception('no society'), StackTrace.empty);
    final pendingDuties = dutiesAsync.whenData((d) => d.where((x) => !x.isCompleted).length);

    // Department breakdown from summary
    final deptBreakdown = (summary['department_breakdown'] as Map?)
        ?.cast<String, dynamic>() ?? {};

    // Maintenance billing — the manager runs it day to day
    final cycles = societyId == null ? null : ref.watch(billingCyclesProvider(societyId)).valueOrNull;
    String cycleSum(String Function(BillingCycle c) field) => cycles == null
        ? '--'
        : formatRupees('${cycles.fold<double>(0, (sum, c) => sum + amountOf(field(c)))}');
    final maintenanceDues = cycleSum((c) => c.totalOutstanding);
    final maintenanceCollected = cycleSum((c) => c.totalCollected);

    return _DashboardShell(
      title: 'Manager Dashboard',
      children: [
        _GreetingCard(user: user, subtitle: 'Manager · Operations & Approvals'),
        if (societyId != null && _on(user, 'checklist')) ...[const SizedBox(height: 14), ChecklistTodayCard(societyId: societyId)],
        const SizedBox(height: 18),
        if (_on(user, 'staff') || _on(user, 'complaints')) ...[
        const _SectionLabel('Today\'s Attendance'),
        const SizedBox(height: 10),
        GridView(
          gridDelegate: SliverGridDelegateWithMaxCrossAxisExtent(
            maxCrossAxisExtent: 280,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            mainAxisExtent: _cardExtent(context),
          ),
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          children: [
            if (_on(user, 'staff')) ...[
            _countCard(
              icon: Icons.login_rounded,
              label: 'Pending Check-in',
              count: pendingCheckin,
              color: (n) => n > 0 ? AppTheme.warning : AppTheme.success,
              retry: retryApprovals,
            ),
            _countCard(
              icon: Icons.logout_rounded,
              label: 'Pending Punch-out',
              count: pendingCheckout,
              color: (n) => n > 0 ? AppTheme.error : AppTheme.success,
              retry: retryApprovals,
            ),
            _countCard(
              icon: Icons.person_off_rounded,
              label: 'Absent Staff',
              count: _summaryCount(summaryAsync, 'absent'),
              color: (_) => AppTheme.error,
              retry: retrySummary,
            ),
            _countCard(
              icon: Icons.schedule_rounded,
              label: 'Late Staff',
              count: _summaryCount(summaryAsync, 'late'),
              color: (_) => AppTheme.warning,
              retry: retrySummary,
            ),
            _SummaryCard(icon: Icons.badge_rounded, label: 'Total Staff', value: totalStaff, color: AppTheme.primary),
            ],
            if (_on(user, 'complaints'))
              _countCard(
                icon: Icons.assignment_rounded,
                label: 'Open Complaints',
                count: openComplaints,
                color: (n) => n > 0 ? AppTheme.error : AppTheme.success,
                retry: () { if (societyId != null) ref.invalidate(openComplaintsCountProvider(societyId)); },
                onTap: () => context.push(AppRoutes.complaintsAssigned),
              ),
            if (_on(user, 'staff'))
              _countCard(
                icon: Icons.assignment_late_rounded,
                label: 'Duty Queue',
                count: pendingDuties,
                color: (n) => n > 0 ? AppTheme.warning : AppTheme.success,
                retry: () { if (societyId != null) ref.invalidate(societyDutiesProvider(societyId)); },
                onTap: societyId != null
                    ? () => context.push(AppRoutes.staffDutyOverview, extra: societyId)
                    : null,
              ),
          ],
        ),
        ],
        if (deptBreakdown.isNotEmpty) ...[
          const SizedBox(height: 18),
          const _SectionLabel('Department Summary'),
          const SizedBox(height: 10),
          _OperationalPanel(
            title: 'Attendance by Department',
            children: [
              for (final entry in deptBreakdown.entries)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _DeptRow(
                    dept: entry.key,
                    present: (entry.value as Map<String, dynamic>)['present'] as int? ?? 0,
                    absent: (entry.value as Map<String, dynamic>)['absent'] as int? ?? 0,
                  ),
                ),
            ],
          ),
        ],
        const SizedBox(height: 18),
        const _SectionLabel('Quick Actions'),
        const SizedBox(height: 10),
        _chipRow([
          if (_on(user, 'staff')) ...[
            _QuickActionChip(
              icon: Icons.approval_rounded, label: 'Approvals',
              onTap: societyId != null ? () => context.push(AppRoutes.staffApprovals, extra: societyId) : null,
            ),
            _QuickActionChip(icon: Icons.badge_rounded, label: 'Staff', route: AppRoutes.staffList),
            _QuickActionChip(
              icon: Icons.assignment_turned_in_rounded, label: 'Assign Duty',
              onTap: societyId != null
                  ? () => context.push(AppRoutes.staffAssignDuty, extra: {'societyId': societyId})
                  : null,
            ),
          ],
          if (_on(user, 'complaints'))
            _QuickActionChip(icon: Icons.report_problem_rounded, label: 'Complaints', route: AppRoutes.complaintsAssigned),
        ]),
        const SizedBox(height: 18),
        const _SectionLabel('Maintenance'),
        const SizedBox(height: 10),
        GridView(
          gridDelegate: SliverGridDelegateWithMaxCrossAxisExtent(
            maxCrossAxisExtent: 280,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            mainAxisExtent: _cardExtent(context),
          ),
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          children: [
            _SummaryCard(
              icon: Icons.account_balance_wallet_rounded,
              label: 'Maintenance Dues',
              value: maintenanceDues,
              color: AppTheme.error,
              onTap: () => context.push(AppRoutes.maintenanceBilling),
            ),
            _SummaryCard(
              icon: Icons.savings_rounded,
              label: 'Collected',
              value: maintenanceCollected,
              color: AppTheme.success,
              onTap: () => context.push(AppRoutes.maintenanceBilling),
            ),
          ],
        ),
        const SizedBox(height: 10),
        _chipRow([
          const _QuickActionChip(icon: Icons.receipt_long_rounded, label: 'Maintenance Billing', route: AppRoutes.maintenanceBilling),
          const _QuickActionChip(icon: Icons.payments_rounded, label: 'Online Payments', route: AppRoutes.onlinePayments),
          if (_on(user, 'vendors'))
            const _QuickActionChip(icon: Icons.request_quote_rounded, label: 'Vendor Bills', route: AppRoutes.vendorBills),
        ]),
        const SizedBox(height: 18),
      ],
    );
  }
}

// ── Supervisor Dashboard ──────────────────────────────────────────────────────

class SupervisorDashboardScreen extends ConsumerWidget {
  const SupervisorDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user      = ref.watch(currentUserProvider);
    final societyId = user?.societyId;
    final staffId   = ref.watch(staffIdProvider);

    // Detect department from role
    final roles = user?.roles ?? [];
    final isHousekeeping = roles.any((r) => r.toLowerCase().contains('housekeeping'));
    final isTechnical    = roles.any((r) => r.toLowerCase().contains('technical'));
    final department = isHousekeeping ? 'housekeeping' : (isTechnical ? 'technical' : 'security');
    final deptLabel  = isHousekeeping ? 'Housekeeping' : (isTechnical ? 'Technical' : 'Security');

    final approvalState = ref.watch(approvalProvider);
    if (societyId != null && approvalState is ApprovalInitial) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        ref.read(approvalProvider.notifier).load(societyId, department: department);
      });
    }

    final summaryAsync = societyId != null
        ? ref.watch(attendanceSummaryProvider(societyId))
        : AsyncValue<Map<String, dynamic>>.error(Exception('no society'), StackTrace.empty);

    final dutiesAsync = societyId != null
        ? ref.watch(societyDutiesProvider(societyId))
        : AsyncValue<List<DutyEntity>>.error(Exception('no society'), StackTrace.empty);

    // Numbers come from the server: loading or failed is shown as such, never as 0.
    final pendingCheckin  = _approvalCount(approvalState, (l) => l.pendingCheckin.length);
    final pendingCheckout = _approvalCount(approvalState, (l) => l.pendingCheckout.length);
    final pendingDuties   = dutiesAsync.whenData((d) => d.where((x) => !x.isCompleted).length);
    final completedDuties = dutiesAsync.whenData((d) => d.where((x) => x.isCompleted).length);
    void retryApprovals() { if (societyId != null) ref.read(approvalProvider.notifier).load(societyId, department: department); }
    void retrySummary() { if (societyId != null) ref.invalidate(attendanceSummaryProvider(societyId)); }
    void retryDuties() { if (societyId != null) ref.invalidate(societyDutiesProvider(societyId)); }

    return _DashboardShell(
      title: '$deptLabel Supervisor',
      children: [
        _GreetingCard(user: user, subtitle: '$deptLabel Supervisor · Team Management'),
        const SizedBox(height: 18),
        const _SectionLabel('Team Status'),
        const SizedBox(height: 10),
        GridView(
          gridDelegate: SliverGridDelegateWithMaxCrossAxisExtent(
            maxCrossAxisExtent: 280,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            mainAxisExtent: _cardExtent(context),
          ),
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          children: [
            _countCard(
                icon: Icons.people_rounded, label: 'Staff Present', count: _summaryCount(summaryAsync, 'present'),
                color: (_) => AppTheme.success, retry: retrySummary),
            _countCard(
                icon: Icons.person_off_rounded, label: 'Staff Absent', count: _summaryCount(summaryAsync, 'absent'),
                color: (_) => AppTheme.error, retry: retrySummary),
            _countCard(
              icon: Icons.login_rounded,
              label: 'Pending Check-in',
              count: pendingCheckin,
              color: (n) => n > 0 ? AppTheme.warning : AppTheme.success,
              retry: retryApprovals,
            ),
            _countCard(
              icon: Icons.logout_rounded,
              label: 'Pending Check-out',
              count: pendingCheckout,
              color: (n) => n > 0 ? AppTheme.error : AppTheme.success,
              retry: retryApprovals,
            ),
            _countCard(
              icon: Icons.assignment_late_rounded,
              label: 'Duties Pending',
              count: pendingDuties,
              color: (n) => n > 0 ? AppTheme.warning : AppTheme.success,
              retry: retryDuties,
              onTap: societyId != null
                  ? () => context.push(AppRoutes.staffDutyOverview, extra: societyId)
                  : null,
            ),
            _countCard(
              icon: Icons.assignment_turned_in_rounded,
              label: 'Duties Done',
              count: completedDuties,
              color: (_) => AppTheme.success,
              retry: retryDuties,
              onTap: societyId != null
                  ? () => context.push(AppRoutes.staffDutyOverview, extra: societyId)
                  : null,
            ),
          ],
        ),
        const SizedBox(height: 18),
        const _SectionLabel('Quick Actions'),
        const SizedBox(height: 10),
        Row(children: [
          _QuickActionChip(
            icon: Icons.approval_rounded, label: 'Approvals',
            onTap: societyId != null
                ? () => context.push(AppRoutes.staffApprovals,
                    extra: {'societyId': societyId, 'department': department})
                : null,
          ),
          const SizedBox(width: 8),
          _QuickActionChip(icon: Icons.badge_rounded, label: 'My Team', route: AppRoutes.staffList),
          const SizedBox(width: 8),
          _QuickActionChip(
            icon: Icons.assignment_turned_in_rounded, label: 'Assign Duty',
            onTap: societyId != null
                ? () => context.push(AppRoutes.staffAssignDuty, extra: {'societyId': societyId})
                : null,
          ),
          const SizedBox(width: 8),
          _QuickActionChip(
            icon: Icons.swap_horiz_rounded, label: 'Handover',
            onTap: staffId != null && societyId != null
                ? () => context.push('/staff/handover/$staffId', extra: societyId)
                : null,
          ),
        ]),
        const SizedBox(height: 18),
        if (isHousekeeping && dutiesAsync.valueOrNull != null) ...[
          _OperationalPanel(title: 'Dept Check-in Approvals', children: [
            _InfoTile(
              icon: Icons.fitness_center_rounded,
              title: '$deptLabel Staff',
              value: pendingCheckin.when(
                data: (n) => n > 0 ? '$n pending approval' : 'All approved',
                loading: () => '…',
                error: (_, __) => 'Could not load',
              ),
              color: (pendingCheckin.valueOrNull ?? 0) > 0 ? AppTheme.warning : AppTheme.success,
            ),
          ]),
          const SizedBox(height: 18),
        ],
      ],
    );
  }
}
