import 'dart:typed_data';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/billing/data/repositories/billing_repository.dart';
import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart';

final billingRepositoryProvider = Provider<BillingRepository>((_) => BillingRepository());

/// Online payment submissions for a society, optionally filtered by status
/// client-side once loaded (the notifier always fetches the full list so
/// switching filters doesn't re-hit the network).
final onlinePaymentsProvider = AsyncNotifierProviderFamily<OnlinePaymentsNotifier,
    List<OnlinePaymentEntity>, String>(OnlinePaymentsNotifier.new);

class OnlinePaymentsNotifier extends FamilyAsyncNotifier<List<OnlinePaymentEntity>, String> {
  Future<List<OnlinePaymentEntity>> _fetch(String societyId) async {
    final result = await ref.read(billingRepositoryProvider).listOnlinePayments(societyId);
    return switch (result) {
      BillingSuccess(:final data) => data,
      BillingFailure(:final message) => throw Exception(message),
    };
  }

  @override
  Future<List<OnlinePaymentEntity>> build(String societyId) => _fetch(societyId);

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => _fetch(arg));
  }

  Future<OnlinePaymentEntity> submit({
    required String flatId,
    required double amount,
    required DateTime paymentDate,
    required String paymentMode,
    String? transactionRef,
    String? bankName,
    String? notes,
    required Uint8List screenshotBytes,
    required String screenshotFileName,
    String screenshotMimeType = 'image/jpeg',
  }) async {
    final result = await ref.read(billingRepositoryProvider).submitOnlinePayment(
          flatId: flatId, amount: amount, paymentDate: paymentDate, paymentMode: paymentMode,
          transactionRef: transactionRef, bankName: bankName, notes: notes,
          screenshotBytes: screenshotBytes, screenshotFileName: screenshotFileName,
          screenshotMimeType: screenshotMimeType,
        );
    switch (result) {
      case BillingSuccess(:final data):
        state = AsyncData([data, ...(state.valueOrNull ?? [])]);
        return data;
      case BillingFailure(:final message):
        throw Exception(message);
    }
  }

  Future<void> updateStatus(String id, String status, {String? reviewNotes}) async {
    final result = await ref.read(billingRepositoryProvider).updateStatus(id, status, reviewNotes: reviewNotes);
    switch (result) {
      case BillingSuccess(:final data):
        final rows = <OnlinePaymentEntity>[...(state.valueOrNull ?? [])];
        final idx = rows.indexWhere((p) => p.id == id);
        if (idx != -1) {
          rows[idx] = data;
        } else {
          rows.add(data);
        }
        state = AsyncData(rows);
      case BillingFailure(:final message):
        throw Exception(message);
    }
  }
}

/// A single submission's screenshot bytes, fetched on demand.
final onlinePaymentScreenshotProvider =
    FutureProviderFamily<Uint8List, String>((ref, id) async {
  final result = await ref.read(billingRepositoryProvider).getScreenshotBytes(id);
  return switch (result) {
    BillingSuccess(:final data) => data,
    BillingFailure(:final message) => throw Exception(message),
  };
});
