import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/utils/server_time.dart';

/// The kinds of light that are checked: (api value, label).
const kLightKinds = <(String, String)>[('tube', 'Tube lights'), ('spot', 'Spot lights')];

class LightCell {
  final String location, label;
  final String? status, lastCheckedBy;
  final DateTime? lastCheckedAt, notWorkingSince;
  const LightCell({
    required this.location,
    required this.label,
    this.status,
    this.lastCheckedBy,
    this.lastCheckedAt,
    this.notWorkingSince,
  });

  factory LightCell.fromJson(Map<String, dynamic> j) => LightCell(
        location: j['location'] as String,
        label: j['label'] as String,
        status: j['status'] as String?,
        lastCheckedBy: j['last_checked_by'] as String?,
        lastCheckedAt: parseStampOrNull(j['last_checked_at']),
        notWorkingSince: parseStampOrNull(j['not_working_since']),
      );
}

/// One floor's tube lights, or one flat's three spot lights.
class LightGroup {
  final String? flatId;
  final String label;
  final List<LightCell> points;
  const LightGroup({this.flatId, required this.label, required this.points});

  factory LightGroup.fromJson(Map<String, dynamic> j) => LightGroup(
        flatId: j['flat_id'] as String?,
        label: j['label'] as String,
        points: [for (final p in j['points'] as List) LightCell.fromJson(p as Map<String, dynamic>)],
      );
}

class LightSheet {
  final List<LightGroup> groups;
  const LightSheet(this.groups);
  factory LightSheet.fromJson(Map<String, dynamic> j) =>
      LightSheet([for (final g in j['groups'] as List) LightGroup.fromJson(g as Map<String, dynamic>)]);
}

class FloorOption {
  final int number;
  final String name;
  const FloorOption(this.number, this.name);
}

/// A light found not working and not replaced yet.
class BrokenLight {
  final String id, kind, label;
  final String? wingName, flatLabel, lastCheckedBy;
  final int floorNumber;
  final DateTime? since, lastCheckedAt;
  const BrokenLight({
    required this.id,
    required this.kind,
    required this.label,
    required this.floorNumber,
    this.wingName,
    this.flatLabel,
    this.lastCheckedBy,
    this.since,
    this.lastCheckedAt,
  });

  factory BrokenLight.fromJson(Map<String, dynamic> j) => BrokenLight(
        id: j['id'] as String,
        kind: j['kind'] as String,
        label: j['label'] as String,
        floorNumber: j['floor_number'] as int,
        wingName: j['wing_name'] as String?,
        flatLabel: j['flat_label'] as String?,
        lastCheckedBy: j['last_checked_by'] as String?,
        since: parseStampOrNull(j['not_working_since']),
        lastCheckedAt: parseStampOrNull(j['last_checked_at']),
      );

  /// "Wing A · Floor 2 · Flat 201", or "Wing A · Floor 2" for a floor's tube light.
  String get where =>
      [if (wingName != null) wingName!, floorNumber == 0 ? 'Ground floor' : 'Floor $floorNumber', if (flatLabel != null) 'Flat $flatLabel']
          .join(' · ');
}

/// Lights checked on one kind (tube or spot) of one floor in a month.
class LightPart {
  final int expected, checked, working, notWorking;
  const LightPart({this.expected = 0, this.checked = 0, this.working = 0, this.notWorking = 0});
  factory LightPart.fromJson(Map<String, dynamic> j) => LightPart(
        expected: j['expected'] as int,
        checked: j['checked'] as int,
        working: j['working'] as int,
        notWorking: j['not_working'] as int,
      );
}

/// One floor in the monthly report. [status]: done | partial | not_checked.
class FloorReport {
  final String wingName, floorName, status;
  final int floorNumber, flats;
  final LightPart tube, spot;
  const FloorReport({
    required this.wingName,
    required this.floorName,
    required this.floorNumber,
    required this.flats,
    required this.status,
    required this.tube,
    required this.spot,
  });
  factory FloorReport.fromJson(Map<String, dynamic> j) => FloorReport(
        wingName: j['wing_name'] as String,
        floorName: j['floor_name'] as String,
        floorNumber: j['floor_number'] as int,
        flats: j['flats'] as int,
        status: j['status'] as String,
        tube: LightPart.fromJson(j['tube'] as Map<String, dynamic>),
        spot: LightPart.fromJson(j['spot'] as Map<String, dynamic>),
      );

