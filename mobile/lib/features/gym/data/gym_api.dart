import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';

/// The words for a member's relationship to the flat, as the server sends it.
const kGymMemberTypes = {'owner': 'Owner', 'co_owner': 'Co-owner', 'family': 'Family', 'dependent': 'Dependent'};

DateTime? _time(dynamic v) => v == null ? null : DateTime.tryParse(v as String)?.toLocal();

/// One person on a flat's list at the gym desk.
class GymMember {
  final String residentId;
  final String name;
  final String memberType;
  final bool inside;
  final String? visitId;
  const GymMember({required this.residentId, required this.name, required this.memberType, required this.inside, this.visitId});

  String get typeLabel => kGymMemberTypes[memberType] ?? memberType;

  factory GymMember.fromJson(Map<String, dynamic> j) => GymMember(
        residentId: j['resident_id'] as String,
        name: j['name'] as String,
        memberType: j['member_type'] as String? ?? '',
        inside: j['inside'] == true,
        visitId: j['visit_id'] as String?,
      );
}

/// The members of one flat who may use the gym: the owners' side only, never tenants.
class GymFlatMembers {
  final String flatId;
  final String flatLabel;
  final bool letToTenants;
  final List<GymMember> members;
  const GymFlatMembers({required this.flatId, required this.flatLabel, required this.letToTenants, required this.members});

  factory GymFlatMembers.fromJson(Map<String, dynamic> j) => GymFlatMembers(
        flatId: j['flat_id'] as String,
        flatLabel: j['flat_label'] as String,
        letToTenants: j['let_to_tenants'] == true,
        members: [for (final m in (j['members'] as List? ?? const [])) GymMember.fromJson(m as Map<String, dynamic>)],
      );
}

/// A visit: someone ticked in, and (once they leave) out.
class GymVisitRow {
  final String visitId;
  final String name;
  final String flatLabel;
  final DateTime? checkedInAt;
  final int? minutesInside;
  const GymVisitRow({required this.visitId, required this.name, required this.flatLabel, this.checkedInAt, this.minutesInside});

  factory GymVisitRow.fromJson(Map<String, dynamic> j) => GymVisitRow(
        visitId: j['visit_id'] as String,
        name: j['name'] as String,
        flatLabel: j['flat_label'] as String,
        checkedInAt: _time(j['checked_in_at']),
        minutesInside: j['minutes_inside'] as int?,
      );
}

/// The gym right now: who is inside, how many came and left today.
class GymLive {
  final int insideNow;
  final int checkedInToday;
  final int checkedOutToday;
  final List<GymVisitRow> inside;

  /// Ticked in on an earlier day and never ticked out.
  final List<GymVisitRow> earlierOpen;
  const GymLive({required this.insideNow, required this.checkedInToday, required this.checkedOutToday,
      required this.inside, required this.earlierOpen});

  factory GymLive.fromJson(Map<String, dynamic> j) => GymLive(
        insideNow: j['inside_now'] as int? ?? 0,
        checkedInToday: j['checked_in_today'] as int? ?? 0,
        checkedOutToday: j['checked_out_today'] as int? ?? 0,
        inside: [for (final v in (j['inside'] as List? ?? const [])) GymVisitRow.fromJson(v as Map<String, dynamic>)],
        earlierOpen: [for (final v in (j['earlier_open'] as List? ?? const [])) GymVisitRow.fromJson(v as Map<String, dynamic>)],
      );
}

class GymDay {
  final DateTime date;
  final int visits;
  final int uniqueMembers;
  const GymDay({required this.date, required this.visits, required this.uniqueMembers});

  factory GymDay.fromJson(Map<String, dynamic> j) => GymDay(
        date: DateTime.parse(j['date'] as String),
        visits: j['visits'] as int? ?? 0,
        uniqueMembers: j['unique_members'] as int? ?? 0,
      );
}

class GymReportMember {
  final String name;
  final String flatLabel;
  final int visits;
  final int totalMinutes;
  const GymReportMember({required this.name, required this.flatLabel, required this.visits, required this.totalMinutes});

