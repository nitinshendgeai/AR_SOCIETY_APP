import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';

// ── Repository provider ───────────────────────────────────────────────────────

final staffRepositoryProvider = Provider<StaffRepository>((ref) {
  return StaffRepository();
});

// ── Staff ID provider (extracted from current user, fetched from backend) ──────

/// Async provider: auto-resolves Staff record for the current user via /staff/by-user/{user_id}.
/// Falls back to manually set staffIdProvider if the API returns nothing.
final currentStaffProvider = FutureProvider<StaffEntity?>((ref) async {
  final user = ref.watch(currentUserProvider);
  if (user == null) return null;
  final repo = ref.read(staffRepositoryProvider);
  final result = await repo.getStaffByUser(user.id);
  if (result is StaffSuccess<StaffEntity>) {
    return result.data;
  }
  // Fallback: manual override via staffIdProvider
  final staffId = ref.read(staffIdProvider);
  if (staffId == null) return null;
  final fallback = await repo.getStaff(staffId);
  return switch (fallback) {
    StaffSuccess(:final data) => data,
    StaffFailure() => null,
  };
});

/// Can be set manually as fallback when auto-resolution fails.
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

  /// Toggles one checklist item on a duty, then reloads the duty list so
  /// DutyEntity.canComplete (and the rendered checkbox) reflect the change —
  /// mirrors completeDuty()'s reload-after-mutate pattern above.
  Future<void> toggleChecklistItem(
      String dutyId, String itemId, String staffId, {required bool isCompleted}) async {
    final result = await _repo.completeChecklistItem(dutyId, itemId, isCompleted: isCompleted);
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
    if (pendingResult is StaffFailure || historyResult is StaffFailure) {
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

// ── Staff list state ──────────────────────────────────────────────────────────

sealed class StaffListState {}
class StaffListInitial extends StaffListState {}
class StaffListLoading  extends StaffListState {}
class StaffListLoaded   extends StaffListState {
  final List<StaffEntity> staff;
  StaffListLoaded(this.staff);
}
class StaffListError    extends StaffListState {
  final String message;
  final int? statusCode;
  StaffListError(this.message, {this.statusCode});
}

class StaffListNotifier extends StateNotifier<StaffListState> {
  final StaffRepository _repo;
  StaffListNotifier(this._repo) : super(StaffListInitial());

  Future<void> load(String societyId, {String? department}) async {
    state = StaffListLoading();
    final result = await _repo.listStaff(societyId, department: department);
    switch (result) {
      case StaffSuccess(:final data): state = StaffListLoaded(data);
      case StaffFailure(:final message, :final statusCode): state = StaffListError(message, statusCode: statusCode);
    }
  }
}

final staffListProvider = StateNotifierProvider<StaffListNotifier, StaffListState>((ref) {
  return StaffListNotifier(ref.read(staffRepositoryProvider));
});

// ── Attendance approval state ─────────────────────────────────────────────────

sealed class ApprovalState {}
class ApprovalInitial extends ApprovalState {}
class ApprovalLoading  extends ApprovalState {}
class ApprovalLoaded   extends ApprovalState {
  final List<AttendanceEntity> pendingCheckin;
  final List<AttendanceEntity> pendingCheckout;
  ApprovalLoaded({required this.pendingCheckin, required this.pendingCheckout});
}
class ApprovalSuccess  extends ApprovalState { final String message; ApprovalSuccess(this.message); }
class ApprovalError    extends ApprovalState { final String message; ApprovalError(this.message); }

class ApprovalNotifier extends StateNotifier<ApprovalState> {
  final StaffRepository _repo;
  ApprovalNotifier(this._repo) : super(ApprovalInitial());

  Future<void> load(String societyId, {String? department}) async {
    state = ApprovalLoading();
    final checkinResult  = await _repo.getPendingAttendance(societyId, department: department);
    final checkoutResult = await _repo.getPendingCheckout(societyId, department: department);

    final checkin  = checkinResult  is StaffSuccess ? (checkinResult  as StaffSuccess<List<AttendanceEntity>>).data : <AttendanceEntity>[];
    final checkout = checkoutResult is StaffSuccess ? (checkoutResult as StaffSuccess<List<AttendanceEntity>>).data : <AttendanceEntity>[];

    if (checkinResult is StaffFailure || checkoutResult is StaffFailure) {
      state = ApprovalError((checkinResult as StaffFailure).message);
      return;
    }
    state = ApprovalLoaded(pendingCheckin: checkin, pendingCheckout: checkout);
  }

  Future<void> approveCheckin(String attendanceId, String societyId, {String? notes, String? department}) async {
    final result = await _repo.approveAttendance(attendanceId, notes: notes);
    switch (result) {
      case StaffSuccess():
        state = ApprovalSuccess('Check-in approved');
        await load(societyId, department: department);
      case StaffFailure(:final message): state = ApprovalError(message);
    }
  }

  Future<void> approveCheckout(String attendanceId, String societyId, {String? notes, String? department}) async {
    final result = await _repo.approveCheckout(attendanceId, notes: notes);
    switch (result) {
      case StaffSuccess():
        state = ApprovalSuccess('Check-out approved');
        await load(societyId, department: department);
      case StaffFailure(:final message): state = ApprovalError(message);
    }
  }

  Future<void> rejectCheckin(String attendanceId, String societyId, {String? reason, String? department}) async {
    final result = await _repo.rejectAttendance(attendanceId, reason: reason);
    switch (result) {
      case StaffSuccess():
        state = ApprovalSuccess('Check-in rejected — staff must re-check-in');
        await load(societyId, department: department);
      case StaffFailure(:final message): state = ApprovalError(message);
    }
  }

  Future<void> rejectCheckout(String attendanceId, String societyId, {String? reason, String? department}) async {
    final result = await _repo.rejectCheckout(attendanceId, reason: reason);
    switch (result) {
      case StaffSuccess():
        state = ApprovalSuccess('Check-out rejected — staff must re-check-out');
        await load(societyId, department: department);
      case StaffFailure(:final message): state = ApprovalError(message);
    }
  }

  void clearStatus() {
    if (state is ApprovalSuccess || state is ApprovalError) {
      state = ApprovalInitial();
    }
  }
}

final approvalProvider = StateNotifierProvider<ApprovalNotifier, ApprovalState>((ref) {
  return ApprovalNotifier(ref.read(staffRepositoryProvider));
});

// ── Attendance correction state ───────────────────────────────────────────────

sealed class CorrectionState {}
class CorrectionInitial extends CorrectionState {}
class CorrectionLoading extends CorrectionState {}
class CorrectionLoaded  extends CorrectionState {
  final List<AttendanceCorrectionEntity> corrections;
  CorrectionLoaded(this.corrections);
}
class CorrectionActionSuccess extends CorrectionState {
  final List<AttendanceCorrectionEntity> corrections;
  final String message;
  CorrectionActionSuccess(this.corrections, this.message);
}
class CorrectionError extends CorrectionState {
  final String message;
  CorrectionError(this.message);
}

class CorrectionNotifier extends StateNotifier<CorrectionState> {
  final StaffRepository _repo;
  CorrectionNotifier(this._repo) : super(CorrectionInitial());

  Future<void> loadMine(String staffId) async {
    state = CorrectionLoading();
    final result = await _repo.listCorrectionsByStaff(staffId);
    switch (result) {
      case StaffSuccess(:final data): state = CorrectionLoaded(data);
      case StaffFailure(:final message): state = CorrectionError(message);
    }
  }

  Future<void> loadForSociety(String societyId, {String? status}) async {
    state = CorrectionLoading();
    final result = await _repo.listCorrectionsBySociety(societyId, status: status);
    switch (result) {
      case StaffSuccess(:final data): state = CorrectionLoaded(data);
      case StaffFailure(:final message): state = CorrectionError(message);
    }
  }

  Future<void> request({
    required String societyId,
    required String staffId,
    required String attendanceId,
    required String correctionDate,
    required String reason,
    String? requestedStatus,
    String? requestedCheckIn,
    String? requestedCheckOut,
  }) async {
    final result = await _repo.requestCorrection(
      societyId: societyId, staffId: staffId, attendanceId: attendanceId,
      correctionDate: correctionDate, reason: reason,
      requestedStatus: requestedStatus,
      requestedCheckIn: requestedCheckIn,
      requestedCheckOut: requestedCheckOut,
    );
    switch (result) {
      case StaffSuccess():
        await loadMine(staffId);
      case StaffFailure(:final message): state = CorrectionError(message);
    }
  }

  Future<void> approve(String correctionId, String societyId) async {
    final result = await _repo.approveCorrection(correctionId);
    switch (result) {
      case StaffSuccess():
        final refreshed = await _repo.listCorrectionsBySociety(societyId);
        state = switch (refreshed) {
          StaffSuccess(:final data) => CorrectionActionSuccess(data, 'Correction approved'),
          StaffFailure(:final message) => CorrectionError(message),
        };
      case StaffFailure(:final message): state = CorrectionError(message);
    }
  }

  Future<void> reject(String correctionId, String societyId, String reason) async {
    final result = await _repo.rejectCorrection(correctionId, reason);
    switch (result) {
      case StaffSuccess():
        final refreshed = await _repo.listCorrectionsBySociety(societyId);
        state = switch (refreshed) {
          StaffSuccess(:final data) => CorrectionActionSuccess(data, 'Correction rejected'),
          StaffFailure(:final message) => CorrectionError(message),
        };
      case StaffFailure(:final message): state = CorrectionError(message);
    }
  }
}

final correctionProvider = StateNotifierProvider<CorrectionNotifier, CorrectionState>((ref) {
  return CorrectionNotifier(ref.read(staffRepositoryProvider));
});

// ── Designations provider ─────────────────────────────────────────────────────

final designationsProvider = FutureProvider.family<List<DesignationEntity>, String>((ref, societyId) async {
  final repo = ref.read(staffRepositoryProvider);
  final result = await repo.listDesignations(societyId);
  return switch (result) {
    StaffSuccess(:final data) => data,
    StaffFailure() => <DesignationEntity>[],
  };
});

// ── Shifts provider ───────────────────────────────────────────────────────────

final shiftsProvider = FutureProvider.family<List<ShiftEntity>, String>((ref, societyId) async {
  final repo = ref.read(staffRepositoryProvider);
  final result = await repo.listShifts(societyId);
  return switch (result) {
    StaffSuccess(:final data) => data,
    StaffFailure() => <ShiftEntity>[],
  };
});

// ── Staff form state (create / edit) ─────────────────────────────────────────

sealed class StaffFormState {}
class StaffFormInitial extends StaffFormState {}
class StaffFormLoading extends StaffFormState {}
class StaffFormSuccess extends StaffFormState {
  final StaffEntity staff;
  final String message;
  StaffFormSuccess(this.staff, this.message);
}
class StaffFormError extends StaffFormState {
  final String message;
  StaffFormError(this.message);
}

class StaffFormNotifier extends StateNotifier<StaffFormState> {
  final StaffRepository _repo;
  StaffFormNotifier(this._repo) : super(StaffFormInitial());

  Future<void> create(Map<String, dynamic> data) async {
    state = StaffFormLoading();
    final result = await _repo.createStaff(data);
    state = switch (result) {
      StaffSuccess(:final data) => StaffFormSuccess(data, 'Staff created successfully'),
      StaffFailure(:final message) => StaffFormError(message),
    };
  }

  Future<void> update(String staffId, Map<String, dynamic> data) async {
    state = StaffFormLoading();
    final result = await _repo.updateStaff(staffId, data);
    state = switch (result) {
      StaffSuccess(:final data) => StaffFormSuccess(data, 'Staff updated successfully'),
      StaffFailure(:final message) => StaffFormError(message),
    };
  }

  void reset() => state = StaffFormInitial();
}

final staffFormProvider = StateNotifierProvider<StaffFormNotifier, StaffFormState>((ref) {
  return StaffFormNotifier(ref.read(staffRepositoryProvider));
});

// ── Attendance summary provider ───────────────────────────────────────────────

final attendanceSummaryProvider = FutureProvider.family<Map<String, dynamic>, String>(
  (ref, societyId) async {
    final repo = ref.read(staffRepositoryProvider);
    final today = DateTime.now();
    final dateStr =
        '${today.year}-${today.month.toString().padLeft(2, '0')}-${today.day.toString().padLeft(2, '0')}';
    final result = await repo.getAttendanceSummary(societyId, dateStr);
    return switch (result) {
      StaffSuccess(:final data) => data,
      StaffFailure() => <String, dynamic>{},
    };
  },
);

// ── Duty assignment state ─────────────────────────────────────────────────────

sealed class DutyAssignState {}
class DutyAssignInitial extends DutyAssignState {}
class DutyAssignLoading extends DutyAssignState {}
class DutyAssignSuccess extends DutyAssignState { final DutyEntity duty; DutyAssignSuccess(this.duty); }
class DutyAssignError   extends DutyAssignState { final String message; DutyAssignError(this.message); }

class DutyAssignNotifier extends StateNotifier<DutyAssignState> {
  final StaffRepository _repo;
  final Ref _ref;
  DutyAssignNotifier(this._repo, this._ref) : super(DutyAssignInitial());

  Future<void> assign({
    required String staffId,
    required String societyId,
    required String dutyName,
    required String dutyDate,
    String? description,
    String? location,
    String? startTime,
    String? endTime,
    String? checklistTemplateId,
  }) async {
    state = DutyAssignLoading();
    final result = await _repo.assignDuty(
      staffId: staffId, societyId: societyId, dutyName: dutyName,
      dutyDate: dutyDate, description: description, location: location,
      startTime: startTime, endTime: endTime,
      checklistTemplateId: checklistTemplateId,
    );
    switch (result) {
      case StaffSuccess(:final data):
        state = DutyAssignSuccess(data);
        // Every call site pushes this screen without awaiting the pop
        // result, so the dashboard's duty-count summary (societyDutiesProvider,
        // a cached FutureProvider.family) would otherwise stay stale until
        // a manual pull-to-refresh — invalidate it here instead of depending
        // on each current (and future) call site to remember to.
        _ref.invalidate(societyDutiesProvider(societyId));
      case StaffFailure(:final message):
        state = DutyAssignError(message);
    }
  }

  void reset() => state = DutyAssignInitial();
}

final dutyAssignProvider = StateNotifierProvider<DutyAssignNotifier, DutyAssignState>((ref) {
  return DutyAssignNotifier(ref.read(staffRepositoryProvider), ref);
});

// ── Daily society duties provider (dashboard summary) ─────────────────────────

final societyDutiesProvider = FutureProvider.family<List<DutyEntity>, String>(
  (ref, societyId) async {
    final repo = ref.read(staffRepositoryProvider);
    final today = DateTime.now();
    final dateStr =
        '${today.year}-${today.month.toString().padLeft(2, '0')}-${today.day.toString().padLeft(2, '0')}';
    final result = await repo.getDailyDuties(societyId, dateStr);
    return switch (result) {
      StaffSuccess(:final data) => data,
      StaffFailure() => <DutyEntity>[],
    };
  },
);

// ── Duty overview (supervisor screen — date-navigable, drives Verify) ────────
//
// Separate from societyDutiesProvider above (which only ever shows today, for
// the dashboard's summary counts): this backs a real screen where a
// supervisor picks a date and verifies completed duties, so it needs its own
// mutable state rather than a FutureProvider.family keyed only by society.

sealed class DutyOverviewState {}
class DutyOverviewInitial extends DutyOverviewState {}
class DutyOverviewLoading extends DutyOverviewState {}
class DutyOverviewLoaded extends DutyOverviewState {
  final List<DutyEntity> duties;
  DutyOverviewLoaded(this.duties);
}
class DutyOverviewError extends DutyOverviewState {
  final String message;
  DutyOverviewError(this.message);
}

class DutyOverviewNotifier extends StateNotifier<DutyOverviewState> {
  final StaffRepository _repo;
  DutyOverviewNotifier(this._repo) : super(DutyOverviewInitial());

  Future<void> load(String societyId, String dateStr) async {
    state = DutyOverviewLoading();
    final result = await _repo.getDailyDuties(societyId, dateStr);
    switch (result) {
      case StaffSuccess(:final data): state = DutyOverviewLoaded(data);
      case StaffFailure(:final message): state = DutyOverviewError(message);
    }
  }

  Future<void> verify(
    String dutyId, {
    required String societyId,
    required String dateStr,
    String? notes,
  }) async {
    final result = await _repo.verifyDuty(dutyId, notes: notes);
    switch (result) {
      case StaffSuccess():
        await load(societyId, dateStr);
      case StaffFailure(:final message):
        state = DutyOverviewError(message);
    }
  }
}

final dutyOverviewProvider =
    StateNotifierProvider<DutyOverviewNotifier, DutyOverviewState>((ref) {
  return DutyOverviewNotifier(ref.read(staffRepositoryProvider));
});

// ── Checklist templates (society-wide; screens filter by department) ───────────

final checklistTemplatesProvider = AsyncNotifierProviderFamily<
    ChecklistTemplatesNotifier, List<ChecklistTemplateEntity>, String>(
  ChecklistTemplatesNotifier.new,
);

class ChecklistTemplatesNotifier
    extends FamilyAsyncNotifier<List<ChecklistTemplateEntity>, String> {
  Future<List<ChecklistTemplateEntity>> _fetch(String societyId) async {
    final result = await ref.read(staffRepositoryProvider).listChecklistTemplates(societyId);
    return switch (result) {
      StaffSuccess(:final data) => data,
      StaffFailure(:final message) => throw Exception(message),
    };
  }

  @override
  Future<List<ChecklistTemplateEntity>> build(String societyId) => _fetch(societyId);

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => _fetch(arg));
  }

  Future<void> create({
    required String department,
    required String name,
    String? description,
    required List<Map<String, dynamic>> items,
  }) async {
    final result = await ref.read(staffRepositoryProvider).createChecklistTemplate(
          societyId: arg, department: department, name: name,
          description: description, items: items,
        );
    switch (result) {
      case StaffSuccess(:final data):
        state = AsyncData([...(state.valueOrNull ?? []), data]);
      case StaffFailure(:final message):
        throw Exception(message);
    }
  }

  Future<void> updateTemplate(
    String templateId, {
    String? name,
    String? description,
    String? department,
    List<Map<String, dynamic>>? items,
  }) async {
    final result = await ref.read(staffRepositoryProvider).updateChecklistTemplate(
          templateId, name: name, description: description,
          department: department, items: items,
        );
    switch (result) {
      case StaffSuccess(:final data):
        final rows = <ChecklistTemplateEntity>[...(state.valueOrNull ?? [])];
        final idx = rows.indexWhere((t) => t.id == templateId);
        if (idx != -1) {
          rows[idx] = data;
        } else {
          rows.add(data);
        }
        state = AsyncData(rows);
      case StaffFailure(:final message):
        throw Exception(message);
    }
  }

  Future<void> delete(String templateId) async {
    final result = await ref.read(staffRepositoryProvider).deleteChecklistTemplate(templateId);
    switch (result) {
      case StaffSuccess():
        state = AsyncData(
          (state.valueOrNull ?? []).where((t) => t.id != templateId).toList(),
        );
      case StaffFailure(:final message):
        throw Exception(message);
    }
  }
}
