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
    String? billId,
    String purpose = 'maintenance',
    String? transactionRef,
    String? bankName,
    String? notes,
    Uint8List? screenshotBytes,
    String? screenshotFileName,
    String screenshotMimeType = 'image/jpeg',
  }) async {
    final result = await ref.read(billingRepositoryProvider).submitOnlinePayment(
          flatId: flatId, amount: amount, paymentDate: paymentDate, paymentMode: paymentMode,
          billId: billId, purpose: purpose,
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

/// A flat's outstanding bills, for the "On Bill" picker on the record-
/// payment form.
final flatOutstandingBillsProvider =
    FutureProviderFamily<List<BillEntity>, String>((ref, flatId) async {
  final result = await ref.read(billingRepositoryProvider).getFlatBills(flatId, outstandingOnly: true);
  return switch (result) {
    BillingSuccess(:final data) => data,
    BillingFailure(:final message) => throw Exception(message),
  };
});

/// Imported bank-statement rows for a society, filtered client-side by
/// match status once loaded — mirrors OnlinePaymentsNotifier's pattern.
final bankStatementEntriesProvider = AsyncNotifierProviderFamily<
    BankStatementEntriesNotifier, List<BankStatementEntryEntity>, String>(
  BankStatementEntriesNotifier.new,
);

class BankStatementEntriesNotifier
    extends FamilyAsyncNotifier<List<BankStatementEntryEntity>, String> {
  Future<List<BankStatementEntryEntity>> _fetch(String societyId) async {
    final result = await ref.read(billingRepositoryProvider).listBankStatementEntries(societyId);
    return switch (result) {
      BillingSuccess(:final data) => data,
      BillingFailure(:final message) => throw Exception(message),
    };
  }

  @override
  Future<List<BankStatementEntryEntity>> build(String societyId) => _fetch(societyId);

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => _fetch(arg));
  }

  Future<List<BankStatementEntryEntity>> importStatement({
    required Uint8List csvBytes,
    required String fileName,
  }) async {
    final result = await ref
        .read(billingRepositoryProvider)
        .importBankStatement(arg, csvBytes: csvBytes, fileName: fileName);
    switch (result) {
      case BillingSuccess(:final data):
        state = AsyncData([...data, ...(state.valueOrNull ?? [])]);
        return data;
      case BillingFailure(:final message):
        throw Exception(message);
    }
  }

  Future<void> _replaceEntry(BankStatementEntryEntity updated) async {
    final rows = <BankStatementEntryEntity>[...(state.valueOrNull ?? [])];
    final idx = rows.indexWhere((e) => e.id == updated.id);
    if (idx != -1) {
      rows[idx] = updated;
    } else {
      rows.insert(0, updated);
    }
    state = AsyncData(rows);
  }

  Future<void> confirmMatch(String entryId, String submissionId) async {
    final result = await ref.read(billingRepositoryProvider).confirmBankMatch(entryId, submissionId);
    switch (result) {
      case BillingSuccess(:final data):
        await _replaceEntry(data);
        ref.invalidate(onlinePaymentsProvider);
      case BillingFailure(:final message):
        throw Exception(message);
    }
  }

  Future<void> ignoreEntry(String entryId, {String? reason}) async {
    final result = await ref.read(billingRepositoryProvider).ignoreBankEntry(entryId, reason: reason);
    switch (result) {
      case BillingSuccess(:final data):
        await _replaceEntry(data);
      case BillingFailure(:final message):
        throw Exception(message);
    }
  }
}

/// Suggested PENDING payment-submission matches for one bank statement
/// entry (amount + nearby date), fetched on demand.
final bankMatchCandidatesProvider =
    FutureProviderFamily<List<OnlinePaymentEntity>, String>((ref, entryId) async {
  final result = await ref.read(billingRepositoryProvider).getBankMatchCandidates(entryId);
  return switch (result) {
    BillingSuccess(:final data) => data,
    BillingFailure(:final message) => throw Exception(message),
  };
});
