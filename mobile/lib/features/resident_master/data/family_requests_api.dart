import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';

DateTime? _date(dynamic v) => v == null ? null : DateTime.tryParse(v as String);

/// A resident's request to add a family member (or dependent) to their flat. It becomes a person on the Residents list
/// only when the office approves; until then nothing that reads that list (the gym's attendance book) can see them.
class FamilyRequest {
  final String id;
  final String flatId;
  final String? flatDisplay;
  final String fullName;

  /// 'family' or 'dependent'.
  final String residentType;
  final String? phone;
  final DateTime? dateOfBirth;
  final String? requesterName;

  /// 'pending', 'approved' or 'rejected'.
  final String status;
  final String? rejectionReason;
  final DateTime? createdAt;

  const FamilyRequest({
    required this.id,
    required this.flatId,
    this.flatDisplay,
    required this.fullName,
    required this.residentType,
    this.phone,
    this.dateOfBirth,
    this.requesterName,
    required this.status,
    this.rejectionReason,
    this.createdAt,
  });

  bool get isPending => status == 'pending';
  bool get isRejected => status == 'rejected';
  String get typeLabel => residentType == 'dependent' ? 'Dependent' : 'Family';

  factory FamilyRequest.fromJson(Map<String, dynamic> j) => FamilyRequest(
        id: j['id'] as String,
        flatId: j['flat_id'] as String,
        flatDisplay: j['flat_display'] as String?,
        fullName: j['full_name'] as String,
        residentType: j['resident_type'] as String? ?? 'family',
        phone: j['phone'] as String?,
        dateOfBirth: _date(j['date_of_birth']),
        requesterName: j['requester_name'] as String?,
        status: j['status'] as String? ?? 'pending',
        rejectionReason: j['rejection_reason'] as String?,
        createdAt: _date(j['created_at']),
      );
}

class FamilyRequestsApi {
  final Dio _dio;
  FamilyRequestsApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  String _iso(DateTime d) => '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  Future<FamilyRequest> create({
    required String fullName,
    required String residentType,
    String? phone,
    DateTime? dateOfBirth,
    String? flatId,
  }) async {
    final r = await _dio.post('/residents/family-requests', data: {
      'full_name': fullName,
      'resident_type': residentType,
      if (phone != null && phone.isNotEmpty) 'phone': phone,
      if (dateOfBirth != null) 'date_of_birth': _iso(dateOfBirth),
      if (flatId != null) 'flat_id': flatId,
    });
    return FamilyRequest.fromJson(r.data as Map<String, dynamic>);
  }

  Future<List<FamilyRequest>> mine() async => [
        for (final e in (await _dio.get('/residents/family-requests/mine')).data as List) FamilyRequest.fromJson(e as Map<String, dynamic>)
      ];

  Future<List<FamilyRequest>> pending() async => [
        for (final e in (await _dio.get('/residents/family-requests/pending')).data as List) FamilyRequest.fromJson(e as Map<String, dynamic>)
      ];

  Future<void> approve(String id) => _dio.post('/residents/family-requests/$id/approve');

  Future<void> reject(String id, String reason) => _dio.post('/residents/family-requests/$id/reject', data: {'reason': reason});
}

final familyRequestsApiProvider = Provider<FamilyRequestsApi>((_) => FamilyRequestsApi());

/// The signed-in resident's own requests, newest first.
final myFamilyRequestsProvider =
    FutureProvider.autoDispose<List<FamilyRequest>>((ref) => ref.watch(familyRequestsApiProvider).mine());

/// What the office has still to approve (Admin and committee only).
final pendingFamilyRequestsProvider =
    FutureProvider.autoDispose<List<FamilyRequest>>((ref) => ref.watch(familyRequestsApiProvider).pending());
