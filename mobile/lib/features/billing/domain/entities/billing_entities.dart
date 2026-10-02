/// A payment receipt recorded by the FMC Manager against a Wing + Flat —
/// either ON BILL (billId set, applied immediately to that bill/due
/// tracker) or ON ACCOUNT (billId null). Either way a receipt is issued
/// immediately; bank reconciliation (non-cash modes only — cash starts
/// already `reconciled`) is a separate, later step. See backend
/// OnlinePaymentSubmission.
/// Part of a recorded payment set off against one maintenance bill.
class PaymentSetOff {
  final String billId;
  final String? invoiceNumber;
  final DateTime? billDate;
  final double amount;
  final DateTime? allocatedAt;
  final DateTime? releasedAt;
  final String? releasedReason;

  const PaymentSetOff({
    required this.billId,
    this.invoiceNumber,
    this.billDate,
    required this.amount,
    this.allocatedAt,
    this.releasedAt,
    this.releasedReason,
  });

  /// Still counts — not undone by a rejected payment or a cancelled bill.
  bool get isLive => releasedAt == null;
}

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

  /// The bills this payment was set off against (oldest first), and what
  /// is left over as the member's advance.
  final List<PaymentSetOff> setOffs;
  final double appliedAmount;
  final double unappliedAmount;

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
    this.setOffs = const [],
    this.appliedAmount = 0,
    this.unappliedAmount = 0,
  });

  bool get isPending => status == 'pending';
  bool get isReconciled => status == 'reconciled';
  bool get isRejected => status == 'rejected';
  List<PaymentSetOff> get liveSetOffs => setOffs.where((a) => a.isLive).toList();
  bool get isOnBill => liveSetOffs.isNotEmpty || billId != null;

  /// "Bill INV-…" / "3 bills (INV-… +2)" / "Advance" / the purpose — what the payment went against.
  String get appliedLabel {
    final bills = liveSetOffs.map((a) => a.invoiceNumber ?? '').where((n) => n.isNotEmpty).toList();
    if (bills.isNotEmpty) {
      final what = bills.length == 1 ? 'Bill ${bills.first}' : '${bills.length} bills (${bills.first} +${bills.length - 1})';
      return '$what${unappliedAmount > 0 ? ' + advance' : ''}';
    }
    if (billId != null) return 'Bill ${billInvoiceNumber ?? ''}';
    if (unappliedAmount > 0) return 'Advance';
    return onlinePaymentPurposeLabel(purpose);
  }
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

/// One credit row imported from a bank statement — the other half of
/// reconciliation. Matching it to a PENDING OnlinePaymentEntity (via
/// confirm) is what actually moves that payment to `reconciled`; import
/// alone only ever creates `unmatched` rows. See backend
/// BankStatementEntry / BillingService's Bank Reconciliation section.
class BankStatementEntryEntity {
  final String id;
  final String societyId;
  final DateTime txnDate;
  final String description;
  final String? reference;
  final String amount;
  final String matchStatus; // unmatched | matched | ignored
  final String? matchedSubmissionId;
  final String? matchedSubmissionReceiptNumber;
  final DateTime? matchedAt;
  final String? ignoreReason;
  final DateTime? createdAt;

  const BankStatementEntryEntity({
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

  bool get isUnmatched => matchStatus == 'unmatched';
  bool get isMatched => matchStatus == 'matched';
  bool get isIgnored => matchStatus == 'ignored';
}

String bankMatchStatusLabel(String value) => switch (value) {
      'unmatched' => 'Unmatched',
      'matched' => 'Matched',
      'ignored' => 'Ignored',
      _ => value,
    };
