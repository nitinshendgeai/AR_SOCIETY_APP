import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';

DateTime? _date(Object? v) => v == null ? null : DateTime.parse(v as String);
String _iso(DateTime d) => d.toIso8601String().split('T').first;
String _money(double v) => v.toStringAsFixed(2);

const kVendorCategories = [
  ('electrical', 'Electrical'),
  ('plumbing', 'Plumbing'),
  ('lift', 'Lift'),
  ('security', 'Security'),
  ('housekeeping', 'Housekeeping'),
  ('gardening', 'Gardening'),
  ('pest_control', 'Pest control'),
  ('cctv', 'CCTV'),
  ('water_supply', 'Water supply'),
  ('generator', 'Generator'),
  ('civil', 'Civil / building'),
  ('it', 'IT'),
  ('other', 'Other'),
];

String vendorCategoryLabel(String v) =>
    kVendorCategories.firstWhere((c) => c.$1 == v, orElse: () => (v, v)).$2;

const kServiceFrequencies = [
  ('weekly', 'Weekly'),
  ('fortnightly', 'Fortnightly'),
  ('monthly', 'Monthly'),
  ('quarterly', 'Quarterly'),
  ('half_yearly', 'Half-yearly'),
  ('yearly', 'Yearly'),
  ('on_call', 'On call'),
];

class VendorRecord {
  final String id;
  final String vendorCode;
  final String companyName;
  final String? contactPerson;
  final String mobile;
  final String? email;
  final String category;
  final String status;
  final String? gstNumber;
  final String? panNumber;
  final String? bankAccount;
  final String? bankName;
  final String? bankIfsc;
  final String? address;
  final String? city;
  final String? pincode;
  final String? notes;
  final String? blacklistReason;

  VendorRecord.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        vendorCode = j['vendor_code'] as String,
        companyName = j['company_name'] as String,
        contactPerson = j['contact_person'] as String?,
        mobile = j['mobile'] as String,
        email = j['email'] as String?,
        category = j['category'] as String,
        status = j['status'] as String,
        gstNumber = j['gst_number'] as String?,
        panNumber = j['pan_number'] as String?,
        bankAccount = j['bank_account'] as String?,
        bankName = j['bank_name'] as String?,
        bankIfsc = j['bank_ifsc'] as String?,
        address = j['address'] as String?,
        city = j['city'] as String?,
        pincode = j['pincode'] as String?,
        notes = j['notes'] as String?,
        blacklistReason = j['blacklist_reason'] as String?;

  bool get isActive => status == 'active';
  String get statusLabel => switch (status) {
        'active' => 'Active',
        'inactive' => 'Inactive',
        'blacklisted' => 'Blacklisted',
        'under_review' => 'Under review',
        _ => status,
      };
}

class Quotation {
  final String id;
  final String vendorId;
  final String vendorName;
  final String? quotationRef;
  final DateTime quotationDate;
  final DateTime? validUntil;
  final String amount;
  final String gstAmount;
  final String totalAmount;
  final String? remarks;
  final bool isSelected;
  final bool isLowest;

  Quotation.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        vendorId = j['vendor_id'] as String,
        vendorName = j['vendor_name'] as String? ?? '',
        quotationRef = j['quotation_ref'] as String?,
        quotationDate = _date(j['quotation_date'])!,
        validUntil = _date(j['valid_until']),
        amount = j['amount'] as String,
        gstAmount = j['gst_amount'] as String,
        totalAmount = j['total_amount'] as String,
        remarks = j['remarks'] as String?,
        isSelected = j['is_selected'] as bool? ?? false,
        isLowest = j['is_lowest'] as bool? ?? false;
}

/// What the bye-laws need before work of [amount] can be given.
class Requirements {
  final String? amount;
  final String committeeLimit;
  final String tenderLimit;
  final int minQuotations;
  final bool needsTenders;
  final bool needsGeneralBody;

