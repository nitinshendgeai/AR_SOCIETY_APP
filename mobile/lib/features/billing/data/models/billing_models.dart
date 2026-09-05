import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart';

class OnlinePaymentModel {
  final String id;
  final String societyId;
  final String? wingId;
  final String? wingName;
  final String flatId;
  final String? flatNumber;
  final String? billId;
  final String receiptNumber;
  final String amount;
  final DateTime paymentDate;
  final String paymentMode;
  final String? transactionRef;
  final String? bankName;
  final String? notes;
  final String status;
  final String? recordedBy;
  final String? reviewedBy;
  final DateTime? reviewedAt;
  final String? reviewNotes;
  final String screenshotMimeType;
  final String? screenshotFileName;
  final DateTime? createdAt;

  OnlinePaymentModel({
    required this.id,
    required this.societyId,
    this.wingId,
    this.wingName,
    required this.flatId,
    this.flatNumber,
    this.billId,
    required this.receiptNumber,
    required this.amount,
    required this.paymentDate,
    required this.paymentMode,
    this.transactionRef,
    this.bankName,
    this.notes,
    this.status = 'pending',
    this.recordedBy,
    this.reviewedBy,
    this.reviewedAt,
    this.reviewNotes,
    this.screenshotMimeType = 'image/jpeg',
    this.screenshotFileName,
    this.createdAt,
  });

  factory OnlinePaymentModel.fromJson(Map<String, dynamic> json) {
    return OnlinePaymentModel(
      id: json['id'] as String,
      societyId: json['society_id'] as String,
      wingId: json['wing_id'] as String?,
      wingName: json['wing_name'] as String?,
      flatId: json['flat_id'] as String,
      flatNumber: json['flat_number'] as String?,
      billId: json['bill_id'] as String?,
      receiptNumber: json['receipt_number'] as String,
      amount: json['amount'] as String,
      paymentDate: DateTime.parse(json['payment_date'] as String),
      paymentMode: json['payment_mode'] as String,
      transactionRef: json['transaction_ref'] as String?,
      bankName: json['bank_name'] as String?,
      notes: json['notes'] as String?,
      status: json['status'] as String? ?? 'pending',
      recordedBy: json['recorded_by'] as String?,
      reviewedBy: json['reviewed_by'] as String?,
      reviewedAt: json['reviewed_at'] != null ? DateTime.parse(json['reviewed_at'] as String) : null,
      reviewNotes: json['review_notes'] as String?,
      screenshotMimeType: json['screenshot_mime_type'] as String? ?? 'image/jpeg',
      screenshotFileName: json['screenshot_file_name'] as String?,
      createdAt: json['created_at'] != null ? DateTime.parse(json['created_at'] as String) : null,
    );
  }

  OnlinePaymentEntity toEntity() => OnlinePaymentEntity(
        id: id,
        societyId: societyId,
        wingId: wingId,
        wingName: wingName,
        flatId: flatId,
        flatNumber: flatNumber,
        billId: billId,
        receiptNumber: receiptNumber,
        amount: amount,
        paymentDate: paymentDate,
        paymentMode: paymentMode,
        transactionRef: transactionRef,
        bankName: bankName,
        notes: notes,
        status: status,
        recordedBy: recordedBy,
        reviewedBy: reviewedBy,
        reviewedAt: reviewedAt,
        reviewNotes: reviewNotes,
        screenshotMimeType: screenshotMimeType,
        screenshotFileName: screenshotFileName,
        createdAt: createdAt,
      );
}
