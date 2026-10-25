import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';

double _num(Object? v) => double.tryParse(v?.toString() ?? '') ?? 0;
DateTime? _date(Object? v) => v == null ? null : DateTime.parse(v as String);
String _iso(DateTime d) => d.toIso8601String().split('T').first;

/// One line of a bank ledger: a deposit the society recorded, or a payment (cheque, transfer) it made.
class BrsLine {
  final String entryId;
  final String voucherId;
  final String voucherNumber;
  final String voucherType;
  final DateTime date;
  final String? reference;
  final String? narration;
  final String? party;
  final double amount;
  final bool isDeposit;
  final DateTime? clearedDate;
  final int daysPending;

  /// On a statement row's suggestions: the bank's reference agrees with this voucher's.
  final bool referenceMatches;
  const BrsLine({
    required this.entryId,
    required this.voucherId,
    required this.voucherNumber,
    required this.voucherType,
    required this.date,
    this.reference,
    this.narration,
    this.party,
    required this.amount,
    required this.isDeposit,
    this.clearedDate,
    this.daysPending = 0,
    this.referenceMatches = false,
  });

  factory BrsLine.fromJson(Map<String, dynamic> j) => BrsLine(
        entryId: j['entry_id'] as String,
        voucherId: j['voucher_id'] as String,
        voucherNumber: j['voucher_number'] as String,
        voucherType: j['voucher_type'] as String? ?? '',
        date: DateTime.parse(j['date'] as String),
        reference: j['reference'] as String?,
        narration: j['narration'] as String?,
        party: j['party'] as String?,
        amount: _num(j['amount']),
        isDeposit: j['direction'] == 'deposit',
        clearedDate: _date(j['cleared_date']),
        daysPending: (j['days_pending'] as num?)?.toInt() ?? 0,
        referenceMatches: j['reference_matches'] as bool? ?? false,
      );
}

/// The Bank Reconciliation Statement of one bank ledger as on a date.
class BankReconciliation {
  final String accountId;
  final String accountName;
  final DateTime asOn;
  final double balancePerBooks;
  final List<BrsLine> paymentsNotCleared;
  final double paymentsNotClearedTotal;
  final List<BrsLine> depositsNotCleared;
  final double depositsNotClearedTotal;
  final double balancePerBank;
  final int unmatchedStatementRows;
  const BankReconciliation({
    required this.accountId,
    required this.accountName,
    required this.asOn,
    required this.balancePerBooks,
    required this.paymentsNotCleared,
    required this.paymentsNotClearedTotal,
    required this.depositsNotCleared,
    required this.depositsNotClearedTotal,
    required this.balancePerBank,
    this.unmatchedStatementRows = 0,
  });

  bool get isFullyCleared => paymentsNotCleared.isEmpty && depositsNotCleared.isEmpty;

  factory BankReconciliation.fromJson(Map<String, dynamic> j) => BankReconciliation(
        accountId: j['account_id'] as String,
        accountName: j['account_name'] as String? ?? '',
        asOn: DateTime.parse(j['as_on'] as String),
        balancePerBooks: _num(j['balance_per_books']),
        paymentsNotCleared: [
          for (final l in (j['payments_not_cleared'] as List? ?? const [])) BrsLine.fromJson(l as Map<String, dynamic>)
        ],
        paymentsNotClearedTotal: _num(j['payments_not_cleared_total']),
        depositsNotCleared: [
          for (final l in (j['deposits_not_cleared'] as List? ?? const [])) BrsLine.fromJson(l as Map<String, dynamic>)
        ],
        depositsNotClearedTotal: _num(j['deposits_not_cleared_total']),
        balancePerBank: _num(j['balance_per_bank']),
        unmatchedStatementRows: (j['unmatched_statement_rows'] as num?)?.toInt() ?? 0,
      );
}

/// One row of an imported bank statement.
class StatementRow {
  final String id;
  final DateTime txnDate;
  final String description;
  final String? reference;
  final double amount;
  final bool isCredit;
  final String? bankAccountId;
  final String matchStatus; // unmatched | matched | ignored
  final String? matchedEntryId;
  final String? matchedReceiptNumber;
  const StatementRow({
    required this.id,
    required this.txnDate,
    required this.description,
    this.reference,
    required this.amount,
    required this.isCredit,
    this.bankAccountId,
    required this.matchStatus,
    this.matchedEntryId,
    this.matchedReceiptNumber,
  });

  bool get isUnmatched => matchStatus == 'unmatched';
  bool get isMatched => matchStatus == 'matched';

