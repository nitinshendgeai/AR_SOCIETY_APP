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
}
