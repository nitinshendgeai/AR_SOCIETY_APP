import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';

// ── Entities ─────────────────────────────────────────────────────────────────

DateTime _date(Object? v) => DateTime.parse(v as String);
String _str(Object? v) => v?.toString() ?? '0';
double amountOf(String v) => double.tryParse(v) ?? 0;

final _rupees = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);
String formatRupees(String v) => _rupees.format(amountOf(v));

String formatBillDate(DateTime d) => DateFormat('d MMM yyyy').format(d);

/// How a charge head becomes a per-flat amount (backend ChargeBasis). The
/// meaning of [ChargeHead.defaultAmount] depends on it.
const kChargeBases = [
  ('fixed', 'Same for every flat'),
  ('per_sqft', 'Per sq ft of flat area'),
  ('construction_cost_pct', '% of construction cost (yearly)'),
  ('budget_equal', 'Annual budget, split equally'),
  ('budget_area', 'Annual budget, split by area'),
  ('parking', 'Per allotted parking slot'),
];

String chargeBasisLabel(String v) =>
    kChargeBases.firstWhere((b) => b.$1 == v, orElse: () => (v, v)).$2;

/// Label for the amount field, which means something different per basis.
String chargeAmountFieldLabel(String basis) => switch (basis) {
      'per_sqft' => 'Rate per sq ft per month (₹)',
      'construction_cost_pct' => 'Rate (% per year)',
      'budget_equal' || 'budget_area' => 'Annual budget (₹)',
      'parking' => 'Rate per slot per month (₹)',
      _ => 'Amount per flat per month (₹)',
    };

String chargeBasisHint(String basis) => switch (basis) {
      'per_sqft' => 'Flat area × rate. Most societies charge ₹2–7 per sq ft.',
      'construction_cost_pct' =>
        'Area × construction cost/sq ft (set in Rules) × % ÷ 12. Bye-laws: sinking fund min 0.25%, repair fund 0.75%.',
      'budget_equal' => 'Yearly cost ÷ number of flats ÷ 12 — e.g. security, housekeeping staff.',
      'budget_area' => 'Yearly cost shared in proportion to each flat\'s area ÷ 12 — e.g. water, electricity.',
      'parking' => 'Charged per active parking allotment. A slot\'s own monthly charge overrides this rate.',
      _ => 'Service charges, lift and common electricity are shared equally under the bye-laws.',
    };

/// e.g. "₹2,500 / flat / month", "0.25% of construction cost / yr".
String basisRateLabel(String basis, String? amount) {
  if (amount == null) return '${chargeBasisLabel(basis)} · amount set per society';
  return switch (basis) {
    'per_sqft' => '${formatRupees(amount)} / sq ft / month',
    'construction_cost_pct' => '$amount% of construction cost / yr',
    'budget_equal' => '${formatRupees(amount)} / yr, split equally',
    'budget_area' => '${formatRupees(amount)} / yr, split by area',
    'parking' => '${formatRupees(amount)} / slot / month',
    _ => '${formatRupees(amount)} / flat / month',
  };
}

/// An entry in the society's maintenance element master (backend
/// MaintenanceElement) — a kind of charge with its default calculation.
/// Charge heads are created from these.
class MaintenanceElement {
  final String id;
  final String code;
  final String name;
  final String? description;
  final String? byeLawRef;
  final String category;
  final String defaultBasis;
  final String? defaultAmount;
  final bool isServiceCharge;
  final bool gstApplicable;
  final bool isSystem;
  final bool isActive;

  const MaintenanceElement({
    required this.id,
    required this.code,
    required this.name,
    this.description,
    this.byeLawRef,
    required this.category,
    required this.defaultBasis,
    this.defaultAmount,
    this.isServiceCharge = false,
    this.gstApplicable = true,
    this.isSystem = false,
    this.isActive = true,
  });

  String get rateLabel => basisRateLabel(defaultBasis, defaultAmount);

