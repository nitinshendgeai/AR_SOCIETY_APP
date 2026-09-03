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
}
