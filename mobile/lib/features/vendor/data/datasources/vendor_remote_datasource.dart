import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/vendor/data/models/vendor_models.dart';

/// Calls FastAPI /vendors/* endpoints. API prefix: /api/v1/vendors
class VendorRemoteDataSource {
  final Dio _dio;
  VendorRemoteDataSource({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  /// POST /vendors/
  Future<VendorModel> createVendor({
    required String societyId,
    required String companyName,
    required String mobile,
    required String category,
    String? contactPerson,
    String? email,
  }) async {
    final r = await _dio.post('/vendors/', data: {
      'society_id': societyId,
      'company_name': companyName,
      'mobile': mobile,
      'category': category,
      if (contactPerson != null && contactPerson.isNotEmpty) 'contact_person': contactPerson,
      if (email != null && email.isNotEmpty) 'email': email,
    });
    return VendorModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// GET /vendors/society/{society_id}
  Future<List<VendorModel>> listVendors(String societyId) async {
    final r = await _dio.get('/vendors/society/$societyId');
    return (r.data as List).map((e) => VendorModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// POST /vendors/invoices
  Future<VendorInvoiceModel> createInvoice({
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
    final r = await _dio.post('/vendors/invoices', data: {
      'society_id': societyId,
      'vendor_id': vendorId,
      'invoice_number': invoiceNumber,
      'invoice_date': invoiceDate.toIso8601String().split('T').first,
      if (dueDate != null) 'due_date': dueDate.toIso8601String().split('T').first,
      'amount': amount.toString(),
      'gst_amount': gstAmount.toString(),
      'total_amount': totalAmount.toString(),
      if (description != null && description.isNotEmpty) 'description': description,
    });
    return VendorInvoiceModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// GET /vendors/invoices/society/{society_id}
  Future<List<VendorInvoiceModel>> listSocietyInvoices(String societyId, {bool? isPaid}) async {
    final r = await _dio.get(
      '/vendors/invoices/society/$societyId',
      queryParameters: {if (isPaid != null) 'is_paid': isPaid},
    );
    return (r.data as List).map((e) => VendorInvoiceModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// GET /vendors/invoices/{id}
  Future<VendorInvoiceModel> getInvoice(String id) async {
    final r = await _dio.get('/vendors/invoices/$id');
    return VendorInvoiceModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// POST /vendors/invoices/{id}/payments
  Future<VendorInvoiceModel> recordPayment({
    required String invoiceId,
    required double amount,
    required DateTime paidDate,
    required String paymentMode,
    String? paymentRef,
    String? bankName,
  }) async {
    final r = await _dio.post('/vendors/invoices/$invoiceId/payments', data: {
      'amount': amount.toString(),
      'paid_date': paidDate.toIso8601String().split('T').first,
      'payment_mode': paymentMode,
      if (paymentRef != null && paymentRef.isNotEmpty) 'payment_ref': paymentRef,
      if (bankName != null && bankName.isNotEmpty) 'bank_name': bankName,
    });
    return VendorInvoiceModel.fromJson(r.data as Map<String, dynamic>);
  }
}
