import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';

DateTime? _date(Object? v) => v == null ? null : DateTime.tryParse(v.toString());
String apiDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// (api value, label)
const kShopOccupancy = <(String, String)>[
  ('owner_run', 'Run by the owner'),
  ('rented', 'Rented out'),
  ('vacant', 'Vacant'),
];
String occupancyLabel(String v) => kShopOccupancy.where((e) => e.$1 == v).firstOrNull?.$2 ?? v;

class Shop {
  final String id;
  final String shopNumber;
  final int? floor;
  final String? location;
  final double? areaSqft;
  final String? businessName;
  final String ownerName;
  final String? ownerPhone;
  final String? ownerEmail;
  final String occupancy;
  final String? tenantName;
  final String? tenantPhone;
  final DateTime? possessionDate;
  final String? electricMeterNo;
  final String? electricConsumerNo;
  final String? remarks;

  Shop.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        shopNumber = j['shop_number'] as String,
        floor = j['floor'] as int?,
        location = j['location'] as String?,
        areaSqft = (j['area_sqft'] as num?)?.toDouble(),
        businessName = j['business_name'] as String?,
        ownerName = j['owner_name'] as String,
        ownerPhone = j['owner_phone'] as String?,
        ownerEmail = j['owner_email'] as String?,
        occupancy = j['occupancy'] as String? ?? 'vacant',
        tenantName = j['tenant_name'] as String?,
        tenantPhone = j['tenant_phone'] as String?,
        possessionDate = _date(j['possession_date']),
        electricMeterNo = j['electric_meter_no'] as String?,
        electricConsumerNo = j['electric_consumer_no'] as String?,
        remarks = j['remarks'] as String?;

  bool get rented => occupancy == 'rented';
  bool get vacant => occupancy == 'vacant';
  bool get hasMeter => (electricMeterNo ?? '').isNotEmpty;
}

/// One line of an import, as the server reads it.
class ImportOutcome {
  final int? line;
  final String? shopNumber;
  final String status; // created | updated | error
  final String? message;
  ImportOutcome.fromJson(Map<String, dynamic> j)
      : line = j['line'] as int?,
        shopNumber = j['shop_number'] as String?,
        status = j['status'] as String,
        message = j['message'] as String?;
}

class ShopsApi {
  final Dio _dio;
  ShopsApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<List<Shop>> list(String societyId) async {
    final r = await _dio.get('/shops/society/$societyId');
    return [for (final s in r.data as List) Shop.fromJson(s as Map<String, dynamic>)];
  }

  Future<Shop> create(Map<String, dynamic> body) async =>
      Shop.fromJson((await _dio.post('/shops/', data: body)).data as Map<String, dynamic>);

  Future<Shop> update(String id, Map<String, dynamic> body) async =>
      Shop.fromJson((await _dio.patch('/shops/$id', data: body)).data as Map<String, dynamic>);

  Future<void> delete(String id) => _dio.delete('/shops/$id');

  /// Rows are maps of the server's import fields (all text); `dryRun` checks them and writes nothing.
  Future<List<ImportOutcome>> importRows(List<Map<String, dynamic>> rows, {required bool dryRun}) async {
    final r = await _dio.post('/shops/import', data: {'rows': rows, 'dry_run': dryRun});
    return [for (final o in r.data as List) ImportOutcome.fromJson(o as Map<String, dynamic>)];
  }
}
