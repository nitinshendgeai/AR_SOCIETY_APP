import 'package:ar_society_app/features/vendor/domain/entities/vendor_entities.dart';

class VendorModel {
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

  VendorModel({
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

  factory VendorModel.fromJson(Map<String, dynamic> json) => VendorModel(
        id: json['id'] as String,
        societyId: json['society_id'] as String,
        vendorCode: json['vendor_code'] as String,
        companyName: json['company_name'] as String,
        contactPerson: json['contact_person'] as String?,
        mobile: json['mobile'] as String,
        email: json['email'] as String?,
        category: json['category'] as String,
        status: json['status'] as String? ?? 'active',
        gstNumber: json['gst_number'] as String?,
        bankAccount: json['bank_account'] as String?,
        bankName: json['bank_name'] as String?,
        bankIfsc: json['bank_ifsc'] as String?,
      );

  VendorEntity toEntity() => VendorEntity(
        id: id,
        societyId: societyId,
        vendorCode: vendorCode,
        companyName: companyName,
        contactPerson: contactPerson,
        mobile: mobile,
        email: email,
        category: category,
        status: status,
        gstNumber: gstNumber,
        bankAccount: bankAccount,
        bankName: bankName,
        bankIfsc: bankIfsc,
      );
}

class VendorInvoiceModel {
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

  VendorInvoiceModel({
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

  factory VendorInvoiceModel.fromJson(Map<String, dynamic> json) => VendorInvoiceModel(
        id: json['id'] as String,
        societyId: json['society_id'] as String,
        vendorId: json['vendor_id'] as String,
        vendorName: json['vendor_name'] as String?,
        invoiceNumber: json['invoice_number'] as String,
        invoiceDate: DateTime.parse(json['invoice_date'] as String),
        dueDate: json['due_date'] != null ? DateTime.parse(json['due_date'] as String) : null,
        amount: json['amount'] as String,
        gstAmount: json['gst_amount'] as String? ?? '0',
        totalAmount: json['total_amount'] as String,
        paidAmount: json['paid_amount'] as String? ?? '0',
        outstanding: json['outstanding'] as String? ?? '0',
        isPaid: json['is_paid'] as bool? ?? false,
        paidDate: json['paid_date'] != null ? DateTime.parse(json['paid_date'] as String) : null,
        paymentMode: json['payment_mode'] as String?,
        paymentRef: json['payment_ref'] as String?,
        bankName: json['bank_name'] as String?,
        description: json['description'] as String?,
        createdAt: json['created_at'] != null ? DateTime.parse(json['created_at'] as String) : null,
      );

  VendorInvoiceEntity toEntity() => VendorInvoiceEntity(
        id: id,
        societyId: societyId,
        vendorId: vendorId,
        vendorName: vendorName,
        invoiceNumber: invoiceNumber,
        invoiceDate: invoiceDate,
        dueDate: dueDate,
        amount: amount,
        gstAmount: gstAmount,
        totalAmount: totalAmount,
        paidAmount: paidAmount,
        outstanding: outstanding,
        isPaid: isPaid,
        paidDate: paidDate,
        paymentMode: paymentMode,
        paymentRef: paymentRef,
        bankName: bankName,
        description: description,
        createdAt: createdAt,
      );
}
