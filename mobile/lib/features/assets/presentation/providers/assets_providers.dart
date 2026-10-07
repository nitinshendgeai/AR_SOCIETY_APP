import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/assets/data/assets_api.dart';

final assetsApiProvider = Provider<AssetsApi>((_) => AssetsApi());

final assetSummaryProvider = FutureProvider.autoDispose.family<AssetSummary, String>(
  (ref, societyId) => ref.watch(assetsApiProvider).summary(societyId),
);

typedef AssetListKey = ({String societyId, String? category, String? status, bool due});

final assetListProvider = FutureProvider.autoDispose.family<List<Asset>, AssetListKey>(
  (ref, k) => ref.watch(assetsApiProvider).list(k.societyId, category: k.category, status: k.status, due: k.due),
);

final assetHistoryProvider = FutureProvider.autoDispose.family<AssetHistory, String>(
  (ref, assetId) => ref.watch(assetsApiProvider).history(assetId),
);

/// After anything on an asset changes: its page, the register and the counts.
void invalidateAssets(WidgetRef ref) {
  ref.invalidate(assetSummaryProvider);
  ref.invalidate(assetListProvider);
  ref.invalidate(assetHistoryProvider);
}