  Requirements.fromJson(Map<String, dynamic> j)
      : amount = j['amount'] as String?,
        committeeLimit = j['committee_limit'] as String,
        tenderLimit = j['tender_limit'] as String,
        minQuotations = j['min_quotations'] as int,
        needsTenders = j['needs_tenders'] as bool,
        needsGeneralBody = j['needs_general_body'] as bool;
}

/// The recorded decision to award a work order or contract.
class Sanction {
  final String? amount;
  final String? level;
  final String? committeeResolutionNo;
  final DateTime? committeeMeetingDate;
  final String? gbResolutionNo;
  final DateTime? gbMeetingDate;
  final DateTime? tendersOpenedOn;
  final String? selectionReason;
  final String? sanctionedByName;

  Sanction.fromJson(Map<String, dynamic> j)
      : amount = j['sanctioned_amount'] as String?,
        level = j['sanction_level'] as String?,
        committeeResolutionNo = j['committee_resolution_no'] as String?,
        committeeMeetingDate = _date(j['committee_meeting_date']),
        gbResolutionNo = j['gb_resolution_no'] as String?,
        gbMeetingDate = _date(j['gb_meeting_date']),
        tendersOpenedOn = _date(j['tenders_opened_on']),
        selectionReason = j['selection_reason'] as String?,
        sanctionedByName = j['sanctioned_by_name'] as String?;

  bool get isSanctioned => amount != null;
  bool get byGeneralBody => level == 'general_body';
}

class WorkOrderBill {
  final String id;
  final String invoiceNumber;
  final DateTime invoiceDate;
  final String totalAmount;
  final String paidAmount;
  final String outstanding;
  final bool isPaid;

  WorkOrderBill.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        invoiceNumber = j['invoice_number'] as String,
        invoiceDate = _date(j['invoice_date'])!,
        totalAmount = j['total_amount'] as String,
        paidAmount = j['paid_amount'] as String,
        outstanding = j['outstanding'] as String,
        isPaid = j['is_paid'] as bool;
}

class WorkOrder {
  final String id;
  final String woNumber;
  final String title;
  final String? scopeOfWork;
  final String? location;
  final String category;
  final String? estimatedCost;
  final String status;
  final String statusLabel;
  final String? vendorId;
  final String? vendorName;
  final String? expenseAccountId;
  final String? expenseAccountName;
  final DateTime? startDate;
  final DateTime? dueDate;
  final String? paymentTerms;
  final String advanceAmount;
  final String retentionPct;
  final int defectLiabilityMonths;
  final DateTime? issuedOn;
  final DateTime? completedOn;
  final String? completionNotes;
  final String? certificateRef;
  final String? certifiedByName;
  final DateTime? retentionDueOn;
  final DateTime? retentionReleasedOn;
  final String? cancelReason;
  final Sanction sanction;
  final List<Quotation> quotations;
  final Requirements requirements;
  final List<WorkOrderBill> bills;
  final String billed;
  final String paid;
  final String unbilled;
  final String retentionHeld;
  final String payableNow;

  WorkOrder.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        woNumber = j['wo_number'] as String,
        title = j['title'] as String,
        scopeOfWork = j['scope_of_work'] as String?,
        location = j['location'] as String?,
        category = j['category'] as String,
        estimatedCost = j['estimated_cost'] as String?,
        status = j['status'] as String,
        statusLabel = j['status_label'] as String,
        vendorId = j['vendor_id'] as String?,
        vendorName = j['vendor_name'] as String?,
        expenseAccountId = j['expense_account_id'] as String?,
        expenseAccountName = j['expense_account_name'] as String?,
        startDate = _date(j['start_date']),
        dueDate = _date(j['due_date']),
        paymentTerms = j['payment_terms'] as String?,
        advanceAmount = j['advance_amount'] as String,
        retentionPct = j['retention_pct'] as String,
        defectLiabilityMonths = j['defect_liability_months'] as int,
        issuedOn = _date(j['issued_on']),
        completedOn = _date(j['completed_on']),
        completionNotes = j['completion_notes'] as String?,
        certificateRef = j['certificate_ref'] as String?,
        certifiedByName = j['certified_by_name'] as String?,
        retentionDueOn = _date(j['retention_due_on']),
        retentionReleasedOn = _date(j['retention_released_on']),
        cancelReason = j['cancel_reason'] as String?,
        sanction = Sanction.fromJson(j),
        quotations = [for (final q in j['quotations'] as List) Quotation.fromJson(q as Map<String, dynamic>)],
        requirements = Requirements.fromJson(j['requirements'] as Map<String, dynamic>),
        bills = [for (final b in j['bills'] as List) WorkOrderBill.fromJson(b as Map<String, dynamic>)],
        billed = j['billed'] as String,
        paid = j['paid'] as String,
        unbilled = j['unbilled'] as String,
        retentionHeld = j['retention_held'] as String,
        payableNow = j['payable_now'] as String;

