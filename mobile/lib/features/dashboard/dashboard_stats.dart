import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/resident_master/data/repositories/resident_master_repository.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/visitor/data/repositories/visitor_repository.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';

// Counts for the dashboard summary tiles. Kept apart from the list
// screens' notifiers so opening the dashboard never resets a list's
// filters, and vice versa.

/// Active residents across the society (the user's society, server-scoped).
final activeResidentCountProvider = FutureProvider.autoDispose<int?>((ref) async {
  final result = await ref
      .read(residentMasterRepositoryProvider)
      .listResidents(isActive: true, limit: 5000);
  return switch (result) {
    RmSuccess(:final data) => data.length,
    RmFailure() => null,
  };
});

/// Visitors logged or checked in today (local time).
final visitorsTodayProvider = FutureProvider.autoDispose.family<int?, String>((ref, societyId) async {
  final result = await ref.read(visitorRepositoryProvider).listSocietyVisitors(societyId, limit: 500);
  final now = DateTime.now();
  bool today(DateTime? d) {
    if (d == null) return false;
    final l = d.toLocal();
    return l.year == now.year && l.month == now.month && l.day == now.day;
  }

  return switch (result) {
    VisitorSuccess(:final data) => data.where((v) => today(v.checkedInAt) || today(v.createdAt)).length,
    VisitorFailure() => null,
  };
});
