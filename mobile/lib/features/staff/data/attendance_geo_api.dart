import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';

/// Whether the staff app must send the phone's location with a check-in.
class GeoStatus {
  final bool enabled;
  final String mode; // off | flag | block
  final double maxAccuracyM;
  const GeoStatus({required this.enabled, required this.mode, required this.maxAccuracyM});

  factory GeoStatus.fromJson(Map<String, dynamic> j) => GeoStatus(
        enabled: j['enabled'] as bool? ?? false,
        mode: j['mode'] as String? ?? 'off',
        maxAccuracyM: (j['max_accuracy_m'] as num?)?.toDouble() ?? 20,
      );
}

class GeoSpot {
  final String id, name;
  final double latitude, longitude;
  final int radiusM;
  const GeoSpot({required this.id, required this.name, required this.latitude, required this.longitude, required this.radiusM});

  factory GeoSpot.fromJson(Map<String, dynamic> j) => GeoSpot(
        id: j['id'] as String,
        name: j['name'] as String,
        latitude: (j['latitude'] as num).toDouble(),
        longitude: (j['longitude'] as num).toDouble(),
        radiusM: (j['radius_m'] as num).toInt(),
      );
}

/// The society's check-in spots and how the location check is applied.
class GeoConfig {
  final String mode;
  final int maxAccuracyM;
  final List<GeoSpot> spots;
  const GeoConfig({required this.mode, required this.maxAccuracyM, required this.spots});

  factory GeoConfig.fromJson(Map<String, dynamic> j) {
    final s = j['settings'] as Map<String, dynamic>;
    return GeoConfig(
      mode: s['mode'] as String,
      maxAccuracyM: (s['max_accuracy_m'] as num).toInt(),
      spots: [for (final x in j['spots'] as List) GeoSpot.fromJson(Map<String, dynamic>.from(x as Map))],
    );
  }
}

class AttendanceGeoApi {
  final Dio _dio;
  AttendanceGeoApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<GeoStatus> status() async =>
      GeoStatus.fromJson((await _dio.get('/staff/attendance-geo/status')).data as Map<String, dynamic>);

  Future<GeoConfig> config(String societyId) async =>
      GeoConfig.fromJson((await _dio.get('/staff/attendance-geo/$societyId')).data as Map<String, dynamic>);

  Future<void> saveSettings(String societyId, {required String mode, required int maxAccuracyM}) =>
      _dio.put('/staff/attendance-geo/$societyId/settings', data: {'mode': mode, 'max_accuracy_m': maxAccuracyM});

  Future<void> addSpot(String societyId,
          {required String name, required double latitude, required double longitude, required int radiusM}) =>
      _dio.post('/staff/attendance-geo/spots',
          data: {'society_id': societyId, 'name': name, 'latitude': latitude, 'longitude': longitude, 'radius_m': radiusM});

  Future<void> editSpot(String id, {String? name, double? latitude, double? longitude, int? radiusM}) =>
      _dio.patch('/staff/attendance-geo/spots/$id', data: {
        if (name != null) 'name': name,
        if (latitude != null) 'latitude': latitude,
        if (longitude != null) 'longitude': longitude,
        if (radiusM != null) 'radius_m': radiusM,
      });

  Future<void> removeSpot(String id) => _dio.delete('/staff/attendance-geo/spots/$id');
}

final attendanceGeoApiProvider = Provider<AttendanceGeoApi>((_) => AttendanceGeoApi());

final attendanceGeoStatusProvider =
    FutureProvider.autoDispose<GeoStatus>((ref) => ref.watch(attendanceGeoApiProvider).status());

final attendanceGeoConfigProvider = FutureProvider.autoDispose.family<GeoConfig, String>(
    (ref, societyId) => ref.watch(attendanceGeoApiProvider).config(societyId));