  factory GymReportMember.fromJson(Map<String, dynamic> j) => GymReportMember(
        name: j['name'] as String,
        flatLabel: j['flat_label'] as String,
        visits: j['visits'] as int? ?? 0,
        totalMinutes: j['total_minutes'] as int? ?? 0,
      );
}

/// A week (Monday to Sunday) or a calendar month of the gym's attendance.
class GymReport {
  final String period;
  final DateTime from;
  final DateTime to;
  final String label;
  final int visits;
  final int uniqueMembers;
  final int uniqueFlats;
  final int? averageMinutes;
  final int notCheckedOut;
  final List<GymDay> days;
  final List<GymReportMember> members;
  const GymReport({required this.period, required this.from, required this.to, required this.label, required this.visits,
      required this.uniqueMembers, required this.uniqueFlats, required this.averageMinutes, required this.notCheckedOut,
      required this.days, required this.members});

  factory GymReport.fromJson(Map<String, dynamic> j) {
    final t = j['totals'] as Map<String, dynamic>;
    return GymReport(
      period: j['period'] as String,
      from: DateTime.parse(j['from'] as String),
      to: DateTime.parse(j['to'] as String),
      label: j['label'] as String,
      visits: t['visits'] as int? ?? 0,
      uniqueMembers: t['unique_members'] as int? ?? 0,
      uniqueFlats: t['unique_flats'] as int? ?? 0,
      averageMinutes: t['average_minutes'] as int?,
      notCheckedOut: t['not_checked_out'] as int? ?? 0,
      days: [for (final d in (j['days'] as List? ?? const [])) GymDay.fromJson(d as Map<String, dynamic>)],
      members: [for (final m in (j['members'] as List? ?? const [])) GymReportMember.fromJson(m as Map<String, dynamic>)],
    );
  }
}

/// The key of a report: the period and a day inside it (null: today).
typedef GymReportKey = ({String period, String? on});

String _isoDay(DateTime d) => '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

class GymApi {
  final Dio _dio;
  GymApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<GymFlatMembers> flatMembers(String flatId) async =>
      GymFlatMembers.fromJson((await _dio.get('/gym/flats/$flatId/members')).data as Map<String, dynamic>);

  /// Ticks [residentIds] of [flatId] in. Returns the names that were already inside (and so not counted again).
  Future<({int checkedIn, List<String> alreadyInside})> checkIn(String flatId, List<String> residentIds) async {
    final r = await _dio.post('/gym/check-in', data: {'flat_id': flatId, 'resident_ids': residentIds});
    final j = r.data as Map<String, dynamic>;
    return (
      checkedIn: (j['checked_in'] as List? ?? const []).length,
      alreadyInside: [for (final n in (j['already_inside'] as List? ?? const [])) n as String],
    );
  }

  Future<int> checkOut(List<String> visitIds) async {
    final r = await _dio.post('/gym/check-out', data: {'visit_ids': visitIds});
    return (r.data as Map<String, dynamic>)['checked_out'] as int? ?? 0;
  }

  Future<int> checkOutAll() async {
    final r = await _dio.post('/gym/check-out-all');
    return (r.data as Map<String, dynamic>)['checked_out'] as int? ?? 0;
  }

  Future<GymLive> live() async => GymLive.fromJson((await _dio.get('/gym/live')).data as Map<String, dynamic>);

  Future<GymReport> report(String period, {DateTime? on}) async => GymReport.fromJson((await _dio.get('/gym/report',
      queryParameters: {'period': period, if (on != null) 'on': _isoDay(on)})).data as Map<String, dynamic>);

  Future<Uint8List> reportPdf(String period, {DateTime? on}) async {
    final r = await _dio.get<List<int>>('/gym/report',
        queryParameters: {'period': period, 'format': 'pdf', if (on != null) 'on': _isoDay(on)},
        options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }
}

final gymApiProvider = Provider<GymApi>((_) => GymApi());

/// Who is in the gym now. Reloaded after every tick and by pulling down.
final gymLiveProvider = FutureProvider.autoDispose<GymLive>((ref) => ref.watch(gymApiProvider).live());

final gymFlatMembersProvider = FutureProvider.autoDispose.family<GymFlatMembers, String>(
    (ref, flatId) => ref.watch(gymApiProvider).flatMembers(flatId));
