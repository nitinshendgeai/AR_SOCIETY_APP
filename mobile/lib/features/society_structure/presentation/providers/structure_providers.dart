import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart';
import 'package:ar_society_app/features/society_structure/data/repositories/structure_repository.dart';
import 'package:ar_society_app/features/society_settings/presentation/providers/society_settings_providers.dart';

// ── Repository ────────────────────────────────────────────────────────────────

final structureRepoProvider = Provider<StructureRepository>(
  (_) => StructureRepository(),
);

// ── Wings ─────────────────────────────────────────────────────────────────────

final wingsProvider =
    AsyncNotifierProvider<WingsNotifier, List<WingModel>>(WingsNotifier.new);

class WingsNotifier extends AsyncNotifier<List<WingModel>> {
  @override
  Future<List<WingModel>> build() async {
    final society =
        await ref.watch(currentSocietyProvider.future);
    return ref.read(structureRepoProvider).getWingsBySociety(society.id);
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => build());
  }

  Future<WingModel> create({required String name, String? code,
      String? description, int? totalFloors}) async {
    final society = await ref.read(currentSocietyProvider.future);
    final wing = await ref.read(structureRepoProvider).createWing(
      name: name, societyId: society.id, code: code,
      description: description, totalFloors: totalFloors,
    );
    state = AsyncData([...state.valueOrNull ?? [], wing]);
    return wing;
  }

  Future<WingModel> update(String id, Map<String, dynamic> data) async {
    final updated = await ref.read(structureRepoProvider).updateWing(id, data);
    state = AsyncData(
      state.valueOrNull?.map((w) => w.id == id ? updated : w).toList() ?? [],
    );
    return updated;
  }

  Future<void> delete(String id) async {
    await ref.read(structureRepoProvider).deleteWing(id);
    state = AsyncData(
      state.valueOrNull?.where((w) => w.id != id).toList() ?? [],
    );
  }
}

// ── Floors per wing ───────────────────────────────────────────────────────────

final floorsByWingProvider = AsyncNotifierProviderFamily<FloorsByWingNotifier,
    List<FloorModel>, String>(FloorsByWingNotifier.new);

class FloorsByWingNotifier
    extends FamilyAsyncNotifier<List<FloorModel>, String> {
  @override
  Future<List<FloorModel>> build(String wingId) =>
      ref.read(structureRepoProvider).getFloorsByWing(wingId);

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
        () => ref.read(structureRepoProvider).getFloorsByWing(arg));
  }

  Future<FloorModel> create(
      {required int floorNumber,
      required String societyId,
      String? floorName}) async {
    final floor = await ref.read(structureRepoProvider).createFloor(
          floorNumber: floorNumber,
          wingId: arg,
          societyId: societyId,
          floorName: floorName,
        );
    state = AsyncData([...(state.valueOrNull ?? []), floor]
      ..sort((a, b) => a.floorNumber.compareTo(b.floorNumber)));
    return floor;
  }

  Future<void> delete(String id) async {
    await ref.read(structureRepoProvider).deleteFloor(id);
    state = AsyncData(
      state.valueOrNull?.where((f) => f.id != id).toList() ?? [],
    );
  }
}

// ── Flats per society ─────────────────────────────────────────────────────────

final flatsBySocietyProvider =
    AsyncNotifierProvider<FlatsBySocietyNotifier, List<FlatModel>>(
        FlatsBySocietyNotifier.new);

class FlatsBySocietyNotifier extends AsyncNotifier<List<FlatModel>> {
  @override
  Future<List<FlatModel>> build() async {
    final society = await ref.watch(currentSocietyProvider.future);
    return ref.read(structureRepoProvider).getFlatsBySociety(society.id);
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => build());
  }

  Future<FlatModel> create({
    required String flatNumber,
    required String wingId,
    int? floor,
    String? flatType,
    double? areaSqft,
    String? occupancyStatus,
    String? remarks,
  }) async {
    final flat = await ref.read(structureRepoProvider).createFlat(
          flatNumber: flatNumber, wingId: wingId, floor: floor,
          flatType: flatType, areaSqft: areaSqft,
          occupancyStatus: occupancyStatus, remarks: remarks,
        );
    state = AsyncData([...(state.valueOrNull ?? []), flat]);
    return flat;
  }

  Future<FlatModel> update(String id, Map<String, dynamic> data) async {
    final updated = await ref.read(structureRepoProvider).updateFlat(id, data);
    state = AsyncData(
      state.valueOrNull?.map((f) => f.id == id ? updated : f).toList() ?? [],
    );
    return updated;
  }

  Future<void> delete(String id) async {
    await ref.read(structureRepoProvider).deleteFlat(id);
    state = AsyncData(
      state.valueOrNull?.where((f) => f.id != id).toList() ?? [],
    );
  }
}
