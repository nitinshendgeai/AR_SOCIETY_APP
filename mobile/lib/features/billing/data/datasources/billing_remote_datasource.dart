import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/billing/data/models/billing_models.dart';

/// Calls FastAPI /billing/online-payments/* endpoints.
/// API prefix: /api/v1/billing
class BillingRemoteDataSource {
  final Dio _dio;
  BillingRemoteDataSource({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  /// POST /billing/online-payments (multipart: form fields + screenshot file)
  Future<OnlinePaymentModel> submitOnlinePayment({
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
    final formData = FormData.fromMap({
      'flat_id': flatId,
      'amount': amount.toString(),
      'payment_date': paymentDate.toIso8601String().split('T').first,
      'payment_mode': paymentMode,
      if (transactionRef != null && transactionRef.isNotEmpty) 'transaction_ref': transactionRef,
      if (bankName != null && bankName.isNotEmpty) 'bank_name': bankName,
      if (notes != null && notes.isNotEmpty) 'notes': notes,
      'screenshot': MultipartFile.fromBytes(
        screenshotBytes,
        filename: screenshotFileName,
        contentType: DioMediaType.parse(screenshotMimeType),
      ),
    });
    final r = await _dio.post('/billing/online-payments', data: formData);
    return OnlinePaymentModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// GET /billing/online-payments/society/{society_id}
  Future<List<OnlinePaymentModel>> listOnlinePayments(
    String societyId, {
    String? status,
    String? wingId,
    String? flatId,
    int skip = 0,
    int limit = 50,
  }) async {
    final r = await _dio.get(
      '/billing/online-payments/society/$societyId',
      queryParameters: {
        if (status != null) 'status': status,
        if (wingId != null) 'wing_id': wingId,
        if (flatId != null) 'flat_id': flatId,
        'skip': skip,
        'limit': limit,
      },
    );
    return (r.data as List)
        .map((e) => OnlinePaymentModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /billing/online-payments/{id}
  Future<OnlinePaymentModel> getOnlinePayment(String id) async {
    final r = await _dio.get('/billing/online-payments/$id');
    return OnlinePaymentModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// PATCH /billing/online-payments/{id}/status
  Future<OnlinePaymentModel> updateStatus(String id, String status, {String? reviewNotes}) async {
    final r = await _dio.patch(
      '/billing/online-payments/$id/status',
      data: {'status': status, if (reviewNotes != null) 'review_notes': reviewNotes},
    );
    return OnlinePaymentModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// GET /billing/online-payments/{id}/screenshot
  Future<Uint8List> getScreenshotBytes(String id) async {
    final r = await _dio.get<List<int>>(
      '/billing/online-payments/$id/screenshot',
      options: Options(responseType: ResponseType.bytes),
    );
    return Uint8List.fromList(r.data!);
  }

  /// GET /billing/online-payments/{id}/receipt
  Future<Uint8List> getReceiptPdfBytes(String id) async {
    final r = await _dio.get<List<int>>(
      '/billing/online-payments/$id/receipt',
      options: Options(responseType: ResponseType.bytes),
    );
    return Uint8List.fromList(r.data!);
  }

  /// GET /billing/online-payments/society/{society_id}/export
  Future<String> exportCsv(String societyId, {String? status, String? wingId, String? flatId}) async {
    final r = await _dio.get<String>(
      '/billing/online-payments/society/$societyId/export',
      queryParameters: {
        if (status != null) 'status': status,
        if (wingId != null) 'wing_id': wingId,
        if (flatId != null) 'flat_id': flatId,
      },
      options: Options(responseType: ResponseType.plain),
    );
    return r.data!;
  }
}
