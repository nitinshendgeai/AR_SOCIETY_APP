import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';

/// Calls FastAPI /residents, /tenants, /occupancy, /vehicles endpoints
/// (Phase M1.2/M1.3 backend). API prefix: /api/v1.
class ResidentMasterRemoteDataSource {
  final Dio _dio;
  ResidentMasterRemoteDataSource({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  // ── Residents ──────────────────────────────────────────────────────────

  /// POST /residents/
  Future<ResidentModel> createResident(Map<String, dynamic> data) async {
    final r = await _dio.post('/residents/', data: data);
    return ResidentModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// GET /residents/?flat_id=&resident_type=&is_active=&search=&skip=&limit=
  Future<List<ResidentModel>> listResidents({
    String? flatId,
    String? residentType,
    bool? isActive,
    String? search,
    int skip = 0,
    int limit = 50,
  }) async {
    final r = await _dio.get('/residents/', queryParameters: {
      if (flatId != null) 'flat_id': flatId,
      if (residentType != null) 'resident_type': residentType,
      if (isActive != null) 'is_active': isActive,
      if (search != null && search.isNotEmpty) 'search': search,
      'skip': skip,
      'limit': limit,
    });
    return (r.data as List)
        .map((e) => ResidentModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /residents/{id}
  Future<ResidentModel> getResident(String id) async {
    final r = await _dio.get('/residents/$id');
    return ResidentModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// PATCH /residents/{id}
  Future<ResidentModel> updateResident(String id, Map<String, dynamic> data) async {
    final r = await _dio.patch('/residents/$id', data: data);
    return ResidentModel.fromJson(r.data as Map<String, dynamic>);
  }

  // ── Tenants ────────────────────────────────────────────────────────────

  /// POST /tenants/
  Future<TenantModel> createTenant(Map<String, dynamic> data) async {
    final r = await _dio.post('/tenants/', data: data);
    return TenantModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// GET /tenants/?flat_id=&is_active=&search=&skip=&limit=
  Future<List<TenantModel>> listTenants({
    String? flatId,
    bool? isActive,
    String? search,
    int skip = 0,
    int limit = 50,
  }) async {
    final r = await _dio.get('/tenants/', queryParameters: {
      if (flatId != null) 'flat_id': flatId,
      if (isActive != null) 'is_active': isActive,
      if (search != null && search.isNotEmpty) 'search': search,
      'skip': skip,
      'limit': limit,
    });
    return (r.data as List)
        .map((e) => TenantModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /tenants/{id}
  Future<TenantModel> getTenant(String id) async {
    final r = await _dio.get('/tenants/$id');
    return TenantModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// PATCH /tenants/{id}
  Future<TenantModel> updateTenant(String id, Map<String, dynamic> data) async {
    final r = await _dio.patch('/tenants/$id', data: data);
    return TenantModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// POST /tenants/{id}/renew-agreement
  Future<AgreementModel> renewAgreement(String tenantId, Map<String, dynamic> data) async {
    final r = await _dio.post('/tenants/$tenantId/renew-agreement', data: data);
    return AgreementModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// GET /tenants/{id}/agreements — full history, newest first (Phase M1.4-R)
  Future<List<AgreementModel>> listTenantAgreements(String tenantId) async {
    final r = await _dio.get('/tenants/$tenantId/agreements');
    return (r.data as List)
        .map((e) => AgreementModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ── Occupancy ──────────────────────────────────────────────────────────

  /// POST /occupancy/resident/move-in
  Future<void> residentMoveIn({
    required String flatId,
    required String residentId,
    required String moveInDate,
  }) async {
    await _dio.post('/occupancy/resident/move-in', data: {
      'flat_id': flatId,
      'resident_id': residentId,
      'move_in_date': moveInDate,
    });
  }

  /// POST /occupancy/resident/move-out
  Future<void> residentMoveOut({
    required String flatId,
    required String residentId,
    required String moveOutDate,
  }) async {
    await _dio.post('/occupancy/resident/move-out', data: {
      'flat_id': flatId,
      'resident_id': residentId,
      'move_out_date': moveOutDate,
    });
  }

  /// POST /occupancy/tenant/move-in
  Future<void> tenantMoveIn({
    required String flatId,
    required String tenantId,
    required String moveInDate,
    bool createAgreement = true,
  }) async {
    await _dio.post('/occupancy/tenant/move-in', data: {
      'flat_id': flatId,
      'tenant_id': tenantId,
      'move_in_date': moveInDate,
      'create_agreement': createAgreement,
    });
  }

  /// POST /occupancy/tenant/move-out
  Future<void> tenantMoveOut({
    required String flatId,
    required String tenantId,
    required String moveOutDate,
  }) async {
    await _dio.post('/occupancy/tenant/move-out', data: {
      'flat_id': flatId,
      'tenant_id': tenantId,
      'move_out_date': moveOutDate,
    });
  }

  /// GET /occupancy/flat/{flat_id}/history
  Future<List<OccupancyLogModel>> getFlatHistory(String flatId) async {
    final r = await _dio.get('/occupancy/flat/$flatId/history');
    return (r.data as List)
        .map((e) => OccupancyLogModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ── Vehicles ───────────────────────────────────────────────────────────

  /// POST /vehicles/
  Future<VehicleModel> createVehicle(Map<String, dynamic> data) async {
    final r = await _dio.post('/vehicles/', data: data);
    return VehicleModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// PATCH /vehicles/{id}
  Future<VehicleModel> updateVehicle(String id, Map<String, dynamic> data) async {
    final r = await _dio.patch('/vehicles/$id', data: data);
    return VehicleModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// GET /vehicles/flat/{flat_id}
  Future<List<VehicleModel>> vehiclesByFlat(String flatId) async {
    final r = await _dio.get('/vehicles/flat/$flatId');
    return (r.data as List)
        .map((e) => VehicleModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// DELETE /vehicles/{id} (deregister — soft delete)
  Future<void> deregisterVehicle(String id) async {
    await _dio.delete('/vehicles/$id');
  }
}
