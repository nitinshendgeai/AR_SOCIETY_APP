import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show DrCr, apiDate;

double _n(Object? v) => double.tryParse('${v ?? 0}') ?? 0;

/// One posting on a TDS ledger.
class TdsLine {
  final DateTime date;
  final String voucherNumber, particulars;
  final String? narration;
  final double debit, credit;
  final DrCr balance;
  const TdsLine({
    required this.date,
    required this.voucherNumber,
    required this.particulars,
    required this.narration,
    required this.debit,
    required this.credit,
    required this.balance,
  });

  factory TdsLine.fromJson(Map<String, dynamic> j) => TdsLine(
        date: DateTime.parse(j['date'] as String),
        voucherNumber: j['voucher_number'] as String? ?? '',
        particulars: j['particulars'] as String? ?? '',
        narration: j['narration'] as String?,
        debit: _n(j['debit']),
        credit: _n(j['credit']),
        balance: DrCr.fromJson(j['balance'] as Map<String, dynamic>?),
      );
}

/// A TDS ledger (Payable or Receivable) for the period.
class TdsStatement {
  final String name;
  final DrCr opening, closing;
  final double totalDebit, totalCredit;
  final List<TdsLine> lines;
  const TdsStatement({
    required this.name,
    required this.opening,
    required this.closing,
    required this.totalDebit,
    required this.totalCredit,
    required this.lines,
  });

  factory TdsStatement.fromJson(Map<String, dynamic> j) => TdsStatement(
        name: (j['account'] as Map)['name'] as String,
        opening: DrCr.fromJson(j['opening'] as Map<String, dynamic>?),
        closing: DrCr.fromJson(j['closing'] as Map<String, dynamic>?),
        totalDebit: _n(j['total_debit']),
        totalCredit: _n(j['total_credit']),
        lines: [for (final l in j['lines'] as List? ?? const []) TdsLine.fromJson(Map<String, dynamic>.from(l as Map))],
      );
}

/// A financial-year quarter's totals on one ledger.
class TdsQuarter {
  final String quarter;
  final double credit, debit;
  const TdsQuarter(this.quarter, this.credit, this.debit);

  factory TdsQuarter.fromJson(Map<String, dynamic> j) =>
      TdsQuarter(j['quarter'] as String, _n(j['credit']), _n(j['debit']));
}

/// What the society must deposit with the government and what it can claim back, with both ledgers.
class TdsLedger {
  final double toPay, excessDeposited, toReceive, receivableOverAdjusted;
  final List<TdsQuarter> payableQuarters, receivableQuarters;
  final TdsStatement payable, receivable;
  const TdsLedger({
    required this.toPay,
    required this.excessDeposited,
    required this.toReceive,
    required this.receivableOverAdjusted,
    required this.payableQuarters,
    required this.receivableQuarters,
    required this.payable,
    required this.receivable,
  });

  factory TdsLedger.fromJson(Map<String, dynamic> j) => TdsLedger(
        toPay: _n(j['to_pay']),
        excessDeposited: _n(j['excess_deposited']),
        toReceive: _n(j['to_receive']),
        receivableOverAdjusted: _n(j['receivable_over_adjusted']),
        payableQuarters: [for (final q in j['payable_quarters'] as List) TdsQuarter.fromJson(Map<String, dynamic>.from(q as Map))],
        receivableQuarters: [for (final q in j['receivable_quarters'] as List) TdsQuarter.fromJson(Map<String, dynamic>.from(q as Map))],
        payable: TdsStatement.fromJson(Map<String, dynamic>.from(j['payable'] as Map)),
        receivable: TdsStatement.fromJson(Map<String, dynamic>.from(j['receivable'] as Map)),
      );
}

class TdsLedgerApi {
  final Dio _dio;
  TdsLedgerApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Map<String, dynamic> _q(DateTime? from, DateTime? to) =>
      {if (from != null) 'date_from': apiDate(from), if (to != null) 'date_to': apiDate(to)};

  Future<TdsLedger> ledger(String societyId, {DateTime? from, DateTime? to}) async => TdsLedger.fromJson(
      (await _dio.get('/accounts/tds-ledger/$societyId', queryParameters: _q(from, to))).data as Map<String, dynamic>);

  Future<Uint8List> pdf(String societyId, {DateTime? from, DateTime? to}) async {
    final r = await _dio.get<List<int>>('/accounts/tds-ledger/$societyId',
        queryParameters: {..._q(from, to), 'format': 'pdf'}, options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }
}

final tdsLedgerApiProvider = Provider<TdsLedgerApi>((ref) => TdsLedgerApi());

typedef TdsLedgerKey = ({String societyId, DateTime? from, DateTime? to});

final tdsLedgerProvider = FutureProvider.autoDispose.family<TdsLedger, TdsLedgerKey>(
    (ref, k) => ref.watch(tdsLedgerApiProvider).ledger(k.societyId, from: k.from, to: k.to));
