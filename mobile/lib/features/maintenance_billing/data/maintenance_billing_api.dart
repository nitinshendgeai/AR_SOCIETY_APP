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
      'parking' => 'Charged per active parking allotment (car rate). A slot\'s own monthly charge overrides this rate.',
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

  /// Billed at what the expense ledgers linked to its element cost over the
  /// last [expenseMonths] months, rather than the typed amount.
  final bool autoFromExpenses;
  final int expenseMonths;

  /// How "budget from expenses" reads the books: `trailing` (the last
  /// [expenseMonths] months, scaled to a year) or `period` (the approved
  /// expenses dated inside each billing cycle, shared out exactly).
  final String expenseMode;

  /// Parking head only: rate for a motorcycle/scooter/cycle slot. Empty
  /// means two-wheelers pay the same as a car.
  final String? twoWheelerRate;
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
    this.autoFromExpenses = false,
    this.expenseMonths = 12,
    this.expenseMode = 'trailing',
    this.twoWheelerRate,
    this.isActive = true,
  });

  bool get isPeriodExpense => autoFromExpenses && expenseMode == 'period';

  String get rateLabel {
    final base = basisRateLabel(basis, defaultAmount ?? '0');
    if (basis != 'parking' || twoWheelerRate == null) return base;
    return '$base (2-wheeler ${formatRupees(twoWheelerRate!)})';
  }

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
        autoFromExpenses: j['auto_from_expenses'] as bool? ?? false,
        expenseMonths: j['expense_months'] as int? ?? 12,
        expenseMode: j['expense_mode'] as String? ?? 'trailing',
        twoWheelerRate: j['two_wheeler_rate'] as String?,
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

  /// How the bill prints: 'standard' (the heads grouped into a fixed list) or 'classic' (every head on its own line, a
  /// receipt slip for the previous bill at the foot).
  final String billLayout;

  /// "Billing in this app starts on": when set, each flat is billed from its possession date (never before this
  /// date) or from the end of its last bill, to the end of the cycle.
  final DateTime? billingStartDate;

  /// A payment entered by an admin / committee member is posted as approved at once (no second approver).
  final bool autoApproveAdminExpenses;

  /// Each bill is rounded to the nearest whole rupee; the difference is shown on the bill as "Round off".
  final bool roundToRupee;

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
    this.billLayout = 'standard',
    this.billingStartDate,
    this.autoApproveAdminExpenses = false,
    this.roundToRupee = false,
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
        billLayout: j['bill_layout'] as String? ?? 'standard',
        billingStartDate:
            j['billing_start_date'] == null ? null : DateTime.parse(j['billing_start_date'] as String),
        autoApproveAdminExpenses: j['auto_approve_admin_expenses'] as bool? ?? false,
        roundToRupee: j['round_to_rupee'] as bool? ?? false,
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
  /// The rounding to a whole rupee inside [total] ('0' when the society does not round).
  final String roundOff;
  /// The days this flat's bill charges for, and how many months that is (more than the cycle's own for a flat
  /// billed from its possession date or last bill; part of it for one that took possession during the cycle).
  final DateTime? periodStart;
  final DateTime? periodEnd;
  final String? months;

  const FlatPreview({required this.flatId, required this.flatLabel, this.areaSqft,
      this.occupancy, required this.previousDues, required this.lines,
      required this.tax, required this.total, this.roundOff = '0', this.periodStart, this.periodEnd, this.months});

  factory FlatPreview.fromJson(Map<String, dynamic> j) => FlatPreview(
        flatId: j['flat_id'] as String,
        flatLabel: j['flat_label'] as String,
        areaSqft: (j['area_sqft'] as num?)?.toDouble(),
        occupancy: j['occupancy'] as String?,
        previousDues: _str(j['previous_dues']),
        lines: [for (final e in (j['lines'] as List)) PreviewLine.fromJson(e as Map<String, dynamic>)],
        tax: _str(j['tax']),
        total: _str(j['total']),
        roundOff: _str(j['round_off'] ?? '0'),
        periodStart: j['period_start'] == null ? null : DateTime.parse(j['period_start'] as String),
        periodEnd: j['period_end'] == null ? null : DateTime.parse(j['period_end'] as String),
        months: j['months'] as String?,
      );
}

