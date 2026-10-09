import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/stores/data/stores_api.dart';

final storesApiProvider = Provider<StoresApi>((_) => StoresApi());

final storesSummaryProvider = FutureProvider.autoDispose.family<StoresSummary, String>(
  (ref, societyId) => ref.watch(storesApiProvider).summary(societyId),
);

final storeItemsProvider = FutureProvider.autoDispose.family<List<StoreItem>, String>(
  (ref, societyId) => ref.watch(storesApiProvider).items(societyId),
);

final storeItemProvider = FutureProvider.autoDispose.family<StoreItem, String>(
  (ref, id) => ref.watch(storesApiProvider).item(id),
);

final stockHistoryProvider = FutureProvider.autoDispose.family<List<StockMove>, String>(
  (ref, itemId) => ref.watch(storesApiProvider).history(itemId),
);

typedef IssueKey = ({String societyId, String? status, String? itemId});

final storeIssuesProvider = FutureProvider.autoDispose.family<List<IssueItem>, IssueKey>(
  (ref, k) => ref.watch(storesApiProvider).issues(k.societyId, status: k.status, itemId: k.itemId),
);

final recipientsProvider = FutureProvider.autoDispose.family<List<Recipient>, String>(
  (ref, societyId) => ref.watch(storesApiProvider).recipients(societyId),
);

/// After anything about the stores changes.
void invalidateStores(WidgetRef ref) {
  ref.invalidate(storesSummaryProvider);
  ref.invalidate(storeItemsProvider);
  ref.invalidate(storeItemProvider);
  ref.invalidate(stockHistoryProvider);
  ref.invalidate(storeIssuesProvider);
}
