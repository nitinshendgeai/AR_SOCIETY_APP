import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/data/repositories/resident_master_repository.dart';

final residentMasterRepositoryProvider = Provider<ResidentMasterRepository>((ref) {
  return ResidentMasterRepository();
});

// ── Resident list state ─────────────────────────────────────────────────────

sealed class ResidentListState {}
class ResidentListInitial extends ResidentListState {}
class ResidentListLoading extends ResidentListState {}
class ResidentListLoaded extends ResidentListState {
  final List<ResidentModel> residents;
  ResidentListLoaded(this.residents);
}
class ResidentListError extends ResidentListState {
  final String message;
  final int? statusCode;
  ResidentListError(this.message, {this.statusCode});
}

class ResidentListNotifier extends StateNotifier<ResidentListState> {
  final ResidentMasterRepository _repo;
  ResidentListNotifier(this._repo) : super(ResidentListInitial());

  String? _lastResidentType;
  bool? _lastIsActive = true;
  String? _lastSearch;
  String? _lastFlatId;

  Future<void> load({String? residentType, bool? isActive = true, String? search, String? flatId}) async {
    _lastResidentType = residentType;
    _lastIsActive = isActive;
    _lastSearch = search;
    _lastFlatId = flatId;
    state = ResidentListLoading();
    final result = await _repo.listResidents(
      flatId: flatId, residentType: residentType, isActive: isActive, search: search,
    );
    switch (result) {
      case RmSuccess(:final data): state = ResidentListLoaded(data);
      case RmFailure(:final message, :final statusCode): state = ResidentListError(message, statusCode: statusCode);
    }
  }

  // Re-runs load() with whatever filters were last used, instead of the
  // caller needing to know the list screen's current filter state — used
  // by the form screen after create/update so the list doesn't get stuck
  // on ResidentListInitial (ref.invalidate() alone resets state but never
  // re-fetches, since the list screen's _load() only runs from initState).
  Future<void> refresh() => load(
        residentType: _lastResidentType, isActive: _lastIsActive,
        search: _lastSearch, flatId: _lastFlatId,
      );
}

final residentListProvider = StateNotifierProvider<ResidentListNotifier, ResidentListState>((ref) {
  return ResidentListNotifier(ref.read(residentMasterRepositoryProvider));
});

// ── Single resident (detail screen — always fetched fresh) ─────────────────

final residentDetailProvider = FutureProvider.family<ResidentModel, String>((ref, id) async {
  final repo = ref.read(residentMasterRepositoryProvider);
  final result = await repo.getResident(id);
  return switch (result) {
    RmSuccess(:final data) => data,
    RmFailure(:final message) => throw Exception(message),
  };
});

// ── Residents by flat (family/tenancy sections on Resident/Flat detail) ────

final residentsByFlatProvider = FutureProvider.family<List<ResidentModel>, String>((ref, flatId) async {
  final repo = ref.read(residentMasterRepositoryProvider);
  final result = await repo.listResidents(flatId: flatId, isActive: true);
  return switch (result) {
    RmSuccess(:final data) => data,
    RmFailure() => <ResidentModel>[],
  };
});

// ── Resident form state (create / edit) ─────────────────────────────────────

sealed class ResidentFormState {}
class ResidentFormInitial extends ResidentFormState {}
class ResidentFormLoading extends ResidentFormState {}
class ResidentFormSuccess extends ResidentFormState {
  final ResidentModel resident;
  final String message;
  ResidentFormSuccess(this.resident, this.message);
}
class ResidentFormError extends ResidentFormState {
  final String message;
  ResidentFormError(this.message);
}

class ResidentFormNotifier extends StateNotifier<ResidentFormState> {
  final ResidentMasterRepository _repo;
  ResidentFormNotifier(this._repo) : super(ResidentFormInitial());

  Future<void> create(Map<String, dynamic> data) async {
    state = ResidentFormLoading();
    final result = await _repo.createResident(data);
    state = switch (result) {
      RmSuccess(:final data) => ResidentFormSuccess(
          data,
          data.warnings.isNotEmpty
              ? 'Resident added — ${data.warnings.first}'
              : 'Resident added successfully',
        ),
      RmFailure(:final message) => ResidentFormError(message),
    };
  }

  Future<void> update(String id, Map<String, dynamic> data) async {
    state = ResidentFormLoading();
    final result = await _repo.updateResident(id, data);
    state = switch (result) {
      RmSuccess(:final data) => ResidentFormSuccess(data, 'Resident updated successfully'),
      RmFailure(:final message) => ResidentFormError(message),
    };
  }

  void reset() => state = ResidentFormInitial();
}

final residentFormProvider = StateNotifierProvider<ResidentFormNotifier, ResidentFormState>((ref) {
  return ResidentFormNotifier(ref.read(residentMasterRepositoryProvider));
});

// ── Tenant list state ────────────────────────────────────────────────────────

