/// A society's vendor (contractor/supplier) — the counterpart of a
/// resident on the payable side. See backend Vendor model.
class VendorEntity {
  final String id;
  final String societyId;
  final String vendorCode;
  final String companyName;
  final String? contactPerson;
  final String mobile;
  final String? email;
  final String category;
  final String status;
  final String? gstNumber;
  final String? bankAccount;
  final String? bankName;
  final String? bankIfsc;

  const VendorEntity({
    required this.id,
    required this.societyId,
    required this.vendorCode,
    required this.companyName,
    this.contactPerson,
    required this.mobile,
    this.email,
    required this.category,
    this.status = 'active',
    this.gstNumber,
    this.bankAccount,
    this.bankName,
    this.bankIfsc,
  });
}

/// A bill owed to a vendor — the society's payable side, the mirror of
/// billing's OnlinePaymentEntity (which is receivable, from residents).
/// paid_amount accumulates across possibly-partial payments; isPaid only
/// flips true once paidAmount reaches totalAmount. See backend
/// VendorInvoice / VendorService_.record_vendor_payment.
class VendorInvoiceEntity {
  final String id;
  final String societyId;
  final String vendorId;
  final String? vendorName;
  final String invoiceNumber;
  final DateTime invoiceDate;
  final DateTime? dueDate;
  final String amount;
  final String gstAmount;
  final String totalAmount;
  final String paidAmount;
  final String outstanding;
  final bool isPaid;
  final DateTime? paidDate;
  final String? paymentMode;
  final String? paymentRef;
  final String? bankName;
  final String? description;
  final DateTime? createdAt;

  const VendorInvoiceEntity({
    required this.id,
    required this.societyId,
    required this.vendorId,
    this.vendorName,
    required this.invoiceNumber,
    required this.invoiceDate,
    this.dueDate,
    required this.amount,
    this.gstAmount = '0',
    required this.totalAmount,
    this.paidAmount = '0',
    this.outstanding = '0',
    this.isPaid = false,
    this.paidDate,
    this.paymentMode,
    this.paymentRef,
    this.bankName,
    this.description,
    this.createdAt,
  });
}

const kVendorCategories = [
  ('electrical', 'Electrical'),
  ('plumbing', 'Plumbing'),
  ('lift', 'Lift'),
  ('security', 'Security'),
  ('housekeeping', 'Housekeeping'),
  ('gardening', 'Gardening'),
  ('pest_control', 'Pest Control'),
  ('cctv', 'CCTV'),
  ('water_supply', 'Water Supply'),
  ('generator', 'Generator'),
  ('civil', 'Civil'),
  ('it', 'IT'),
  ('other', 'Other'),
];

String vendorCategoryLabel(String value) =>
    kVendorCategories.firstWhere((c) => c.$1 == value, orElse: () => (value, value)).$2;

const kVendorPaymentModes = [
  ('cash', 'Cash'),
  ('upi', 'UPI'),
  ('bank_transfer', 'Bank Transfer'),
  ('cheque', 'Cheque'),
  ('neft', 'NEFT'),
  ('rtgs', 'RTGS'),
];

String vendorPaymentModeLabel(String value) =>
    kVendorPaymentModes.firstWhere((m) => m.$1 == value, orElse: () => (value, value)).$2;
