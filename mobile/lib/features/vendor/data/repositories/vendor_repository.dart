import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/vendor/data/datasources/vendor_remote_datasource.dart';
import 'package:ar_society_app/features/vendor/domain/entities/vendor_entities.dart';

sealed class VendorResult<T> {}

class VendorSuccess<T> extends VendorResult<T> {
  final T data;
  VendorSuccess(this.data);
}

class VendorFailure<T> extends VendorResult<T> {
  final String message;
  final int? statusCode;
  VendorFailure(this.message, {this.statusCode});
}

class VendorRepository {
  final VendorRemoteDataSource _ds;
  VendorRepository({VendorRemoteDataSource? ds}) : _ds = ds ?? VendorRemoteDataSource();

  VendorResult<T> _handle<T>(Object e) {
    if (e is DioException) {
      final code = e.response?.statusCode;
      if (code == 422 || code == 409) {
        final detail = (e.response?.data as Map?)?['detail']?.toString() ?? '';
        return VendorFailure(detail.isNotEmpty ? detail : 'Request failed', statusCode: code);
      }
      return VendorFailure(parseApiError(e), statusCode: code);
    }
    return VendorFailure('Unexpected error: $e');
  }

  Future<VendorResult<VendorEntity>> createVendor({
    required String societyId,
    required String companyName,
    required String mobile,
    required String category,
    String? contactPerson,
    String? email,
  }) async {
    try {
      final m = await _ds.createVendor(
        societyId: societyId, companyName: companyName, mobile: mobile,
        category: category, contactPerson: contactPerson, email: email,
      );
      return VendorSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<VendorResult<List<VendorEntity>>> listVendors(String societyId) async {
    try {
      final list = await _ds.listVendors(societyId);
      return VendorSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) { return _handle(e); }
  }

  Future<VendorResult<VendorInvoiceEntity>> createInvoice({
    required String societyId,
    required String vendorId,
    required String invoiceNumber,
    required DateTime invoiceDate,
    DateTime? dueDate,
    required double amount,
    double gstAmount = 0,
    required double totalAmount,
    String? description,
  }) async {
    try {
      final m = await _ds.createInvoice(
        societyId: societyId, vendorId: vendorId, invoiceNumber: invoiceNumber,
        invoiceDate: invoiceDate, dueDate: dueDate, amount: amount,
        gstAmount: gstAmount, totalAmount: totalAmount, description: description,
      );
      return VendorSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<VendorResult<List<VendorInvoiceEntity>>> listSocietyInvoices(
      String societyId, {bool? isPaid}) async {
    try {
      final list = await _ds.listSocietyInvoices(societyId, isPaid: isPaid);
      return VendorSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) { return _handle(e); }
  }

  Future<VendorResult<VendorInvoiceEntity>> recordPayment({
    required String invoiceId,
    required double amount,
    required DateTime paidDate,
    required String paymentMode,
    String? paymentRef,
    String? bankName,
  }) async {
    try {
      final m = await _ds.recordPayment(
        invoiceId: invoiceId, amount: amount, paidDate: paidDate,
        paymentMode: paymentMode, paymentRef: paymentRef, bankName: bankName,
      );
      return VendorSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }
}
