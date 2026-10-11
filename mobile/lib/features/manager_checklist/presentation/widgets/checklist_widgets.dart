import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/manager_checklist/data/checklist_api.dart';

String shortDate(DateTime d) => '${d.day} ${kMonthNames[d.month - 1]} ${d.year}';
String dayName(DateTime d) => '${kWeekdays[d.weekday - 1]}, ${d.day} ${kMonthNames[d.month - 1]} ${d.year}';

/// The screen each "where is the work done" key opens. Null when there is nowhere to go.
void openLink(BuildContext context, String? key, String societyId) {
  if (key == 'staff_approvals') {
    context.push(AppRoutes.staffApprovals, extra: societyId);
    return;
  }
  final path = switch (key) {
    'complaints' => AppRoutes.complaintsSociety.replaceFirst(':societyId', societyId),
    'visitors' => AppRoutes.visitorsSociety.replaceFirst(':societyId', societyId),
    'staff' => AppRoutes.staffList,
    'cash_bank_book' => AppRoutes.accountsCashBook,
    'accounts' => AppRoutes.accounts,
    'recurring' => AppRoutes.accountsRecurring,
    'approvals' => AppRoutes.accountsApprovals,
    'parking' => AppRoutes.parkingManagement,
    'assets' => AppRoutes.assets,
    'inventory' => AppRoutes.stores,
    'defaulters' => AppRoutes.defaulters,
    'billing' => AppRoutes.maintenanceBilling,
    'bank_reconciliation' => AppRoutes.bankReconciliation,
    'vendors' => AppRoutes.vendorsWork,
    'meetings' => AppRoutes.meetings,
    'residents' => AppRoutes.residentsList,
    'tenants' => AppRoutes.tenantsList,
    'pending_changes' => AppRoutes.pendingResidentChanges,
    'password_resets' => AppRoutes.passwordResetRequests,
    'amenities' => AppRoutes.amenities,
    'certificates' => AppRoutes.certificates,
    'parcels' => AppRoutes.parcels,
    _ => null,
  };
  if (path != null) context.push(path);
}

({String label, Color color, Color soft}) stateLook(ChecklistEntry e) {
  final due = e.dueOn == null ? '' : shortDate(e.dueOn!);
  switch (e.state) {
    case 'overdue':
      return (label: 'Overdue · was due $due', color: AppTheme.error, soft: AppTheme.errorSoft);
    case 'due':
      return (label: 'Due today', color: AppTheme.warning, soft: AppTheme.warningSoft);
    case 'soon':
      final n = e.daysLeft ?? 0;
      return (label: 'Due in $n day${n == 1 ? '' : 's'} · $due', color: AppTheme.warning, soft: AppTheme.warningSoft);
    case 'unconfirmed':
      return (label: 'Confirm if done · was due $due', color: AppTheme.warning, soft: AppTheme.warningSoft);
    case 'unrecorded':
      return (label: 'Not recorded yet', color: AppTheme.warning, soft: AppTheme.warningSoft);
    case 'done':
      return (label: 'Done', color: AppTheme.success, soft: AppTheme.successSoft);
    case 'skipped':
      return (label: 'Skipped', color: AppTheme.textSecondary, soft: AppTheme.surface);
    default:
      final until = e.isLicence && e.validUntil != null ? 'Valid until ${shortDate(e.validUntil!)}' : (e.dueOn == null ? 'Up to date' : 'Next $due');
      return (label: until, color: AppTheme.success, soft: AppTheme.successSoft);
  }
}

class StatePill extends StatelessWidget {
  final ChecklistEntry entry;
  const StatePill(this.entry, {super.key});

  @override
  Widget build(BuildContext context) {
    final look = stateLook(entry);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: look.soft, borderRadius: BorderRadius.circular(20)),
      child: Text(look.label, style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: look.color)),
    );
  }
}

Color severityColor(String severity) => switch (severity) {
      'high' => AppTheme.error,
      'medium' => AppTheme.warning,
      _ => AppTheme.primary,
    };

/// A white rounded card: the surface the checklist's sections sit on.
class ChecklistCard extends StatelessWidget {
  final Widget child;
  final EdgeInsets padding;
  const ChecklistCard({super.key, required this.child, this.padding = const EdgeInsets.all(16)});

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: padding,
        decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
        child: child,
      );
}

class SectionTitle extends StatelessWidget {
  final String text;
  final String? trailing;
  const SectionTitle(this.text, {super.key, this.trailing});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(2, 20, 2, 8),
        child: Row(children: [
          Expanded(child: Text(text, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700))),
          if (trailing != null) Text(trailing!, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
        ]),
      );
}

/// The legal-advice caveat and, for a state without built-in rules, what to do about it.
class JurisdictionNote extends StatelessWidget {
  final Jurisdiction jurisdiction;
  const JurisdictionNote(this.jurisdiction, {super.key});

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
            color: jurisdiction.statePackLoaded ? AppTheme.primarySoft : AppTheme.warningSoft,
            borderRadius: BorderRadius.circular(AppTheme.radiusM)),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(Icons.gavel_rounded, size: 18, color: jurisdiction.statePackLoaded ? AppTheme.primary : AppTheme.warning),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Rules loaded: ${jurisdiction.packs.join(' + ')}',
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
              const SizedBox(height: 3),
              Text(jurisdiction.note, style: const TextStyle(fontSize: 12.5, height: 1.4, color: AppTheme.textSecondary)),
            ]),
          ),
        ]),
      );
}


/// A dashboard card: how far through today's checklist the manager is, opening the checklist when tapped.
class ChecklistTodayCard extends ConsumerWidget {
  final String societyId;
  const ChecklistTodayCard({super.key, required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(todayChecklistProvider(societyId)).valueOrNull;
    final s = t?.summary;
    final fraction = s == null || s.total == 0 ? 0.0 : s.done / s.total;
    return InkWell(
      onTap: () => context.go(AppRoutes.managerChecklist),
      borderRadius: BorderRadius.circular(AppTheme.radiusM),
      child: ChecklistCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.fact_check_rounded, color: AppTheme.primary),
            const SizedBox(width: 10),
            const Expanded(child: Text("Today's checklist", style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700))),
            const Icon(Icons.chevron_right_rounded, color: AppTheme.textTertiary),
          ]),
          const SizedBox(height: 8),
          Text(
              s == null
                  ? 'Your daily routine, by your assets and staff'
                  : '${s.done} of ${s.total} done${s.overdue > 0 ? ' · ${s.overdue} overdue' : ''}${s.liveOpen > 0 ? ' · ${s.liveOpen} flagged from records' : ''}',
              style: TextStyle(fontSize: 13, color: s != null && s.overdue > 0 ? AppTheme.error : AppTheme.textSecondary)),
          if (s != null) ...[
            const SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(
                  value: fraction, minHeight: 6, backgroundColor: AppTheme.surface, color: fraction >= 1 ? AppTheme.success : AppTheme.primary),
            ),
          ],
        ]),
      ),
    );
  }
}
