import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';

/// (api value, label)
const kViolationTypes = <(String, String)>[
  ('unauthorized', 'Unauthorised vehicle'),
  ('expired_permit', 'Expired permit'),
  ('wrong_slot', 'Wrong slot'),
  ('double_parking', 'Double parking'),
  ('blocked_access', 'Blocking access'),
  ('restricted_zone', 'Restricted zone'),
  ('no_parking', 'No-parking area'),
];

String violationTypeLabel(String t) => kViolationTypes.where((e) => e.$1 == t).firstOrNull?.$2 ?? t;

/// Where a violation's fine stands on the flat's maintenance bills.
enum FineStatus {
  none,
  active,
  billed,
  cancelled;

  static FineStatus parse(String? v) => switch (v) {
        'active' => active,
        'billed' => billed,
        'cancelled' => cancelled,
        _ => none,
      };

  String get label => switch (this) {
        none => 'Not charged',
        active => 'On the next bill',
        billed => 'Billed',
        cancelled => 'Waived',
      };
}

class ViolationItem {
  final String id;
  final String vehicleNumber;
  final String type;
  final String? description;
  final bool resolved;
  final int? fineAmount;
  final FineStatus fine;
  final DateTime? reportedAt;

  const ViolationItem({
    required this.id,
    required this.vehicleNumber,
    required this.type,
    this.description,
    this.resolved = false,
    this.fineAmount,
    this.fine = FineStatus.none,
    this.reportedAt,
  });

  factory ViolationItem.fromJson(Map<String, dynamic> j) => ViolationItem(
        id: j['id'] as String,
        vehicleNumber: j['vehicle_number'] as String? ?? '',
        type: j['violation_type'] as String? ?? '',
        description: j['description'] as String?,
        resolved: j['is_resolved'] as bool? ?? false,
        fineAmount: (j['fine_amount'] as num?)?.toInt(),
        fine: FineStatus.parse(j['fine_status'] as String?),
        reportedAt: DateTime.tryParse('${j['created_at'] ?? ''}'),
      );

  bool get hasFine => (fineAmount ?? 0) > 0;

  /// A fine can be put on a flat's bill when it is not on one already (a waived fine can be charged again).
  bool get canCharge => fine == FineStatus.none || fine == FineStatus.cancelled;

  /// It can be waived until it has gone onto a bill.
  bool get canWaive => fine == FineStatus.active;
}

class ParkingViolationsApi {
  final Dio _dio;
  ParkingViolationsApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<List<ViolationItem>> list(String societyId, {bool unresolvedOnly = false}) async {
    final r = await _dio.get('/parking/violations/society/$societyId', queryParameters: {'unresolved_only': unresolvedOnly});
    return (r.data as List).map((e) => ViolationItem.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<ViolationItem> report({
    required String societyId,
    required String vehicleNumber,
    required String type,
    String? description,
    int? fineAmount,
  }) async =>
      ViolationItem.fromJson((await _dio.post('/parking/violations', data: {
        'society_id': societyId,
        'vehicle_number': vehicleNumber,
        'violation_type': type,
        if (description != null && description.isNotEmpty) 'description': description,
        if (fineAmount != null) 'fine_amount': fineAmount,
      })).data as Map<String, dynamic>);

  /// Put the fine on a flat's next maintenance bill. [flatId] is needed only when the vehicle is not registered to a
  /// flat; [amount] only when the violation was recorded without a fine.
  Future<ViolationItem> chargeFine(String id, {String? flatId, int? amount}) async =>
      ViolationItem.fromJson((await _dio.post('/parking/violations/$id/fine', data: {
        if (flatId != null) 'flat_id': flatId,
        if (amount != null) 'amount': amount,
      })).data as Map<String, dynamic>);

  Future<ViolationItem> waiveFine(String id, String reason) async =>
      ViolationItem.fromJson((await _dio.post('/parking/violations/$id/waive-fine', data: {'reason': reason})).data
          as Map<String, dynamic>);

  Future<ViolationItem> resolve(String id) async =>
      ViolationItem.fromJson((await _dio.post('/parking/violations/$id/resolve')).data as Map<String, dynamic>);
}

final parkingViolationsApiProvider = Provider<ParkingViolationsApi>((_) => ParkingViolationsApi());

final parkingViolationsProvider = FutureProvider.autoDispose.family<List<ViolationItem>, String>(
  (ref, societyId) => ref.watch(parkingViolationsApiProvider).list(societyId),
);