  factory MaintenanceElement.fromJson(Map<String, dynamic> j) => MaintenanceElement(
        id: j['id'] as String,
        code: j['code'] as String,
        name: j['name'] as String,
        description: j['description'] as String?,
        byeLawRef: j['bye_law_ref'] as String?,
        category: j['category'] as String,
        defaultBasis: j['default_basis'] as String,
        defaultAmount: j['default_amount'] as String?,
        isServiceCharge: j['is_service_charge'] as bool? ?? false,
        gstApplicable: j['gst_applicable'] as bool? ?? true,
        isSystem: j['is_system'] as bool? ?? false,
        isActive: j['is_active'] as bool? ?? true,
      );
}

/// A society charge head (backend MaintenanceChargeConfig) — calculated
/// per flat and copied onto every bill as a line item at generation time.
class ChargeHead {
  final String id;
  final String chargeType;
  final String name;
  final String? description;
  final String? defaultAmount;
  final String basis;
  final bool isServiceCharge;
  final bool gstApplicable;
  final String taxPercent;
  final String? elementId;
  final String? elementName;
  final bool isActive;

  const ChargeHead({
    required this.id,
    required this.chargeType,
    required this.name,
    this.description,
    this.defaultAmount,
    this.basis = 'fixed',
    this.isServiceCharge = false,
    this.gstApplicable = true,
    this.taxPercent = '0',
    this.elementId,
    this.elementName,
    this.isActive = true,
  });

  String get rateLabel => basisRateLabel(basis, defaultAmount ?? '0');

  factory ChargeHead.fromJson(Map<String, dynamic> j) => ChargeHead(
        id: j['id'] as String,
        chargeType: j['charge_type'] as String,
        name: j['name'] as String,
        description: j['description'] as String?,
        defaultAmount: j['default_amount'] as String?,
        basis: j['basis'] as String? ?? ((j['is_per_sqft'] as bool? ?? false) ? 'per_sqft' : 'fixed'),
        isServiceCharge: j['is_service_charge'] as bool? ?? false,
        gstApplicable: j['gst_applicable'] as bool? ?? true,
        taxPercent: _str(j['tax_percent']),
        elementId: j['element_id'] as String?,
        elementName: j['element_name'] as String?,
        isActive: j['is_active'] as bool? ?? true,
      );
}

/// Society-wide calculation rules (backend MaintenanceSettings).
class MaintenanceRules {
  final String? constructionCostPerSqft;
  final String interestRatePct;
  final int interestGraceDays;
  final String nonOccupancyPct;
  final bool gstEnabled;
  final String gstRatePct;
  final String gstThresholdMonthly;
  // Printed on bills so members know where to pay.
  final String? bankAccountName;
  final String? bankName;
  final String? bankAccountNumber;
  final String? bankIfsc;
  final String? upiId;
  final String? billNotes;

  const MaintenanceRules({
    this.constructionCostPerSqft,
    this.interestRatePct = '12',
    this.interestGraceDays = 0,
    this.nonOccupancyPct = '0',
    this.gstEnabled = false,
    this.gstRatePct = '18',
    this.gstThresholdMonthly = '7500',
    this.bankAccountName,
    this.bankName,
    this.bankAccountNumber,
    this.bankIfsc,
    this.upiId,
    this.billNotes,
  });

  factory MaintenanceRules.fromJson(Map<String, dynamic> j) => MaintenanceRules(
        constructionCostPerSqft: j['construction_cost_per_sqft'] as String?,
        interestRatePct: _str(j['interest_rate_pct']),
        interestGraceDays: j['interest_grace_days'] as int? ?? 0,
        nonOccupancyPct: _str(j['non_occupancy_pct']),
        gstEnabled: j['gst_enabled'] as bool? ?? false,
        gstRatePct: _str(j['gst_rate_pct']),
        gstThresholdMonthly: _str(j['gst_threshold_monthly']),
        bankAccountName: j['bank_account_name'] as String?,
        bankName: j['bank_name'] as String?,
        bankAccountNumber: j['bank_account_number'] as String?,
        bankIfsc: j['bank_ifsc'] as String?,
        upiId: j['upi_id'] as String?,
        billNotes: j['bill_notes'] as String?,
      );
}

