import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/parking/data/repositories/parking_repository.dart';
import 'package:ar_society_app/features/parking/domain/entities/parking_entities.dart';

// ── Repository provider ───────────────────────────────────────────────────────

final parkingRepositoryProvider = Provider<ParkingRepository>((ref) {
  return ParkingRepository();
});

// ── Gate check state (validate → log) ───────────────────────────────────────

sealed class GateCheckState {}

class GateCheckInitial extends GateCheckState {}

class GateCheckLoading extends GateCheckState {}

class GateCheckLookedUp extends GateCheckState {
  final GateVehicleLookupEntity lookup;
  GateCheckLookedUp(this.lookup);
}

/// A confirmed entry/exit was written — carries the lookup that led to it
/// so the screen can keep showing the same details alongside the outcome.
class GateCheckLogged extends GateCheckState {
  final GateVehicleLookupEntity lookup;
  final ParkingAccessLogEntity log;
  GateCheckLogged(this.lookup, this.log);
}

class GateCheckError extends GateCheckState {
  final String message;
  GateCheckError(this.message);
}

class GateCheckNotifier extends StateNotifier<GateCheckState> {
  final ParkingRepository _repo;
  GateCheckNotifier(this._repo) : super(GateCheckInitial());

  Future<void> validate({
    required String societyId,
    required String vehicleNumber,
  }) async {
    state = GateCheckLoading();
    final result = await _repo.validateVehicle(
        societyId: societyId, vehicleNumber: vehicleNumber);
    state = switch (result) {
      ParkingSuccess(:final data) => GateCheckLookedUp(data),
      ParkingFailure(:final message) => GateCheckError(message),
    };
  }

  Future<void> logAccess({
    required String societyId,
    required GateAccessType accessType,
    String? notes,
  }) async {
    final current = state;
    if (current is! GateCheckLookedUp) return;
    state = GateCheckLoading();
    final result = await _repo.logAccess(
      societyId: societyId,
      vehicleNumber: current.lookup.vehicleNumber,
      accessType: accessType,
      notes: notes,
    );
    state = switch (result) {
      ParkingSuccess(:final data) => GateCheckLogged(current.lookup, data),
      ParkingFailure(:final message) => GateCheckError(message),
    };
  }

  void reset() => state = GateCheckInitial();
}

final gateCheckProvider =
    StateNotifierProvider<GateCheckNotifier, GateCheckState>((ref) {
  return GateCheckNotifier(ref.read(parkingRepositoryProvider));
});

// ── Zones / slots / allocations (management screen) ─────────────────────────

final parkingZonesProvider =
    FutureProvider.family<List<ParkingZoneEntity>, String>((ref, societyId) async {
  final repo = ref.read(parkingRepositoryProvider);
  final result = await repo.listZones(societyId);
  return switch (result) {
    ParkingSuccess(:final data) => data,
    ParkingFailure(:final message) => throw Exception(message),
  };
});

final parkingSlotsProvider =
    FutureProvider.family<List<ParkingSlotEntity>, String>((ref, societyId) async {
  final repo = ref.read(parkingRepositoryProvider);
  final result = await repo.listSlotsBySociety(societyId);
  return switch (result) {
    ParkingSuccess(:final data) => data,
    ParkingFailure(:final message) => throw Exception(message),
  };
});

final parkingAvailableSlotsProvider =
    FutureProvider.family<List<ParkingSlotEntity>, String>((ref, societyId) async {
  final repo = ref.read(parkingRepositoryProvider);
  final result = await repo.listAvailableSlots(societyId);
  return switch (result) {
    ParkingSuccess(:final data) => data,
    ParkingFailure(:final message) => throw Exception(message),
  };
});

final parkingAllocationsProvider =
    FutureProvider.family<List<ParkingAllocationEntity>, String>((ref, societyId) async {
  final repo = ref.read(parkingRepositoryProvider);
  final result = await repo.listAllocations(societyId);
  return switch (result) {
    ParkingSuccess(:final data) => data,
    ParkingFailure(:final message) => throw Exception(message),
  };
});

// ── Parking management actions (create zone/slot/allocation, release) ───────

sealed class ParkingActionState {}

class ParkingActionInitial extends ParkingActionState {}

class ParkingActionLoading extends ParkingActionState {}

class ParkingActionSuccess extends ParkingActionState {
  final String message;
  ParkingActionSuccess(this.message);
}

class ParkingActionError extends ParkingActionState {
  final String message;
  ParkingActionError(this.message);
}

class ParkingManagementNotifier extends StateNotifier<ParkingActionState> {
  final ParkingRepository _repo;
  final Ref _ref;
  ParkingManagementNotifier(this._repo, this._ref) : super(ParkingActionInitial());

  Future<void> createZone({
    required String societyId,
    required String name,
    String? code,
  }) async {
    state = ParkingActionLoading();
    final result = await _repo.createZone(societyId: societyId, name: name, code: code);
    switch (result) {
      case ParkingSuccess():
        state = ParkingActionSuccess('Zone created');
        _ref.invalidate(parkingZonesProvider(societyId));
      case ParkingFailure(:final message):
        state = ParkingActionError(message);
    }
  }

  Future<void> createSlot({
    required String societyId,
    required String zoneId,
    required String slotNumber,
    String slotType = 'resident',
  }) async {
    state = ParkingActionLoading();
    final result = await _repo.createSlot(
      societyId: societyId, zoneId: zoneId, slotNumber: slotNumber, slotType: slotType,
    );
    switch (result) {
      case ParkingSuccess():
        state = ParkingActionSuccess('Slot created');
        _ref.invalidate(parkingSlotsProvider(societyId));
        _ref.invalidate(parkingAvailableSlotsProvider(societyId));
        _ref.invalidate(parkingZonesProvider(societyId));
      case ParkingFailure(:final message):
        state = ParkingActionError(message);
    }
  }

  Future<void> createAllocation({
    required String societyId,
    required String slotId,
    String? flatId,
    String? vehicleId,
    required String allocationType,
    required String startDate,
    int? monthlyCharge,
  }) async {
    state = ParkingActionLoading();
    final result = await _repo.createAllocation(
      societyId: societyId, slotId: slotId, flatId: flatId, vehicleId: vehicleId,
      allocationType: allocationType, startDate: startDate, monthlyCharge: monthlyCharge,
    );
    switch (result) {
      case ParkingSuccess():
        state = ParkingActionSuccess('Parking allocated');
        _ref.invalidate(parkingAllocationsProvider(societyId));
        _ref.invalidate(parkingSlotsProvider(societyId));
        _ref.invalidate(parkingAvailableSlotsProvider(societyId));
      case ParkingFailure(:final message):
        state = ParkingActionError(message);
    }
  }

  Future<void> releaseAllocation(String allocationId, String societyId) async {
    state = ParkingActionLoading();
    final result = await _repo.releaseAllocation(allocationId);
    switch (result) {
      case ParkingSuccess():
        state = ParkingActionSuccess('Allocation released');
        _ref.invalidate(parkingAllocationsProvider(societyId));
        _ref.invalidate(parkingSlotsProvider(societyId));
        _ref.invalidate(parkingAvailableSlotsProvider(societyId));
      case ParkingFailure(:final message):
        state = ParkingActionError(message);
    }
  }

  void reset() => state = ParkingActionInitial();
}

final parkingManagementProvider =
    StateNotifierProvider<ParkingManagementNotifier, ParkingActionState>((ref) {
  return ParkingManagementNotifier(ref.read(parkingRepositoryProvider), ref);
});