  bool get isDraft => status == 'draft';
  bool get canPrint => !{'draft', 'cancelled'}.contains(status);
  bool get canBill => status == 'issued' || status == 'completed';
  bool get hasRetention => (double.tryParse(retentionPct) ?? 0) > 0;
}

class AmcContract {
  final String id;
  final String contractNumber;
  final String contractName;
  final String vendorId;
  final String? vendorName;
  final String category;
  final String status;
  final DateTime startDate;
  final DateTime endDate;
  final int daysToExpiry;
  final String serviceFrequency;
  final String? scopeOfWork;
  final String? annualValue;
  final Sanction sanction;
  final List<Quotation> quotations;
  final Requirements requirements;

  AmcContract.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        contractNumber = j['contract_number'] as String,
        contractName = j['contract_name'] as String,
        vendorId = j['vendor_id'] as String,
        vendorName = j['vendor_name'] as String?,
        category = j['category'] as String,
        status = j['status'] as String,
        startDate = _date(j['start_date'])!,
        endDate = _date(j['end_date'])!,
        daysToExpiry = j['days_to_expiry'] as int,
        serviceFrequency = j['service_frequency'] as String,
        scopeOfWork = j['scope_of_work'] as String?,
        annualValue = j['annual_value'] as String?,
        sanction = Sanction.fromJson(j),
        quotations = [for (final q in j['quotations'] as List) Quotation.fromJson(q as Map<String, dynamic>)],
        requirements = Requirements.fromJson(j['requirements'] as Map<String, dynamic>);

  bool get isDraft => status == 'draft';
  String get statusLabel => switch (status) {
        'draft' => sanction.isSanctioned ? 'Sanctioned, not started' : 'Collecting quotations',
        'active' => 'Active',
        'expired' => 'Expired',
        'renewed' => 'Renewed',
        'terminated' => 'Terminated',
        _ => status,
      };
}

/// The committee's spending limit and the tender limit (bye-law 157).
class ProcurementLimits {
  final int members;
  final String byeLawLimit;
  final String committeeLimit;
  final bool committeeLimitSet;
  final String tenderLimit;
  final bool tenderLimitSet;
  final int minQuotations;
  final String? gbResolutionNo;
  final DateTime? gbMeetingDate;

  ProcurementLimits.fromJson(Map<String, dynamic> j)
      : members = j['members'] as int,
        byeLawLimit = j['bye_law_limit'] as String,
        committeeLimit = j['committee_limit'] as String,
        committeeLimitSet = j['committee_limit_set'] as bool,
        tenderLimit = j['tender_limit'] as String,
        tenderLimitSet = j['tender_limit_set'] as bool,
        minQuotations = j['min_quotations'] as int,
        gbResolutionNo = j['gb_resolution_no'] as String?,
        gbMeetingDate = _date(j['gb_meeting_date']);
}

/// The sanction form's values, shared by work orders and contracts.
class SanctionInput {
  final String quotationId;
  final String committeeResolutionNo;
  final DateTime committeeMeetingDate;
  final String? gbResolutionNo;
  final DateTime? gbMeetingDate;
  final DateTime? tendersOpenedOn;
  final String? selectionReason;
  final bool noInterestDeclared;

