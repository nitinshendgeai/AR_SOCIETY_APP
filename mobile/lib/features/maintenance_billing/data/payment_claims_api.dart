import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';

/// Where to pay: the society's UPI id and bank details (the ones printed on every bill).
class PaymentInfo {
  final String? upiId;
  final String? accountName;
  final String? bankName;
  final String? accountNumber;
  final String? ifsc;
  final String? notes;

  const PaymentInfo({this.upiId, this.accountName, this.bankName, this.accountNumber, this.ifsc, this.notes});

  factory PaymentInfo.fromJson(Map<String, dynamic> j) => PaymentInfo(
        upiId: j['upi_id'] as String?,
        accountName: j['bank_account_name'] as String?,
        bankName: j['bank_name'] as String?,
        accountNumber: j['bank_account_number'] as String?,
        ifsc: j['bank_ifsc'] as String?,
        notes: j['notes'] as String?,
      );

  bool get hasUpi => upiId != null && upiId!.isNotEmpty;
  bool get hasBank => accountNumber != null && accountNumber!.isNotEmpty;

  /// The society has not told us where to pay.
  bool get isEmpty => !hasUpi && !hasBank;
}

/// A resident's "I have paid", as the resident and the office see it.
class PaymentClaimItem {
  final String id;
  final String status; // pending | confirmed | rejected
  final String flatId;
  final String flatLabel;
  final String? billId;
  final String? billInvoiceNumber;
  final String amount;
  final DateTime paymentDate;
  final String paymentMode;
  final String? transactionRef;
  final String? bankName;
  final String? notes;
  final String? claimedByName;
  final bool hasScreenshot;
  final String? reviewNotes;
  final String? receiptNumber;
  final DateTime? createdAt;

  const PaymentClaimItem({
    required this.id,
    required this.status,
    required this.flatId,
    required this.flatLabel,
    this.billId,
    this.billInvoiceNumber,
    required this.amount,
    required this.paymentDate,
    required this.paymentMode,
    this.transactionRef,
    this.bankName,
    this.notes,
    this.claimedByName,
    this.hasScreenshot = false,
    this.reviewNotes,
    this.receiptNumber,
    this.createdAt,
  });

  bool get isPending => status == 'pending';
  bool get isRejected => status == 'rejected';

  factory PaymentClaimItem.fromJson(Map<String, dynamic> j) => PaymentClaimItem(
        id: j['id'] as String,
        status: j['status'] as String? ?? 'pending',
        flatId: j['flat_id'] as String,
        flatLabel: j['flat_label'] as String? ?? '',
        billId: j['bill_id'] as String?,
        billInvoiceNumber: j['bill_invoice_number'] as String?,
        amount: j['amount']?.toString() ?? '0',
        paymentDate: DateTime.parse(j['payment_date'] as String),
        paymentMode: j['payment_mode'] as String? ?? '',
        transactionRef: j['transaction_ref'] as String?,
        bankName: j['bank_name'] as String?,
        notes: j['notes'] as String?,
        claimedByName: j['claimed_by_name'] as String?,
        hasScreenshot: j['has_screenshot'] as bool? ?? false,
        reviewNotes: j['review_notes'] as String?,
        receiptNumber: j['receipt_number'] as String?,
        createdAt: j['created_at'] == null ? null : DateTime.tryParse(j['created_at'] as String),
      );
}

class PaymentClaimsApi {
  final Dio _dio;
  PaymentClaimsApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<PaymentInfo> info() async =>
      PaymentInfo.fromJson((await _dio.get('/billing/payment-info')).data as Map<String, dynamic>);

  Future<List<PaymentClaimItem>> mine() async => ((await _dio.get('/billing/payment-claims/mine')).data as List)
      .map((e) => PaymentClaimItem.fromJson(e as Map<String, dynamic>))
      .toList();

  Future<List<PaymentClaimItem>> forSociety(String societyId, {String? status}) async =>
      ((await _dio.get('/billing/payment-claims/society/$societyId', queryParameters: {if (status != null) 'status': status}))
              .data as List)
          .map((e) => PaymentClaimItem.fromJson(e as Map<String, dynamic>))
          .toList();

  Future<PaymentClaimItem> create({
    required double amount,
    required DateTime paymentDate,
    required String paymentMode,
    String? flatId,
    String? billId,
    String? transactionRef,
    String? bankName,
    String? notes,
    Uint8List? screenshotBytes,
    String? screenshotName,
  }) async {
    String d(DateTime x) => '${x.year.toString().padLeft(4, '0')}-${x.month.toString().padLeft(2, '0')}-${x.day.toString().padLeft(2, '0')}';
    final form = FormData.fromMap({
      'amount': amount.toStringAsFixed(2),
      'payment_date': d(paymentDate),
      'payment_mode': paymentMode,
      if (flatId != null) 'flat_id': flatId,
      if (billId != null) 'bill_id': billId,
      if (transactionRef != null && transactionRef.isNotEmpty) 'transaction_ref': transactionRef,
      if (bankName != null && bankName.isNotEmpty) 'bank_name': bankName,
      if (notes != null && notes.isNotEmpty) 'notes': notes,
      if (screenshotBytes != null)
        'screenshot': MultipartFile.fromBytes(screenshotBytes,
            filename: screenshotName ?? 'payment.jpg', contentType: DioMediaType.parse('image/${_subtype(screenshotName)}')),
    });
    return PaymentClaimItem.fromJson((await _dio.post('/billing/payment-claims', data: form)).data as Map<String, dynamic>);
  }

  Future<Uint8List> screenshot(String id) async {
    final r = await _dio.get<List<int>>('/billing/payment-claims/$id/screenshot',
        options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }

  Future<PaymentClaimItem> confirm(String id, {String? notes}) async => PaymentClaimItem.fromJson(
      (await _dio.post('/billing/payment-claims/$id/confirm', data: {if (notes != null && notes.isNotEmpty) 'notes': notes}))
          .data as Map<String, dynamic>);

  Future<PaymentClaimItem> reject(String id, String reason) async => PaymentClaimItem.fromJson(
      (await _dio.post('/billing/payment-claims/$id/reject', data: {'reason': reason})).data as Map<String, dynamic>);

  static String _subtype(String? name) {
    final n = (name ?? '').toLowerCase();
    if (n.endsWith('.png')) return 'png';
    if (n.endsWith('.webp')) return 'webp';
    if (n.endsWith('.heic')) return 'heic';
    return 'jpeg';
  }
}

final paymentClaimsApiProvider = Provider<PaymentClaimsApi>((_) => PaymentClaimsApi());

/// Where to pay (UPI id, bank account) for a resident about to pay.
final paymentInfoProvider = FutureProvider.autoDispose<PaymentInfo>((ref) => ref.watch(paymentClaimsApiProvider).info());

/// The signed-in resident's own payment reports, newest first.
final myPaymentClaimsProvider =
    FutureProvider.autoDispose<List<PaymentClaimItem>>((ref) => ref.watch(paymentClaimsApiProvider).mine());

/// Payments residents reported that the office has yet to check.
final pendingPaymentClaimsProvider = FutureProvider.autoDispose.family<List<PaymentClaimItem>, String>(
    (ref, societyId) => ref.watch(paymentClaimsApiProvider).forSociety(societyId, status: 'pending'));