  factory StatementRow.fromJson(Map<String, dynamic> j) => StatementRow(
        id: j['id'] as String,
        txnDate: DateTime.parse(j['txn_date'] as String),
        description: j['description'] as String? ?? '',
        reference: j['reference'] as String?,
        amount: _num(j['amount']),
        isCredit: (j['direction'] as String? ?? 'credit') == 'credit',
        bankAccountId: j['bank_account_id'] as String?,
        matchStatus: j['match_status'] as String? ?? 'unmatched',
        matchedEntryId: j['matched_entry_id'] as String?,
        matchedReceiptNumber: j['matched_submission_receipt_number'] as String?,
      );
}

class AutoMatchResult {
  final int matched;
  final int leftForAPerson;
  const AutoMatchResult({required this.matched, required this.leftForAPerson});
}

/// The bank reconciliation endpoints: the statement and clearing in `/accounts/bank-reconciliation`, and the imported
/// statement rows in `/billing/bank-reconciliation` (shared with the resident-payment matching screen).
class BankReconciliationApi {
  final Dio _dio;
  BankReconciliationApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<BankReconciliation> statement(String societyId, {String? accountId, DateTime? asOn}) async {
    final r = await _dio.get('/accounts/bank-reconciliation/$societyId', queryParameters: {
      if (accountId != null) 'account_id': accountId,
      if (asOn != null) 'as_on': _iso(asOn),
    });
    return BankReconciliation.fromJson(r.data as Map<String, dynamic>);
  }

  Future<List<BrsLine>> cleared(String societyId, {String? accountId}) async {
    final r = await _dio.get('/accounts/bank-reconciliation/$societyId/cleared',
        queryParameters: {if (accountId != null) 'account_id': accountId});
    return [for (final l in r.data as List) BrsLine.fromJson(l as Map<String, dynamic>)];
  }

  Future<int> clear(String societyId, List<String> entryIds, DateTime clearedOn) async {
    final r = await _dio.post('/accounts/bank-reconciliation/$societyId/clear',
        data: {'entry_ids': entryIds, 'cleared_date': _iso(clearedOn)});
    return (r.data['cleared'] as num).toInt();
  }

  Future<int> unclear(String societyId, List<String> entryIds) async {
    final r = await _dio.post('/accounts/bank-reconciliation/$societyId/unclear', data: {'entry_ids': entryIds});
    return (r.data['uncleared'] as num).toInt();
  }

  Future<List<StatementRow>> rows(String societyId) async {
    final r = await _dio.get('/billing/bank-reconciliation/society/$societyId', queryParameters: {'limit': 500});
    return [for (final e in r.data as List) StatementRow.fromJson(e as Map<String, dynamic>)];
  }

  /// Imports the bank's CSV (credits and debits) for one bank ledger.
  Future<int> importStatement(String societyId,
      {required Uint8List csvBytes, required String fileName, String? accountId}) async {
    final r = await _dio.post(
      '/billing/bank-reconciliation/society/$societyId/import',
      queryParameters: {'include_debits': true, if (accountId != null) 'bank_account_id': accountId},
      data: FormData.fromMap({
        'statement': MultipartFile.fromBytes(csvBytes, filename: fileName, contentType: DioMediaType.parse('text/csv')),
      }),
    );
    return (r.data as List).length;
  }

  Future<List<BrsLine>> suggestions(String societyId, String rowId) async {
    final r = await _dio.get('/accounts/bank-reconciliation/$societyId/rows/$rowId/suggestions');
    return [for (final l in r.data as List) BrsLine.fromJson(l as Map<String, dynamic>)];
  }

  Future<void> match(String societyId, String rowId, String entryId) async {
    await _dio.post('/accounts/bank-reconciliation/$societyId/rows/$rowId/match', data: {'entry_id': entryId});
  }

  Future<void> unmatch(String societyId, String rowId) async {
    await _dio.post('/accounts/bank-reconciliation/$societyId/rows/$rowId/unmatch');
  }

  Future<AutoMatchResult> autoMatch(String societyId, {String? accountId}) async {
    final r = await _dio.post('/accounts/bank-reconciliation/$societyId/auto-match',
        queryParameters: {if (accountId != null) 'account_id': accountId});
    return AutoMatchResult(
        matched: (r.data['matched'] as num).toInt(), leftForAPerson: (r.data['left_for_a_person'] as num).toInt());
  }

  Future<void> ignore(String rowId, String? reason) async {
    await _dio.post('/billing/bank-reconciliation/$rowId/ignore', data: {if (reason != null) 'reason': reason});
  }
}
