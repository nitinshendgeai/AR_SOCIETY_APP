import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/parking/data/models/parking_models.dart';

/// Calls FastAPI /parking/* endpoints. API prefix: /api/v1/parking
class ParkingRemoteDataSource {
  final Dio _dio;
  ParkingRemoteDataSource({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  /// GET /parking/gate/validate/{society_id}/{vehicle_number}
  /// Read-only pre-entry check — does not create an access log entry.
  Future<GateVehicleLookupModel> validateVehicle({
    required String societyId,
    required String vehicleNumber,
  }) async {
    final r = await _dio.get('/parking/gate/validate/$societyId/$vehicleNumber');
    return GateVehicleLookupModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// POST /parking/access-log — records the guard's entry/exit decision.
  /// is_authorized and vehicle_id are always derived server-side from the
  /// same lookup validateVehicle() uses, so they are never sent here.
  Future<ParkingAccessLogModel> logAccess({
    required String societyId,
    required String vehicleNumber,
    required String accessType,
    String? notes,
  }) async {
    final r = await _dio.post('/parking/access-log', data: {
      'society_id': societyId,
      'vehicle_number': vehicleNumber,
      'access_type': accessType,
      if (notes != null && notes.isNotEmpty) 'notes': notes,
    });
    return ParkingAccessLogModel.fromJson(r.data as Map<String, dynamic>);
  }

  // ── Zones ──────────────────────────────────────────────────────────────────

  /// GET /parking/zones/{society_id}
  Future<List<ParkingZoneModel>> listZones(String societyId) async {
    final r = await _dio.get('/parking/zones/$societyId');
    return (r.data as List)
        .map((e) => ParkingZoneModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// POST /parking/zones
  Future<ParkingZoneModel> createZone({
    required String societyId,
    required String name,
    String? code,
  }) async {
    final r = await _dio.post('/parking/zones', data: {
      'society_id': societyId,
      'name': name,
      if (code != null && code.isNotEmpty) 'code': code,
    });
    return ParkingZoneModel.fromJson(r.data as Map<String, dynamic>);
  }

  // ── Slots ──────────────────────────────────────────────────────────────────

  /// GET /parking/slots/society/{society_id} — every slot regardless of status.
  Future<List<ParkingSlotModel>> listSlotsBySociety(String societyId) async {
    final r = await _dio.get('/parking/slots/society/$societyId');
    return (r.data as List)
        .map((e) => ParkingSlotModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /parking/slots/available/{society_id}
  Future<List<ParkingSlotModel>> listAvailableSlots(String societyId) async {
    final r = await _dio.get('/parking/slots/available/$societyId');
    return (r.data as List)
        .map((e) => ParkingSlotModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// POST /parking/slots
  Future<ParkingSlotModel> createSlot({
    required String societyId,
    required String zoneId,
    required String slotNumber,
    String slotType = 'resident',
    bool isCovered = false,
    bool isEvCharging = false,
  }) async {
    final r = await _dio.post('/parking/slots', data: {
      'society_id': societyId,
      'zone_id': zoneId,
      'slot_number': slotNumber,
      'slot_type': slotType,
      'is_covered': isCovered,
      'is_ev_charging': isEvCharging,
    });
    return ParkingSlotModel.fromJson(r.data as Map<String, dynamic>);
  }

  // ── Allocations ────────────────────────────────────────────────────────────

  /// GET /parking/allocations/society/{society_id}
  Future<List<ParkingAllocationModel>> listAllocations(String societyId) async {
    final r = await _dio.get('/parking/allocations/society/$societyId');
    return (r.data as List)
        .map((e) => ParkingAllocationModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// POST /parking/allocations
  Future<ParkingAllocationModel> createAllocation({
    required String societyId,
    required String slotId,
    String? flatId,
    String? vehicleId,
    required String allocationType,
    required String startDate,
    int? monthlyCharge,
  }) async {
    final r = await _dio.post('/parking/allocations', data: {
      'society_id': societyId,
      'slot_id': slotId,
      if (flatId != null) 'flat_id': flatId,
      if (vehicleId != null) 'vehicle_id': vehicleId,
      'allocation_type': allocationType,
      'start_date': startDate,
      if (monthlyCharge != null) 'monthly_charge': monthlyCharge,
    });
    return ParkingAllocationModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// POST /parking/allocations/{allocation_id}/release
  Future<ParkingAllocationModel> releaseAllocation(String allocationId) async {
    final r = await _dio.post('/parking/allocations/$allocationId/release');
    return ParkingAllocationModel.fromJson(r.data as Map<String, dynamic>);
  }
}