  SanctionInput({
    required this.quotationId,
    required this.committeeResolutionNo,
    required this.committeeMeetingDate,
    this.gbResolutionNo,
    this.gbMeetingDate,
    this.tendersOpenedOn,
    this.selectionReason,
    required this.noInterestDeclared,
  });

  Map<String, dynamic> toJson() => {
        'quotation_id': quotationId,
        'committee_resolution_no': committeeResolutionNo,
        'committee_meeting_date': _iso(committeeMeetingDate),
        if (gbResolutionNo != null && gbResolutionNo!.isNotEmpty) 'gb_resolution_no': gbResolutionNo,
        if (gbMeetingDate != null) 'gb_meeting_date': _iso(gbMeetingDate!),
        if (tendersOpenedOn != null) 'tenders_opened_on': _iso(tendersOpenedOn!),
        if (selectionReason != null && selectionReason!.isNotEmpty) 'selection_reason': selectionReason,
        'no_interest_declared': noInterestDeclared,
      };
}

class QuotationInput {
  final String vendorId;
  final String? ref;
  final DateTime date;
  final DateTime? validUntil;
  final double amount;
  final double gst;
  final String? remarks;

  QuotationInput({required this.vendorId, this.ref, required this.date, this.validUntil, required this.amount,
      required this.gst, this.remarks});

  Map<String, dynamic> toJson() => {
        'vendor_id': vendorId,
        if (ref != null && ref!.isNotEmpty) 'quotation_ref': ref,
        'quotation_date': _iso(date),
        if (validUntil != null) 'valid_until': _iso(validUntil!),
        'amount': _money(amount),
        'gst_amount': _money(gst),
        'total_amount': _money(amount + gst),
        if (remarks != null && remarks!.isNotEmpty) 'remarks': remarks,
      };
}

class VendorsWorkApi {
  final Dio _dio;
  VendorsWorkApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  // Vendors
  Future<List<VendorRecord>> vendors(String societyId) async {
    final r = await _dio.get('/vendors/society/$societyId', queryParameters: {'limit': 500});
    return [for (final v in r.data as List) VendorRecord.fromJson(v as Map<String, dynamic>)];
  }

  Future<VendorRecord> createVendor(Map<String, dynamic> body) async =>
      VendorRecord.fromJson((await _dio.post('/vendors/', data: body)).data as Map<String, dynamic>);

  Future<VendorRecord> updateVendor(String id, Map<String, dynamic> body) async =>
      VendorRecord.fromJson((await _dio.patch('/vendors/$id', data: body)).data as Map<String, dynamic>);

  Future<VendorRecord> blacklistVendor(String id, String reason) async => VendorRecord.fromJson(
      (await _dio.post('/vendors/$id/blacklist', data: {'reason': reason})).data as Map<String, dynamic>);

  // Limits
  Future<ProcurementLimits> limits(String societyId) async => ProcurementLimits.fromJson(
      (await _dio.get('/vendors/procurement-settings/$societyId')).data as Map<String, dynamic>);

  Future<ProcurementLimits> saveLimits(String societyId, Map<String, dynamic> body) async =>
      ProcurementLimits.fromJson(
          (await _dio.put('/vendors/procurement-settings/$societyId', data: body)).data as Map<String, dynamic>);

  // Work orders
  Future<List<WorkOrder>> workOrders(String societyId) async {
    final r = await _dio.get('/vendors/work-orders/society/$societyId');
    return [for (final w in r.data as List) WorkOrder.fromJson(w as Map<String, dynamic>)];
  }

  Future<WorkOrder> workOrder(String id) async =>
      WorkOrder.fromJson((await _dio.get('/vendors/work-orders/$id')).data as Map<String, dynamic>);

  Future<WorkOrder> _wo(Future<Response> call) async => WorkOrder.fromJson((await call).data as Map<String, dynamic>);