class PreviewLine {
  final String description;
  final String amount;
  final String taxAmount;
  final String total;

  const PreviewLine({required this.description, required this.amount,
      required this.taxAmount, required this.total});

  factory PreviewLine.fromJson(Map<String, dynamic> j) => PreviewLine(
        description: j['description'] as String,
        amount: _str(j['amount']),
        taxAmount: _str(j['tax_amount']),
        total: _str(j['total']),
      );
}

class FlatPreview {
  final String flatId;
  final String flatLabel;
  final double? areaSqft;
  final String? occupancy;
  final String previousDues;
  final List<PreviewLine> lines;
  final String tax;
  final String total;

  const FlatPreview({required this.flatId, required this.flatLabel, this.areaSqft,
      this.occupancy, required this.previousDues, required this.lines,
      required this.tax, required this.total});

  factory FlatPreview.fromJson(Map<String, dynamic> j) => FlatPreview(
        flatId: j['flat_id'] as String,
        flatLabel: j['flat_label'] as String,
        areaSqft: (j['area_sqft'] as num?)?.toDouble(),
        occupancy: j['occupancy'] as String?,
        previousDues: _str(j['previous_dues']),
        lines: [for (final e in (j['lines'] as List)) PreviewLine.fromJson(e as Map<String, dynamic>)],
        tax: _str(j['tax']),
        total: _str(j['total']),
      );
}

/// Dry run of bill generation for a cycle — exactly what Generate would create.
class CyclePreview {
  final int months;
  final int flatsCount;
  final String total;
  final List<String> warnings;
  final List<FlatPreview> flats;

  const CyclePreview({required this.months, required this.flatsCount, required this.total,
      required this.warnings, required this.flats});

  factory CyclePreview.fromJson(Map<String, dynamic> j) => CyclePreview(
        months: j['months'] as int? ?? 1,
        flatsCount: j['flats_count'] as int? ?? 0,
        total: _str(j['total']),
        warnings: [for (final w in (j['warnings'] as List? ?? const [])) w as String],
        flats: [for (final e in (j['flats'] as List)) FlatPreview.fromJson(e as Map<String, dynamic>)],
      );
}

class BillingCycle {
  final String id;
  final String name;
  final DateTime cycleStart;
  final DateTime cycleEnd;
  final DateTime dueDate;
  final String frequency;
  final bool isFinalized;
  final String? notes;
  final int billsCount;
  final int generatedCount;
  final int paidCount;
  final int overdueCount;
  final String totalBilled;
  final String totalCollected;
  final String totalOutstanding;

  const BillingCycle({
    required this.id,
    required this.name,
    required this.cycleStart,
    required this.cycleEnd,
    required this.dueDate,
    required this.frequency,
    required this.isFinalized,
    this.notes,
    this.billsCount = 0,
    this.generatedCount = 0,
    this.paidCount = 0,
    this.overdueCount = 0,
    this.totalBilled = '0',
    this.totalCollected = '0',
    this.totalOutstanding = '0',
  });

  /// Bills exist but none have been sent to residents yet.
  bool get awaitingIssue => generatedCount > 0;

  factory BillingCycle.fromJson(Map<String, dynamic> j) => BillingCycle(
        id: j['id'] as String,
        name: j['name'] as String,
        cycleStart: _date(j['cycle_start']),
        cycleEnd: _date(j['cycle_end']),
        dueDate: _date(j['due_date']),
        frequency: j['frequency'] as String? ?? 'monthly',
        isFinalized: j['is_finalized'] as bool? ?? false,
        notes: j['notes'] as String?,
        billsCount: j['bills_count'] as int? ?? 0,
        generatedCount: j['generated_count'] as int? ?? 0,
        paidCount: j['paid_count'] as int? ?? 0,
        overdueCount: j['overdue_count'] as int? ?? 0,
        totalBilled: _str(j['total_billed']),
        totalCollected: _str(j['total_collected']),
        totalOutstanding: _str(j['total_outstanding']),
      );
}