/// Dry run of bill generation for a cycle — exactly what Generate would create.
/// One voucher in the pool of a head that bills a period's actual expenses.
class ExpenseSource {
  final String voucherNumber;
  final DateTime voucherDate;
  final String ledgerName;
  final String amount;

  const ExpenseSource({required this.voucherNumber, required this.voucherDate,
      required this.ledgerName, required this.amount});

  factory ExpenseSource.fromJson(Map<String, dynamic> j) => ExpenseSource(
        voucherNumber: j['voucher_number'] as String? ?? '',
        voucherDate: _date(j['voucher_date']),
        ledgerName: j['ledger_name'] as String? ?? '',
        amount: _str(j['amount']),
      );
}

/// The working of a charge head that bills the cycle's actual expenses: what
/// was spent, how it is shared and the rate.
class ExpenseAllocation {
  final String chargeName;
  final String? elementName;
  final String method; // area | equal
  final DateTime periodStart;
  final DateTime periodEnd;
  final String poolAmount;
  final String allocatedAmount;
  final int eligibleFlats;
  final String rate;
  final String pendingAmount;
  final List<ExpenseSource> sources;

  const ExpenseAllocation({
    required this.chargeName,
    this.elementName,
    required this.method,
    required this.periodStart,
    required this.periodEnd,
    required this.poolAmount,
    required this.allocatedAmount,
    required this.eligibleFlats,
    required this.rate,
    this.pendingAmount = '0',
    this.sources = const [],
  });

  bool get byArea => method == 'area';

  /// The shares add up to the expenses to the paisa.
  bool get reconciled => poolAmount == allocatedAmount;

  factory ExpenseAllocation.fromJson(Map<String, dynamic> j) => ExpenseAllocation(
        chargeName: j['charge_name'] as String? ?? '',
        elementName: j['element_name'] as String?,
        method: j['method'] as String? ?? 'equal',
        periodStart: _date(j['period_start']),
        periodEnd: _date(j['period_end']),
        poolAmount: _str(j['pool_amount']),
        allocatedAmount: _str(j['allocated_amount']),
        eligibleFlats: j['eligible_flats'] as int? ?? 0,
        rate: _str(j['rate']),
        pendingAmount: _str(j['pending_amount']),
        sources: [for (final e in (j['sources'] as List? ?? const [])) ExpenseSource.fromJson(e as Map<String, dynamic>)],
      );
}

/// A ledger holding approved spend in the cycle that no maintenance element covers.
class UnlinkedLedger {
  final String accountId;
  final String name;
  final String amount;
  const UnlinkedLedger({required this.accountId, required this.name, required this.amount});
  factory UnlinkedLedger.fromJson(Map<String, dynamic> j) => UnlinkedLedger(
        accountId: j['account_id'] as String,
        name: j['name'] as String? ?? '',
        amount: _str(j['amount']),
      );
}

/// An element with approved spend in the cycle that no head bills as actual expenses.
class UncoveredElement {
  final String elementId;
  final String elementName;
  final String amount;

  /// A charge head exists for the element (billing a typed rate or an estimate) – false means none does.
  final bool hasHead;
  const UncoveredElement(
      {required this.elementId, required this.elementName, required this.amount, this.hasHead = false});
  factory UncoveredElement.fromJson(Map<String, dynamic> j) => UncoveredElement(
        elementId: j['element_id'] as String,
        elementName: j['element_name'] as String? ?? '',
        amount: _str(j['amount']),
        hasHead: j['has_head'] as bool? ?? false,
      );
}

/// The month-end checklist for a cycle: what in the books would leave the bills short of what was spent.
class CycleReadiness {
  final bool applies;
  final bool ready;
  final int pendingCount;
  final String pendingAmount;
  final List<UnlinkedLedger> unlinkedLedgers;
  final List<UncoveredElement> uncoveredElements;
  final List<String> headsWithoutSpend;

