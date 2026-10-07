import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show Voucher, apiDate;

double? _numOrNull(Object? v) => v == null ? null : double.tryParse(v.toString());

/// A standing monthly expense: the security agency, the lift AMC, the rent.
class RecurringExpense {
  final String id;
  final String name;
  final String expenseAccountId;
  final String? expenseAccountName;
  final String? elementName;
  final String? paidFromId;
  final String? paidFromName;
  final double? amount; // null: it changes every month
  final int dayOfMonth;
  final DateTime startMonth;
  final DateTime? endMonth;
  final String? payee;
  final String? note;
  final bool isActive;
  final int dueMonths;

  const RecurringExpense({
    required this.id,
    required this.name,
    required this.expenseAccountId,
    this.expenseAccountName,
    this.elementName,
    this.paidFromId,
    this.paidFromName,
    this.amount,
    this.dayOfMonth = 1,
    required this.startMonth,
    this.endMonth,
    this.payee,
    this.note,
    this.isActive = true,
    this.dueMonths = 0,
  });

  factory RecurringExpense.fromJson(Map<String, dynamic> j) => RecurringExpense(
        id: j['id'] as String,
        name: j['name'] as String? ?? '',
        expenseAccountId: j['expense_account_id'] as String,
        expenseAccountName: j['expense_account_name'] as String?,
        elementName: j['element_name'] as String?,
        paidFromId: j['paid_from_id'] as String?,
        paidFromName: j['paid_from_name'] as String?,
        amount: _numOrNull(j['amount']),
        dayOfMonth: j['day_of_month'] as int? ?? 1,
        startMonth: DateTime.parse(j['start_month'] as String),
        endMonth: j['end_month'] == null ? null : DateTime.parse(j['end_month'] as String),
        payee: j['payee'] as String?,
        note: j['note'] as String?,
        isActive: j['is_active'] as bool? ?? true,
        dueMonths: j['due_months'] as int? ?? 0,
      );
}

/// One month of a recurring expense that has come due and nobody has recorded or skipped.
class DueExpense {
  final String recurringId;
  final String name;
  final DateTime month;
  final DateTime dueDate;
  final int daysLate;
  final double? amount;
  final String? expenseAccountName;
  final String? elementName;
  final String? paidFromId;
  final String? payee;

  const DueExpense({
    required this.recurringId,
    required this.name,
    required this.month,
    required this.dueDate,
    required this.daysLate,
    this.amount,
    this.expenseAccountName,
    this.elementName,
    this.paidFromId,
    this.payee,
  });

  factory DueExpense.fromJson(Map<String, dynamic> j) => DueExpense(
        recurringId: j['recurring_id'] as String,
        name: j['name'] as String? ?? '',
        month: DateTime.parse(j['month'] as String),
        dueDate: DateTime.parse(j['due_date'] as String),
        daysLate: j['days_late'] as int? ?? 0,
        amount: _numOrNull(j['amount']),
        expenseAccountName: j['expense_account_name'] as String?,
        elementName: j['element_name'] as String?,
        paidFromId: j['paid_from_id'] as String?,
        payee: j['payee'] as String?,
      );
}

class RecurringApi {
  final Dio _dio;
  RecurringApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<List<RecurringExpense>> list(String societyId) async =>
      ((await _dio.get('/accounts/recurring-expenses/$societyId')).data as List)
          .map((e) => RecurringExpense.fromJson(e as Map<String, dynamic>))
          .toList();

  Future<List<DueExpense>> due(String societyId) async =>
      ((await _dio.get('/accounts/recurring-expenses/$societyId/due')).data as List)
          .map((e) => DueExpense.fromJson(e as Map<String, dynamic>))
          .toList();

  Future<RecurringExpense> create(Map<String, dynamic> body) async => RecurringExpense.fromJson(
      (await _dio.post('/accounts/recurring-expenses', data: body)).data as Map<String, dynamic>);

  /// Only the keys present are changed; a null value clears an optional field.
  Future<RecurringExpense> update(String id, Map<String, dynamic> body) async => RecurringExpense.fromJson(
      (await _dio.patch('/accounts/recurring-expenses/$id', data: body)).data as Map<String, dynamic>);

  Future<Voucher> record(
    String id, {
    required DateTime month,
    double? amount,
    DateTime? date,
    String? paidFromId,
    String? reference,
    String? note,
  }) async {
    final r = await _dio.post('/accounts/recurring-expenses/$id/record', data: {
      'month': apiDate(month),
      if (amount != null) 'amount': amount,
      if (date != null) 'voucher_date': apiDate(date),
      if (paidFromId != null) 'paid_from_id': paidFromId,
      if (reference != null && reference.isNotEmpty) 'reference': reference,
      if (note != null && note.isNotEmpty) 'note': note,
    });
    return Voucher.fromJson(r.data as Map<String, dynamic>);
  }

  Future<void> skip(String id, DateTime month, {String? reason}) => _dio.post('/accounts/recurring-expenses/$id/skip', data: {
        'month': apiDate(month),
        if (reason != null && reason.isNotEmpty) 'reason': reason,
      });
}
