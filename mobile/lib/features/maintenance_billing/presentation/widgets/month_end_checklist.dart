import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/bill_actual_expenses_sheet.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The month-end checklist at the top of a cycle preview: what in the books would leave the bills short of what
/// was spent, each with the one tap that puts it right (as the period-end exceptions list does in Tally).
class MonthEndChecklist extends ConsumerWidget {
  final String cycleId;
  final CyclePreview preview;
  const MonthEndChecklist({super.key, required this.cycleId, required this.preview});

  void _refresh(WidgetRef ref) {
    ref.invalidate(cyclePreviewProvider(cycleId));
    ref.invalidate(pendingApprovalsProvider);
  }

  Future<void> _approveAll(BuildContext context, WidgetRef ref, String societyId) async {
    try {
      final r = await ref.read(maintenanceBillingApiProvider).approvePendingPayments(
          societyId, from: preview.cycleStart, to: preview.cycleEnd);
      if (!context.mounted) return;
      final left = r.leftForAnother == 0
          ? ''
          : ' · ${r.leftForAnother} you entered yourself wait for another admin or committee member';
      AppToast.success(context, '${r.approved} approved$left');
      _refresh(ref);
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  /// One tap: make (or switch) the element's head so it bills the cycle's actual expenses.
  Future<void> _addHead(BuildContext context, WidgetRef ref, String societyId, UncoveredElement e) async {
    try {
      final r = await ref.read(maintenanceBillingApiProvider)
          .billActualExpenses(societyId, const [], elementIds: [e.elementId]);
      if (!context.mounted) return;
      if (r.changed.isEmpty) {
        AppToast.error(context, r.skipped.isEmpty ? 'Nothing was changed' : r.skipped.first.reason);
      } else {
        AppToast.success(context, '${r.changed.first.name} now bills the actual expenses of each cycle');
        ref.invalidate(chargeHeadsProvider(societyId));
      }
      _refresh(ref);
    } catch (ex) {
      if (context.mounted) showErrorToast(context, ex);
    }
  }

  Future<void> _link(BuildContext context, WidgetRef ref, String societyId, UnlinkedLedger l) async {
    final elements = await ref.read(maintenanceElementsProvider((societyId: societyId, includeInactive: false)).future);
    if (!context.mounted) return;
    final picked = await showAppSheet<MaintenanceElement>(
      context: context,
      builder: (ctx) => AppSheetFrame(
        title: 'What is “${l.name}” for?',
        subtitle: 'Its expenses will then be recovered through the charge head for that element.',
        scrollBody: false,
        child: ListView(shrinkWrap: true, children: [
          for (final e in elements)
            ListTile(key: ValueKey('element-${e.id}'), title: Text(e.name), onTap: () => Navigator.pop(ctx, e)),
        ]),
      ),
    );
    if (picked == null || !context.mounted) return;
    try {
      await ref.read(accountsApiProvider).updateLedger(l.accountId, {'maintenance_element_id': picked.id});
      if (!context.mounted) return;
      AppToast.success(context, '“${l.name}” now counts towards ${picked.name}');
      _refresh(ref);
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  Widget _row({required IconData icon, required Color color, required String text, String? action,
      VoidCallback? onTap, Key? actionKey}) =>
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 13))),
          if (action != null)
            TextButton(key: actionKey, onPressed: onTap, child: Text(action)),
        ]),
      );

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    final r = preview.readiness;
    if (societyId == null) return const SizedBox.shrink();

    if (!r.applies) {
      return Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: _row(
            icon: Icons.info_outline_rounded,
            color: AppTheme.primary,
            text: 'No charge head bills the actual expenses of the cycle yet.',
            action: 'Set up',
            actionKey: const ValueKey('checklist-setup'),
            onTap: () => showBillActualExpensesSheet(context, societyId).then((_) => _refresh(ref)),
          ),
        ),
      );
    }
    return Card(
      key: const ValueKey('month-end-checklist'),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(r.ready ? 'Month-end check: all clear' : 'Month-end check',
              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
          const SizedBox(height: 4),
          if (r.ready)
            _row(
              icon: Icons.check_circle_rounded,
              color: AppTheme.success,
              text: 'Every approved expense of the cycle is in the bills.',
            ),
          if (r.pendingCount > 0)
            _row(
              icon: Icons.hourglass_top_rounded,
              color: AppTheme.warning,
              text: '${r.pendingCount} expense(s) of ${formatRupees(r.pendingAmount)} are waiting for approval '
                  'and are not in the bills.',
              action: 'Approve all',
              actionKey: const ValueKey('checklist-approve-all'),
              onTap: () => _approveAll(context, ref, societyId),
            ),
          for (final l in r.unlinkedLedgers)
            _row(
              icon: Icons.link_off_rounded,
              color: AppTheme.warning,
              text: '${l.name}: ${formatRupees(l.amount)} spent, but no maintenance element covers it.',
              action: 'Link',
              actionKey: ValueKey('checklist-link-${l.accountId}'),
              onTap: () => _link(context, ref, societyId, l),
            ),
          for (final e in r.uncoveredElements)
            _row(
              icon: Icons.rule_rounded,
              color: AppTheme.warning,
              text: '${e.elementName}: ${formatRupees(e.amount)} spent, but no charge head bills it as actual expenses.',
              action: e.hasHead ? 'Switch head' : 'Add head',
              actionKey: ValueKey('checklist-cover-${e.elementId}'),
              onTap: () => _addHead(context, ref, societyId, e),
            ),
          for (final h in r.headsWithoutSpend)
            _row(
              icon: Icons.remove_circle_outline_rounded,
              color: AppTheme.textSecondary,
              text: '$h: nothing spent in this period, so nothing is billed for it.',
            ),
        ]),
      ),
    );
  }
}
