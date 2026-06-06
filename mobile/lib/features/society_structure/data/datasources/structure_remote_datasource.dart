import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';

class StructureRemoteDataSource {
  final Dio _dio;
  StructureRemoteDataSource({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  // ── Wings ─────────────────────────────────────────────────────────────────

  Future<List<WingModel>> getWingsBySociety(String societyId) async {
    final r = await _dio.get('/wings/by-society/$societyId');
    return (r.data as List)
        .map((e) => WingModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<WingModel> createWing({
    required String name,
    required String societyId,
    String? code,
    String? description,
    int? totalFloors,
  }) async {
    final r = await _dio.post('/wings/', data: {
      'name': name,
      'society_id': societyId,
      if (code != null) 'code': code,
      if (description != null) 'description': description,
      if (totalFloors != null) 'total_floors': totalFloors,
    });
    return WingModel.fromJson(r.data as Map<String, dynamic>);
  }

  Future<WingModel> updateWing(String wingId, Map<String, dynamic> data) async {
    final r = await _dio.patch('/wings/$wingId', data: data);
    return WingModel.fromJson(r.data as Map<String, dynamic>);
  }

  Future<WingModel> toggleWing(String wingId, {required bool activate}) async {
    final action = activate ? 'activate' : 'deactivate';
    final r = await _dio.post('/wings/$wingId/$action');
    return WingModel.fromJson(r.data as Map<String, dynamic>);
  }

  Future<void> deleteWing(String wingId) async {
    await _dio.delete('/wings/$wingId');
  }

  // ── Floors ────────────────────────────────────────────────────────────────

  Future<List<FloorModel>> getFloorsByWing(String wingId) async {
    final r = await _dio.get('/floors/by-wing/$wingId');
    return (r.data as List)
        .map((e) => FloorModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<FloorModel> createFloor({
    required int floorNumber,
    required String wingId,
    required String societyId,
    String? floorName,
  }) async {
    final r = await _dio.post('/floors/', data: {
      'floor_number': floorNumber,
      'wing_id': wingId,
      'society_id': societyId,
      if (floorName != null && floorName.isNotEmpty) 'floor_name': floorName,
    });
    return FloorModel.fromJson(r.data as Map<String, dynamic>);
  }

  Future<FloorModel> updateFloor(
      String floorId, Map<String, dynamic> data) async {
    final r = await _dio.patch('/floors/$floorId', data: data);
    return FloorModel.fromJson(r.data as Map<String, dynamic>);
  }

  Future<void> deleteFloor(String floorId) async {
    await _dio.delete('/floors/$floorId');
  }

  // ── Flats ─────────────────────────────────────────────────────────────────

  Future<List<FlatModel>> getFlatsBySociety(String societyId) async {
    final r = await _dio.get('/flats/by-society/$societyId');
    return (r.data as List)
        .map((e) => FlatModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<FlatModel>> getFlatsByWing(String wingId) async {
    final r = await _dio.get('/flats/by-wing/$wingId');
    return (r.data as List)
        .map((e) => FlatModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<FlatModel> createFlat({
    required String flatNumber,
    required String wingId,
    int? floor,
    String? flatType,
    double? areaSqft,
    String? occupancyStatus,
    String? remarks,
  }) async {
    final r = await _dio.post('/flats/', data: {
      'flat_number': flatNumber,
      'wing_id': wingId,
      if (floor != null) 'floor': floor,
      if (flatType != null) 'flat_type': flatType,
      if (areaSqft != null) 'area_sqft': areaSqft,
      if (occupancyStatus != null) 'occupancy_status': occupancyStatus,
      if (remarks != null && remarks.isNotEmpty) 'remarks': remarks,
    });
    return FlatModel.fromJson(r.data as Map<String, dynamic>);
  }

  Future<FlatModel> updateFlat(
      String flatId, Map<String, dynamic> data) async {
    final r = await _dio.patch('/flats/$flatId', data: data);
    return FlatModel.fromJson(r.data as Map<String, dynamic>);
  }

  Future<void> deleteFlat(String flatId) async {
    await _dio.delete('/flats/$flatId');
  }
}
