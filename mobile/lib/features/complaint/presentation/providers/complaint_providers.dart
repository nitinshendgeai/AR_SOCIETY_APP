import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/complaint/data/repositories/complaint_repository.dart';
import 'package:ar_society_app/features/complaint/domain/entities/complaint_entities.dart';

// ── Repository provider ───────────────────────────────────────────────────────

final complaintRepositoryProvider = Provider<ComplaintRepository>((ref) {
  return ComplaintRepository();
});

// ── Complaint list state ──────────────────────────────────────────────────────

sealed class ComplaintListState {}

class ComplaintListInitial extends ComplaintListState {}

class ComplaintListLoading extends ComplaintListState {}

class ComplaintListLoaded extends ComplaintListState {
  final List<ComplaintListEntity> complaints;
  ComplaintListLoaded(this.complaints);
}

class ComplaintListError extends ComplaintListState {
  final String message;
  ComplaintListError(this.message);
}

// ── Complaint list notifier ───────────────────────────────────────────────────

class ComplaintListNotifier extends StateNotifier<ComplaintListState> {
  final ComplaintRepository _repo;
  ComplaintListNotifier(this._repo) : super(ComplaintListInitial());

  Future<void> loadSocietyComplaints(String societyId) async {
    state = ComplaintListLoading();
    final result = await _repo.listSocietyComplaints(societyId);
    switch (result) {
      case ComplaintSuccess(:final data):
        state = ComplaintListLoaded(data);
      case ComplaintFailure(:final message):
        state = ComplaintListError(message);
    }
  }

  Future<void> loadMyComplaints() async {
    state = ComplaintListLoading();
    final result = await _repo.listMyComplaints();
    switch (result) {
      case ComplaintSuccess(:final data):
        state = ComplaintListLoaded(data);
      case ComplaintFailure(:final message):
        state = ComplaintListError(message);
    }
  }
}

final complaintListProvider =
    StateNotifierProvider<ComplaintListNotifier, ComplaintListState>((ref) {
  return ComplaintListNotifier(ref.read(complaintRepositoryProvider));
});

// ── Complaint detail state ────────────────────────────────────────────────────

sealed class ComplaintDetailState {}

class ComplaintDetailInitial extends ComplaintDetailState {}

class ComplaintDetailLoading extends ComplaintDetailState {}

class ComplaintDetailLoaded extends ComplaintDetailState {
  final ComplaintEntity complaint;
  ComplaintDetailLoaded(this.complaint);
}

class ComplaintDetailError extends ComplaintDetailState {
  final String message;
  ComplaintDetailError(this.message);
}

class ComplaintDetailActionSuccess extends ComplaintDetailState {
  final ComplaintEntity complaint;
  final String message;
  ComplaintDetailActionSuccess(this.complaint, this.message);
}

// ── Complaint detail notifier ─────────────────────────────────────────────────

class ComplaintDetailNotifier extends StateNotifier<ComplaintDetailState> {
  final ComplaintRepository _repo;
  ComplaintDetailNotifier(this._repo) : super(ComplaintDetailInitial());

  Future<void> load(String id) async {
    state = ComplaintDetailLoading();
    final result = await _repo.getComplaint(id);
    switch (result) {
      case ComplaintSuccess(:final data):
        state = ComplaintDetailLoaded(data);
      case ComplaintFailure(:final message):
        state = ComplaintDetailError(message);
    }
  }

  Future<void> addComment(String id, String body, {bool isInternal = false}) async {
    final result = await _repo.addComment(id, body, isInternal: isInternal);
    switch (result) {
      case ComplaintSuccess():
        // Reload full complaint to get updated comments list
        await load(id);
      case ComplaintFailure(:final message):
        state = ComplaintDetailError(message);
    }
  }

  Future<void> updateStatus(String id, String status, {String? notes, String? resolutionNotes}) async {
    final result = await _repo.updateStatus(id, status, notes: notes, resolutionNotes: resolutionNotes);
    switch (result) {
      case ComplaintSuccess(:final data):
        state = ComplaintDetailActionSuccess(data, 'Status updated to ${data.status.label}');
      case ComplaintFailure(:final message):
        state = ComplaintDetailError(message);
    }
  }

  void clearActionStatus() {
    if (state is ComplaintDetailActionSuccess) {
      final s = state as ComplaintDetailActionSuccess;
      state = ComplaintDetailLoaded(s.complaint);
    }
  }

  void reset() => state = ComplaintDetailInitial();
}

final complaintDetailProvider =
    StateNotifierProvider<ComplaintDetailNotifier, ComplaintDetailState>((ref) {
  return ComplaintDetailNotifier(ref.read(complaintRepositoryProvider));
});

// ── Open complaints count (FutureProvider, society-scoped) ────────────────────

final openComplaintsCountProvider =
    FutureProvider.family<int, String>((ref, societyId) async {
  final repo = ref.read(complaintRepositoryProvider);
  final result = await repo.openComplaintsCount(societyId);
  return switch (result) {
    ComplaintSuccess(:final data) => data,
    ComplaintFailure() => 0,
  };
});
