import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';

// ── Repository provider ───────────────────────────────────────────────────────

final staffRepositoryProvider = Provider<StaffRepository>((ref) {
  return StaffRepository();
});

// ── Staff ID provider (extracted from current user, fetched from backend) ──────

/// Async provider: fetches StaffEntity for the current logged-in user.
/// Staff user_id links to User, then to Staff record via /staff/{id}.
final currentStaffProvider = FutureProvider<StaffEntity?>((ref) async {
  final user = ref.watch(currentUserProvider);
  if (user == null) return null;
  // The staff_id must come from user profile or a dedicated endpoint.
  // For now we store it after first successful staff fetch.
  final repo = ref.read(staffRepositoryProvider);
  // Try to get staff by stored staff_id if available
  final staffId = ref.read(staffIdProvider);
  if (staffId == null) return null;
  final result = await repo.getStaff(staffId);
  return switch (result) {
    StaffSuccess(:final data) => data,
    StaffFailure() => null,
  };
});

/// Manually set staff_id once we know it (stored in state).
final staffIdProvider = StateProvider<String?>((ref) => null);

// ── Attendance state ──────────────────────────────────────────────────────────

sealed class AttendanceState {}
class AttendanceInitial   extends AttendanceState {}
class AttendanceLoading   extends AttendanceState {}
class AttendanceLoaded    extends AttendanceState {
  final AttendanceEntity? today;
  final List<AttendanceEntity> history;
  AttendanceLoaded({this.today, required this.history});
}
class AttendanceSuccess   extends AttendanceState {
  final AttendanceEntity record;
  final String message;
  AttendanceSuccess(this.record, this.message);
}
class AttendanceError     extends AttendanceState {
  final String message;
  final bool isDuplicate;
  AttendanceError(this.message, {this.isDuplicate = false});
}

class AttendanceNotifier extends StateNotifier<AttendanceState> {
  final StaffRepository _repo;
  AttendanceNotifier(this._repo) : super(AttendanceInitial());

  Future<void> loadHistory(String staffId) async {
    state = AttendanceLoading();
    final result = await _repo.getAttendanceHistory(staffId, limit: 30);
    switch (result) {
      case StaffSuccess(:final data):
        // Determine today's record
        final todayStr = DateTime.now().toIso8601String().substring(0, 10);
        final todayRecord = data.where((a) => a.attendanceDate == todayStr).firstOrNull;
        state = AttendanceLoaded(today: todayRecord, history: data);
      case StaffFailure(:final message):
        state = AttendanceError(message);
    }
  }

  Future<void> checkIn(String staffId, {String? notes}) async {
    state = AttendanceLoading();
    final result = await _repo.checkIn(staffId, notes: notes);
    switch (result) {
      case StaffSuccess(:final data):
        state = AttendanceSuccess(data, 'Checked in successfully');
        await loadHistory(staffId);
      case StaffFailure(:final message, :final statusCode):
        state = AttendanceError(message, isDuplicate: statusCode == 409);
    }
  }

  Future<void> checkOut(String staffId, {String? notes}) async {
    state = AttendanceLoading();
    final result = await _repo.checkOut(staffId, notes: notes);
    switch (result) {
      case StaffSuccess(:final data):
        state = AttendanceSuccess(data, 'Checked out successfully');
        await loadHistory(staffId);
      case StaffFailure(:final message, :final statusCode):
        state = AttendanceError(message, isDuplicate: statusCode == 409);
    }
  }

  void clearStatus() {
    if (state is AttendanceSuccess || state is AttendanceError) {
      state = AttendanceInitial();
    }
  }
}

final attendanceProvider =
    StateNotifierProvider<AttendanceNotifier, AttendanceState>((ref) {
  return AttendanceNotifier(ref.read(staffRepositoryProvider));
});

// ── Duty state ────────────────────────────────────────────────────────────────

sealed class DutyState {}
class DutyInitial extends DutyState {}
class DutyLoading extends DutyState {}
class DutyLoaded  extends DutyState {
  final List<DutyEntity> duties;
  DutyLoaded(this.duties);
}
class DutyError   extends DutyState {
  final String message;
  DutyError(this.message);
}

