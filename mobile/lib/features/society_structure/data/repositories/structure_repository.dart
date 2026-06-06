import 'package:ar_society_app/features/society_structure/data/datasources/structure_remote_datasource.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';

class StructureRepository {
  final StructureRemoteDataSource _ds;
  StructureRepository({StructureRemoteDataSource? ds})
      : _ds = ds ?? StructureRemoteDataSource();

  // Wings
  Future<List<WingModel>> getWingsBySociety(String id) => _ds.getWingsBySociety(id);
  Future<WingModel> createWing({required String name, required String societyId,
      String? code, String? description, int? totalFloors}) =>
      _ds.createWing(name: name, societyId: societyId, code: code,
          description: description, totalFloors: totalFloors);
  Future<WingModel> updateWing(String id, Map<String, dynamic> data) =>
      _ds.updateWing(id, data);
  Future<WingModel> toggleWing(String id, {required bool activate}) =>
      _ds.toggleWing(id, activate: activate);
  Future<void> deleteWing(String id) => _ds.deleteWing(id);

  // Floors
  Future<List<FloorModel>> getFloorsByWing(String wingId) =>
      _ds.getFloorsByWing(wingId);
  Future<FloorModel> createFloor({required int floorNumber,
      required String wingId, required String societyId, String? floorName}) =>
      _ds.createFloor(floorNumber: floorNumber, wingId: wingId,
          societyId: societyId, floorName: floorName);
  Future<FloorModel> updateFloor(String id, Map<String, dynamic> data) =>
      _ds.updateFloor(id, data);
  Future<void> deleteFloor(String id) => _ds.deleteFloor(id);

  // Flats
  Future<List<FlatModel>> getFlatsBySociety(String id) =>
      _ds.getFlatsBySociety(id);
  Future<List<FlatModel>> getFlatsByWing(String wingId) =>
      _ds.getFlatsByWing(wingId);
  Future<FlatModel> createFlat({required String flatNumber,
      required String wingId, int? floor, String? flatType,
      double? areaSqft, String? occupancyStatus, String? remarks}) =>
      _ds.createFlat(flatNumber: flatNumber, wingId: wingId, floor: floor,
          flatType: flatType, areaSqft: areaSqft,
          occupancyStatus: occupancyStatus, remarks: remarks);
  Future<FlatModel> updateFlat(String id, Map<String, dynamic> data) =>
      _ds.updateFlat(id, data);
  Future<void> deleteFlat(String id) => _ds.deleteFlat(id);
}