class BillLineItem {
  final String description;
  final String amount;
  final String taxAmount;
  final String total;

  const BillLineItem({required this.description, required this.amount,
      required this.taxAmount, required this.total});

  factory BillLineItem.fromJson(Map<String, dynamic> j) => BillLineItem(
        description: j['description'] as String,
        amount: _str(j['amount']),
        taxAmount: _str(j['tax_amount']),
        total: _str(j['total']),
      );
}

class BillPayment {
  final String receiptNumber;
  final DateTime paymentDate;
  final String amount;
  final String paymentMode;
  final String? transactionRef;

  const BillPayment({required this.receiptNumber, required this.paymentDate,
      required this.amount, required this.paymentMode, this.transactionRef});

  factory BillPayment.fromJson(Map<String, dynamic> j) => BillPayment(
        receiptNumber: j['receipt_number'] as String,
        paymentDate: _date(j['payment_date']),
        amount: _str(j['amount']),
        paymentMode: j['payment_mode'] as String,
        transactionRef: j['transaction_ref'] as String?,
      );
}

class MaintenanceBill {
  final String id;
  final String cycleId;
  final String? cycleName;
  final String flatId;
  final String? flatNumber;
  final String? wingId;
  final String? wingName;
  final String? residentName;
  final String invoiceNumber;
  final String status;
  final bool isOverdue;
  final DateTime billDate;
  final DateTime dueDate;
  final String subtotal;
  final String taxAmount;
  final String penaltyAmount;
  final String totalAmount;
  final String paidAmount;
  final String outstanding;
  final String? cancellationReason;
  final String previousDues;
  final List<BillLineItem> lineItems;
  final List<BillPayment> payments;

  const MaintenanceBill({
    required this.id,
    required this.cycleId,
    this.cycleName,
    required this.flatId,
    this.flatNumber,
    this.wingId,
    this.wingName,
    this.residentName,
    required this.invoiceNumber,
    required this.status,
    this.isOverdue = false,
    required this.billDate,
    required this.dueDate,
    this.subtotal = '0',
    this.taxAmount = '0',
    this.penaltyAmount = '0',
    required this.totalAmount,
    required this.paidAmount,
    required this.outstanding,
    this.cancellationReason,
    this.previousDues = '0',
    this.lineItems = const [],
    this.payments = const [],
  });

  String get flatLabel => [wingName, flatNumber].whereType<String>().join(' / ');
  bool get isGenerated => status == 'generated';
  bool get isPaid => status == 'paid';
  bool get isCancelled => status == 'cancelled';
  bool get canRecordPayment => !isPaid && !isCancelled && amountOf(outstanding) > 0;

  /// Overdue is derived server-side from due date + outstanding, since no
  /// job flips bill_status to `overdue` on its own.
  String get displayStatus => isOverdue ? 'overdue' : status;

  factory MaintenanceBill.fromJson(Map<String, dynamic> j) => MaintenanceBill(
        id: j['id'] as String,
        cycleId: j['cycle_id'] as String,
        cycleName: j['cycle_name'] as String?,
        flatId: j['flat_id'] as String,
        flatNumber: j['flat_number'] as String?,
        wingId: j['wing_id'] as String?,
        wingName: j['wing_name'] as String?,
        residentName: j['resident_name'] as String?,
        invoiceNumber: j['invoice_number'] as String,
        status: j['bill_status'] as String,
        isOverdue: j['is_overdue'] as bool? ?? false,
        billDate: _date(j['bill_date']),
        dueDate: _date(j['due_date']),
        subtotal: _str(j['subtotal']),
        taxAmount: _str(j['tax_amount']),
        penaltyAmount: _str(j['penalty_amount']),
        totalAmount: _str(j['total_amount']),
        paidAmount: _str(j['paid_amount']),
        outstanding: _str(j['outstanding']),
        cancellationReason: j['cancellation_reason'] as String?,
        previousDues: _str(j['previous_dues']),
        lineItems: [
          for (final e in (j['line_items'] as List? ?? const []))
            BillLineItem.fromJson(e as Map<String, dynamic>)
        ],
        payments: [
          for (final e in (j['payments'] as List? ?? const []))
            BillPayment.fromJson(e as Map<String, dynamic>)
        ],
      );
}

