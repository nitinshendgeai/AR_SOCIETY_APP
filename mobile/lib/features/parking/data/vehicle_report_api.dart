import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';

Map<String, dynamic> _m(Object? v) => (v as Map?)?.cast<String, dynamic>() ?? const {};
List<Map<String, dynamic>> _l(Object? v) => [for (final e in (v as List? ?? const [])) (e as Map).cast<String, dynamic>()];

/// The vehicle report: four parts, each a `summary` of numbers and lists of rows. The screen gets the first rows of
/// each list; [rowCount] says how many there are in all, and the downloaded file carries every one.
class VehicleReport {
  final String month, monthLabel, asOn;
  final String? wing, flat;
  final Map<String, dynamic> vehicles, parking, violations, gate;
  const VehicleReport({
    required this.month,
    required this.monthLabel,
    required this.asOn,
    this.wing,
    this.flat,
    required this.vehicles,
    required this.parking,
    required this.violations,
    required this.gate,
  });

  factory VehicleReport.fromJson(Map<String, dynamic> j) => VehicleReport(
        month: j['month'] as String,
        monthLabel: j['month_label'] as String,
        asOn: j['as_on'] as String,
        wing: j['wing'] as String?,
        flat: j['flat'] as String?,
        vehicles: _m(j['vehicles']),
        parking: _m(j['parking']),
        violations: _m(j['violations']),
        gate: _m(j['gate']),
      );

  Map<String, dynamic> summaryOf(Map<String, dynamic> part) => _m(part['summary']);
  List<Map<String, dynamic>> rowsOf(Map<String, dynamic> part, [String key = 'rows']) => _l(part[key]);
  int rowCountOf(Map<String, dynamic> part) => (part['row_count'] as int?) ?? rowsOf(part).length;
}

class VehicleReportApi {
  final Dio _dio;
  VehicleReportApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Map<String, dynamic> _query(String? month, String? wingId, String? flatId) => {
        if (month != null) 'month': month,
        if (wingId != null) 'wing_id': wingId,
        if (flatId != null) 'flat_id': flatId,
      };

  Future<VehicleReport> report(String societyId, {String? month, String? wingId, String? flatId}) async {
    final r = await _dio.get('/parking/report/$societyId', queryParameters: _query(month, wingId, flatId));
    return VehicleReport.fromJson(r.data as Map<String, dynamic>);
  }

  /// Deregister vehicles (committee or admin): off the active lists, their RFID tags cleared and their parking freed;
  /// the records are kept. [notFound] counts ids that were not an active vehicle of the society.
  Future<({int deregistered, int notFound})> deregister(List<String> vehicleIds) async {
    final r = await _dio.post('/vehicles/deregister', data: {'vehicle_ids': vehicleIds});
    final j = r.data as Map<String, dynamic>;
    return (deregistered: (j['deregistered'] as num).toInt(), notFound: (j['not_found'] as num).toInt());
  }

  /// The whole report as a PDF (`pdf`) or an Excel file (`xlsx`).
  Future<Uint8List> file(String societyId, String format, {String? month, String? wingId, String? flatId}) async {
    final r = await _dio.get<List<int>>('/parking/report/$societyId/file',
        queryParameters: {'format': format, ..._query(month, wingId, flatId)},
        options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }
}

final vehicleReportApiProvider = Provider<VehicleReportApi>((_) => VehicleReportApi());

typedef VehicleReportKey = ({String societyId, String? month, String? wingId, String? flatId});

final vehicleReportProvider = FutureProvider.autoDispose.family<VehicleReport, VehicleReportKey>(
  (ref, k) => ref.watch(vehicleReportApiProvider).report(k.societyId, month: k.month, wingId: k.wingId, flatId: k.flatId),
);