  Future<WorkOrder> createWorkOrder(Map<String, dynamic> body) => _wo(_dio.post('/vendors/work-orders', data: body));
  Future<WorkOrder> updateWorkOrder(String id, Map<String, dynamic> body) =>
      _wo(_dio.patch('/vendors/work-orders/$id', data: body));
  Future<WorkOrder> addWorkOrderQuotation(String id, QuotationInput q) =>
      _wo(_dio.post('/vendors/work-orders/$id/quotations', data: q.toJson()));
  Future<WorkOrder> removeWorkOrderQuotation(String id, String quotationId) =>
      _wo(_dio.delete('/vendors/work-orders/$id/quotations/$quotationId'));
  Future<WorkOrder> sanctionWorkOrder(String id, SanctionInput s) =>
      _wo(_dio.post('/vendors/work-orders/$id/sanction', data: s.toJson()));
  Future<WorkOrder> reviseSanction(String id, Map<String, dynamic> body) =>
      _wo(_dio.post('/vendors/work-orders/$id/revise-sanction', data: body));
  Future<WorkOrder> issueWorkOrder(String id, DateTime on) =>
      _wo(_dio.post('/vendors/work-orders/$id/issue', data: {'issued_on': _iso(on)}));
  Future<WorkOrder> completeWorkOrder(String id, DateTime on, String notes, String? certificateRef) =>
      _wo(_dio.post('/vendors/work-orders/$id/complete', data: {
        'completed_on': _iso(on),
        'completion_notes': notes,
        if (certificateRef != null && certificateRef.isNotEmpty) 'certificate_ref': certificateRef,
      }));
  Future<WorkOrder> releaseRetention(String id, DateTime on) =>
      _wo(_dio.post('/vendors/work-orders/$id/release-retention', data: {'released_on': _iso(on)}));
  Future<WorkOrder> closeWorkOrder(String id) => _wo(_dio.post('/vendors/work-orders/$id/close'));
  Future<WorkOrder> cancelWorkOrder(String id, String reason) =>
      _wo(_dio.post('/vendors/work-orders/$id/cancel', data: {'reason': reason}));

  Future<Uint8List> workOrderPdf(String id) async {
    final r = await _dio.get<List<int>>('/vendors/work-orders/$id/pdf',
        options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }

  /// A vendor's bill against a work order (booked to the work order's expense head).
  Future<void> recordBill({
    required String societyId,
    required WorkOrder wo,
    required String invoiceNumber,
    required DateTime invoiceDate,
    required double amount,
    required double gst,
    String? description,
  }) =>
      _dio.post('/vendors/invoices', data: {
        'society_id': societyId,
        'vendor_id': wo.vendorId,
        'work_order_id': wo.id,
        'invoice_number': invoiceNumber,
        'invoice_date': _iso(invoiceDate),
        'amount': _money(amount),
        'gst_amount': _money(gst),
        'total_amount': _money(amount + gst),
        if (description != null && description.isNotEmpty) 'description': description,
      });

  // Contracts
  Future<List<AmcContract>> contracts(String societyId) async {
    final r = await _dio.get('/vendors/contracts/society/$societyId', queryParameters: {'limit': 500});
    return [for (final c in r.data as List) AmcContract.fromJson(c as Map<String, dynamic>)];
  }

  Future<AmcContract> _c(Future<Response> call) async =>
      AmcContract.fromJson((await call).data as Map<String, dynamic>);

  Future<AmcContract> contract(String id) => _c(_dio.get('/vendors/contracts/$id'));
  Future<AmcContract> createContract(Map<String, dynamic> body) => _c(_dio.post('/vendors/contracts', data: body));
  Future<AmcContract> addContractQuotation(String id, QuotationInput q) =>
      _c(_dio.post('/vendors/contracts/$id/quotations', data: q.toJson()));
  Future<AmcContract> removeContractQuotation(String id, String quotationId) =>
      _c(_dio.delete('/vendors/contracts/$id/quotations/$quotationId'));
  Future<AmcContract> sanctionContract(String id, SanctionInput s) =>
      _c(_dio.post('/vendors/contracts/$id/sanction', data: s.toJson()));
  Future<AmcContract> activateContract(String id) => _c(_dio.post('/vendors/contracts/$id/activate'));
}
