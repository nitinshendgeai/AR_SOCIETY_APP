import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/governance/data/governance_api.dart' show apiDay;

/// The offices of a managing committee, in the order they are listed.
const kCommitteePositions = <(String, String)>[
  ('chairman', 'Chairman'),
  ('vice_chairman', 'Vice-Chairman'),
  ('secretary', 'Secretary'),
  ('joint_secretary', 'Joint Secretary'),
  ('treasurer', 'Treasurer'),
  ('member', 'Committee Member'),
  ('co_opted', 'Co-opted Member'),
  ('invitee', 'Special Invitee'),
];

String positionLabel(String key) => _labelOf(key);
String _labelOf(String key) => kCommitteePositions.where((p) => p.$1 == key).firstOrNull?.$2 ?? key;

DateTime? _d(Object? v) => v == null ? null : DateTime.tryParse('$v');

class CommitteeMember {
  final String id;
  final String fullName;
  final String? flat;
  final String position;
  final String positionLabel;
  final String? phone;
  final String? email;
  final DateTime fromDate;
  final DateTime? toDate;
  final bool chequeSignatory;
  final bool approvesPayments;
  final bool signsDocuments;
  final int? spendingLimit;
  final List<String> authorities;
  final String? responsibilities;
  const CommitteeMember(this.id, this.fullName, this.flat, this.position, this.positionLabel, this.phone, this.email,
      this.fromDate, this.toDate, this.chequeSignatory, this.approvesPayments, this.signsDocuments, this.spendingLimit,
      this.authorities, this.responsibilities);
  factory CommitteeMember.fromJson(Map<String, dynamic> j) => CommitteeMember(
        j['id'] as String,
        j['full_name'] as String? ?? '',
        j['flat'] as String?,
        j['position'] as String? ?? 'member',
        j['position_label'] as String? ?? _labelOf(j['position'] as String? ?? 'member'),
        j['phone'] as String?,
        j['email'] as String?,
        _d(j['from_date']) ?? DateTime.now(),
        _d(j['to_date']),
        j['cheque_signatory'] as bool? ?? false,
        j['approves_payments'] as bool? ?? false,
        j['signs_documents'] as bool? ?? false,
        (j['spending_limit'] as num?)?.toInt(),
        [for (final a in (j['authorities'] as List? ?? const [])) '$a'],
        j['responsibilities'] as String?,
      );
}

class Committee {
  final String id;
  final String name;
  final DateTime formedOn;
  final DateTime? termEndsOn;
  final int? daysLeft;
  final bool termOver;
  final String? electionNote;
  final List<CommitteeMember> members;
  final List<CommitteeMember> formerMembers;
  final List<String> warnings;
  const Committee(this.id, this.name, this.formedOn, this.termEndsOn, this.daysLeft, this.termOver, this.electionNote,
      this.members, this.formerMembers, this.warnings);
  factory Committee.fromJson(Map<String, dynamic> j) => Committee(
        j['id'] as String,
        j['name'] as String? ?? '',
        _d(j['formed_on']) ?? DateTime.now(),
        _d(j['term_ends_on']),
        (j['days_left'] as num?)?.toInt(),
        j['term_over'] as bool? ?? false,
        j['election_note'] as String?,
        [for (final m in (j['members'] as List? ?? const [])) CommitteeMember.fromJson((m as Map).cast<String, dynamic>())],
        [for (final m in (j['former_members'] as List? ?? const [])) CommitteeMember.fromJson((m as Map).cast<String, dynamic>())],
        [for (final w in (j['warnings'] as List? ?? const [])) '$w'],
      );
}

class CommitteeRegister {
  final Committee? current;
  final List<Committee> past;
  const CommitteeRegister(this.current, this.past);
  factory CommitteeRegister.fromJson(Map<String, dynamic> j) => CommitteeRegister(
        j['current'] == null ? null : Committee.fromJson((j['current'] as Map).cast<String, dynamic>()),
        [for (final c in (j['past'] as List? ?? const [])) Committee.fromJson((c as Map).cast<String, dynamic>())],
      );
}

/// What the "add member" form sends: the resident chosen (name, flat and contacts come from them) or a name typed in.
Map<String, dynamic> committeeMemberPayload({
  String? residentId,
  String? fullName,
  String? flat,
  required String position,
  String? phone,
  String? email,
  DateTime? fromDate,
  bool? chequeSignatory,
  bool? approvesPayments,
  bool? signsDocuments,
  String? spendingLimit,
  String? responsibilities,
  bool replace = false,
}) {
  String? clean(String? s) => (s == null || s.trim().isEmpty) ? null : s.trim();
  if (residentId == null && clean(fullName) == null) {
    throw const FormatException('Choose the resident or type the member\'s name');
  }
  final limit = clean(spendingLimit)?.replaceAll(',', '');
  if (limit != null && int.tryParse(limit) == null) throw const FormatException('The spending limit must be a number');
  return {
    if (residentId != null) 'resident_id': residentId,
    if (clean(fullName) != null) 'full_name': clean(fullName),
    if (clean(flat) != null) 'flat': clean(flat),
    'position': position,
    if (clean(phone) != null) 'phone': clean(phone),
    if (clean(email) != null) 'email': clean(email),
    if (fromDate != null) 'from_date': apiDay(fromDate),
    if (chequeSignatory != null) 'cheque_signatory': chequeSignatory,
    if (approvesPayments != null) 'approves_payments': approvesPayments,
    if (signsDocuments != null) 'signs_documents': signsDocuments,
    if (limit != null) 'spending_limit': int.parse(limit),
    if (clean(responsibilities) != null) 'responsibilities': clean(responsibilities),
    if (replace) 'replace': true,
  };
}

class CommitteeApi {
  final Dio _dio;
  CommitteeApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;
  static const _b = '/governance/committee';

  Future<CommitteeRegister> register(String sid) async =>
      CommitteeRegister.fromJson((await _dio.get('$_b/society/$sid')).data as Map<String, dynamic>);

  Future<Committee> create(String sid, {required DateTime formedOn, DateTime? termEndsOn, String? name, String? note}) async =>
      Committee.fromJson((await _dio.post('$_b/society/$sid', data: {
        'formed_on': apiDay(formedOn),
        if (termEndsOn != null) 'term_ends_on': apiDay(termEndsOn),
        if ((name ?? '').trim().isNotEmpty) 'name': name!.trim(),
        if ((note ?? '').trim().isNotEmpty) 'election_note': note!.trim(),
      })).data as Map<String, dynamic>);

  Future<Committee> addMember(String committeeId, Map<String, dynamic> body) async =>
      Committee.fromJson((await _dio.post('$_b/$committeeId/members', data: body)).data as Map<String, dynamic>);

  Future<Committee> updateMember(String memberId, Map<String, dynamic> changes) async =>
      Committee.fromJson((await _dio.put('$_b/members/$memberId', data: changes)).data as Map<String, dynamic>);

  Future<Committee> removeMember(String memberId) async =>
      Committee.fromJson((await _dio.delete('$_b/members/$memberId')).data as Map<String, dynamic>);
}

final committeeApiProvider = Provider<CommitteeApi>((_) => CommitteeApi());

final committeeRegisterProvider = FutureProvider.autoDispose.family<CommitteeRegister, String>(
    (ref, sid) => ref.watch(committeeApiProvider).register(sid));