  int get notWorking => tube.notWorking + spot.notWorking;
}

class LightReport {
  final String month;
  final int checked, working, notWorking, replaced, stillNotWorking, floorsNotChecked, floorsPartlyChecked;
  final List<FloorReport> floors;
  const LightReport({
    required this.month,
    required this.checked,
    required this.working,
    required this.notWorking,
    required this.replaced,
    required this.stillNotWorking,
    required this.floorsNotChecked,
    required this.floorsPartlyChecked,
    required this.floors,
  });
  factory LightReport.fromJson(Map<String, dynamic> j) {
    final t = j['totals'] as Map<String, dynamic>;
    return LightReport(
      month: j['month'] as String,
      checked: t['checked'] as int,
      working: t['working'] as int,
      notWorking: t['not_working'] as int,
      replaced: t['replaced'] as int,
      stillNotWorking: t['still_not_working'] as int,
      floorsNotChecked: j['floors_not_checked'] as int,
      floorsPartlyChecked: j['floors_partly_checked'] as int,
      floors: [for (final f in j['floors'] as List) FloorReport.fromJson(f as Map<String, dynamic>)],
    );
  }
}

class LightsApi {
  final Dio _dio;
  LightsApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<List<FloorOption>> floors(String societyId, String wingId) async {
    final r = await _dio.get('/light-checks/$societyId/floors', queryParameters: {'wing_id': wingId});
    return [
      for (final f in r.data as List) FloorOption(f['floor_number'] as int, f['name'] as String),
    ];
  }

  Future<LightSheet> sheet(String societyId, String wingId, int floor, String kind) async {
    final r = await _dio.get('/light-checks/$societyId/sheet',
        queryParameters: {'wing_id': wingId, 'floor_number': floor, 'kind': kind});
    return LightSheet.fromJson(r.data as Map<String, dynamic>);
  }

  /// [results]: each `{location, status, flat_id?}`. Returns how many were marked not working.
  Future<int> check(String societyId,
      {required String wingId, required int floor, required String kind, required List<Map<String, dynamic>> results}) async {
    final r = await _dio.post('/light-checks/$societyId/check',
        data: {'wing_id': wingId, 'floor_number': floor, 'kind': kind, 'results': results});
    return (r.data as Map<String, dynamic>)['not_working'] as int;
  }

  Future<List<BrokenLight>> notWorking(String societyId) async {
    final r = await _dio.get('/light-checks/$societyId/not-working');
    return [for (final e in (r.data as Map<String, dynamic>)['rows'] as List) BrokenLight.fromJson(e as Map<String, dynamic>)];
  }

  /// [month] is "YYYY-MM"; null means the current month.
  Future<LightReport> report(String societyId, {String? month}) async {
    final r = await _dio.get('/light-checks/$societyId/report', queryParameters: {if (month != null) 'month': month});
    return LightReport.fromJson(r.data as Map<String, dynamic>);
  }

  Future<void> replace(String pointId, {required String itemId, double quantity = 1, String? note}) =>
      _dio.post('/light-checks/point/$pointId/replace',
          data: {'item_id': itemId, 'quantity': quantity, if (note != null && note.isNotEmpty) 'note': note});
}

final lightsApiProvider = Provider<LightsApi>((_) => LightsApi());

typedef FloorsKey = ({String societyId, String wingId});
typedef SheetKey = ({String societyId, String wingId, int floor, String kind});

final lightFloorsProvider = FutureProvider.autoDispose.family<List<FloorOption>, FloorsKey>(
  (ref, k) => ref.watch(lightsApiProvider).floors(k.societyId, k.wingId),
);

final lightSheetProvider = FutureProvider.autoDispose.family<LightSheet, SheetKey>(
  (ref, k) => ref.watch(lightsApiProvider).sheet(k.societyId, k.wingId, k.floor, k.kind),
);

typedef ReportKey = ({String societyId, String? month});

final lightReportProvider = FutureProvider.autoDispose.family<LightReport, ReportKey>(
  (ref, k) => ref.watch(lightsApiProvider).report(k.societyId, month: k.month),
);

final brokenLightsProvider = FutureProvider.autoDispose.family<List<BrokenLight>, String>(
  (ref, societyId) => ref.watch(lightsApiProvider).notWorking(societyId),
);