class MyBillsSummary {
  final String totalOutstanding;
  final int openCount;
  final int overdueCount;
  final List<MaintenanceBill> bills;

  const MyBillsSummary({required this.totalOutstanding, required this.openCount,
      required this.overdueCount, required this.bills});

  factory MyBillsSummary.fromJson(Map<String, dynamic> j) => MyBillsSummary(
        totalOutstanding: _str(j['total_outstanding']),
        openCount: j['open_count'] as int? ?? 0,
        overdueCount: j['overdue_count'] as int? ?? 0,
        bills: [
          for (final e in (j['bills'] as List? ?? const []))
            MaintenanceBill.fromJson(e as Map<String, dynamic>)
        ],
      );
}

const kChargeTypes = [
  ('maintenance', 'Maintenance'),
  ('water', 'Water'),
  ('parking', 'Parking'),
  ('sinking_fund', 'Sinking Fund'),
  ('repair_fund', 'Repair Fund'),
  ('amenities', 'Amenities'),
  ('special_assessment', 'Special Assessment'),
  ('other', 'Other'),
];

String chargeTypeLabel(String v) =>
    kChargeTypes.firstWhere((c) => c.$1 == v, orElse: () => (v, v)).$2;

String billStatusLabel(String v) => switch (v) {
      'generated' => 'Not Issued',
      'issued' => 'Issued',
      'partially_paid' => 'Part Paid',
      'paid' => 'Paid',
      'overdue' => 'Overdue',
      'cancelled' => 'Cancelled',
      _ => v,
    };

// ── API ──────────────────────────────────────────────────────────────────────

/// FastAPI /billing maintenance-bill endpoints. Errors propagate as
/// DioException; screens surface them via showErrorToast.
/// One charge head's suggested amount from recent vendor bills (backend
/// services/budget_suggestions.py). [suggestedAmount] is in the unit of the
/// head's basis — annual budget, ₹ per flat per month or ₹ per sq ft per
/// month — and is null when no matching bills were found.
class BudgetSuggestion {
  final String chargeId;
  final String chargeName;
  final String basis;
  final String? currentAmount;
  final List<String> vendorCategories;
  final String spent;
  final String annualEstimate;
  final String? suggestedAmount;

  const BudgetSuggestion({
    required this.chargeId,
    required this.chargeName,
    required this.basis,
    this.currentAmount,
    required this.vendorCategories,
    required this.spent,
    required this.annualEstimate,
    this.suggestedAmount,
  });

  factory BudgetSuggestion.fromJson(Map<String, dynamic> j) => BudgetSuggestion(
        chargeId: j['charge_id'] as String,
        chargeName: j['charge_name'] as String,
        basis: j['basis'] as String,
        currentAmount: j['current_amount'] as String?,
        vendorCategories: [for (final c in j['vendor_categories'] as List) c as String],
        spent: _str(j['spent']),
        annualEstimate: _str(j['annual_estimate']),
        suggestedAmount: j['suggested_amount'] as String?,
      );
}

class BudgetSuggestions {
  final DateTime periodStart;
  final DateTime periodEnd;
  final int monthsCovered;
  final List<BudgetSuggestion> suggestions;

  /// Vendor spend (category, amount) that no charge head recovers.
  final List<(String, String)> unlinked;

  const BudgetSuggestions({
    required this.periodStart,
    required this.periodEnd,
    required this.monthsCovered,
    required this.suggestions,
    required this.unlinked,
  });