sealed class TenantListState {}
class TenantListInitial extends TenantListState {}
class TenantListLoading extends TenantListState {}
class TenantListLoaded extends TenantListState {
  final List<TenantModel> tenants;
  TenantListLoaded(this.tenants);
}
class TenantListError extends TenantListState {
  final String message;
  final int? statusCode;
  TenantListError(this.message, {this.statusCode});
}

class TenantListNotifier extends StateNotifier<TenantListState> {
  final ResidentMasterRepository _repo;
  TenantListNotifier(this._repo) : super(TenantListInitial());

  bool? _lastIsActive = true;
  String? _lastSearch;
  String? _lastFlatId;

  Future<void> load({bool? isActive = true, String? search, String? flatId}) async {
    _lastIsActive = isActive;
    _lastSearch = search;
    _lastFlatId = flatId;
    state = TenantListLoading();
    final result = await _repo.listTenants(flatId: flatId, isActive: isActive, search: search);
    switch (result) {
      case RmSuccess(:final data): state = TenantListLoaded(data);
      case RmFailure(:final message, :final statusCode): state = TenantListError(message, statusCode: statusCode);
    }
  }

  // See ResidentListNotifier.refresh() — same fix, same reason.
  Future<void> refresh() => load(isActive: _lastIsActive, search: _lastSearch, flatId: _lastFlatId);
}

final tenantListProvider = StateNotifierProvider<TenantListNotifier, TenantListState>((ref) {
  return TenantListNotifier(ref.read(residentMasterRepositoryProvider));
});

// ── Single tenant (detail screen — always fetched fresh) ───────────────────

final tenantDetailProvider = FutureProvider.family<TenantModel, String>((ref, id) async {
  final repo = ref.read(residentMasterRepositoryProvider);
  final result = await repo.getTenant(id);
  return switch (result) {
    RmSuccess(:final data) => data,
    RmFailure(:final message) => throw Exception(message),
  };
});

// ── Tenants by flat ──────────────────────────────────────────────────────────

final tenantsByFlatProvider = FutureProvider.family<List<TenantModel>, String>((ref, flatId) async {
  final repo = ref.read(residentMasterRepositoryProvider);
  final result = await repo.listTenants(flatId: flatId, isActive: true);
  return switch (result) {
    RmSuccess(:final data) => data,
    RmFailure() => <TenantModel>[],
  };
});

// ── Tenant form state (create / edit / renew agreement) ────────────────────

sealed class TenantFormState {}
class TenantFormInitial extends TenantFormState {}
class TenantFormLoading extends TenantFormState {}
class TenantFormSuccess extends TenantFormState {
  final TenantModel tenant;
  final String message;
  TenantFormSuccess(this.tenant, this.message);
}
class TenantFormError extends TenantFormState {
  final String message;
  TenantFormError(this.message);
}
class AgreementRenewalSuccess extends TenantFormState {
  final AgreementModel agreement;
  AgreementRenewalSuccess(this.agreement);
}

class TenantFormNotifier extends StateNotifier<TenantFormState> {
  final ResidentMasterRepository _repo;
  TenantFormNotifier(this._repo) : super(TenantFormInitial());

  Future<void> create(Map<String, dynamic> data) async {
    state = TenantFormLoading();
    final result = await _repo.createTenant(data);
    state = switch (result) {
      RmSuccess(:final data) => TenantFormSuccess(
          data,
          data.warnings.isNotEmpty
              ? 'Tenant added — ${data.warnings.first}'
              : 'Tenant added successfully',
        ),
      RmFailure(:final message) => TenantFormError(message),
    };
  }

  Future<void> update(String id, Map<String, dynamic> data) async {
    state = TenantFormLoading();
    final result = await _repo.updateTenant(id, data);
    state = switch (result) {
      RmSuccess(:final data) => TenantFormSuccess(data, 'Tenant updated successfully'),
      RmFailure(:final message) => TenantFormError(message),
    };
  }

  Future<void> renewAgreement(String tenantId, Map<String, dynamic> data) async {
    state = TenantFormLoading();
    final result = await _repo.renewAgreement(tenantId, data);
    state = switch (result) {
      RmSuccess(:final data) => AgreementRenewalSuccess(data),
      RmFailure(:final message) => TenantFormError(message),
    };
  }

  void reset() => state = TenantFormInitial();
}

final tenantFormProvider = StateNotifierProvider<TenantFormNotifier, TenantFormState>((ref) {
  return TenantFormNotifier(ref.read(residentMasterRepositoryProvider));
});

// ── Agreement history (Phase M1.4-R) ─────────────────────────────────────

/// Full agreement history for a tenant — current + historical, newest first
/// (see backend TenantService.list_agreements). Throws on failure so the UI
/// can distinguish a genuine ERROR state from an empty (but successful) list.
final tenantAgreementsProvider = FutureProvider.family<List<AgreementModel>, String>((ref, tenantId) async {
  final repo = ref.read(residentMasterRepositoryProvider);
  final result = await repo.listTenantAgreements(tenantId);
  return switch (result) {
    RmSuccess(:final data) => data,
    RmFailure(:final message) => throw Exception(message),
  };
});

