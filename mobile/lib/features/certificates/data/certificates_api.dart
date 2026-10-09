import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/utils/server_time.dart';

/// What a member can ask for: (code, title, needs the flat's dues to be clear).
const kCertificateKinds = <(String, String, bool)>[
  ('noc_sale', 'NOC for sale / transfer of flat', true),
  ('noc_rent', 'NOC for letting the flat', true),
  ('noc_loan', 'NOC for home loan / mortgage', true),
  ('noc_renovation', 'NOC for interior work / renovation', false),
  ('no_dues', 'No dues certificate', true),
  ('address_proof', 'Address / residence certificate', false),
  ('other', 'Other certificate', false),
];
const kTenantCertificateKinds = {'address_proof', 'other'};

class CertificateRequest {
  final String id, kind, title, status, applicantName;
  final String? flat, purpose, partyName, decisionNote, certificateNo;
  final double? duesAtDecision;
  final DateTime? decidedOn, createdAt;
  CertificateRequest.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        kind = j['kind'] as String,
        title = j['title'] as String,
        status = j['status'] as String,
        applicantName = j['applicant_name'] as String,
        flat = j['flat'] as String?,
        purpose = j['purpose'] as String?,
        partyName = j['party_name'] as String?,
        decisionNote = j['decision_note'] as String?,
        certificateNo = j['certificate_no'] as String?,
        duesAtDecision = (j['dues_at_decision'] as num?)?.toDouble(),
        decidedOn = j['decided_on'] == null
            ? null
            : DateTime.parse(j['decided_on'] as String),
        createdAt = parseStampOrNull(j['created_at']);

  bool get pending => status == 'pending';
  bool get approved => status == 'approved';
}

class CertificatesApi {
  final Dio _dio;
  CertificatesApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<List<CertificateRequest>> list(String sid) async => [
        for (final r
            in (await _dio.get('/certificates/society/$sid')).data as List)
          CertificateRequest.fromJson(r as Map<String, dynamic>)
      ];

  Future<CertificateRequest> request(String sid,
          {required String kind, String? purpose, String? partyName}) async =>
      CertificateRequest.fromJson(
          (await _dio.post('/certificates/society/$sid', data: {
        'kind': kind,
        if ((purpose ?? '').isNotEmpty) 'purpose': purpose,
        if ((partyName ?? '').isNotEmpty) 'party_name': partyName,
      }))
              .data as Map<String, dynamic>);

  Future<CertificateRequest> decide(String id,
          {required bool approve,
          String? note,
          bool overrideDues = false}) async =>
      CertificateRequest.fromJson(
          (await _dio.post('/certificates/$id/decision', data: {
        'approve': approve,
        if ((note ?? '').isNotEmpty) 'note': note,
        'override_dues': overrideDues,
      }))
              .data as Map<String, dynamic>);

  Future<void> cancel(String id) => _dio.post('/certificates/$id/cancel');

  /// [lang] is en, hi (Hindi) or mr (Marathi).
  Future<Uint8List> pdf(String id, {String lang = 'en'}) async {
    final r = await _dio.get<List<int>>('/certificates/$id/pdf',
        queryParameters: {'lang': lang},
        options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }
}

final certificatesApiProvider =
    Provider<CertificatesApi>((ref) => CertificatesApi());
final certificatesProvider = FutureProvider.autoDispose
    .family<List<CertificateRequest>, String>(
        (ref, sid) => ref.watch(certificatesApiProvider).list(sid));
