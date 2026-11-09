import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/api/paged.dart';
import 'package:ar_society_app/features/vendor/data/models/vendor_models.dart';

/// Calls FastAPI /vendors/* endpoints. API prefix: /api/v1/vendors
class VendorRemoteDataSource {
  final Dio _dio;
  VendorRemoteDataSource({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  /// Every row of a list the server cuts into pages (500 at most a page): see [getAllPages].
  Future<List<Map<String, dynamic>>> _allRows(String path, [Map<String, dynamic> query = const {}]) =>
      getAllPages(_dio, path, query: query, pageSize: 500, maxPages: 40);

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
    final rows = await _allRows('/vendors/society/$societyId');
    return rows.map(VendorModel.fromJson).toList();
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
    String? expenseAccountId,
  }) async {
    final r = await _dio.post('/vendors/invoices', data: {
      'society_id': societyId,
      'vendor_id': vendorId,
      'invoice_number': invoiceNumber,
      'invoice_date': invoiceDate.toIso8601String().split('T').first,
      if (dueDate != null) 'due_date': dueDate.toIso8601String().split('T').first,
      // Rupees to the paisa: a double's raw toString() can carry float noise
      // (100.30000000000001) that the server refuses.
      'amount': amount.toStringAsFixed(2),
      'gst_amount': gstAmount.toStringAsFixed(2),
      'total_amount': totalAmount.toStringAsFixed(2),
      if (description != null && description.isNotEmpty) 'description': description,
      if (expenseAccountId != null) 'expense_account_id': expenseAccountId,
    });
    return VendorInvoiceModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// GET /vendors/invoices/society/{society_id}
  Future<List<VendorInvoiceModel>> listSocietyInvoices(String societyId, {bool? isPaid}) async {
    final rows = await _allRows('/vendors/invoices/society/$societyId', {if (isPaid != null) 'is_paid': isPaid});
    return rows.map(VendorInvoiceModel.fromJson).toList();
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
    String? bankAccountId,
  }) async {
    final r = await _dio.post('/vendors/invoices/$invoiceId/payments', data: {
      'amount': amount.toStringAsFixed(2),
      'paid_date': paidDate.toIso8601String().split('T').first,
      'payment_mode': paymentMode,
      if (paymentRef != null && paymentRef.isNotEmpty) 'payment_ref': paymentRef,
      if (bankName != null && bankName.isNotEmpty) 'bank_name': bankName,
      if (bankAccountId != null) 'bank_account_id': bankAccountId,
    });
    return VendorInvoiceModel.fromJson(r.data as Map<String, dynamic>);
  }
}
