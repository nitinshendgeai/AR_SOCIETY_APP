import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart';

class OnlinePaymentModel {
  final String id;
  final String societyId;
  final String? wingId;
  final String? wingName;
  final String flatId;
  final String? flatNumber;
  final String? billId;
  final String? billInvoiceNumber;
  final String receiptNumber;
  final String amount;
  final String purpose;
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
  final String? screenshotMimeType;
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
    this.billInvoiceNumber,
    required this.receiptNumber,
    required this.amount,
    this.purpose = 'maintenance',
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
    this.screenshotMimeType,
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
      billInvoiceNumber: json['bill_invoice_number'] as String?,
      receiptNumber: json['receipt_number'] as String,
      amount: json['amount'] as String,
      purpose: json['purpose'] as String? ?? 'maintenance',
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
      screenshotMimeType: json['screenshot_mime_type'] as String?,
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
        billInvoiceNumber: billInvoiceNumber,
        receiptNumber: receiptNumber,
        amount: amount,
        purpose: purpose,
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

class BillModel {
  final String id;
  final String invoiceNumber;
  final String billStatus;
  final DateTime dueDate;
  final String totalAmount;
  final String paidAmount;
  final String outstanding;

  BillModel({
    required this.id,
    required this.invoiceNumber,
    required this.billStatus,
    required this.dueDate,
    required this.totalAmount,
    required this.paidAmount,
    required this.outstanding,
  });

  factory BillModel.fromJson(Map<String, dynamic> json) {
    return BillModel(
      id: json['id'] as String,
      invoiceNumber: json['invoice_number'] as String,
      billStatus: json['bill_status'] as String,
      dueDate: DateTime.parse(json['due_date'] as String),
      totalAmount: json['total_amount'] as String,
      paidAmount: json['paid_amount'] as String,
      outstanding: json['outstanding'] as String,
    );
  }

  BillEntity toEntity() => BillEntity(
        id: id,
        invoiceNumber: invoiceNumber,
        billStatus: billStatus,
        dueDate: dueDate,
        totalAmount: totalAmount,
        paidAmount: paidAmount,
        outstanding: outstanding,
      );
}

class BankStatementEntryModel {
  final String id;
  final String societyId;
  final DateTime txnDate;
  final String description;
  final String? reference;
  final String amount;
  final String matchStatus;
  final String? matchedSubmissionId;
  final String? matchedSubmissionReceiptNumber;
  final DateTime? matchedAt;
  final String? ignoreReason;
  final DateTime? createdAt;

  BankStatementEntryModel({
    required this.id,
    required this.societyId,
    required this.txnDate,
    required this.description,
    this.reference,
    required this.amount,
    this.matchStatus = 'unmatched',
    this.matchedSubmissionId,
    this.matchedSubmissionReceiptNumber,
    this.matchedAt,
    this.ignoreReason,
    this.createdAt,
  });

  factory BankStatementEntryModel.fromJson(Map<String, dynamic> json) {
    return BankStatementEntryModel(
      id: json['id'] as String,
      societyId: json['society_id'] as String,
      txnDate: DateTime.parse(json['txn_date'] as String),
      description: json['description'] as String,
      reference: json['reference'] as String?,
      amount: json['amount'] as String,
      matchStatus: json['match_status'] as String? ?? 'unmatched',
      matchedSubmissionId: json['matched_submission_id'] as String?,
      matchedSubmissionReceiptNumber: json['matched_submission_receipt_number'] as String?,
      matchedAt: json['matched_at'] != null ? DateTime.parse(json['matched_at'] as String) : null,
      ignoreReason: json['ignore_reason'] as String?,
      createdAt: json['created_at'] != null ? DateTime.parse(json['created_at'] as String) : null,
    );
  }

  BankStatementEntryEntity toEntity() => BankStatementEntryEntity(
        id: id,
        societyId: societyId,
        txnDate: txnDate,
        description: description,
        reference: reference,
        amount: amount,
        matchStatus: matchStatus,
        matchedSubmissionId: matchedSubmissionId,
        matchedSubmissionReceiptNumber: matchedSubmissionReceiptNumber,
        matchedAt: matchedAt,
        ignoreReason: ignoreReason,
        createdAt: createdAt,
      );
}
