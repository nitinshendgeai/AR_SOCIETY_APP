import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show DrCr, apiDate;

double _n(Object? v) => double.tryParse(v?.toString() ?? '') ?? 0;
DateTime _d(Object? v) => DateTime.parse(v as String);

/// A signed balance (positive: debit) as "1,234.00 Dr" / "Cr".
DrCr drCrOf(double signed) => DrCr(signed.abs(), signed < 0 ? 'Cr' : 'Dr');

// ── Cash and bank book ───────────────────────────────────────────────────────

class BookLine {
  final String voucherId;
  final DateTime date;
  final String voucherNumber;
  final String voucherType;
  final String particulars;
  final String? narration;
  final String? reference;
  final double receipt;
  final double payment;
  final double balance;
  final String? enteredBy;
  final String? approvedBy;
  final bool isAuto;

  const BookLine({
    required this.voucherId,
    required this.date,
    required this.voucherNumber,
    required this.voucherType,
    required this.particulars,
    this.narration,
    this.reference,
    required this.receipt,
    required this.payment,
    required this.balance,
    this.enteredBy,
    this.approvedBy,
    required this.isAuto,
  });

  factory BookLine.fromJson(Map<String, dynamic> j) => BookLine(
        voucherId: j['voucher_id'] as String,
        date: _d(j['date']),
        voucherNumber: j['voucher_number'] as String,
        voucherType: j['voucher_type'] as String,
        particulars: j['particulars'] as String? ?? '',
        narration: j['narration'] as String?,
        reference: j['reference'] as String?,
        receipt: _n(j['receipt']),
        payment: _n(j['payment']),
        balance: _n(j['balance']),
        enteredBy: j['entered_by'] as String?,
        approvedBy: j['approved_by'] as String?,
        isAuto: j['is_auto'] as bool? ?? false,
      );

  /// Who approved it; for what the app posted itself, that it posted it.
  String get approvedLabel => approvedBy ?? (isAuto ? 'Auto-posted' : '—');
}

class BookSection {
  final String accountId;
  final String accountName;
  final bool isCash;
  final String? bankName;
  final String? bankAccountNumber;
  final double opening;
  final double receipts;
  final double payments;
  final double closing;
  final List<BookLine> lines;

  const BookSection({
    required this.accountId,
    required this.accountName,
    required this.isCash,
    this.bankName,
    this.bankAccountNumber,
    required this.opening,
    required this.receipts,
    required this.payments,
    required this.closing,
    required this.lines,
  });

  factory BookSection.fromJson(Map<String, dynamic> j) => BookSection(
        accountId: j['account_id'] as String,
        accountName: j['account_name'] as String,
        isCash: j['kind'] == 'cash',
        bankName: j['bank_name'] as String?,
        bankAccountNumber: j['bank_account_number'] as String?,
        opening: _n(j['opening']),
        receipts: _n(j['receipts']),
        payments: _n(j['payments']),
        closing: _n(j['closing']),
        lines: (j['lines'] as List? ?? const []).map((e) => BookLine.fromJson(e as Map<String, dynamic>)).toList(),
      );
}

class CashBankBook {
  final List<BookSection> sections;
  final double opening;
  final double receipts;
  final double payments;
  final double closing;

  const CashBankBook(
      {required this.sections, required this.opening, required this.receipts, required this.payments, required this.closing});

  factory CashBankBook.fromJson(Map<String, dynamic> j) {
    final t = j['totals'] as Map<String, dynamic>;
    return CashBankBook(
      sections: (j['sections'] as List? ?? const []).map((e) => BookSection.fromJson(e as Map<String, dynamic>)).toList(),
      opening: _n(t['opening']),
      receipts: _n(t['receipts']),
      payments: _n(t['payments']),
      closing: _n(t['closing']),
    );
  }
}

// ── Invoice register ─────────────────────────────────────────────────────────

class InvoiceRow {
  final String billId;
  final String invoiceNumber;
  final DateTime billDate;
  final DateTime dueDate;
  final String flat;
  final String member;
  final String? cycle;
  final double subtotal;
  final double tax;
  final double penalty;
  final double discount;
  final double total;
  final double paid;
  final double outstanding;
  final String status;
  final bool isCancelled;
  final String? enteredBy;

  const InvoiceRow({
    required this.billId,
    required this.invoiceNumber,
    required this.billDate,
    required this.dueDate,
    required this.flat,
    required this.member,
    this.cycle,
    required this.subtotal,
    required this.tax,
    required this.penalty,
    required this.discount,
    required this.total,
    required this.paid,
    required this.outstanding,
    required this.status,
    required this.isCancelled,
    this.enteredBy,
  });

  factory InvoiceRow.fromJson(Map<String, dynamic> j) => InvoiceRow(
        billId: j['bill_id'] as String,
        invoiceNumber: j['invoice_number'] as String,
        billDate: _d(j['bill_date']),
        dueDate: _d(j['due_date']),
        flat: j['flat'] as String? ?? '',
        member: j['member'] as String? ?? '',
        cycle: j['cycle'] as String?,
        subtotal: _n(j['subtotal']),
        tax: _n(j['tax']),
        penalty: _n(j['penalty']),
        discount: _n(j['discount']),
        total: _n(j['total']),
        paid: _n(j['paid']),
        outstanding: _n(j['outstanding']),
        status: j['status'] as String? ?? '',
        isCancelled: j['is_cancelled'] as bool? ?? false,
        enteredBy: j['entered_by'] as String?,
      );
}

