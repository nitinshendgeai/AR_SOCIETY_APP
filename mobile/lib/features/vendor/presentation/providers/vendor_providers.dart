import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/vendor/data/repositories/vendor_repository.dart';
import 'package:ar_society_app/features/vendor/domain/entities/vendor_entities.dart';

final vendorRepositoryProvider = Provider<VendorRepository>((_) => VendorRepository());

/// Vendors for a society — used by the vendor picker on the bill form.
final vendorsProvider = AsyncNotifierProviderFamily<VendorsNotifier, List<VendorEntity>, String>(
  VendorsNotifier.new,
);

class VendorsNotifier extends FamilyAsyncNotifier<List<VendorEntity>, String> {
  Future<List<VendorEntity>> _fetch(String societyId) async {
    final result = await ref.read(vendorRepositoryProvider).listVendors(societyId);
    return switch (result) {
      VendorSuccess(:final data) => data,
      VendorFailure(:final message) => throw Exception(message),
    };
  }

  @override
  Future<List<VendorEntity>> build(String societyId) => _fetch(societyId);

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => _fetch(arg));
  }

  Future<VendorEntity> create({
    required String companyName,
    required String mobile,
    required String category,
    String? contactPerson,
    String? email,
  }) async {
    final result = await ref.read(vendorRepositoryProvider).createVendor(
          societyId: arg, companyName: companyName, mobile: mobile,
          category: category, contactPerson: contactPerson, email: email,
        );
    switch (result) {
      case VendorSuccess(:final data):
        state = AsyncData([data, ...(state.valueOrNull ?? [])]);
        return data;
      case VendorFailure(:final message):
        throw Exception(message);
    }
  }
}

/// Vendor bills (invoices) for a society, filtered client-side once
/// loaded — mirrors OnlinePaymentsNotifier's pattern in billing.
final vendorInvoicesProvider =
    AsyncNotifierProviderFamily<VendorInvoicesNotifier, List<VendorInvoiceEntity>, String>(
  VendorInvoicesNotifier.new,
);

class VendorInvoicesNotifier extends FamilyAsyncNotifier<List<VendorInvoiceEntity>, String> {
  Future<List<VendorInvoiceEntity>> _fetch(String societyId) async {
    final result = await ref.read(vendorRepositoryProvider).listSocietyInvoices(societyId);
    return switch (result) {
      VendorSuccess(:final data) => data,
      VendorFailure(:final message) => throw Exception(message),
    };
  }

  @override
  Future<List<VendorInvoiceEntity>> build(String societyId) => _fetch(societyId);

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => _fetch(arg));
  }

  Future<VendorInvoiceEntity> createInvoice({
    required String vendorId,
    required String invoiceNumber,
    required DateTime invoiceDate,
    DateTime? dueDate,
    required double amount,
    double gstAmount = 0,
    required double totalAmount,
    String? description,
  }) async {
    final result = await ref.read(vendorRepositoryProvider).createInvoice(
          societyId: arg, vendorId: vendorId, invoiceNumber: invoiceNumber,
          invoiceDate: invoiceDate, dueDate: dueDate, amount: amount,
          gstAmount: gstAmount, totalAmount: totalAmount, description: description,
        );
    switch (result) {
      case VendorSuccess(:final data):
        state = AsyncData([data, ...(state.valueOrNull ?? [])]);
        return data;
      case VendorFailure(:final message):
        throw Exception(message);
    }
  }

  Future<VendorInvoiceEntity> recordPayment({
    required String invoiceId,
    required double amount,
    required DateTime paidDate,
    required String paymentMode,
    String? paymentRef,
    String? bankName,
  }) async {
    final result = await ref.read(vendorRepositoryProvider).recordPayment(
          invoiceId: invoiceId, amount: amount, paidDate: paidDate,
          paymentMode: paymentMode, paymentRef: paymentRef, bankName: bankName,
        );
    switch (result) {
      case VendorSuccess(:final data):
        final rows = <VendorInvoiceEntity>[...(state.valueOrNull ?? [])];
        final idx = rows.indexWhere((i) => i.id == data.id);
        if (idx != -1) {
          rows[idx] = data;
        } else {
          rows.insert(0, data);
        }
        state = AsyncData(rows);
        return data;
      case VendorFailure(:final message):
        throw Exception(message);
    }
  }
}