  const CycleReadiness({
    this.applies = false,
    this.ready = true,
    this.pendingCount = 0,
    this.pendingAmount = '0',
    this.unlinkedLedgers = const [],
    this.uncoveredElements = const [],
    this.headsWithoutSpend = const [],
  });

  factory CycleReadiness.fromJson(Map<String, dynamic> j) => CycleReadiness(
        applies: j['applies'] as bool? ?? false,
        ready: j['ready'] as bool? ?? true,
        pendingCount: j['pending_count'] as int? ?? 0,
        pendingAmount: _str(j['pending_amount']),
        unlinkedLedgers: [
          for (final e in (j['unlinked_ledgers'] as List? ?? const [])) UnlinkedLedger.fromJson(e as Map<String, dynamic>)
        ],
        uncoveredElements: [
          for (final e in (j['uncovered_elements'] as List? ?? const []))
            UncoveredElement.fromJson(e as Map<String, dynamic>)
        ],
        headsWithoutSpend: [for (final e in (j['heads_without_spend'] as List? ?? const [])) e as String],
      );
}

/// What changed when charge heads were switched to actual expenses in one step.
class BillActualResult {
  final List<ChargeHead> changed;
  final List<({String name, String reason})> skipped;
  const BillActualResult({required this.changed, required this.skipped});
  factory BillActualResult.fromJson(Map<String, dynamic> j) => BillActualResult(
        changed: [for (final e in (j['changed'] as List? ?? const [])) ChargeHead.fromJson(e as Map<String, dynamic>)],
        skipped: [
          for (final e in (j['skipped'] as List? ?? const []))
            (name: (e as Map)['name'] as String? ?? '', reason: e['reason'] as String? ?? '')
        ],
      );
}

class CyclePreview {
  final int months;
  final int flatsCount;
  final String total;
  final List<String> warnings;
  final List<ExpenseAllocation> expenseAllocations;
  final CycleReadiness readiness;
  final DateTime? cycleStart;
  final DateTime? cycleEnd;
  final List<FlatPreview> flats;

  const CyclePreview({required this.months, required this.flatsCount, required this.total,
      required this.warnings, this.expenseAllocations = const [], this.readiness = const CycleReadiness(),
      this.cycleStart, this.cycleEnd, required this.flats});