// ── Occupancy actions (move-in / move-out) ──────────────────────────────────

sealed class OccupancyActionState {}
class OccupancyActionInitial extends OccupancyActionState {}
class OccupancyActionLoading extends OccupancyActionState {}
class OccupancyActionSuccess extends OccupancyActionState {
  final String message;
  OccupancyActionSuccess(this.message);
}
class OccupancyActionError extends OccupancyActionState {
  final String message;
  OccupancyActionError(this.message);
}

class OccupancyActionNotifier extends StateNotifier<OccupancyActionState> {
  final ResidentMasterRepository _repo;
  OccupancyActionNotifier(this._repo) : super(OccupancyActionInitial());

  Future<void> residentMoveIn(String flatId, String residentId, String moveInDate) async {
    state = OccupancyActionLoading();
    final result = await _repo.residentMoveIn(flatId: flatId, residentId: residentId, moveInDate: moveInDate);
    state = switch (result) {
      RmSuccess() => OccupancyActionSuccess('Resident moved in successfully'),
      RmFailure(:final message) => OccupancyActionError(message),
    };
  }

  Future<void> residentMoveOut(String flatId, String residentId, String moveOutDate) async {
    state = OccupancyActionLoading();
    final result = await _repo.residentMoveOut(flatId: flatId, residentId: residentId, moveOutDate: moveOutDate);
    state = switch (result) {
      RmSuccess() => OccupancyActionSuccess('Resident moved out successfully'),
      RmFailure(:final message) => OccupancyActionError(message),
    };
  }

  Future<void> tenantMoveIn(String flatId, String tenantId, String moveInDate) async {
    state = OccupancyActionLoading();
    final result = await _repo.tenantMoveIn(flatId: flatId, tenantId: tenantId, moveInDate: moveInDate);
    state = switch (result) {
      RmSuccess() => OccupancyActionSuccess('Tenant moved in successfully'),
      RmFailure(:final message) => OccupancyActionError(message),
    };
  }

  Future<void> tenantMoveOut(String flatId, String tenantId, String moveOutDate) async {
    state = OccupancyActionLoading();
    final result = await _repo.tenantMoveOut(flatId: flatId, tenantId: tenantId, moveOutDate: moveOutDate);
    state = switch (result) {
      RmSuccess() => OccupancyActionSuccess('Tenant moved out successfully'),
      RmFailure(:final message) => OccupancyActionError(message),
    };
  }

  void reset() => state = OccupancyActionInitial();
}

final occupancyActionProvider = StateNotifierProvider<OccupancyActionNotifier, OccupancyActionState>((ref) {
  return OccupancyActionNotifier(ref.read(residentMasterRepositoryProvider));
});

// ── Flat occupancy history ──────────────────────────────────────────────────

final flatHistoryProvider = FutureProvider.family<List<OccupancyLogModel>, String>((ref, flatId) async {
  final repo = ref.read(residentMasterRepositoryProvider);
  final result = await repo.getFlatHistory(flatId);
  return switch (result) {
    RmSuccess(:final data) => data,
    RmFailure() => <OccupancyLogModel>[],
  };
});

// ── Vehicles by flat ──────────────────────────────────────────────────────

final vehiclesByFlatProvider =
    AsyncNotifierProviderFamily<VehiclesByFlatNotifier, List<VehicleModel>, String>(
        VehiclesByFlatNotifier.new);

class VehiclesByFlatNotifier extends FamilyAsyncNotifier<List<VehicleModel>, String> {
  @override
  Future<List<VehicleModel>> build(String flatId) async {
    final repo = ref.read(residentMasterRepositoryProvider);
    final result = await repo.vehiclesByFlat(flatId);
    return switch (result) {
      RmSuccess(:final data) => data,
      RmFailure(:final message) => throw Exception(message),
    };
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => build(arg));
  }

  Future<VehicleModel> add(Map<String, dynamic> data) async {
    final repo = ref.read(residentMasterRepositoryProvider);
    final result = await repo.createVehicle(data);
    switch (result) {
      case RmSuccess(:final data):
        state = AsyncData([...(state.valueOrNull ?? []), data]);
        return data;
      case RmFailure(:final message):
        throw Exception(message);
    }
  }

  Future<VehicleModel> edit(String id, Map<String, dynamic> data) async {
    final repo = ref.read(residentMasterRepositoryProvider);
    final result = await repo.updateVehicle(id, data);
    switch (result) {
      case RmSuccess(:final data):
        state = AsyncData(state.valueOrNull?.map((v) => v.id == id ? data : v).toList() ?? [data]);
        return data;
      case RmFailure(:final message):
        throw Exception(message);
    }
  }

  Future<void> remove(String id) async {
    final repo = ref.read(residentMasterRepositoryProvider);
    final result = await repo.deregisterVehicle(id);
    switch (result) {
      case RmSuccess():
        state = AsyncData(state.valueOrNull?.where((v) => v.id != id).toList() ?? []);
      case RmFailure(:final message):
        throw Exception(message);
    }
  }
}
