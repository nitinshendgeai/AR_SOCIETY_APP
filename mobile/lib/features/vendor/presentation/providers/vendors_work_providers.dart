import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart';

final vendorsWorkApiProvider = Provider<VendorsWorkApi>((_) => VendorsWorkApi());

final vendorRecordsProvider = FutureProvider.autoDispose.family<List<VendorRecord>, String>(
  (ref, societyId) => ref.watch(vendorsWorkApiProvider).vendors(societyId),
);

final procurementLimitsProvider = FutureProvider.autoDispose.family<ProcurementLimits, String>(
  (ref, societyId) => ref.watch(vendorsWorkApiProvider).limits(societyId),
);

final workOrdersProvider = FutureProvider.autoDispose.family<List<WorkOrder>, String>(
  (ref, societyId) => ref.watch(vendorsWorkApiProvider).workOrders(societyId),
);

final workOrderProvider = FutureProvider.autoDispose.family<WorkOrder, String>(
  (ref, id) => ref.watch(vendorsWorkApiProvider).workOrder(id),
);

final contractsProvider = FutureProvider.autoDispose.family<List<AmcContract>, String>(
  (ref, societyId) => ref.watch(vendorsWorkApiProvider).contracts(societyId),
);

final contractProvider = FutureProvider.autoDispose.family<AmcContract, String>(
  (ref, id) => ref.watch(vendorsWorkApiProvider).contract(id),
);