  factory BudgetSuggestions.fromJson(Map<String, dynamic> j) => BudgetSuggestions(
        periodStart: _date(j['period_start']),
        periodEnd: _date(j['period_end']),
        monthsCovered: j['months_covered'] as int? ?? 0,
        suggestions: [
          for (final s in j['suggestions'] as List) BudgetSuggestion.fromJson(s as Map<String, dynamic>)
        ],
        unlinked: [
          for (final u in j['unlinked'] as List)
            ((u as Map<String, dynamic>)['category'] as String, _str(u['spent']))
        ],
      );
}

/// Human label for a vendor category code ("pest_control" → "Pest control").
String vendorCategoryLabel(String code) => switch (code) {
      'cctv' => 'CCTV',
      'it' => 'IT',
      _ => code.isEmpty ? code : code[0].toUpperCase() + code.substring(1).replaceAll('_', ' '),
    };

class MaintenanceBillingApi {
  final Dio _dio;
  MaintenanceBillingApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  List<T> _list<T>(Object? data, T Function(Map<String, dynamic>) f) =>
      [for (final e in data as List) f(e as Map<String, dynamic>)];

  Future<List<ChargeHead>> listChargeHeads(String societyId) async =>
      _list((await _dio.get('/billing/charges/$societyId')).data, ChargeHead.fromJson);

  Future<ChargeHead> createChargeHead({
    required String societyId,
    String? elementId,
    required String chargeType,
    required String name,
    required String amount,
    required String basis,
    required bool isServiceCharge,
    required bool gstApplicable,
    String taxPercent = '0',
  }) async {
    final r = await _dio.post('/billing/charges', data: {
      'society_id': societyId,
      if (elementId != null) 'element_id': elementId,
      'charge_type': chargeType,
      'name': name,
      'default_amount': amount,
      'basis': basis,
      'is_service_charge': isServiceCharge,
      'gst_applicable': gstApplicable,
      'tax_percent': taxPercent,
    });
    return ChargeHead.fromJson(r.data as Map<String, dynamic>);
  }

  /// Suggested charge-head amounts from the last [months] of vendor bills.
  Future<BudgetSuggestions> budgetSuggestions(String societyId, {int months = 12}) async {
    final r = await _dio.get('/billing/charges/$societyId/budget-suggestions',
        queryParameters: {'months': months});
    return BudgetSuggestions.fromJson(r.data as Map<String, dynamic>);
  }

  Future<ChargeHead> updateChargeHead(String id, Map<String, dynamic> changes) async {
    final r = await _dio.patch('/billing/charges/$id', data: changes);
    return ChargeHead.fromJson(r.data as Map<String, dynamic>);
  }

  Future<List<MaintenanceElement>> listElements(String societyId, {bool includeInactive = false}) async =>
      _list(
        (await _dio.get('/billing/elements/$societyId',
                queryParameters: {'include_inactive': includeInactive}))
            .data,
        MaintenanceElement.fromJson,
      );

  Future<MaintenanceElement> createElement(String societyId, Map<String, dynamic> fields) async {
    final r = await _dio.post('/billing/elements', data: {'society_id': societyId, ...fields});
    return MaintenanceElement.fromJson(r.data as Map<String, dynamic>);
  }

  Future<MaintenanceElement> updateElement(String id, Map<String, dynamic> changes) async {
    final r = await _dio.patch('/billing/elements/$id', data: changes);
    return MaintenanceElement.fromJson(r.data as Map<String, dynamic>);
  }

  /// Bulk-creates charge heads from elements; items are (elementId, amount
  /// or null for the element's default). Elements already in use are skipped.
  Future<List<ChargeHead>> createChargesFromElements(
      String societyId, List<(String, String?)> items) async {
    final r = await _dio.post('/billing/charges/from-elements', data: {
      'society_id': societyId,
      'items': [
        for (final (id, amount) in items) {'element_id': id, if (amount != null) 'amount': amount}
      ],
    });
    return _list(r.data, ChargeHead.fromJson);
  }

