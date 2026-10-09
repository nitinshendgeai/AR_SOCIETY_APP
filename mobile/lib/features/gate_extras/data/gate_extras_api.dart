import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/utils/server_time.dart';

// ── Parcels ──────────────────────────────────────────────────────────────────

class Parcel {
  final String id, flatId, status;
  final String? flat,
      courier,
      description,
      recipientName,
      collectedByName,
      note;
  final DateTime? receivedAt, collectedAt;
  Parcel.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        flatId = j['flat_id'] as String,
        status = j['status'] as String,
        flat = j['flat'] as String?,
        courier = j['courier'] as String?,
        description = j['description'] as String?,
        recipientName = j['recipient_name'] as String?,
        collectedByName = j['collected_by_name'] as String?,
        note = j['note'] as String?,
        receivedAt = parseStampOrNull(j['received_at']),
        collectedAt = parseStampOrNull(j['collected_at']);
  bool get atGate => status == 'at_gate';
}

// ── Domestic help ────────────────────────────────────────────────────────────

const kHelpKinds = <(String, String)>[
  ('maid', 'Maid'),
  ('cook', 'Cook'),
  ('driver', 'Driver'),
  ('nanny', 'Nanny'),
  ('cleaner', 'Cleaner'),
  ('gardener', 'Gardener'),
  ('other', 'Other'),
];
String helpKindLabel(String v) =>
    kHelpKinds.where((e) => e.$1 == v).firstOrNull?.$2 ?? v;

class HelpFlat {
  final String flatId, label;
  HelpFlat.fromJson(Map<String, dynamic> j)
      : flatId = j['flat_id'] as String,
        label = j['label'] as String;
}

class DomesticHelp {
  final String id, name, mobile, kind, status, effectiveStatus;
  final String? idProof, passNo, note;
  final bool policeVerified, inside;
  final DateTime? validUntil, inAt;
  final List<HelpFlat> flats;
  DomesticHelp.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        name = j['name'] as String,
        mobile = j['mobile'] as String,
        kind = j['kind'] as String,
        status = j['status'] as String,
        effectiveStatus = j['effective_status'] as String,
        idProof = j['id_proof'] as String?,
        passNo = j['pass_no'] as String?,
        note = j['note'] as String?,
        policeVerified = j['police_verified'] as bool? ?? false,
        inside = j['inside'] as bool? ?? false,
        validUntil = j['valid_until'] == null
            ? null
            : DateTime.parse(j['valid_until'] as String),
        inAt = parseStampOrNull(j['in_at']),
        flats = [
          for (final f in (j['flats'] as List))
            HelpFlat.fromJson(f as Map<String, dynamic>)
        ];
  bool get active => effectiveStatus == 'active';
}

class HelpEntry {
  final DateTime? inAt, outAt;
  HelpEntry.fromJson(Map<String, dynamic> j)
      : inAt = parseStampOrNull(j['in_at']),
        outAt = parseStampOrNull(j['out_at']);
}

class ScanResult {
  final String direction, name, kind;
  final List<String> flats;
  ScanResult.fromJson(Map<String, dynamic> j)
      : direction = j['direction'] as String,
        name = j['name'] as String,
        kind = j['kind'] as String,
        flats = [for (final f in (j['flats'] as List)) f as String];
}

class GateExtrasApi {
  final Dio _dio;
  GateExtrasApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  List<T> _list<T>(Response r, T Function(Map<String, dynamic>) f) =>
      [for (final x in r.data as List) f(x as Map<String, dynamic>)];

  Future<List<Parcel>> parcels(String sid) async =>
      _list(await _dio.get('/gate/parcels/society/$sid'), Parcel.fromJson);

  Future<void> logParcel(String sid,
          {required String flatId,
          String? courier,
          String? description,
          String? recipientName}) =>
      _dio.post('/gate/parcels/society/$sid', data: {
        'flat_id': flatId,
        if ((courier ?? '').isNotEmpty) 'courier': courier,
        if ((description ?? '').isNotEmpty) 'description': description,
        if ((recipientName ?? '').isNotEmpty) 'recipient_name': recipientName,
      });

  Future<void> collectParcel(String id, {String? collectedBy}) =>
      _dio.post('/gate/parcels/$id/collect', data: {
        if ((collectedBy ?? '').isNotEmpty) 'collected_by_name': collectedBy
      });

  Future<void> returnParcel(String id, {String? note}) =>
      _dio.post('/gate/parcels/$id/return',
          data: {if ((note ?? '').isNotEmpty) 'note': note});

  Future<List<DomesticHelp>> help(String sid, {String? q}) async => _list(
      await _dio.get('/gate/help/society/$sid',
          queryParameters: {if ((q ?? '').isNotEmpty) 'q': q}),
      DomesticHelp.fromJson);

  Future<void> register(String sid,
          {required String name,
          required String mobile,
          required String kind,
          String? idProof,
          List<String>? flatIds}) =>
      _dio.post('/gate/help/society/$sid', data: {
        'name': name,
        'mobile': mobile,
        'kind': kind,
        if ((idProof ?? '').isNotEmpty) 'id_proof': idProof,
        if (flatIds != null) 'flat_ids': flatIds,
      });

  Future<void> approve(String id,
          {DateTime? validUntil, bool? policeVerified}) =>
      _dio.post('/gate/help/$id/approve', data: {
        if (validUntil != null) 'valid_until': _day(validUntil),
        if (policeVerified != null) 'police_verified': policeVerified,
      });

  Future<void> setStatus(String id, String status, {String? note}) =>
      _dio.post('/gate/help/$id/status',
          data: {'status': status, if ((note ?? '').isNotEmpty) 'note': note});

  Future<void> renew(String id) => _dio.post('/gate/help/$id/renew', data: {});

  Future<void> removeFlat(String id, String flatId) =>
      _dio.delete('/gate/help/$id/flats/$flatId');

  Future<ScanResult> scan(String id) async => ScanResult.fromJson(
      (await _dio.post('/gate/help/$id/scan')).data as Map<String, dynamic>);

  Future<List<HelpEntry>> entries(String id) async =>
      _list(await _dio.get('/gate/help/$id/entries'), HelpEntry.fromJson);

  Future<Uint8List> pass(String id) async {
    final r = await _dio.get<List<int>>('/gate/help/$id/pass',
        options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }

  static String _day(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}

final gateExtrasApiProvider = Provider<GateExtrasApi>((ref) => GateExtrasApi());
final parcelsProvider = FutureProvider.autoDispose.family<List<Parcel>, String>(
    (ref, sid) => ref.watch(gateExtrasApiProvider).parcels(sid));
final domesticHelpProvider = FutureProvider.autoDispose
    .family<List<DomesticHelp>, String>(
        (ref, sid) => ref.watch(gateExtrasApiProvider).help(sid));
