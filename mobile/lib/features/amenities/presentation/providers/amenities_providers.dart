import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/amenities/data/amenities_api.dart';

final amenitiesApiProvider = Provider<AmenitiesApi>((_) => AmenitiesApi());

typedef AmenityListKey = ({String societyId, bool includeClosed});

final amenityListProvider = FutureProvider.autoDispose.family<List<AmenityItem>, AmenityListKey>(
  (ref, k) => ref.watch(amenitiesApiProvider).amenities(k.societyId, includeClosed: k.includeClosed),
);

final amenityProvider = FutureProvider.autoDispose.family<AmenityItem, String>(
  (ref, id) => ref.watch(amenitiesApiProvider).amenity(id),
);

final amenityRulesProvider = FutureProvider.autoDispose.family<List<AmenityRule>, String>(
  (ref, id) => ref.watch(amenitiesApiProvider).rules(id),
);

final amenityRatesProvider = FutureProvider.autoDispose.family<List<AmenityRate>, String>(
  (ref, id) => ref.watch(amenitiesApiProvider).rates(id),
);

final amenityClosedDatesProvider = FutureProvider.autoDispose.family<List<ClosedDate>, String>(
  (ref, id) => ref.watch(amenitiesApiProvider).closedDates(id),
);

typedef DayKey = ({String amenityId, String date});

final amenityDayProvider = FutureProvider.autoDispose.family<DayView, DayKey>(
  (ref, k) => ref.watch(amenitiesApiProvider).day(k.amenityId, DateTime.parse(k.date)),
);

final myBookingsProvider = FutureProvider.autoDispose<List<BookingItem>>((ref) => ref.watch(amenitiesApiProvider).mine());

final pendingBookingsProvider = FutureProvider.autoDispose.family<List<BookingItem>, String>(
  (ref, societyId) => ref.watch(amenitiesApiProvider).pending(societyId),
);

final allBookingsProvider = FutureProvider.autoDispose.family<List<BookingItem>, String>(
  (ref, societyId) => ref.watch(amenitiesApiProvider).all(societyId),
);

/// After anything about amenities or bookings changes.
void invalidateAmenities(WidgetRef ref) {
  ref.invalidate(amenityListProvider);
  ref.invalidate(amenityProvider);
  ref.invalidate(amenityRulesProvider);
  ref.invalidate(amenityRatesProvider);
  ref.invalidate(amenityClosedDatesProvider);
  ref.invalidate(amenityDayProvider);
  ref.invalidate(myBookingsProvider);
  ref.invalidate(pendingBookingsProvider);
  ref.invalidate(allBookingsProvider);
}
