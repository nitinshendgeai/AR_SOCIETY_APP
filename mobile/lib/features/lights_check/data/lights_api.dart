import 'package:dio/dio.dart';
import 'package:intl/intl.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/utils/server_time.dart';

/// "5 Nov, 10:30 am" - the date and time a light was checked.
String lightStamp(DateTime d) => DateFormat('d MMM, h:mm a').format(d);

/// "28 Oct" - just the day, for "not working since".
String lightDay(DateTime d) => DateFormat('d MMM').format(d);

/// The kinds of thing that are checked on a floor: (api value, label).
const kLightKinds = <(String, String)>[('tube', 'Tube lights'), ('spot', 'Spot lights'), ('camera', 'Camera')];

/// What a common area can hold: (api value, label), in the order the form shows it.
const kAreaKinds = <(String, String)>[
  ('tube', 'Tube lights'),
  ('spot', 'Spot lights'),
  ('drum', 'Drum lights'),
  ('halogen', 'Halogens'),
  ('camera', 'Cameras'),
];

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
  final String? wingName, flatLabel, lastCheckedBy, areaName;
  final int? floorNumber;
  final DateTime? since, lastCheckedAt;
  const BrokenLight({
    required this.id,
    required this.kind,
    required this.label,
    this.floorNumber,
    this.areaName,
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
        floorNumber: j['floor_number'] as int?,
        areaName: j['area_name'] as String?,
        wingName: j['wing_name'] as String?,
        flatLabel: j['flat_label'] as String?,
        lastCheckedBy: j['last_checked_by'] as String?,
        since: parseStampOrNull(j['not_working_since']),
        lastCheckedAt: parseStampOrNull(j['last_checked_at']),
      );

  /// "Wing A · Floor 2 · Flat 201", "Wing A · Floor 2" for a floor's light, or the area ("Parking") for a common area's.
  String get where => areaName != null
      ? [areaName!, if (wingName != null) wingName!].join(' · ')
      : [
          if (wingName != null) wingName!,
          if (floorNumber != null) floorNumber == 0 ? 'Ground floor' : 'Floor $floorNumber',
          if (flatLabel != null) 'Flat $flatLabel',
        ].join(' · ');
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

  /// The wing's id, which the floor's lights are asked for with. Null only for a reply that does not carry it.
  final String? wingId;
  final int floorNumber, flats;
  final LightPart tube, spot, camera;
  const FloorReport({
    this.wingId,
    required this.wingName,
    required this.floorName,
    required this.floorNumber,
    required this.flats,
    required this.status,
    required this.tube,
    required this.spot,
    this.camera = const LightPart(),
  });
  factory FloorReport.fromJson(Map<String, dynamic> j) => FloorReport(
        wingId: j['wing_id'] as String?,
        wingName: j['wing_name'] as String,
        floorName: j['floor_name'] as String,
        floorNumber: j['floor_number'] as int,
        flats: j['flats'] as int,
        status: j['status'] as String,
        tube: LightPart.fromJson(j['tube'] as Map<String, dynamic>),
        spot: LightPart.fromJson(j['spot'] as Map<String, dynamic>),
        camera: j['camera'] == null ? const LightPart() : LightPart.fromJson(j['camera'] as Map<String, dynamic>),
      );

  int get notWorking => tube.notWorking + spot.notWorking + camera.notWorking;
}

/// One of a flat's three spot lights as it stood at the end of the month; [status] null: not checked that month.
class FlatLight {
  final String label;
  final String? status;
  final DateTime? checkedAt;
  const FlatLight(this.label, this.status, this.checkedAt);
}

