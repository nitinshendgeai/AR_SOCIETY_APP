/// A payment receipt recorded by the FMC Manager against a Wing + Flat —
/// either ON BILL (billId set, applied immediately to that bill/due
/// tracker) or ON ACCOUNT (billId null). Either way a receipt is issued
/// immediately; bank reconciliation (non-cash modes only — cash starts
/// already `reconciled`) is a separate, later step. See backend
/// OnlinePaymentSubmission.
class OnlinePaymentEntity {
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
  final String status; // pending | reconciled | rejected
  final String? recordedBy;
  final String? reviewedBy;
  final DateTime? reviewedAt;
  final String? reviewNotes;
  final String? screenshotMimeType;
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

  bool get isPending => status == 'pending';
  bool get isReconciled => status == 'reconciled';
  bool get isRejected => status == 'rejected';
  bool get isOnBill => billId != null;
  bool get hasScreenshot => screenshotMimeType != null;
}

/// A per-flat maintenance invoice, for the "On Bill" bill picker. See
/// backend MaintenanceBill / GET /billing/bills/flat/{flat_id}.
class BillEntity {
  final String id;
  final String invoiceNumber;
  final String billStatus;
  final DateTime dueDate;
  final String totalAmount;
  final String paidAmount;
  final String outstanding;

  const BillEntity({
    required this.id,
    required this.invoiceNumber,
    required this.billStatus,
    required this.dueDate,
    required this.totalAmount,
    required this.paidAmount,
    required this.outstanding,
  });
}

const kOnlinePaymentPurposes = [
  ('maintenance', 'Maintenance'),
  ('water', 'Water'),
  ('parking', 'Parking'),
  ('sinking_fund', 'Sinking Fund'),
  ('repair_fund', 'Repair Fund'),
  ('amenities', 'Amenities'),
  ('special_assessment', 'Special Assessment'),
  ('other', 'Other'),
];

String onlinePaymentPurposeLabel(String value) =>
    kOnlinePaymentPurposes.firstWhere((p) => p.$1 == value, orElse: () => (value, value)).$2;

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

/// Modes where a resident actually has proof to show (a UPI/bank app
/// screen) — cash and cheque don't, so the screenshot picker is optional
/// for those. Mirrors BillingService.SCREENSHOT_REQUIRED_MODES.
const kScreenshotRequiredModes = {'upi', 'bank_transfer', 'neft', 'rtgs', 'online_gateway'};

String reconciliationStatusLabel(String value) => switch (value) {
      'pending' => 'Pending Review',
      'reconciled' => 'Reconciled',
      'rejected' => 'Rejected',
      _ => value,
    };
