import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';

final maintenanceBillingApiProvider = Provider<MaintenanceBillingApi>((_) => MaintenanceBillingApi());

final chargeHeadsProvider = FutureProvider.autoDispose.family<List<ChargeHead>, String>(
  (ref, societyId) => ref.watch(maintenanceBillingApiProvider).listChargeHeads(societyId),
);

final maintenanceRulesProvider = FutureProvider.autoDispose.family<MaintenanceRules, String>(
  (ref, societyId) => ref.watch(maintenanceBillingApiProvider).getRules(societyId),
);

final cyclePreviewProvider = FutureProvider.autoDispose.family<CyclePreview, String>(
  (ref, cycleId) => ref.watch(maintenanceBillingApiProvider).previewCycle(cycleId),
);

final billingCyclesProvider = FutureProvider.autoDispose.family<List<BillingCycle>, String>(
  (ref, societyId) => ref.watch(maintenanceBillingApiProvider).listCycles(societyId),
);

final billingCycleProvider = FutureProvider.autoDispose.family<BillingCycle, String>(
  (ref, cycleId) => ref.watch(maintenanceBillingApiProvider).getCycle(cycleId),
);

final cycleBillsProvider = FutureProvider.autoDispose.family<List<MaintenanceBill>, String>(
  (ref, cycleId) => ref.watch(maintenanceBillingApiProvider).cycleBills(cycleId),
);

final maintenanceBillProvider = FutureProvider.autoDispose.family<MaintenanceBill, String>(
  (ref, billId) => ref.watch(maintenanceBillingApiProvider).getBill(billId),
);

final myBillsProvider = FutureProvider.autoDispose<MyBillsSummary>(
  (ref) => ref.watch(maintenanceBillingApiProvider).myBills(),
);

/// Refreshes everything a change to one cycle's bills can affect: the
/// cycle's totals, its bill list, and the society-wide cycle list.
void invalidateCycle(WidgetRef ref, String societyId, String cycleId) {
  ref.invalidate(billingCycleProvider(cycleId));
  ref.invalidate(cycleBillsProvider(cycleId));
  ref.invalidate(billingCyclesProvider(societyId));
}