class DutyNotifier extends StateNotifier<DutyState> {
  final StaffRepository _repo;
  DutyNotifier(this._repo) : super(DutyInitial());

  Future<void> loadDuties(String staffId) async {
    state = DutyLoading();
    final result = await _repo.getMyDuties(staffId);
    switch (result) {
      case StaffSuccess(:final data): state = DutyLoaded(data);
      case StaffFailure(:final message): state = DutyError(message);
    }
  }

  Future<void> completeDuty(String dutyId, String staffId) async {
    final result = await _repo.completeDuty(dutyId);
    switch (result) {
      case StaffSuccess(): await loadDuties(staffId);
      case StaffFailure(:final message): state = DutyError(message);
    }
  }
}

final dutyProvider = StateNotifierProvider<DutyNotifier, DutyState>((ref) {
  return DutyNotifier(ref.read(staffRepositoryProvider));
});

// ── Handover state ────────────────────────────────────────────────────────────

sealed class HandoverState {}
class HandoverInitial extends HandoverState {}
class HandoverLoading extends HandoverState {}
class HandoverLoaded  extends HandoverState {
  final List<HandoverEntity> pending;
  final List<HandoverEntity> history;
  HandoverLoaded({required this.pending, required this.history});
}
class HandoverCreated extends HandoverState {
  final HandoverEntity handover;
  HandoverCreated(this.handover);
}
class HandoverError   extends HandoverState {
  final String message;
  HandoverError(this.message);
}

class HandoverNotifier extends StateNotifier<HandoverState> {
  final StaffRepository _repo;
  HandoverNotifier(this._repo) : super(HandoverInitial());

  Future<void> loadHandovers(String staffId) async {
    state = HandoverLoading();
    final pendingResult = await _repo.getPendingHandovers(staffId);
    final historyResult = await _repo.getHandoverHistory(staffId);
    if (pendingResult is StaffFailure && historyResult is StaffFailure) {
      state = HandoverError((pendingResult as StaffFailure).message);
      return;
    }
    state = HandoverLoaded(
      pending: pendingResult is StaffSuccess ? (pendingResult as StaffSuccess).data : [],
      history: historyResult is StaffSuccess ? (historyResult as StaffSuccess).data : [],
    );
  }

  Future<void> createAndSubmit({
    required String societyId,
    String? outgoingStaffId,
    String? incomingStaffId,
    String? area,
    required String summary,
    required List<Map<String, dynamic>> items,
  }) async {
    state = HandoverLoading();
    final createResult = await _repo.createHandover(
      societyId: societyId,
      outgoingStaffId: outgoingStaffId,
      incomingStaffId: incomingStaffId,
      area: area,
      summary: summary,
      items: items,
    );
    if (createResult is StaffFailure) {
      state = HandoverError((createResult as StaffFailure).message);
      return;
    }
    final handover = (createResult as StaffSuccess<HandoverEntity>).data;
    // If incoming staff is set, auto-submit
    if (incomingStaffId != null) {
      final submitResult = await _repo.submitHandover(handover.id);
      if (submitResult is StaffSuccess) {
        state = HandoverCreated((submitResult as StaffSuccess<HandoverEntity>).data);
        return;
      }
    }
    state = HandoverCreated(handover);
  }

  Future<void> acceptHandover(String handoverId, String staffId, {String? notes}) async {
    final result = await _repo.acceptHandover(handoverId, notes: notes);
    switch (result) {
      case StaffSuccess(): await loadHandovers(staffId);
      case StaffFailure(:final message): state = HandoverError(message);
    }
  }

  Future<void> disputeHandover(String handoverId, String staffId, String reason) async {
    final result = await _repo.disputeHandover(handoverId, reason);
    switch (result) {
      case StaffSuccess(): await loadHandovers(staffId);
      case StaffFailure(:final message): state = HandoverError(message);
    }
  }

  void reset() => state = HandoverInitial();
}

final handoverProvider = StateNotifierProvider<HandoverNotifier, HandoverState>((ref) {
  return HandoverNotifier(ref.read(staffRepositoryProvider));
});