// ── Bills register ───────────────────────────────────────────────────────────

class BillRow {
  final String invoiceId;
  final String invoiceNumber;
  final DateTime invoiceDate;
  final DateTime? dueDate;
  final String? vendor;
  final String? description;
  final String? expenseHead;
  final double amount;
  final double gst;
  final double tds;
  final double total;
  final double paid;
  final double outstanding;
  final String status; // unpaid | part_paid | paid
  final String? enteredBy;

  const BillRow({
    required this.invoiceId,
    required this.invoiceNumber,
    required this.invoiceDate,
    this.dueDate,
    this.vendor,
    this.description,
    this.expenseHead,
    required this.amount,
    required this.gst,
    required this.tds,
    required this.total,
    required this.paid,
    required this.outstanding,
    required this.status,
    this.enteredBy,
  });

  factory BillRow.fromJson(Map<String, dynamic> j) => BillRow(
        invoiceId: j['invoice_id'] as String,
        invoiceNumber: j['invoice_number'] as String,
        invoiceDate: _d(j['invoice_date']),
        dueDate: j['due_date'] == null ? null : _d(j['due_date']),
        vendor: j['vendor'] as String?,
        description: j['description'] as String?,
        expenseHead: j['expense_head'] as String?,
        amount: _n(j['amount']),
        gst: _n(j['gst']),
        tds: _n(j['tds']),
        total: _n(j['total']),
        paid: _n(j['paid']),
        outstanding: _n(j['outstanding']),
        status: j['status'] as String? ?? '',
        enteredBy: j['entered_by'] as String?,
      );
}

/// A register of invoices or bills with its totals.
class Register<T> {
  final List<T> rows;
  final int count;
  final double total;
  final double paid;
  final double outstanding;
  const Register({required this.rows, required this.count, required this.total, required this.paid, required this.outstanding});

  static Register<T> fromJson<T>(Map<String, dynamic> j, T Function(Map<String, dynamic>) row) {
    final t = j['totals'] as Map<String, dynamic>;
    return Register<T>(
      rows: (j['rows'] as List? ?? const []).map((e) => row(e as Map<String, dynamic>)).toList(),
      count: (t['count'] as num?)?.toInt() ?? 0,
      total: _n(t['total']),
      paid: _n(t['paid']),
      outstanding: _n(t['outstanding']),
    );
  }
}

class RegistersApi {
  final Dio _dio;
  RegistersApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Map<String, dynamic> _q(DateTime? from, DateTime? to, [Map<String, dynamic>? more]) => {
        if (from != null) 'date_from': apiDate(from),
        if (to != null) 'date_to': apiDate(to),
        ...?more,
      };

  Future<CashBankBook> cashBankBook(String societyId, {DateTime? from, DateTime? to, String? accountId}) async =>
      CashBankBook.fromJson((await _dio.get('/accounts/registers/cash-bank/$societyId',
              queryParameters: _q(from, to, {if (accountId != null) 'account_id': accountId})))
          .data as Map<String, dynamic>);

  Future<Register<InvoiceRow>> invoices(String societyId,
          {DateTime? from, DateTime? to, String? status, String? search}) async =>
      Register.fromJson((await _dio.get('/accounts/registers/invoices/$societyId',
              queryParameters: _q(from, to, {
                if (status != null) 'status': status,
                if (search != null && search.isNotEmpty) 'q': search,
              })))
          .data as Map<String, dynamic>, InvoiceRow.fromJson);

  Future<Register<BillRow>> bills(String societyId,
          {DateTime? from, DateTime? to, String? status, String? search}) async =>
      Register.fromJson((await _dio.get('/accounts/registers/bills/$societyId',
              queryParameters: _q(from, to, {
                if (status != null) 'status': status,
                if (search != null && search.isNotEmpty) 'q': search,
              })))
          .data as Map<String, dynamic>, BillRow.fromJson);

  Future<Uint8List> _pdf(String path, Map<String, dynamic> query) async {
    final r = await _dio.get<List<int>>(path,
        queryParameters: {...query, 'format': 'pdf'}, options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }

  Future<Uint8List> cashBankPdf(String societyId, {DateTime? from, DateTime? to, String? accountId}) =>
      _pdf('/accounts/registers/cash-bank/$societyId', _q(from, to, {if (accountId != null) 'account_id': accountId}));

  Future<Uint8List> invoicesPdf(String societyId, {DateTime? from, DateTime? to, String? status}) =>
      _pdf('/accounts/registers/invoices/$societyId', _q(from, to, {if (status != null) 'status': status}));

  Future<Uint8List> billsPdf(String societyId, {DateTime? from, DateTime? to, String? status}) =>
      _pdf('/accounts/registers/bills/$societyId', _q(from, to, {if (status != null) 'status': status}));
}