  factory CyclePreview.fromJson(Map<String, dynamic> j) => CyclePreview(
        months: j['months'] as int? ?? 1,
        flatsCount: j['flats_count'] as int? ?? 0,
        total: _str(j['total']),
        warnings: [for (final w in (j['warnings'] as List? ?? const [])) w as String],
        expenseAllocations: [
          for (final e in (j['expense_allocations'] as List? ?? const []))
            ExpenseAllocation.fromJson(e as Map<String, dynamic>)
        ],
        cycleStart: j['cycle_start'] == null ? null : _date(j['cycle_start']),
        cycleEnd: j['cycle_end'] == null ? null : _date(j['cycle_end']),
        readiness: j['readiness'] == null
            ? const CycleReadiness()
            : CycleReadiness.fromJson(j['readiness'] as Map<String, dynamic>),
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
  final bool canRegenerate;
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
    this.canRegenerate = false,
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

  /// No bill is issued or paid (cancelled ones do not count), so the bills can be thrown away and made again. The
  /// server decides; see `can_regenerate`.

  factory BillingCycle.fromJson(Map<String, dynamic> j) => BillingCycle(
        id: j['id'] as String,
        name: j['name'] as String,
        cycleStart: _date(j['cycle_start']),
        cycleEnd: _date(j['cycle_end']),
        dueDate: _date(j['due_date']),
        frequency: j['frequency'] as String? ?? 'monthly',
        isFinalized: j['is_finalized'] as bool? ?? false,
        canRegenerate: j['can_regenerate'] as bool? ?? false,
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
  /// The rounding to a whole rupee inside [totalAmount] (negative: rounded down).
  final String roundOff;
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
    this.roundOff = '0',
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
        roundOff: _str(j['round_off'] ?? '0'),
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

// ── Fines and additional charges on a flat ───────────────────────────────────

/// A fine or additional charge on one flat; it goes on the flat's next
/// maintenance bill (every bill, when recurring).
class FlatCharge {
  final String id;
  final String flatId;
  final String flatNumber;
  final String? wingName;
  final String kind; // fine | extra
  final String title;
  final String? reason;
  final String amount;
  final bool gstApplicable;
  final DateTime effectiveDate;
  final bool recurring;
  final DateTime? endDate;
  final String status; // active | billed | cancelled
  final String? invoiceNumber;
  final String? cancelReason;

  const FlatCharge({
    required this.id,
    required this.flatId,
    required this.flatNumber,
    this.wingName,
    required this.kind,
    required this.title,
    this.reason,
    required this.amount,
    this.gstApplicable = false,
    required this.effectiveDate,
    this.recurring = false,
    this.endDate,
    required this.status,
    this.invoiceNumber,
    this.cancelReason,
  });

  bool get isFine => kind == 'fine';
  bool get canCancel => status == 'active';
  String get flatLabel => wingName == null || wingName!.isEmpty ? flatNumber : '$wingName / $flatNumber';

  String get statusLabel => switch (status) {
        'billed' => invoiceNumber == null ? 'On a bill' : 'On bill $invoiceNumber',
        'cancelled' => 'Cancelled',
        _ => recurring ? 'Every bill' : 'Waiting for next bill',
      };

  factory FlatCharge.fromJson(Map<String, dynamic> j) => FlatCharge(
        id: j['id'] as String,
        flatId: j['flat_id'] as String,
        flatNumber: j['flat_number'] as String? ?? '',
        wingName: j['wing_name'] as String?,
        kind: j['kind'] as String,
        title: j['title'] as String,
        reason: j['reason'] as String?,
        amount: _str(j['amount']),
        gstApplicable: j['gst_applicable'] as bool? ?? false,
        effectiveDate: _date(j['effective_date']),
        recurring: j['recurring'] as bool? ?? false,
        endDate: j['end_date'] == null ? null : _date(j['end_date']),
        status: j['status'] as String,
        invoiceNumber: j['invoice_number'] as String?,
        cancelReason: j['cancel_reason'] as String?,
      );
}

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
  final List<String> expenseHeads;
  final String spent;
  final String annualEstimate;
  final String? suggestedAmount;
  final bool autoFromExpenses;

  const BudgetSuggestion({
    required this.chargeId,
    required this.chargeName,
    required this.basis,
    this.currentAmount,
    required this.expenseHeads,
    required this.spent,
    required this.annualEstimate,
    this.suggestedAmount,
    this.autoFromExpenses = false,
  });

  factory BudgetSuggestion.fromJson(Map<String, dynamic> j) => BudgetSuggestion(
        chargeId: j['charge_id'] as String,
        chargeName: j['charge_name'] as String,
        basis: j['basis'] as String,
        currentAmount: j['current_amount'] as String?,
        expenseHeads: [for (final c in j['expense_heads'] as List) c as String],
        spent: _str(j['spent']),
        annualEstimate: _str(j['annual_estimate']),
        suggestedAmount: j['suggested_amount'] as String?,
        autoFromExpenses: j['auto_from_expenses'] as bool? ?? false,
      );
}

class BudgetSuggestions {
  final DateTime periodStart;
  final DateTime periodEnd;
  final int monthsCovered;
  final List<BudgetSuggestion> suggestions;

  /// Expense ledgers (name, amount spent) that count towards no maintenance element.
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
            ((u as Map<String, dynamic>)['name'] as String, _str(u['spent']))
        ],
      );
}

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
    bool autoFromExpenses = false,
    int expenseMonths = 12,
    String expenseMode = 'trailing',
    String? twoWheelerRate,
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
      'auto_from_expenses': autoFromExpenses,
      'expense_months': expenseMonths,
      'expense_mode': expenseMode,
      if (twoWheelerRate != null) 'two_wheeler_rate': twoWheelerRate,
    });
    return ChargeHead.fromJson(r.data as Map<String, dynamic>);
  }

  /// Suggested charge-head amounts from what the last [months] cost on the
  /// expense ledgers linked to each element.
  Future<BudgetSuggestions> budgetSuggestions(String societyId, {int months = 12}) async {
    final r = await _dio.get('/billing/charges/$societyId/budget-suggestions',
        queryParameters: {'months': months});
    return BudgetSuggestions.fromJson(r.data as Map<String, dynamic>);
  }

  /// Put the chosen heads on "actual expenses of each billing cycle"; the ones that cannot say why.
  /// [elementIds] are elements with spend but no head: one is made for each (or its head switched).
  Future<BillActualResult> billActualExpenses(String societyId, List<String> chargeIds,
      {List<String> elementIds = const []}) async {
    final r = await _dio.post('/billing/charges/$societyId/bill-actual-expenses',
        data: {'charge_ids': chargeIds, 'element_ids': elementIds});
    return BillActualResult.fromJson(r.data as Map<String, dynamic>);
  }

  /// Approve every payment waiting for approval (the caller's own wait for another approver when there is one).
  /// Returns (approved, left for another approver).
  Future<({int approved, int leftForAnother})> approvePendingPayments(String societyId,
      {DateTime? from, DateTime? to}) async {
    String d(DateTime x) => '${x.year.toString().padLeft(4, '0')}-${x.month.toString().padLeft(2, '0')}-${x.day.toString().padLeft(2, '0')}';
    final r = await _dio.post('/accounts/vouchers/$societyId/approve-pending',
        data: {if (from != null) 'date_from': d(from), if (to != null) 'date_to': d(to)});
    final m = r.data as Map<String, dynamic>;
    return (approved: m['approved'] as int? ?? 0, leftForAnother: m['left_for_another_approver'] as int? ?? 0);
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

  /// Deletes the cycle's bills and makes them again from today's charges and rules; the server refuses once any bill
  /// is issued or paid. Returns how many bills were made.
  Future<int> regenerateBills(String cycleId) async {
    final r = await _dio.post('/billing/cycles/$cycleId/regenerate-bills');
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

  /// Every bill of a cycle in one PDF, flat by flat (cancelled bills left out).
  /// [withReceipts] false leaves out the receipts towards each flat's previous bill.
  Future<Uint8List> cycleBillsPdf(String cycleId, {bool withReceipts = true}) async {
    final r = await _dio.get<List<int>>(
      '/billing/cycles/$cycleId/bills.pdf',
      queryParameters: {if (!withReceipts) 'with_receipts': false},
      options: Options(responseType: ResponseType.bytes),
    );
    return Uint8List.fromList(r.data!);
  }

  Future<Uint8List> billPdf(String billId, {bool withReceipts = true}) async {
    final r = await _dio.get<List<int>>(
      '/billing/bills/$billId/pdf',
      queryParameters: {if (!withReceipts) 'with_receipts': false},
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

  Future<MyBillsSummary> myBills({String? flatId}) async {
    final r = await _dio.get('/billing/bills/me', queryParameters: {if (flatId != null) 'flat_id': flatId});
    return MyBillsSummary.fromJson(r.data as Map<String, dynamic>);
  }

  Future<List<FlatCharge>> listFlatCharges(String societyId, {String? status}) async => _list(
        (await _dio.get('/billing/flat-charges/society/$societyId',
                queryParameters: {if (status != null) 'status': status, 'limit': 500}))
            .data,
        FlatCharge.fromJson,
      );

  Future<List<FlatCharge>> flatChargesOfFlat(String flatId) async =>
      _list((await _dio.get('/billing/flat-charges/flat/$flatId')).data, FlatCharge.fromJson);

  Future<FlatCharge> createFlatCharge({
    required String societyId,
    required String flatId,
    required String kind,
    required String title,
    String? reason,
    required String amount,
    bool gstApplicable = false,
    required DateTime effectiveDate,
    bool recurring = false,
    DateTime? endDate,
  }) async {
    final r = await _dio.post('/billing/flat-charges', data: {
      'society_id': societyId,
      'flat_id': flatId,
      'kind': kind,
      'title': title,
      if (reason != null && reason.isNotEmpty) 'reason': reason,
      'amount': amount,
      'gst_applicable': gstApplicable,
      'effective_date': DateFormat('yyyy-MM-dd').format(effectiveDate),
      'recurring': recurring,
      if (recurring && endDate != null) 'end_date': DateFormat('yyyy-MM-dd').format(endDate),
    });
    return FlatCharge.fromJson(r.data as Map<String, dynamic>);
  }

  Future<FlatCharge> cancelFlatCharge(String id, String reason) async {
    final r = await _dio.post('/billing/flat-charges/$id/cancel', data: {'reason': reason});
    return FlatCharge.fromJson(r.data as Map<String, dynamic>);
  }

  Future<List<InterestWaiver>> listInterestWaivers(String societyId, {String status = 'active'}) async => _list(
        (await _dio.get('/billing/interest-waivers/society/$societyId', queryParameters: {'status': status})).data,
        InterestWaiver.fromJson,
      );

  Future<InterestWaiver> createInterestWaiver({
    required String societyId,
    required String flatId,
    required String mode,
    String? ratePct,
    required DateTime from,
    DateTime? to,
    required String reason,
  }) async {
    final fmt = DateFormat('yyyy-MM-dd');
    final r = await _dio.post('/billing/interest-waivers', data: {
      'society_id': societyId,
      'flat_id': flatId,
      'mode': mode,
      if (mode == 'rate' && ratePct != null) 'rate_pct': ratePct,
      'from_date': fmt.format(from),
      if (to != null) 'to_date': fmt.format(to),
      'reason': reason,
    });
    return InterestWaiver.fromJson(r.data as Map<String, dynamic>);
  }

  Future<InterestWaiver> cancelInterestWaiver(String id, String reason) async {
    final r = await _dio.post('/billing/interest-waivers/$id/cancel', data: {'reason': reason});
    return InterestWaiver.fromJson(r.data as Map<String, dynamic>);
  }
}

/// A concession on the interest charged on one flat's arrears: none at all
/// (`waive`) or a lower rate (`rate`), for the days from [from] to [to].
class InterestWaiver {
  final String id;
  final String flatId;
  final String flatNumber;
  final String? wingName;
  final String mode; // waive | rate
  final String? ratePct;
  final DateTime from;
  final DateTime? to;
  final String reason;
  final String status; // active | cancelled

  const InterestWaiver({
    required this.id,
    required this.flatId,
    required this.flatNumber,
    this.wingName,
    required this.mode,
    this.ratePct,
    required this.from,
    this.to,
    required this.reason,
    this.status = 'active',
  });

  String get flatLabel => wingName == null || wingName!.isEmpty ? flatNumber : '$wingName / $flatNumber';

  String get title => mode == 'waive' ? 'No interest' : 'Interest at ${_trimRate(ratePct ?? '0')}% a year';

  static String _trimRate(String v) {
    final n = double.tryParse(v);
    return n == null ? v : (n == n.roundToDouble() ? n.toStringAsFixed(0) : n.toString());
  }

  factory InterestWaiver.fromJson(Map<String, dynamic> j) => InterestWaiver(
        id: j['id'] as String,
        flatId: j['flat_id'] as String,
        flatNumber: j['flat_number'] as String? ?? '',
        wingName: j['wing_name'] as String?,
        mode: j['mode'] as String? ?? 'waive',
        ratePct: j['rate_pct'] as String?,
        from: DateTime.parse(j['from_date'] as String),
        to: j['to_date'] == null ? null : DateTime.parse(j['to_date'] as String),
        reason: j['reason'] as String? ?? '',
        status: j['status'] as String? ?? 'active',
      );
}
