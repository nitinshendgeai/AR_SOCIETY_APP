import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/parking/data/datasources/parking_remote_datasource.dart';
import 'package:ar_society_app/features/parking/domain/entities/parking_entities.dart';

// ── Result type ───────────────────────────────────────────────────────────────

sealed class ParkingResult<T> {}

class ParkingSuccess<T> extends ParkingResult<T> {
  final T data;
  ParkingSuccess(this.data);
}

class ParkingFailure<T> extends ParkingResult<T> {
  final String message;
  final int? statusCode;
  ParkingFailure(this.message, {this.statusCode});
}

// ── Repository ────────────────────────────────────────────────────────────────

class ParkingRepository {
  final ParkingRemoteDataSource _ds;
  ParkingRepository({ParkingRemoteDataSource? ds})
      : _ds = ds ?? ParkingRemoteDataSource();

  ParkingResult<T> _handle<T>(Object e) {
    if (e is DioException) {
      return ParkingFailure(parseApiError(e), statusCode: e.response?.statusCode);
    }
    return ParkingFailure('Unexpected error: $e');
  }

  Future<ParkingResult<GateVehicleLookupEntity>> validateVehicle({
    required String societyId,
    required String vehicleNumber,
  }) async {
    try {
      final m = await _ds.validateVehicle(
          societyId: societyId, vehicleNumber: vehicleNumber);
      return ParkingSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<ParkingResult<ParkingAccessLogEntity>> logAccess({
    required String societyId,
    required String vehicleNumber,
    required GateAccessType accessType,
    String? notes,
  }) async {
    try {
      final m = await _ds.logAccess(
        societyId: societyId,
        vehicleNumber: vehicleNumber,
        accessType: accessType.value,
        notes: notes,
      );
      return ParkingSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }

  // ── Zones ──────────────────────────────────────────────────────────────────

  Future<ParkingResult<List<ParkingZoneEntity>>> listZones(String societyId) async {
    try {
      final list = await _ds.listZones(societyId);
      return ParkingSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<ParkingResult<ParkingZoneEntity>> createZone({
    required String societyId,
    required String name,
    String? code,
  }) async {
    try {
      final m = await _ds.createZone(societyId: societyId, name: name, code: code);
      return ParkingSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }

  // ── Slots ──────────────────────────────────────────────────────────────────

  Future<ParkingResult<List<ParkingSlotEntity>>> listSlotsBySociety(String societyId) async {
    try {
      final list = await _ds.listSlotsBySociety(societyId);
      return ParkingSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<ParkingResult<List<ParkingSlotEntity>>> listAvailableSlots(String societyId) async {
    try {
      final list = await _ds.listAvailableSlots(societyId);
      return ParkingSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<ParkingResult<ParkingSlotEntity>> createSlot({
    required String societyId,
    required String zoneId,
    required String slotNumber,
    String slotType = 'resident',
    bool isCovered = false,
    bool isEvCharging = false,
  }) async {
    try {
      final m = await _ds.createSlot(
        societyId: societyId, zoneId: zoneId, slotNumber: slotNumber,
        slotType: slotType, isCovered: isCovered, isEvCharging: isEvCharging,
      );
      return ParkingSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }

  // ── Allocations ────────────────────────────────────────────────────────────

  Future<ParkingResult<List<ParkingAllocationEntity>>> listAllocations(String societyId) async {
    try {
      final list = await _ds.listAllocations(societyId);
      return ParkingSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<ParkingResult<ParkingAllocationEntity>> createAllocation({
    required String societyId,
    required String slotId,
    String? flatId,
    String? vehicleId,
    required String allocationType,
    required String startDate,
    int? monthlyCharge,
  }) async {
    try {
      final m = await _ds.createAllocation(
        societyId: societyId, slotId: slotId, flatId: flatId, vehicleId: vehicleId,
        allocationType: allocationType, startDate: startDate, monthlyCharge: monthlyCharge,
      );
      return ParkingSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<ParkingResult<ParkingAllocationEntity>> releaseAllocation(String allocationId) async {
    try {
      final m = await _ds.releaseAllocation(allocationId);
      return ParkingSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }
}
