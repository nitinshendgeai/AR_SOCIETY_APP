import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';

/// One column of a register: what to call it, whether it is a number, and whether a phone shows it.
class MoreRegisterColumn {
  final String key, label;
  final bool right, phone;
  const MoreRegisterColumn({required this.key, required this.label, this.right = false, this.phone = false});

  factory MoreRegisterColumn.fromJson(Map<String, dynamic> j) => MoreRegisterColumn(
        key: j['key'] as String,
        label: j['label'] as String,
        right: j['right'] as bool? ?? false,
        phone: j['phone'] as bool? ?? false,
      );
}

/// A register in the shared shape the server sends for the rental, receipts and staff attendance registers: the
/// columns, the rows (a display string for every column), the totals and the filters it offers. One screen draws any of
/// them, so a new register needs nothing here.
class MoreRegister {
  final String kind, title, subtitle;
  final List<MoreRegisterColumn> columns;
  final List<Map<String, String>> rows;
  final List<(String, String)> totals;
  final List<(String?, String)> statuses;
  final bool usesPeriod, usesMonth;
  final String? month;
  const MoreRegister({
    required this.kind,
    required this.title,
    required this.subtitle,
    required this.columns,
    required this.rows,
    required this.totals,
    required this.statuses,
    required this.usesPeriod,
    required this.usesMonth,
    this.month,
  });

  factory MoreRegister.fromJson(Map<String, dynamic> j) => MoreRegister(
        kind: j['kind'] as String,
        title: j['title'] as String,
        subtitle: j['subtitle'] as String? ?? '',
        columns: [for (final c in j['columns'] as List) MoreRegisterColumn.fromJson(Map<String, dynamic>.from(c as Map))],
        rows: [
          for (final r in j['rows'] as List)
            {for (final e in (r as Map).entries) '${e.key}': '${e.value ?? ''}'}
        ],
        totals: [for (final t in j['totals'] as List) ('${(t as Map)['label']}', '${t['value']}')],
        statuses: [for (final s in j['statuses'] as List) ((s as Map)['value'] as String?, '${s['label']}')],
        usesPeriod: j['uses_period'] as bool? ?? false,
        usesMonth: j['uses_month'] as bool? ?? false,
        month: j['month'] as String?,
      );
}

/// Which register and how it is filtered.
typedef MoreRegisterKey = ({
  String kind,
  String societyId,
  DateTime? from,
  DateTime? to,
  String? month,
  String? status,
  String search,
});

class MoreRegistersApi {
  final Dio _dio;
  MoreRegistersApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Map<String, dynamic> _query(MoreRegisterKey k) {
    final fmt = DateFormat('yyyy-MM-dd');
    return {
      if (k.from != null) 'date_from': fmt.format(k.from!),
      if (k.to != null) 'date_to': fmt.format(k.to!),
      if (k.month != null) 'month': k.month,
      if (k.status != null) 'status': k.status,
      if (k.search.isNotEmpty) 'q': k.search,
    };
  }

  Future<MoreRegister> load(MoreRegisterKey k) async {
    final r = await _dio.get('/accounts/registers/${k.kind}/${k.societyId}', queryParameters: _query(k));
    return MoreRegister.fromJson(Map<String, dynamic>.from(r.data as Map));
  }

  /// The printout (`pdf`) or the spreadsheet (`csv`) of the same view.
  Future<Uint8List> file(MoreRegisterKey k, String format) async {
    final r = await _dio.get<List<int>>('/accounts/registers/${k.kind}/${k.societyId}',
        queryParameters: {..._query(k), 'format': format}, options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }
}

final moreRegistersApiProvider = Provider<MoreRegistersApi>((_) => MoreRegistersApi());

final moreRegisterProvider = FutureProvider.autoDispose.family<MoreRegister, MoreRegisterKey>(
  (ref, k) => ref.watch(moreRegistersApiProvider).load(k),
);
