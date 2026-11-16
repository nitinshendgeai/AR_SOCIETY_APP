import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/assets/data/assets_api.dart' show assetCategoryLabel;

double _n(Object? v) => double.tryParse('${v ?? 0}') ?? 0;
DateTime? _d(Object? v) => v == null ? null : DateTime.tryParse('$v');

const kDepreciationMethods = <(String, String)>[
  ('wdv', 'Reducing balance (WDV)'),
  ('slm', 'Straight line (SLM)'),
];
String depreciationMethodLabel(String m) => kDepreciationMethods.where((e) => e.$1 == m).firstOrNull?.$2 ?? m;

/// How one kind of asset is depreciated.
class DepreciationRule {
  final String id, category, method;
  final double rate, salvagePercent;
  final int? lifeYears;
  const DepreciationRule({
    required this.id,
    required this.category,
    required this.method,
    required this.rate,
    required this.salvagePercent,
    required this.lifeYears,
  });

  factory DepreciationRule.fromJson(Map<String, dynamic> j) => DepreciationRule(
        id: j['id'] as String,
        category: j['asset_category'] as String,
        method: j['method'] as String,
        rate: _n(j['rate']),
        salvagePercent: _n(j['salvage_percent']),
        lifeYears: (j['life_years'] as num?)?.toInt(),
      );

  String get label => assetCategoryLabel(category);
}

/// An asset with the setting that applies to it (its own, else its kind's) and what is missing before it can be depreciated.
class AssetDepreciationSetting {
  final String assetId, code, name, category, status, method;
  final DateTime? purchaseDate, startOn, stopOn;
  final double cost, rate, salvage;
  final int? lifeYears;
  final bool depreciate;
  final Map<String, dynamic>? own;
  final List<String> problems;
  const AssetDepreciationSetting({
    required this.assetId,
    required this.code,
    required this.name,
    required this.category,
    required this.status,
    required this.method,
    required this.purchaseDate,
    required this.startOn,
    required this.stopOn,
    required this.cost,
    required this.rate,
    required this.salvage,
    required this.lifeYears,
    required this.depreciate,
    required this.own,
    required this.problems,
  });

  factory AssetDepreciationSetting.fromJson(Map<String, dynamic> j) => AssetDepreciationSetting(
        assetId: j['asset_id'] as String,
        code: j['asset_code'] as String,
        name: j['name'] as String,
        category: j['category'] as String,
        status: j['status'] as String? ?? 'active',
        method: j['method'] as String,
        purchaseDate: _d(j['purchase_date']),
        startOn: _d(j['start_on']),
        stopOn: _d(j['stop_on']),
        cost: _n(j['cost']),
        rate: _n(j['rate']),
        salvage: _n(j['salvage']),
        lifeYears: (j['life_years'] as num?)?.toInt(),
        depreciate: j['depreciate'] as bool? ?? true,
        own: j['own'] == null ? null : Map<String, dynamic>.from(j['own'] as Map),
        problems: [for (final p in j['problems'] as List? ?? const []) '$p'],
      );
}

class DepreciationRow {
  final String code, name, category, method;
  final DateTime start;
  final double rate, cost, openingWdv, depreciation, closingWdv, additions;
  final int days;
  const DepreciationRow({
    required this.code,
    required this.name,
    required this.category,
    required this.method,
    required this.start,
    required this.rate,
    required this.cost,
    required this.openingWdv,
    required this.depreciation,
    required this.closingWdv,
    required this.additions,
    required this.days,
  });

  factory DepreciationRow.fromJson(Map<String, dynamic> j) => DepreciationRow(
        code: j['asset_code'] as String,
        name: j['name'] as String,
        category: j['category'] as String,
        method: j['method'] as String,
        start: DateTime.parse(j['start'] as String),
        rate: _n(j['rate']),
        cost: _n(j['cost']),
        openingWdv: _n(j['opening_wdv']),
        depreciation: _n(j['depreciation']),
        closingWdv: _n(j['closing_wdv']),
        additions: _n(j['additions']),
        days: (j['days'] as num?)?.toInt() ?? 0,
      );
}

class JournalLine {
  final String ledger;
  final double amount;
  const JournalLine(this.ledger, this.amount);
}

