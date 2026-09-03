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
