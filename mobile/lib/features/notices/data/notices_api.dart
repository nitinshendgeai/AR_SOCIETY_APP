import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

DateTime? _dt(Object? v) => v == null ? null : DateTime.tryParse(v.toString());

/// (api value, label, icon)
const kNoticeCategories = <(String, String, IconData)>[
  ('general', 'General', Icons.campaign_outlined),
  ('maintenance', 'Maintenance', Icons.build_outlined),
  ('water_shutdown', 'Water shutdown', Icons.water_drop_outlined),
  ('power_shutdown', 'Power shutdown', Icons.power_off_outlined),
  ('finance', 'Finance', Icons.currency_rupee_rounded),
  ('events', 'Events', Icons.celebration_outlined),
  ('security', 'Security', Icons.shield_outlined),
  ('parking', 'Parking', Icons.local_parking_rounded),
  ('amenities', 'Amenities', Icons.pool_outlined),
  ('staff_notice', 'For staff', Icons.badge_outlined),
  ('emergency', 'Emergency', Icons.warning_amber_rounded),
];
String noticeCategoryLabel(String c) => kNoticeCategories.where((e) => e.$1 == c).firstOrNull?.$2 ?? c;
IconData noticeCategoryIcon(String c) => kNoticeCategories.where((e) => e.$1 == c).firstOrNull?.$3 ?? Icons.campaign_outlined;

const kNoticePriorities = <(String, String)>[('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')];
Color noticePriorityColor(String p) => switch (p) {
      'urgent' => AppTheme.error,
      'high' => AppTheme.warning,
      'low' => AppTheme.textSecondary,
      _ => AppTheme.primary,
    };
String noticePriorityLabel(String p) => kNoticePriorities.where((e) => e.$1 == p).firstOrNull?.$2 ?? p;

/// (api value, label, hint)
const kAudiences = <(String, String, String)>[
  ('all', 'Everyone', 'Residents, tenants, staff and the committee'),
  ('all_residents', 'All residents and tenants', 'Everyone who lives in the society'),
  ('owners_only', 'Owners only', 'Flat owners and co-owners'),
  ('tenants_only', 'Tenants only', 'People renting a flat'),
  ('specific_wings', 'Chosen wings', 'The residents of the wings you pick'),
  ('specific_flats', 'Chosen flats', 'The residents of the flats you pick'),
  ('all_staff', 'All staff', 'Manager, supervisors and staff'),
  ('security_team', 'Security team', 'Security supervisor and guards'),
  ('committee', 'Committee', 'Admin and committee members'),
];
String audienceLabel(String a) => kAudiences.where((e) => e.$1 == a).firstOrNull?.$2 ?? a;

class NoticeItem {
  final String id;
  final String title;
  final String content;
  final String category;
  final String priority;
  final String status; // draft | published | archived
  final DateTime? publishDate;
  final DateTime? expiryDate;
  final bool ackRequired;
  final String audience;
  final List<String> wingIds;
  final List<String> flatIds;
  final int totalAudience;
  final int ackCount;
  final String? createdByName;
  final DateTime? createdAt;
  final bool isExpired;
  final bool? acknowledged;

  const NoticeItem({
    required this.id,
    required this.title,
    required this.content,
    required this.category,
    required this.priority,
    required this.status,
    this.publishDate,
    this.expiryDate,
    this.ackRequired = false,
    this.audience = 'all',
    this.wingIds = const [],
    this.flatIds = const [],
    this.totalAudience = 0,
    this.ackCount = 0,
    this.createdByName,
    this.createdAt,
    this.isExpired = false,
    this.acknowledged,
  });

  factory NoticeItem.fromJson(Map<String, dynamic> j) => NoticeItem(
        id: j['id'] as String,
        title: j['title'] as String? ?? '',
        content: j['content'] as String? ?? '',
        category: j['category'] as String? ?? 'general',
        priority: j['priority'] as String? ?? 'normal',
        status: j['status'] as String? ?? 'draft',
        publishDate: _dt(j['publish_date']),
        expiryDate: _dt(j['expiry_date']),
        ackRequired: j['acknowledgement_required'] as bool? ?? false,
        audience: j['audience_type'] as String? ?? 'all',
        wingIds: ((j['target_wing_ids'] as List?) ?? const []).map((e) => e.toString()).toList(),
        flatIds: ((j['target_flat_ids'] as List?) ?? const []).map((e) => e.toString()).toList(),
        totalAudience: j['total_audience'] as int? ?? 0,
        ackCount: j['acknowledgement_count'] as int? ?? 0,
        createdByName: j['created_by_name'] as String?,
        createdAt: _dt(j['created_at']),
        isExpired: j['is_expired'] as bool? ?? false,
        acknowledged: j['acknowledged'] as bool?,
      );

  bool get isDraft => status == 'draft';
  bool get isPublished => status == 'published';

  /// Waiting for the reader to say they have read it.
  bool get needsAck => ackRequired && acknowledged == false;
}

class AckPerson {
  final String name;
  final String flat;
  final DateTime? at;
  const AckPerson(this.name, this.flat, this.at);
}

class AckReport {
  final int total, acknowledged, pending;
  final double ratePct;
  final List<AckPerson> acknowledgers;
  final List<AckPerson> pendingPeople;
  const AckReport(this.total, this.acknowledged, this.pending, this.ratePct, this.acknowledgers, this.pendingPeople);

  factory AckReport.fromJson(Map<String, dynamic> j) {
    List<AckPerson> people(String key) => ((j[key] as List?) ?? const [])
        .map((e) => AckPerson(e['name'] as String? ?? '', e['flat'] as String? ?? '', _dt(e['ack_at'])))
        .toList();
    return AckReport(
      j['total_audience'] as int? ?? 0,
      j['acknowledged'] as int? ?? 0,
      j['pending'] as int? ?? 0,
      (j['rate_pct'] as num?)?.toDouble() ?? 0,
      people('acknowledgers'),
      people('pending_people'),
    );
  }
}