class LightReport {
  final String month;
  final String? flatLabel;
  final List<FlatLight> flatLights;
  final List<AreaReport> areas;
  final int areasNotChecked, areasPartlyChecked;
  final int checked, working, notWorking, replaced, stillNotWorking, floorsNotChecked, floorsPartlyChecked;
  final List<FloorReport> floors;
  const LightReport({
    required this.month,
    this.flatLabel,
    this.flatLights = const [],
    this.areas = const [],
    this.areasNotChecked = 0,
    this.areasPartlyChecked = 0,
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
    final flat = j['flat'] as Map<String, dynamic>?;
    return LightReport(
      month: j['month'] as String,
      areas: [for (final a in (j['areas'] as List? ?? const [])) AreaReport.fromJson(a as Map<String, dynamic>)],
      areasNotChecked: (j['areas_not_checked'] as int?) ?? 0,
      areasPartlyChecked: (j['areas_partly_checked'] as int?) ?? 0,
      flatLabel: flat?['label'] as String?,
      flatLights: [
        for (final l in (flat?['lights'] as List? ?? const []))
          FlatLight((l as Map<String, dynamic>)['label'] as String, l['status'] as String?, parseStampOrNull(l['checked_at'])),
      ],
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

/// A common area as the Manager or Admin set it up: what it holds and how many of each.
class AreaItem {
  final String kind;
  final int count;
  const AreaItem(this.kind, this.count);
}

class CommonAreaInfo {
  final String id, name;
  final String? wingId, wingName;
  final List<AreaItem> items;
  const CommonAreaInfo({required this.id, required this.name, this.wingId, this.wingName, required this.items});

  factory CommonAreaInfo.fromJson(Map<String, dynamic> j) => CommonAreaInfo(
        id: j['id'] as String,
        name: j['name'] as String,
        wingId: j['wing_id'] as String?,
        wingName: j['wing_name'] as String?,
        items: [for (final i in j['items'] as List) AreaItem((i as Map<String, dynamic>)['kind'] as String, i['count'] as int)],
      );

  int countOf(String kind) => items.where((i) => i.kind == kind).fold(0, (n, i) => n + i.count);

  /// "4 tube lights · 2 cameras"
  String get summary => [
        for (final (kind, label) in kAreaKinds)
          if (countOf(kind) > 0)
            // every label is a plural ending in "s"; one of them reads better without it
            '${countOf(kind)} ${(countOf(kind) == 1 ? label.substring(0, label.length - 1) : label).toLowerCase()}'
      ].join(' · ');
}

/// One kind of thing in an area, in a month's report.
class AreaReportItem {
  final String kind, label;
  final LightPart part;
  const AreaReportItem(this.kind, this.label, this.part);
}

/// One common area in the monthly report. [status]: done | partial | not_checked.
class AreaReport {
  final String id, name, status;
  final String? wingName;
  final List<AreaReportItem> items;
  const AreaReport({required this.id, required this.name, required this.status, this.wingName, required this.items});

  factory AreaReport.fromJson(Map<String, dynamic> j) => AreaReport(
        id: j['id'] as String,
        name: j['name'] as String,
        status: j['status'] as String,
        wingName: j['wing_name'] as String?,
        items: [
          for (final i in j['items'] as List)
            AreaReportItem((i as Map<String, dynamic>)['kind'] as String, i['label'] as String, LightPart.fromJson(i)),
        ],
      );

  int get notWorking => items.fold(0, (n, i) => n + i.part.notWorking);
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

  // ── Common areas ──
  Future<List<CommonAreaInfo>> areas(String societyId) async {
    final r = await _dio.get('/light-checks/$societyId/areas');
    return [for (final e in r.data as List) CommonAreaInfo.fromJson(e as Map<String, dynamic>)];
  }

  Map<String, dynamic> _areaBody(String name, String? wingId, List<AreaItem> items) => {
        'name': name,
        if (wingId != null) 'wing_id': wingId,
        'items': [for (final i in items) {'kind': i.kind, 'count': i.count}],
      };

  Future<void> createArea(String societyId, {required String name, String? wingId, required List<AreaItem> items}) =>
      _dio.post('/light-checks/$societyId/areas', data: _areaBody(name, wingId, items));

  Future<void> updateArea(String areaId, {required String name, String? wingId, required List<AreaItem> items}) =>
      _dio.put('/light-checks/area/$areaId', data: _areaBody(name, wingId, items));

  Future<void> deleteArea(String areaId) => _dio.delete('/light-checks/area/$areaId');

  Future<LightSheet> areaSheet(String areaId) async =>
      LightSheet.fromJson((await _dio.get('/light-checks/area/$areaId/sheet')).data as Map<String, dynamic>);

  /// Returns how many were marked not working.
  Future<int> checkArea(String areaId, List<Map<String, dynamic>> results) async {
    final r = await _dio.post('/light-checks/area/$areaId/check', data: {'results': results});
    return (r.data as Map<String, dynamic>)['not_working'] as int;
  }

  Future<List<BrokenLight>> notWorking(String societyId) async {
    final r = await _dio.get('/light-checks/$societyId/not-working');
    return [for (final e in (r.data as Map<String, dynamic>)['rows'] as List) BrokenLight.fromJson(e as Map<String, dynamic>)];
  }

  /// [month] is "YYYY-MM"; null means the current month.
  /// Narrowed to a [wingId], a [floor] of it, or one [flatId] (its spot lights).
  Future<LightReport> report(String societyId, {String? month, String? wingId, int? floor, String? flatId}) async {
    final r = await _dio.get('/light-checks/$societyId/report', queryParameters: {
      if (month != null) 'month': month,
      if (wingId != null) 'wing_id': wingId,
      if (floor != null) 'floor_number': floor,
      if (flatId != null) 'flat_id': flatId,
    });
    return LightReport.fromJson(r.data as Map<String, dynamic>);
  }

  /// [itemId] is the tube or bulb taken from the store; a camera put right needs none.
  Future<void> replace(String pointId, {String? itemId, double quantity = 1, String? note}) =>
      _dio.post('/light-checks/point/$pointId/replace', data: {
        if (itemId != null) 'item_id': itemId,
        if (itemId != null) 'quantity': quantity,
        if (note != null && note.isNotEmpty) 'note': note,
      });
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

typedef ReportKey = ({String societyId, String? month, String? wingId, int? floor, String? flatId});

final lightReportProvider = FutureProvider.autoDispose.family<LightReport, ReportKey>(
  (ref, k) => ref.watch(lightsApiProvider).report(k.societyId, month: k.month, wingId: k.wingId, floor: k.floor, flatId: k.flatId),
);

final lightAreasProvider = FutureProvider.autoDispose.family<List<CommonAreaInfo>, String>(
  (ref, societyId) => ref.watch(lightsApiProvider).areas(societyId),
);

final lightAreaSheetProvider = FutureProvider.autoDispose.family<LightSheet, String>(
  (ref, areaId) => ref.watch(lightsApiProvider).areaSheet(areaId),
);

final brokenLightsProvider = FutureProvider.autoDispose.family<List<BrokenLight>, String>(
  (ref, societyId) => ref.watch(lightsApiProvider).notWorking(societyId),
);
