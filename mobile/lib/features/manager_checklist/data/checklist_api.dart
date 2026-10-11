import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';

DateTime? _date(Object? v) => v == null ? null : DateTime.tryParse(v.toString());
String apiDay(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// The kinds of frequency an item can have: (api value, label).
const kFrequencies = <(String, String)>[
  ('daily', 'Every day'),
  ('weekly', 'Every week'),
  ('monthly', 'Every month'),
  ('on_dates', 'On fixed dates (some months)'),
  ('licence', 'When a licence or certificate runs out'),
];
const kWeekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const kMonthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

class ItemLog {
  final String id;
  final DateTime forDate;
  final String status;
  final DateTime doneOn;
  final String? note, reference, doneBy;
  final DateTime? validUntil;
  ItemLog.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        forDate = DateTime.parse(j['for_date'] as String),
        status = j['status'] as String,
        doneOn = DateTime.parse(j['done_on'] as String),
        note = j['note'] as String?,
        reference = j['reference'] as String?,
        doneBy = j['done_by'] as String?,
        validUntil = _date(j['valid_until']);
}

class ChecklistEntry {
  final String id;
  final String? code;
  final String title;
  final String? detail;
  final String category, categoryLabel, frequency, schedule, group;
  final int? dueWeekday, dueDay;
  final List<int> dueMonths;
  final int leadDays;
  final String? assetCategory, staffDepartment, legalBasis, jurisdiction, jurisdictionLabel, linkKey;
  final bool statutory, isEnabled, isStandard, applicable;
  final String? appliesBecause;
  final DateTime? dueOn;
  final int? daysLeft;
  final String? state;
  final ItemLog? log;
  final DateTime? lastDoneOn;
  final String? lastReference;
  final DateTime? validUntil;

  ChecklistEntry.fromJson(Map<String, dynamic> j)
      : id = j['id'] as String,
        code = j['code'] as String?,
        title = j['title'] as String,
        detail = j['detail'] as String?,
        category = j['category'] as String,
        categoryLabel = j['category_label'] as String? ?? '',
        frequency = j['frequency'] as String,
        schedule = j['schedule'] as String? ?? '',
        group = j['group'] as String? ?? 'daily',
        dueWeekday = j['due_weekday'] as int?,
        dueDay = j['due_day'] as int?,
        dueMonths = [for (final m in (j['due_months'] as List? ?? const [])) m as int],
        leadDays = j['lead_days'] as int? ?? 0,
        assetCategory = j['asset_category'] as String?,
        staffDepartment = j['staff_department'] as String?,
        legalBasis = j['legal_basis'] as String?,
        jurisdiction = j['jurisdiction'] as String?,
        jurisdictionLabel = j['jurisdiction_label'] as String?,
        linkKey = j['link_key'] as String?,
        statutory = j['statutory'] as bool? ?? false,
        isEnabled = j['is_enabled'] as bool? ?? true,
        isStandard = j['is_standard'] as bool? ?? false,
        applicable = j['applicable'] as bool? ?? true,
        appliesBecause = j['applies_because'] as String?,
        dueOn = _date(j['due_on']),
        daysLeft = j['days_left'] as int?,
        state = j['state'] as String?,
        log = j['log'] == null ? null : ItemLog.fromJson(j['log'] as Map<String, dynamic>),
        lastDoneOn = _date(j['last_done_on']),
        lastReference = j['last_reference'] as String?,
        validUntil = _date(j['valid_until']);

  bool get isDone => state == 'done' || state == 'skipped';
  bool get isLicence => frequency == 'licence';

  /// Statutory dates and licences are recorded with a date and a reference rather than ticked.
  bool get needsRecord => group == 'compliance';
}

class LiveLine {
  final String key, category, severity, title;
  final String? linkKey, detail;
  final int count;
  LiveLine.fromJson(Map<String, dynamic> j)
      : key = j['key'] as String,
        category = j['category'] as String? ?? '',
        severity = j['severity'] as String? ?? 'info',
        title = j['title'] as String,
        linkKey = j['link_key'] as String?,
        detail = j['detail'] as String?,
        count = j['count'] as int? ?? 0;
}

class Signoff {
  final String? signedBy, remarks;
  final int routineTotal, routineDone, liveOpen;
  final DateTime? signedAt;
  Signoff.fromJson(Map<String, dynamic> j)
      : signedBy = j['signed_by'] as String?,
        remarks = j['remarks'] as String?,
        routineTotal = j['routine_total'] as int? ?? 0,
        routineDone = j['routine_done'] as int? ?? 0,
        liveOpen = j['live_open'] as int? ?? 0,
        signedAt = _date(j['signed_at']);
}

class Jurisdiction {
  final String? state;
  final bool statePackLoaded;
  final String note;
  final List<String> packs;
  Jurisdiction.fromJson(Map<String, dynamic> j)
      : state = j['state'] as String?,
        statePackLoaded = j['state_pack_loaded'] as bool? ?? false,
        note = j['note'] as String? ?? '',
        packs = [for (final p in (j['packs'] as List? ?? const [])) (p as Map)['label'] as String];
}

class TodaySummary {
  final int total, done, overdue, liveOpen, liveHigh, complianceUnrecorded, complianceUnconfirmed;
  TodaySummary.fromJson(Map<String, dynamic> j)
      : total = j['total'] as int? ?? 0,
        done = j['done'] as int? ?? 0,
        overdue = j['overdue'] as int? ?? 0,
        liveOpen = j['live_open'] as int? ?? 0,
        liveHigh = j['live_high'] as int? ?? 0,
        complianceUnrecorded = j['compliance_unrecorded'] as int? ?? 0,
        complianceUnconfirmed = j['compliance_unconfirmed'] as int? ?? 0;
}

class TodayChecklist {
  final DateTime asOf;
  final List<ChecklistEntry> items;
  final List<LiveLine> live;
  final TodaySummary summary;
  final Signoff? signoff;
  final Jurisdiction jurisdiction;
  TodayChecklist.fromJson(Map<String, dynamic> j)
      : asOf = DateTime.parse(j['as_of'] as String),
        items = [for (final i in (j['items'] as List)) ChecklistEntry.fromJson(i as Map<String, dynamic>)],
        live = [for (final i in (j['live'] as List)) LiveLine.fromJson(i as Map<String, dynamic>)],
        summary = TodaySummary.fromJson(j['summary'] as Map<String, dynamic>),
        signoff = j['signoff'] == null ? null : Signoff.fromJson(j['signoff'] as Map<String, dynamic>),
        jurisdiction = Jurisdiction.fromJson(j['jurisdiction'] as Map<String, dynamic>);
}

class ComplianceSummary {
  final int overdue, unconfirmed, soon, unrecorded, total;
  ComplianceSummary.fromJson(Map<String, dynamic> j)
      : overdue = j['overdue'] as int? ?? 0,
        unconfirmed = j['unconfirmed'] as int? ?? 0,
        soon = j['soon'] as int? ?? 0,
        unrecorded = j['unrecorded'] as int? ?? 0,
        total = j['total'] as int? ?? 0;
}

class ComplianceCalendar {
  final List<ChecklistEntry> items;
  final Jurisdiction jurisdiction;
  final ComplianceSummary summary;
  ComplianceCalendar.fromJson(Map<String, dynamic> j)
      : items = [for (final i in (j['items'] as List)) ChecklistEntry.fromJson(i as Map<String, dynamic>)],
        jurisdiction = Jurisdiction.fromJson(j['jurisdiction'] as Map<String, dynamic>),
        summary = ComplianceSummary.fromJson(j['summary'] as Map<String, dynamic>);
}

class Choice {
  final String key, label;
  Choice(this.key, this.label);
}

class ItemList {
  final List<ChecklistEntry> items;
  final Jurisdiction jurisdiction;
  final List<Choice> categories, assetCategories, departments;
  ItemList.fromJson(Map<String, dynamic> j)
      : items = [for (final i in (j['items'] as List)) ChecklistEntry.fromJson(i as Map<String, dynamic>)],
        jurisdiction = Jurisdiction.fromJson(j['jurisdiction'] as Map<String, dynamic>),
        categories = _choices(j['categories']),
        assetCategories = _choices(j['asset_categories']),
        departments = _choices(j['departments']);
  static List<Choice> _choices(Object? v) =>
      [for (final c in (v as List? ?? const [])) Choice((c as Map)['key'] as String, c['label'] as String)];
}

class ChecklistApi {
  final Dio _dio;
  ChecklistApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;
  static const _base = '/manager-checklist';

  Future<TodayChecklist> today(String societyId) async =>
      TodayChecklist.fromJson((await _dio.get('$_base/society/$societyId/today')).data as Map<String, dynamic>);

  Future<ComplianceCalendar> compliance(String societyId) async => ComplianceCalendar.fromJson(
      (await _dio.get('$_base/society/$societyId/compliance')).data as Map<String, dynamic>);

  Future<ItemList> items(String societyId) async =>
      ItemList.fromJson((await _dio.get('$_base/society/$societyId/items')).data as Map<String, dynamic>);

  Future<void> complete(String itemId,
          {String status = 'done', DateTime? doneOn, String? note, String? reference, DateTime? validUntil}) =>
      _dio.post('$_base/items/$itemId/complete', data: {
        'status': status,
        if (doneOn != null) 'done_on': apiDay(doneOn),
        if (note != null && note.trim().isNotEmpty) 'note': note.trim(),
        if (reference != null && reference.trim().isNotEmpty) 'reference': reference.trim(),
        if (validUntil != null) 'valid_until': apiDay(validUntil),
      });

  Future<void> undo(String itemId, DateTime forDate) =>
      _dio.delete('$_base/items/$itemId/complete', queryParameters: {'for_date': apiDay(forDate)});

  Future<void> create(String societyId, Map<String, dynamic> body) => _dio.post('$_base/society/$societyId/items', data: body);
  Future<void> update(String itemId, Map<String, dynamic> body) => _dio.patch('$_base/items/$itemId', data: body);
  Future<void> delete(String itemId) => _dio.delete('$_base/items/$itemId');

  Future<Signoff> signOff(String societyId, String? remarks) async => Signoff.fromJson(
      (await _dio.post('$_base/society/$societyId/signoff', data: {'remarks': remarks})).data as Map<String, dynamic>);

  Future<Uint8List> todayPdf(String societyId) async {
    final r = await _dio.get<List<int>>('$_base/society/$societyId/today.pdf',
        options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }
}

final checklistApiProvider = Provider<ChecklistApi>((_) => ChecklistApi());

final todayChecklistProvider = FutureProvider.autoDispose.family<TodayChecklist, String>(
    (ref, societyId) => ref.watch(checklistApiProvider).today(societyId));

final complianceProvider = FutureProvider.autoDispose.family<ComplianceCalendar, String>(
    (ref, societyId) => ref.watch(checklistApiProvider).compliance(societyId));

final checklistItemsProvider = FutureProvider.autoDispose.family<ItemList, String>(
    (ref, societyId) => ref.watch(checklistApiProvider).items(societyId));

void invalidateChecklist(WidgetRef ref) {
  ref.invalidate(todayChecklistProvider);
  ref.invalidate(complianceProvider);
  ref.invalidate(checklistItemsProvider);
}
