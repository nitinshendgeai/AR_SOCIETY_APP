/// A resident's online (UPI/bank transfer) payment screenshot recorded by
/// the FMC Manager against a Wing + Flat, captured for later bank
/// reconciliation. See backend OnlinePaymentSubmission.
class OnlinePaymentEntity {
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
  final String status; // pending | reconciled | rejected
  final String? recordedBy;
  final String? reviewedBy;
  final DateTime? reviewedAt;
  final String? reviewNotes;
  final String screenshotMimeType;
  final String? screenshotFileName;
  final DateTime? createdAt;

  const OnlinePaymentEntity({
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

  bool get isPending => status == 'pending';
  bool get isReconciled => status == 'reconciled';
  bool get isRejected => status == 'rejected';
}

const kPaymentModes = [
  ('upi', 'UPI'),
  ('bank_transfer', 'Bank Transfer'),
  ('neft', 'NEFT'),
  ('rtgs', 'RTGS'),
  ('cheque', 'Cheque'),
  ('cash', 'Cash'),
  ('online_gateway', 'Online Gateway'),
];

String paymentModeLabel(String value) =>
    kPaymentModes.firstWhere((m) => m.$1 == value, orElse: () => (value, value)).$2;

String reconciliationStatusLabel(String value) => switch (value) {
      'pending' => 'Pending Review',
      'reconciled' => 'Reconciled',
      'rejected' => 'Rejected',
      _ => value,
    };