class AssetProblem {
  final String code, name;
  final List<String> issues;
  const AssetProblem(this.code, this.name, this.issues);
}

/// The year's depreciation, with the journal that would book it. It posts nothing.
class DepreciationSchedule {
  final String fy;
  final List<DepreciationRow> rows;
  final double cost, additions, openingWdv, depreciation, closingWdv;
  final JournalLine debit;
  final List<JournalLine> credits;
  final List<AssetProblem> problems;
  const DepreciationSchedule({
    required this.fy,
    required this.rows,
    required this.cost,
    required this.additions,
    required this.openingWdv,
    required this.depreciation,
    required this.closingWdv,
    required this.debit,
    required this.credits,
    required this.problems,
  });

  factory DepreciationSchedule.fromJson(Map<String, dynamic> j) {
    final t = j['totals'] as Map<String, dynamic>;
    final journal = j['journal'] as Map<String, dynamic>;
    final d = journal['debit'] as Map<String, dynamic>;
    return DepreciationSchedule(
      fy: j['fy'] as String,
      rows: [for (final r in j['rows'] as List) DepreciationRow.fromJson(Map<String, dynamic>.from(r as Map))],
      cost: _n(t['cost']),
      additions: _n(t['additions']),
      openingWdv: _n(t['opening_wdv']),
      depreciation: _n(t['depreciation']),
      closingWdv: _n(t['closing_wdv']),
      debit: JournalLine(d['ledger'] as String, _n(d['amount'])),
      credits: [
        for (final c in journal['credits'] as List) JournalLine((c as Map)['ledger'] as String, _n(c['amount']))
      ],
      problems: [
        for (final p in j['problems'] as List)
          AssetProblem((p as Map)['asset_code'] as String, p['name'] as String, [for (final i in p['issues'] as List) '$i'])
      ],
    );
  }
}

class DepreciationApi {
  final Dio _dio;
  DepreciationApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<DepreciationSchedule> schedule(String societyId, String fy) async => DepreciationSchedule.fromJson(
      (await _dio.get('/accounts/depreciation/schedule/$societyId', queryParameters: {'fy': fy})).data as Map<String, dynamic>);

  Future<Uint8List> schedulePdf(String societyId, String fy) async {
    final r = await _dio.get<List<int>>('/accounts/depreciation/schedule/$societyId',
        queryParameters: {'fy': fy, 'format': 'pdf'}, options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }

  Future<List<DepreciationRule>> rules(String societyId) async => [
        for (final r in (await _dio.get('/accounts/depreciation/rules/$societyId')).data as List)
          DepreciationRule.fromJson(Map<String, dynamic>.from(r as Map))
      ];

  Future<void> updateRule(String id, {required String method, required String rate, int? lifeYears, required String salvagePercent}) =>
      _dio.patch('/accounts/depreciation/rules/$id',
          data: {'method': method, 'rate': rate, 'life_years': lifeYears, 'salvage_percent': salvagePercent});

  Future<List<AssetDepreciationSetting>> assets(String societyId) async => [
        for (final r in (await _dio.get('/accounts/depreciation/assets/$societyId')).data as List)
          AssetDepreciationSetting.fromJson(Map<String, dynamic>.from(r as Map))
      ];

  /// Null for a field goes back to the kind of asset's value.
  Future<void> setAsset(String assetId, Map<String, dynamic> body) => _dio.put('/accounts/depreciation/assets/$assetId', data: body);
}

final depreciationApiProvider = Provider<DepreciationApi>((ref) => DepreciationApi());

typedef DepreciationKey = ({String societyId, String fy});

final depreciationScheduleProvider = FutureProvider.autoDispose.family<DepreciationSchedule, DepreciationKey>(
    (ref, k) => ref.watch(depreciationApiProvider).schedule(k.societyId, k.fy));
final depreciationRulesProvider = FutureProvider.autoDispose.family<List<DepreciationRule>, String>(
    (ref, id) => ref.watch(depreciationApiProvider).rules(id));
final depreciationAssetsProvider = FutureProvider.autoDispose.family<List<AssetDepreciationSetting>, String>(
    (ref, id) => ref.watch(depreciationApiProvider).assets(id));
