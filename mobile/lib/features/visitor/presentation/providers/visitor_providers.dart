import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/visitor/data/repositories/visitor_repository.dart';
import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';

// ── Repository provider ───────────────────────────────────────────────────────

final visitorRepositoryProvider = Provider<VisitorRepository>((ref) {
  return VisitorRepository();
});

// ── Visitor list state ────────────────────────────────────────────────────────

sealed class VisitorListState {}

class VisitorListInitial extends VisitorListState {}

class VisitorListLoading extends VisitorListState {}

class VisitorListLoaded extends VisitorListState {
  final List<VisitorEntity> visitors;
  VisitorListLoaded(this.visitors);
}

class VisitorListError extends VisitorListState {
  final String message;
  VisitorListError(this.message);
}

// ── Visitor list notifier ─────────────────────────────────────────────────────

class VisitorListNotifier extends StateNotifier<VisitorListState> {
  final VisitorRepository _repo;
  VisitorListNotifier(this._repo) : super(VisitorListInitial());

  Future<void> loadSocietyVisitors(String societyId) async {
    state = VisitorListLoading();
    final result = await _repo.listSocietyVisitors(societyId);
    switch (result) {
      case VisitorSuccess(:final data):
        state = VisitorListLoaded(data);
      case VisitorFailure(:final message):
        state = VisitorListError(message);
    }
  }

  Future<void> loadMyVisitors() async {
    state = VisitorListLoading();
    final result = await _repo.getMyVisitors();
    switch (result) {
      case VisitorSuccess(:final data):
        state = VisitorListLoaded(data);
      case VisitorFailure(:final message):
        state = VisitorListError(message);
    }
  }

  Future<void> loadPendingApprovals() async {
    state = VisitorListLoading();
    final result = await _repo.getPendingApprovals();
    switch (result) {
      case VisitorSuccess(:final data):
        state = VisitorListLoaded(data);
      case VisitorFailure(:final message):
        state = VisitorListError(message);
    }
  }
}

final visitorListProvider =
    StateNotifierProvider<VisitorListNotifier, VisitorListState>((ref) {
  return VisitorListNotifier(ref.read(visitorRepositoryProvider));
});

// ── Visitor action state ──────────────────────────────────────────────────────

sealed class VisitorActionState {}

class VisitorActionIdle extends VisitorActionState {}

class VisitorActionLoading extends VisitorActionState {}

class VisitorActionSuccess extends VisitorActionState {
  final String message;
  final VisitorEntity visitor;
  VisitorActionSuccess(this.message, this.visitor);
}

class VisitorActionError extends VisitorActionState {
  final String message;
  VisitorActionError(this.message);
}

// ── Visitor action notifier ───────────────────────────────────────────────────

class VisitorActionNotifier extends StateNotifier<VisitorActionState> {
  final VisitorRepository _repo;
  VisitorActionNotifier(this._repo) : super(VisitorActionIdle());

  Future<void> approve(String id, {String? notes}) async {
    state = VisitorActionLoading();
    final result = await _repo.approveVisitor(id, notes: notes);
    switch (result) {
      case VisitorSuccess(:final data):
        state = VisitorActionSuccess('Visitor approved successfully', data);
      case VisitorFailure(:final message):
        state = VisitorActionError(message);
    }
  }

  Future<void> reject(String id, String reason) async {
    state = VisitorActionLoading();
    final result = await _repo.rejectVisitor(id, reason);
    switch (result) {
      case VisitorSuccess(:final data):
        state = VisitorActionSuccess('Visitor rejected', data);
      case VisitorFailure(:final message):
        state = VisitorActionError(message);
    }
  }

  Future<void> checkIn(String id, {String? gateId}) async {
    state = VisitorActionLoading();
    final result = await _repo.checkIn(id, gateId: gateId);
    switch (result) {
      case VisitorSuccess(:final data):
        state = VisitorActionSuccess('Visitor checked in successfully', data);
      case VisitorFailure(:final message):
        state = VisitorActionError(message);
    }
  }

  Future<void> checkOut(String id, {String? gateId}) async {
    state = VisitorActionLoading();
    final result = await _repo.checkOut(id, gateId: gateId);
    switch (result) {
      case VisitorSuccess(:final data):
        state = VisitorActionSuccess('Visitor checked out successfully', data);
      case VisitorFailure(:final message):
        state = VisitorActionError(message);
    }
  }

  void reset() => state = VisitorActionIdle();
}

final visitorActionProvider =
    StateNotifierProvider<VisitorActionNotifier, VisitorActionState>((ref) {
  return VisitorActionNotifier(ref.read(visitorRepositoryProvider));
});
