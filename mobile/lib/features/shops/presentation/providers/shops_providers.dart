import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/shops/data/shops_api.dart';

final shopsApiProvider = Provider<ShopsApi>((_) => ShopsApi());

final shopsProvider = FutureProvider.autoDispose.family<List<Shop>, String>(
  (ref, societyId) => ref.watch(shopsApiProvider).list(societyId),
);
