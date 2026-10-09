import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/platform/data/platform_api.dart';

final platformApiProvider = Provider<PlatformApi>((_) => PlatformApi());

final platformStatsProvider = FutureProvider.autoDispose<PlatformStats>((ref) => ref.watch(platformApiProvider).stats());

typedef SocietyQuery = ({String q, String? status});

final platformSocietiesProvider = FutureProvider.autoDispose.family<List<PlatformSociety>, SocietyQuery>(
  (ref, k) => ref.watch(platformApiProvider).societies(q: k.q, status: k.status),
);

final platformSocietyProvider = FutureProvider.autoDispose.family<PlatformSociety, String>(
  (ref, id) => ref.watch(platformApiProvider).society(id),
);

final platformActivityProvider = FutureProvider.autoDispose<List<PlatformEvent>>((ref) => ref.watch(platformApiProvider).activity());

/// After anything about a society changes.
void invalidatePlatform(WidgetRef ref) {
  ref.invalidate(platformStatsProvider);
  ref.invalidate(platformSocietiesProvider);
  ref.invalidate(platformSocietyProvider);
  ref.invalidate(platformActivityProvider);
}
