import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The bases whose amount can follow what was spent.
const _spendBases = {'fixed', 'per_sqft', 'budget_equal', 'budget_area'};

/// Heads whose rate is a yearly budget are the natural ones to bill from the books; a typed monthly rate is a
/// decision the society made, so those start unticked.
bool _suggested(ChargeHead c) => c.basis == 'budget_equal' || c.basis == 'budget_area';

bool _eligible(ChargeHead c) => c.isActive && c.elementId != null && _spendBases.contains(c.basis);

/// Open the "Bill actual expenses" sheet: tick the charge heads that should bill exactly what was spent in each
/// billing cycle and switch them in one step.
Future<void> showBillActualExpensesSheet(BuildContext context, String societyId) =>
    showAppSheet(context: context, builder: (_) => BillActualExpensesSheet(societyId: societyId));

class BillActualExpensesSheet extends ConsumerStatefulWidget {
  final String societyId;
  const BillActualExpensesSheet({super.key, required this.societyId});

  @override
  ConsumerState<BillActualExpensesSheet> createState() => _BillActualExpensesSheetState();
}

class _BillActualExpensesSheetState extends ConsumerState<BillActualExpensesSheet> {
  final Set<String> _picked = {};
  bool _seeded = false;
  bool _saving = false;

  Future<void> _apply() async {
    setState(() => _saving = true);
    try {
      final r = await ref.read(maintenanceBillingApiProvider).billActualExpenses(widget.societyId, _picked.toList());
      ref.invalidate(chargeHeadsProvider(widget.societyId));
      if (!mounted) return;
      final skipped = r.skipped.isEmpty ? '' : ' · ${r.skipped.length} skipped: ${r.skipped.first.reason}';
      AppToast.success(context, '${r.changed.length} charge head(s) now bill actual expenses$skipped');
      Navigator.pop(context);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final heads = ref.watch(chargeHeadsProvider(widget.societyId));
    return AppSheetFrame(
      title: 'Bill actual expenses',
      subtitle: 'Each tick bills exactly what was spent in the billing cycle, shared by area or equally.',
      child: heads.when(
        loading: () => const Padding(padding: EdgeInsets.all(24), child: AppLoader()),
        error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
        data: (all) {
          final list = all.where(_eligible).toList();
          if (!_seeded) {
            _seeded = true;
            _picked.addAll(list.where((c) => !c.isPeriodExpense && _suggested(c)).map((c) => c.id));
          }
          if (list.isEmpty) {
            return const Text('No charge head is made from an element with a spend-based calculation yet.',
                style: TextStyle(color: AppTheme.textSecondary));
          }
          final changeable = _picked.where((id) => list.any((c) => c.id == id && !c.isPeriodExpense)).length;
          return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            for (final c in list)
              CheckboxListTile(
                key: ValueKey('actual-${c.id}'),
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                value: c.isPeriodExpense || _picked.contains(c.id),
                onChanged: c.isPeriodExpense
                    ? null
                    : (v) => setState(() => v == true ? _picked.add(c.id) : _picked.remove(c.id)),
                title: Text(c.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                subtitle: Text(c.isPeriodExpense
                    ? 'Already bills actual expenses'
                    : _suggested(c)
                        ? 'Now ${c.rateLabel} · a yearly budget, usually best billed from the books'
                        : 'Now ${c.rateLabel} · has a typed rate — tick only if it should follow spend'),
              ),
            const SizedBox(height: 4),
            const Text(
              'A head with no expense in a cycle puts nothing on the bills for that cycle. '
              'Only one head can bill an element\'s expenses.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _saving || changeable == 0 ? null : _apply,
              child: _saving
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : Text(changeable == 0 ? 'Nothing to switch' : 'Switch $changeable charge head(s)'),
            ),
          ]);
        },
      ),
    );
  }
}