const kAlertTypes = <(String, String, IconData)>[
  ('fire', 'Fire', Icons.local_fire_department_rounded),
  ('medical', 'Medical emergency', Icons.medical_services_rounded),
  ('security_threat', 'Security threat', Icons.shield_rounded),
  ('water_leakage', 'Water leakage', Icons.water_damage_rounded),
  ('lift_failure', 'Lift failure', Icons.elevator_rounded),
  ('power_failure', 'Power failure', Icons.power_off_rounded),
  ('gas_leak', 'Gas leak', Icons.gas_meter_rounded),
  ('flood', 'Flood', Icons.flood_rounded),
  ('earthquake', 'Earthquake', Icons.vibration_rounded),
  ('other', 'Other', Icons.warning_amber_rounded),
];
String alertTypeLabel(String t) => kAlertTypes.where((e) => e.$1 == t).firstOrNull?.$2 ?? t;
IconData alertTypeIcon(String t) => kAlertTypes.where((e) => e.$1 == t).firstOrNull?.$3 ?? Icons.warning_amber_rounded;

class EmergencyAlertItem {
  final String id;
  final String type;
  final String title;
  final String? description;
  final String? location;
  final DateTime triggeredAt;
  final String? triggeredBy;
  final bool active;
  final DateTime? resolvedAt;
  final String? resolutionNotes;
  final int? reached;

  const EmergencyAlertItem({
    required this.id,
    required this.type,
    required this.title,
    this.description,
    this.location,
    required this.triggeredAt,
    this.triggeredBy,
    this.active = true,
    this.resolvedAt,
    this.resolutionNotes,
    this.reached,
  });

  factory EmergencyAlertItem.fromJson(Map<String, dynamic> j) => EmergencyAlertItem(
        id: j['id'] as String,
        type: j['alert_type'] as String? ?? 'other',
        title: j['title'] as String? ?? '',
        description: j['description'] as String?,
        location: j['location'] as String?,
        triggeredAt: _dt(j['triggered_at']) ?? DateTime.now(),
        triggeredBy: j['triggered_by_name'] as String?,
        active: (j['status'] as String? ?? 'active') == 'active',
        resolvedAt: _dt(j['resolved_at']),
        resolutionNotes: j['resolution_notes'] as String?,
        reached: j['reached'] as int?,
      );
}

class NoticesApi {
  final Dio _dio;
  NoticesApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<List<NoticeItem>> board(String societyId) async =>
      ((await _dio.get('/notices/society/$societyId/mine')).data as List)
          .map((e) => NoticeItem.fromJson(e as Map<String, dynamic>))
          .toList();

  Future<List<NoticeItem>> manage(String societyId, {String? status}) async =>
      ((await _dio.get('/notices/society/$societyId/all', queryParameters: {'limit': 200, if (status != null) 'status': status}))
              .data as List)
          .map((e) => NoticeItem.fromJson(e as Map<String, dynamic>))
          .toList();

  Future<NoticeItem> get(String id) async =>
      NoticeItem.fromJson((await _dio.get('/notices/$id')).data as Map<String, dynamic>);

  Future<NoticeItem> create(Map<String, dynamic> body) async =>
      NoticeItem.fromJson((await _dio.post('/notices/', data: body)).data as Map<String, dynamic>);

  Future<NoticeItem> update(String id, Map<String, dynamic> body) async =>
      NoticeItem.fromJson((await _dio.patch('/notices/$id', data: body)).data as Map<String, dynamic>);

  Future<void> deleteDraft(String id) => _dio.delete('/notices/$id');

  Future<NoticeItem> publish(String id) async =>
      NoticeItem.fromJson((await _dio.post('/notices/$id/publish')).data as Map<String, dynamic>);

  Future<NoticeItem> archive(String id) async =>
      NoticeItem.fromJson((await _dio.post('/notices/$id/archive')).data as Map<String, dynamic>);

  Future<void> acknowledge(String id, {String? notes}) =>
      _dio.post('/notices/$id/acknowledge', data: {if (notes != null && notes.isNotEmpty) 'notes': notes});

  Future<AckReport> ackReport(String id) async =>
      AckReport.fromJson((await _dio.get('/notices/$id/acknowledgements')).data as Map<String, dynamic>);

  Future<List<EmergencyAlertItem>> activeAlerts(String societyId) async =>
      ((await _dio.get('/notices/emergency/active/$societyId')).data as List)
          .map((e) => EmergencyAlertItem.fromJson(e as Map<String, dynamic>))
          .toList();

  Future<List<EmergencyAlertItem>> alertHistory(String societyId) async =>
      ((await _dio.get('/notices/emergency/history/$societyId')).data as List)
          .map((e) => EmergencyAlertItem.fromJson(e as Map<String, dynamic>))
          .toList();

  Future<EmergencyAlertItem> raiseAlert({
    required String type,
    required String title,
    String? description,
    String? location,
    bool residents = true,
    bool security = true,
    bool committee = true,
  }) async =>
      EmergencyAlertItem.fromJson((await _dio.post('/notices/emergency/', data: {
        'alert_type': type,
        'title': title,
        if (description != null && description.isNotEmpty) 'description': description,
        if (location != null && location.isNotEmpty) 'location': location,
        'notify_all_residents': residents,
        'notify_security': security,
        'notify_committee': committee,
      }))
          .data as Map<String, dynamic>);

  Future<void> resolveAlert(String id, {String? notes}) =>
      _dio.post('/notices/emergency/$id/resolve', data: {if (notes != null && notes.isNotEmpty) 'notes': notes});
}
