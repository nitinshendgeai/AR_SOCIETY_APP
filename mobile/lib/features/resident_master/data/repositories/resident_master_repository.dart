import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/resident_master/data/datasources/resident_master_remote_datasource.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';

// ── Result type (mirrors StaffResult — see staff_repository.dart) ──────────

sealed class RmResult<T> {}

class RmSuccess<T> extends RmResult<T> {
  final T data;
  RmSuccess(this.data);
}

class RmFailure<T> extends RmResult<T> {
  final String message;
  final int? statusCode;
  RmFailure(this.message, {this.statusCode});
}

// ── Repository ────────────────────────────────────────────────────────────

class ResidentMasterRepository {
  final ResidentMasterRemoteDataSource _ds;
  ResidentMasterRepository({ResidentMasterRemoteDataSource? ds})
      : _ds = ds ?? ResidentMasterRemoteDataSource();

  RmResult<T> _handle<T>(Object e) {
    if (e is DioException) {
      final code = e.response?.statusCode;
      if (code == 409) {
        final detail = (e.response?.data as Map?)?['detail']?.toString() ?? '';
        return RmFailure(detail.isNotEmpty ? detail : 'Action not allowed in current state', statusCode: 409);
      }
      return RmFailure(parseApiError(e), statusCode: code);
    }
    return RmFailure('Unexpected error: $e');
  }

  // ── Residents ──────────────────────────────────────────────────────────

  Future<RmResult<ResidentModel>> createResident(Map<String, dynamic> data) async {
    try {
      return RmSuccess(await _ds.createResident(data));
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<List<ResidentModel>>> listResidents({
    String? flatId,
    String? residentType,
    bool? isActive,
    String? search,
    int skip = 0,
    int limit = 50,
  }) async {
    try {
      return RmSuccess(await _ds.listResidents(
        flatId: flatId, residentType: residentType, isActive: isActive,
        search: search, skip: skip, limit: limit,
      ));
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<ResidentModel>> getResident(String id) async {
    try {
      return RmSuccess(await _ds.getResident(id));
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<ResidentModel>> updateResident(String id, Map<String, dynamic> data) async {
    try {
      return RmSuccess(await _ds.updateResident(id, data));
    } catch (e) {
      return _handle(e);
    }
  }

  // ── Tenants ────────────────────────────────────────────────────────────

  Future<RmResult<TenantModel>> createTenant(Map<String, dynamic> data) async {
    try {
      return RmSuccess(await _ds.createTenant(data));
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<List<TenantModel>>> listTenants({
    String? flatId,
    bool? isActive,
    String? search,
    int skip = 0,
    int limit = 50,
  }) async {
    try {
      return RmSuccess(await _ds.listTenants(
        flatId: flatId, isActive: isActive, search: search, skip: skip, limit: limit,
      ));
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<TenantModel>> getTenant(String id) async {
    try {
      return RmSuccess(await _ds.getTenant(id));
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<TenantModel>> updateTenant(String id, Map<String, dynamic> data) async {
    try {
      return RmSuccess(await _ds.updateTenant(id, data));
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<AgreementModel>> renewAgreement(String tenantId, Map<String, dynamic> data) async {
    try {
      return RmSuccess(await _ds.renewAgreement(tenantId, data));
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<List<AgreementModel>>> listTenantAgreements(String tenantId) async {
    try {
      return RmSuccess(await _ds.listTenantAgreements(tenantId));
    } catch (e) {
      return _handle(e);
    }
  }

  // ── Occupancy ──────────────────────────────────────────────────────────

  Future<RmResult<void>> residentMoveIn({
    required String flatId,
    required String residentId,
    required String moveInDate,
  }) async {
    try {
      await _ds.residentMoveIn(flatId: flatId, residentId: residentId, moveInDate: moveInDate);
      return RmSuccess(null);
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<void>> residentMoveOut({
    required String flatId,
    required String residentId,
    required String moveOutDate,
  }) async {
    try {
      await _ds.residentMoveOut(flatId: flatId, residentId: residentId, moveOutDate: moveOutDate);
      return RmSuccess(null);
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<void>> tenantMoveIn({
    required String flatId,
    required String tenantId,
    required String moveInDate,
    bool createAgreement = true,
  }) async {
    try {
      await _ds.tenantMoveIn(
        flatId: flatId, tenantId: tenantId, moveInDate: moveInDate, createAgreement: createAgreement,
      );
      return RmSuccess(null);
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<void>> tenantMoveOut({
    required String flatId,
    required String tenantId,
    required String moveOutDate,
  }) async {
    try {
      await _ds.tenantMoveOut(flatId: flatId, tenantId: tenantId, moveOutDate: moveOutDate);
      return RmSuccess(null);
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<List<OccupancyLogModel>>> getFlatHistory(String flatId) async {
    try {
      return RmSuccess(await _ds.getFlatHistory(flatId));
    } catch (e) {
      return _handle(e);
    }
  }

  // ── Vehicles ───────────────────────────────────────────────────────────

  Future<RmResult<VehicleModel>> createVehicle(Map<String, dynamic> data) async {
    try {
      return RmSuccess(await _ds.createVehicle(data));
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<VehicleModel>> updateVehicle(String id, Map<String, dynamic> data) async {
    try {
      return RmSuccess(await _ds.updateVehicle(id, data));
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<List<VehicleModel>>> vehiclesByFlat(String flatId) async {
    try {
      return RmSuccess(await _ds.vehiclesByFlat(flatId));
    } catch (e) {
      return _handle(e);
    }
  }

  Future<RmResult<void>> deregisterVehicle(String id) async {
    try {
      await _ds.deregisterVehicle(id);
      return RmSuccess(null);
    } catch (e) {
      return _handle(e);
    }
  }
}
