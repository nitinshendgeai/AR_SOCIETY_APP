import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show Voucher, apiDate;

double _n(Object? v) => double.tryParse('${v ?? 0}') ?? 0;
double? _nOrNull(Object? v) => v == null ? null : double.tryParse(v.toString());

/// The petty cash box: what the books say is in it and what is free to spend.
class PettyCash {
  final String accountId;
  final double balance;
  final double pending; // set aside by expenses waiting for approval
  final double available;
  final double? floatAmount;
  final double? expenseLimit;
  final String? custodianName;
  final double? topUpNeeded;
  final double spentToday;
  final double spentMonth;
  final PettyCashCount? lastCount;
  final DateTime today;

  const PettyCash({
    required this.accountId,
    required this.balance,
    required this.pending,
    required this.available,
    this.floatAmount,
    this.expenseLimit,
    this.custodianName,
    this.topUpNeeded,
    required this.spentToday,
    required this.spentMonth,
    this.lastCount,
    required this.today,
  });

  factory PettyCash.fromJson(Map<String, dynamic> j) => PettyCash(
        accountId: j['account_id'] as String,
        balance: _n(j['balance']),
        pending: _n(j['pending']),
        available: _n(j['available']),
        floatAmount: _nOrNull(j['float_amount']),
        expenseLimit: _nOrNull(j['expense_limit']),
        custodianName: j['custodian_name'] as String?,
        topUpNeeded: _nOrNull(j['top_up_needed']),
        spentToday: _n(j['spent_today']),
        spentMonth: _n(j['spent_month']),
        lastCount: j['last_count'] == null ? null : PettyCashCount.fromJson(j['last_count'] as Map<String, dynamic>),
        today: DateTime.parse(j['today'] as String),
      );
}

/// Cash counted in the box against what the books said.
class PettyCashCount {
  final DateTime date;
  final double counted;
  final double book;
  final double difference;
  final String state; // tallies | short | excess
  final String? note;
  final String? countedBy;

  const PettyCashCount({
    required this.date,
    required this.counted,
    required this.book,
    required this.difference,
    required this.state,
    this.note,
    this.countedBy,
  });

  factory PettyCashCount.fromJson(Map<String, dynamic> j) => PettyCashCount(
        date: DateTime.parse(j['date'] as String),
        counted: _n(j['counted']),
        book: _n(j['book']),
        difference: _n(j['difference']),
        state: j['state'] as String? ?? 'tallies',
        note: j['note'] as String?,
        countedBy: j['counted_by'] as String?,
      );
}

class PettyCashApi {
  final Dio _dio;
  PettyCashApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<PettyCash> overview(String societyId) async =>
      PettyCash.fromJson((await _dio.get('/accounts/petty-cash/$societyId')).data as Map<String, dynamic>);

  Future<List<PettyCashCount>> counts(String societyId) async =>
      ((await _dio.get('/accounts/petty-cash/$societyId/counts')).data as List)
          .map((e) => PettyCashCount.fromJson(e as Map<String, dynamic>))
          .toList();

  /// Only the keys present are changed; null clears one.
  Future<PettyCash> saveSettings(String societyId, Map<String, dynamic> body) async => PettyCash.fromJson(
      (await _dio.put('/accounts/petty-cash/$societyId/settings', data: body)).data as Map<String, dynamic>);

  Future<Voucher> topUp(String societyId,
      {required double amount, DateTime? date, String? fromAccountId, String? note}) async {
    final r = await _dio.post('/accounts/petty-cash/top-up', data: {
      'society_id': societyId,
      'amount': amount,
      if (date != null) 'voucher_date': apiDate(date),
      if (fromAccountId != null) 'from_account_id': fromAccountId,
      if (note != null && note.isNotEmpty) 'note': note,
    });
    return Voucher.fromJson(r.data as Map<String, dynamic>);
  }

  /// A day's expenses, each `{expense_account_id, amount, note}`, as one voucher.
  Future<Voucher> spend(String societyId, {required DateTime date, required List<Map<String, dynamic>> items}) async {
    final r = await _dio.post('/accounts/petty-cash/expenses',
        data: {'society_id': societyId, 'voucher_date': apiDate(date), 'items': items});
    return Voucher.fromJson(r.data as Map<String, dynamic>);
  }

  Future<PettyCashCount> count(String societyId, {required double counted, DateTime? date, String? note}) async {
    final r = await _dio.post('/accounts/petty-cash/counts', data: {
      'society_id': societyId,
      'counted_amount': counted,
      if (date != null) 'count_date': apiDate(date),
      if (note != null && note.isNotEmpty) 'note': note,
    });
    return PettyCashCount.fromJson(r.data as Map<String, dynamic>);
  }
}