  Future<MaintenanceRules> getRules(String societyId) async {
    final r = await _dio.get('/billing/maintenance-settings/$societyId');
    return MaintenanceRules.fromJson(r.data as Map<String, dynamic>);
  }

  Future<MaintenanceRules> updateRules(String societyId, Map<String, dynamic> changes) async {
    final r = await _dio.put('/billing/maintenance-settings/$societyId', data: changes);
    return MaintenanceRules.fromJson(r.data as Map<String, dynamic>);
  }

  Future<CyclePreview> previewCycle(String cycleId) async {
    final r = await _dio.get('/billing/cycles/$cycleId/preview');
    return CyclePreview.fromJson(r.data as Map<String, dynamic>);
  }

  Future<List<BillingCycle>> listCycles(String societyId) async =>
      _list((await _dio.get('/billing/cycles/$societyId')).data, BillingCycle.fromJson);

  Future<BillingCycle> getCycle(String cycleId) async {
    final r = await _dio.get('/billing/cycles/detail/$cycleId');
    return BillingCycle.fromJson(r.data as Map<String, dynamic>);
  }

  Future<BillingCycle> createCycle({
    required String societyId,
    required String name,
    required DateTime start,
    required DateTime end,
    required DateTime dueDate,
    String frequency = 'monthly',
  }) async {
    String d(DateTime v) => v.toIso8601String().split('T').first;
    final r = await _dio.post('/billing/cycles', data: {
      'society_id': societyId,
      'name': name,
      'cycle_start': d(start),
      'cycle_end': d(end),
      'due_date': d(dueDate),
      'frequency': frequency,
    });
    return BillingCycle.fromJson(r.data as Map<String, dynamic>);
  }

  Future<int> generateBills(String cycleId) async {
    final r = await _dio.post('/billing/cycles/$cycleId/generate-bills');
    return (r.data as Map<String, dynamic>)['bills_generated'] as int;
  }

  Future<int> issueAll(String cycleId) async {
    final r = await _dio.post('/billing/cycles/$cycleId/issue-all');
    return (r.data as Map<String, dynamic>)['bills_issued'] as int;
  }

  Future<List<MaintenanceBill>> cycleBills(String cycleId) async =>
      _list((await _dio.get('/billing/cycles/$cycleId/bills')).data, MaintenanceBill.fromJson);

  Future<MaintenanceBill> getBill(String billId) async {
    final r = await _dio.get('/billing/bills/$billId');
    return MaintenanceBill.fromJson(r.data as Map<String, dynamic>);
  }

  Future<MaintenanceBill> issueBill(String billId) async {
    final r = await _dio.post('/billing/bills/$billId/issue');
    return MaintenanceBill.fromJson(r.data as Map<String, dynamic>);
  }

  Future<MaintenanceBill> cancelBill(String billId, String reason) async {
    final r = await _dio.post('/billing/bills/$billId/cancel', data: {'reason': reason});
    return MaintenanceBill.fromJson(r.data as Map<String, dynamic>);
  }

  Future<Uint8List> billPdf(String billId) async {
    final r = await _dio.get<List<int>>(
      '/billing/bills/$billId/pdf',
      options: Options(responseType: ResponseType.bytes),
    );
    return Uint8List.fromList(r.data!);
  }

  /// A payment's receipt — its own document, for payments on a bill or on
  /// account (receipts are never printed on the bill).
  Future<Uint8List> receiptPdf(String receiptNumber) async {
    final r = await _dio.get<List<int>>(
      '/billing/receipts/${Uri.encodeComponent(receiptNumber)}/pdf',
      options: Options(responseType: ResponseType.bytes),
    );
    return Uint8List.fromList(r.data!);
  }

  Future<MyBillsSummary> myBills() async {
    final r = await _dio.get('/billing/bills/me');
    return MyBillsSummary.fromJson(r.data as Map<String, dynamic>);
  }
}
