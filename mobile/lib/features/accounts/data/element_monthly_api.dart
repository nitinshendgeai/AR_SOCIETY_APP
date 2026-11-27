import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show apiDate;

double _n(Object? v) => v == null ? 0 : (v is num ? v.toDouble() : double.tryParse('$v') ?? 0);
List<double> _list(Object? v) => [for (final x in (v as List? ?? const [])) _n(x)];

/// One row of the element-wise monthly report: an element (or the expense heads no element covers).
class ElementMonthRow {
  final String elementId;
  final String element;
  final List<double> spent;
  final List<double> billed;
  final double spentTotal;
  final double billedTotal;
  final double difference;
  final bool hasLedger;
  const ElementMonthRow(this.elementId, this.element, this.spent, this.billed, this.spentTotal, this.billedTotal,
      this.difference, this.hasLedger);
  factory ElementMonthRow.fromJson(Map<String, dynamic> j) => ElementMonthRow(
        '${j['element_id'] ?? 'none'}',
        j['element'] as String? ?? '',
        _list(j['spent']),
        _list(j['billed']),
        _n(j['spent_total']),
        _n(j['billed_total']),
        _n(j['difference']),
        j['has_ledger'] as bool? ?? false,
      );

  /// Billed minus spent, month by month.
  List<double> get monthlyDifference => [for (var i = 0; i < spent.length; i++) (i < billed.length ? billed[i] : 0) - spent[i]];
}

/// Elements as rows, months as columns: what the books spent and what the bills charged.
class ElementMonthly {
  final DateTime from;
  final DateTime to;
  final List<String> months;
  final List<ElementMonthRow> rows;
  final ElementMonthRow totals;
  final String note;
  const ElementMonthly(this.from, this.to, this.months, this.rows, this.totals, this.note);
  factory ElementMonthly.fromJson(Map<String, dynamic> j) {
    final t = (j['totals'] as Map? ?? const {}).cast<String, dynamic>();
    return ElementMonthly(
      DateTime.parse(j['date_from'] as String),
      DateTime.parse(j['date_to'] as String),
      [for (final m in (j['months'] as List? ?? const [])) '${(m as Map)['label']}'],
      [for (final r in (j['rows'] as List? ?? const [])) ElementMonthRow.fromJson((r as Map).cast<String, dynamic>())],
      ElementMonthRow('total', 'Total', _list(t['spent']), _list(t['billed']), _n(t['spent_total']),
          _n(t['billed_total']), _n(t['difference']), true),
      j['note'] as String? ?? '',
    );
  }
}

class ElementMonthlyApi {
  final Dio _dio;
  ElementMonthlyApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<ElementMonthly> fetch(String societyId, DateTime from, DateTime to) async =>
      ElementMonthly.fromJson((await _dio.get('/accounts/expenses-by-element/$societyId/monthly',
              queryParameters: {'date_from': apiDate(from), 'date_to': apiDate(to)}))
          .data as Map<String, dynamic>);
}

typedef ElementMonthlyKey = ({String societyId, DateTime from, DateTime to});

final elementMonthlyApiProvider = Provider<ElementMonthlyApi>((_) => ElementMonthlyApi());

final elementMonthlyProvider = FutureProvider.autoDispose.family<ElementMonthly, ElementMonthlyKey>(
    (ref, k) => ref.watch(elementMonthlyApiProvider).fetch(k.societyId, k.from, k.to));
