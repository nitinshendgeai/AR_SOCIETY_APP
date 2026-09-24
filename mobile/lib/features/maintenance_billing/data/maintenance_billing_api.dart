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

/// A society charge head (backend MaintenanceChargeConfig) — copied onto
/// every bill as a line item at generation time.
class ChargeHead {
  final String id;
  final String chargeType;
  final String name;
  final String? description;
  final String? defaultAmount;
  final bool isPerSqft;
  final String taxPercent;
  final bool isActive;

  const ChargeHead({
    required this.id,
    required this.chargeType,
    required this.name,
    this.description,
    this.defaultAmount,
    this.isPerSqft = false,
    this.taxPercent = '0',
    this.isActive = true,
  });

  factory ChargeHead.fromJson(Map<String, dynamic> j) => ChargeHead(
        id: j['id'] as String,
        chargeType: j['charge_type'] as String,
        name: j['name'] as String,
        description: j['description'] as String?,
        defaultAmount: j['default_amount'] as String?,
        isPerSqft: j['is_per_sqft'] as bool? ?? false,
        taxPercent: _str(j['tax_percent']),
        isActive: j['is_active'] as bool? ?? true,
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
class MaintenanceBillingApi {
  final Dio _dio;
  MaintenanceBillingApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  List<T> _list<T>(Object? data, T Function(Map<String, dynamic>) f) =>
      [for (final e in data as List) f(e as Map<String, dynamic>)];

  Future<List<ChargeHead>> listChargeHeads(String societyId) async =>
      _list((await _dio.get('/billing/charges/$societyId')).data, ChargeHead.fromJson);

  Future<ChargeHead> createChargeHead({
    required String societyId,
    required String chargeType,
    required String name,
    required String amount,
    required String taxPercent,
    bool isPerSqft = false,
  }) async {
    final r = await _dio.post('/billing/charges', data: {
      'society_id': societyId,
      'charge_type': chargeType,
      'name': name,
      'default_amount': amount,
      'tax_percent': taxPercent,
      'is_per_sqft': isPerSqft,
    });
    return ChargeHead.fromJson(r.data as Map<String, dynamic>);
  }

  Future<ChargeHead> updateChargeHead(String id, Map<String, dynamic> changes) async {
    final r = await _dio.patch('/billing/charges/$id', data: changes);
    return ChargeHead.fromJson(r.data as Map<String, dynamic>);
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

  Future<MyBillsSummary> myBills() async {
    final r = await _dio.get('/billing/bills/me');
    return MyBillsSummary.fromJson(r.data as Map<String, dynamic>);
  }
}
