import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';

double _n(Object? v) => double.tryParse(v?.toString() ?? '') ?? 0;

/// One bill behind a party's outstanding: when it was raised, when it fell due and how late it is.
class OutstandingBill {
  final String ref;
  final String? label;
  final DateTime date;
  final DateTime dueDate;
  final double outstanding;
  final int daysOverdue;
  final String bucket;
  final bool noDueDate;
  const OutstandingBill({
    required this.ref,
    this.label,
    required this.date,
    required this.dueDate,
    required this.outstanding,
    required this.daysOverdue,
    required this.bucket,
    this.noDueDate = false,
  });

  factory OutstandingBill.fromJson(Map<String, dynamic> j) => OutstandingBill(
        ref: j['ref'] as String? ?? '',
        label: j['label'] as String?,
        date: DateTime.parse(j['date'] as String),
        dueDate: DateTime.parse(j['due_date'] as String),
        outstanding: _n(j['outstanding']),
        daysOverdue: (j['days_overdue'] as num?)?.toInt() ?? 0,
        bucket: j['bucket'] as String? ?? 'not_due',
        noDueDate: j['no_due_date'] == true,
      );
}

/// A flat (receivable) or a vendor (payable) with its outstanding aged into bands.
class OutstandingParty {
  final String key;
  final String name;
  final String? sub;
  final double total;
  final Map<String, double> buckets;
  final DateTime oldestDueDate;
  final int daysOverdue;
  final List<OutstandingBill> bills;
  const OutstandingParty({
    required this.key,
    required this.name,
    this.sub,
    required this.total,
    required this.buckets,
    required this.oldestDueDate,
    required this.daysOverdue,
    required this.bills,
  });

  factory OutstandingParty.fromJson(Map<String, dynamic> j) => OutstandingParty(
        key: j['key'] as String? ?? '',
        name: j['name'] as String? ?? '',
        sub: j['sub'] as String?,
        total: _n(j['total']),
        buckets: {for (final e in (j['buckets'] as Map? ?? const {}).entries) e.key as String: _n(e.value)},
        oldestDueDate: DateTime.parse(j['oldest_due_date'] as String),
        daysOverdue: (j['days_overdue'] as num?)?.toInt() ?? 0,
        bills: (j['bills'] as List? ?? const [])
            .map((e) => OutstandingBill.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class OutstandingReport {
  final String kind;
  final DateTime asOf;
  final List<(String, String)> bucketLabels;
  final int parties;
  final int bills;
  final double outstanding;
  final double overdue;
  final Map<String, double> bucketTotals;
  final List<OutstandingParty> rows;
  const OutstandingReport({
    required this.kind,
    required this.asOf,
    required this.bucketLabels,
    required this.parties,
    required this.bills,
    required this.outstanding,
    required this.overdue,
    required this.bucketTotals,
    required this.rows,
  });

  factory OutstandingReport.fromJson(Map<String, dynamic> j) {
    final t = j['totals'] as Map<String, dynamic>;
    return OutstandingReport(
      kind: j['kind'] as String? ?? 'receivable',
      asOf: DateTime.parse(j['as_of'] as String),
      bucketLabels: [
        for (final b in (j['bucket_labels'] as List? ?? const [])) ((b as Map)['key'] as String, b['label'] as String)
      ],
      parties: (t['parties'] as num?)?.toInt() ?? 0,
      bills: (t['bills'] as num?)?.toInt() ?? 0,
      outstanding: _n(t['outstanding']),
      overdue: _n(t['overdue']),
      bucketTotals: {for (final e in (t['buckets'] as Map? ?? const {}).entries) e.key as String: _n(e.value)},
      rows: (j['parties'] as List? ?? const [])
          .map((e) => OutstandingParty.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

class OutstandingApi {
  final Dio _dio;
  OutstandingApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<OutstandingReport> report(String societyId, String kind) async => OutstandingReport.fromJson(
      (await _dio.get('/accounts/outstanding/$societyId', queryParameters: {'kind': kind})).data
          as Map<String, dynamic>);

  Future<Uint8List> pdf(String societyId, String kind) async {
    final r = await _dio.get<List<int>>('/accounts/outstanding/$societyId',
        queryParameters: {'kind': kind, 'format': 'pdf'}, options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }
}

final outstandingApiProvider = Provider<OutstandingApi>((_) => OutstandingApi());

typedef OutstandingKey = ({String societyId, String kind});

/// What members owe (receivable) or the society owes vendors (payable), aged by days past the due date.
final outstandingProvider = FutureProvider.autoDispose.family<OutstandingReport, OutstandingKey>(
  (ref, k) => ref.watch(outstandingApiProvider).report(k.societyId, k.kind),
);
