import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/billing/data/datasources/billing_remote_datasource.dart';
import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart';

// ── Result type ───────────────────────────────────────────────────────────────

sealed class BillingResult<T> {}

class BillingSuccess<T> extends BillingResult<T> {
  final T data;
  BillingSuccess(this.data);
}

class BillingFailure<T> extends BillingResult<T> {
  final String message;
  final int? statusCode;
  BillingFailure(this.message, {this.statusCode});
}

// ── Repository ────────────────────────────────────────────────────────────────

class BillingRepository {
  final BillingRemoteDataSource _ds;
  BillingRepository({BillingRemoteDataSource? ds}) : _ds = ds ?? BillingRemoteDataSource();

  BillingResult<T> _handle<T>(Object e) {
    if (e is DioException) {
      final code = e.response?.statusCode;
      if (code == 422) {
        final detail = (e.response?.data as Map?)?['detail']?.toString() ?? '';
        return BillingFailure(detail.isNotEmpty ? detail : 'Invalid submission', statusCode: 422);
      }
      return BillingFailure(parseApiError(e), statusCode: code);
    }
    return BillingFailure('Unexpected error: $e');
  }

  Future<BillingResult<OnlinePaymentEntity>> submitOnlinePayment({
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
    try {
      final m = await _ds.submitOnlinePayment(
        flatId: flatId, amount: amount, paymentDate: paymentDate, paymentMode: paymentMode,
        transactionRef: transactionRef, bankName: bankName, notes: notes,
        screenshotBytes: screenshotBytes, screenshotFileName: screenshotFileName,
        screenshotMimeType: screenshotMimeType,
      );
      return BillingSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<BillingResult<List<OnlinePaymentEntity>>> listOnlinePayments(
    String societyId, {String? status, String? wingId, String? flatId}) async {
    try {
      final list = await _ds.listOnlinePayments(societyId, status: status, wingId: wingId, flatId: flatId);
      return BillingSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) { return _handle(e); }
  }

  Future<BillingResult<OnlinePaymentEntity>> getOnlinePayment(String id) async {
    try {
      final m = await _ds.getOnlinePayment(id);
      return BillingSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<BillingResult<OnlinePaymentEntity>> updateStatus(
      String id, String status, {String? reviewNotes}) async {
    try {
      final m = await _ds.updateStatus(id, status, reviewNotes: reviewNotes);
      return BillingSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<BillingResult<Uint8List>> getScreenshotBytes(String id) async {
    try {
      return BillingSuccess(await _ds.getScreenshotBytes(id));
    } catch (e) { return _handle(e); }
  }

  Future<BillingResult<Uint8List>> getReceiptPdfBytes(String id) async {
    try {
      return BillingSuccess(await _ds.getReceiptPdfBytes(id));
    } catch (e) { return _handle(e); }
  }

  Future<BillingResult<String>> exportCsv(String societyId, {String? status, String? wingId, String? flatId}) async {
    try {
      return BillingSuccess(await _ds.exportCsv(societyId, status: status, wingId: wingId, flatId: flatId));
    } catch (e) { return _handle(e); }
  }
}
