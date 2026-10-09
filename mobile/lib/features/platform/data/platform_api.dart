import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

DateTime? _dt(Object? v) => v == null ? null : DateTime.tryParse(v.toString());

String dayText(DateTime? d) => d == null ? '' : DateFormat('d MMM yyyy').format(d.toLocal());
String dayTimeText(DateTime? d) => d == null ? '' : DateFormat('d MMM yyyy, h:mm a').format(d.toLocal());
String apiDay(DateTime d) => DateFormat('yyyy-MM-dd').format(d);

/// "3 days ago", "today"
String ago(DateTime? d) {
  if (d == null) return 'never';
  final days = DateTime.now().difference(d.toLocal()).inDays;
  if (days <= 0) return 'today';
  if (days == 1) return 'yesterday';
  if (days < 60) return '$days days ago';
  return dayText(d);
}

const kStatuses = <(String?, String)>[
  (null, 'All'), ('TRIAL', 'On trial'), ('ACTIVE', 'Paid'), ('EXPIRED', 'Expired'), ('SUSPENDED', 'Suspended'), ('CANCELLED', 'Closed'),
];

const kPlans = <(String, String)>[('starter', 'Starter'), ('growth', 'Growth'), ('enterprise', 'Enterprise')];
String planLabel(String? p) => kPlans.where((e) => e.$1 == p).firstOrNull?.$2 ?? (p ?? '—');

String statusLabel(String s) => switch (s) {
      'TRIAL' => 'On trial',
      'ACTIVE' => 'Paid',
      'EXPIRED' => 'Expired',
      'SUSPENDED' => 'Suspended',
      'CANCELLED' => 'Closed',
      _ => s,
    };
Color statusColor(String s) => switch (s) {
      'ACTIVE' => AppTheme.success,
      'TRIAL' => AppTheme.primary,
      'EXPIRED' => AppTheme.warning,
      'SUSPENDED' => AppTheme.error,
      _ => AppTheme.textSecondary,
    };

String eventLabel(String? e) => switch (e) {
      'society_suspended' => 'Suspended',
      'society_activated' => 'Activated',
      'trial_extended' => 'Trial extended',
      'limits_changed' => 'Limits changed',
      'society_self_registered' => 'Registered',
      _ => e ?? 'Changed',
    };

/// One line saying what an event did, from its details.
String eventDetail(String? e, Map<String, dynamic> d) => switch (e) {
      'society_suspended' => 'Reason: ${d['reason'] ?? '—'}',
      'society_activated' => 'On the ${planLabel(d['plan']?.toString())} plan${d['expires_on'] == null ? '' : ' until ${dayText(_dt(d['expires_on']))}'}',
      'trial_extended' => '${d['extend_days']} more days, now ends ${dayText(_dt(d['new_end_date']))}',
      'limits_changed' => 'Users ${(d['old'] as Map?)?['users']} → ${(d['new'] as Map?)?['users']}, flats ${(d['old'] as Map?)?['flats']} → ${(d['new'] as Map?)?['flats']}',
      _ => '',
    };

class PlatformStats {
  final int societies;
  final int trial;
  final int active;
  final int expired;
  final int suspended;
  final int expiringSoon;
  final int endedNotMarked;
  final int users;
  final int flats;
  const PlatformStats({this.societies = 0, this.trial = 0, this.active = 0, this.expired = 0, this.suspended = 0, this.expiringSoon = 0, this.endedNotMarked = 0, this.users = 0, this.flats = 0});

  factory PlatformStats.fromJson(Map<String, dynamic> j) => PlatformStats(
        societies: j['total_societies'] as int? ?? 0,
        trial: j['trial_societies'] as int? ?? 0,
        active: j['active_societies'] as int? ?? 0,
        expired: j['expired_societies'] as int? ?? 0,
        suspended: j['suspended_societies'] as int? ?? 0,
        expiringSoon: j['expiring_soon'] as int? ?? 0,
        endedNotMarked: j['trial_ended_not_marked'] as int? ?? 0,
        users: j['total_users'] as int? ?? 0,
        flats: j['total_flats'] as int? ?? 0,
      );
}

class AdminPerson {
  final String name;
  final String? email;
  final String? phone;
  final String? status;
  final DateTime? lastLogin;
  const AdminPerson({required this.name, this.email, this.phone, this.status, this.lastLogin});
}

class PlatformEvent {
  final DateTime? at;
  final String? by;
  final String? societyName;
  final String? event;
  final Map<String, dynamic> details;
  const PlatformEvent({this.at, this.by, this.societyName, this.event, this.details = const {}});

  factory PlatformEvent.fromJson(Map<String, dynamic> j) => PlatformEvent(
        at: _dt(j['at']),
        by: j['by'] as String?,
        societyName: j['society_name'] as String?,
        event: j['event'] as String?,
        details: Map<String, dynamic>.from(j['details'] as Map? ?? const {}),
      );
}

class PlatformSociety {
  final String id;
  final String name;
  final String? code;
  final String? city;
  final String status;
  final bool trialEnded;
  final DateTime? trialEnd;
  final int trialDaysRemaining;
  final String? plan;
  final DateTime? subscriptionExpiry;
  final int setupPct;
  final int users;
  final int flats;
  final int allowedUsers;
  final int allowedFlats;
  final DateTime? lastLogin;
  final String? contactName;
  final String? contactEmail;
  final String? contactPhone;
  final DateTime? createdAt;
  // detail only
  final String? address;
  final String? timezone;
  final int allowedStorageMb;
  final int wings;
  final List<AdminPerson> admins;
  final List<PlatformEvent> history;

  const PlatformSociety({
    required this.id,
    required this.name,
    this.code,
    this.city,
    required this.status,
    this.trialEnded = false,
    this.trialEnd,
    this.trialDaysRemaining = 0,
    this.plan,
    this.subscriptionExpiry,
    this.setupPct = 0,
    this.users = 0,
    this.flats = 0,
    this.allowedUsers = 0,
    this.allowedFlats = 0,
    this.lastLogin,
    this.contactName,
    this.contactEmail,
    this.contactPhone,
    this.createdAt,
    this.address,
    this.timezone,
    this.allowedStorageMb = 0,
    this.wings = 0,
    this.admins = const [],
    this.history = const [],
  });

  factory PlatformSociety.fromJson(Map<String, dynamic> j) => PlatformSociety(
        id: j['id'] as String,
        name: j['name'] as String? ?? '',
        code: j['society_code'] as String?,
        city: j['city'] as String?,
        status: j['account_status'] as String? ?? 'TRIAL',
        trialEnded: j['trial_ended'] as bool? ?? false,
        trialEnd: _dt(j['trial_end_date']),
        trialDaysRemaining: j['trial_days_remaining'] as int? ?? 0,
        plan: j['subscription_plan'] as String?,
        subscriptionExpiry: _dt(j['subscription_expiry_date']),
        setupPct: j['setup_completion_percentage'] as int? ?? 0,
        users: j['user_count'] as int? ?? 0,
        flats: j['flat_count'] as int? ?? 0,
        allowedUsers: j['allowed_users'] as int? ?? 0,
        allowedFlats: j['allowed_flats'] as int? ?? 0,
        lastLogin: _dt(j['last_login']),
        contactName: j['contact_person_name'] as String?,
        contactEmail: j['contact_email'] as String?,
        contactPhone: j['contact_phone'] as String?,
        createdAt: _dt(j['created_at']),
        address: j['address'] as String?,
        timezone: j['timezone'] as String?,
        allowedStorageMb: j['allowed_storage_mb'] as int? ?? 0,
        wings: j['wings'] as int? ?? 0,
        admins: [
          for (final a in (j['admins'] as List? ?? const []))
            AdminPerson(name: a['name'] as String? ?? '', email: a['email'] as String?, phone: a['phone'] as String?, status: a['status'] as String?, lastLogin: _dt(a['last_login'])),
        ],
        history: [for (final e in (j['history'] as List? ?? const [])) PlatformEvent.fromJson(e as Map<String, dynamic>)],
      );

  bool get suspended => status == 'SUSPENDED';
  bool get closed => status == 'CANCELLED';

  /// One line about where the society stands with us.
  String get standing {
    switch (status) {
      case 'TRIAL':
        if (trialEnd == null) return 'On trial, no end date set';
        return trialEnded ? 'Trial ended ${dayText(trialEnd)}' : 'Trial ends ${dayText(trialEnd)} ($trialDaysRemaining ${trialDaysRemaining == 1 ? 'day' : 'days'})';
      case 'ACTIVE':
        return '${planLabel(plan)} plan${subscriptionExpiry == null ? '' : ' until ${dayText(subscriptionExpiry)}'}';
      case 'EXPIRED':
        return 'Expired ${dayText(trialEnd)}';
      case 'SUSPENDED':
        return 'Locked out';
      default:
        return statusLabel(status);
    }
  }
}

class PlatformApi {
  final Dio _dio;
  PlatformApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<PlatformStats> stats() async => PlatformStats.fromJson((await _dio.get('/platform-admin/stats')).data as Map<String, dynamic>);

  Future<List<PlatformSociety>> societies({String? q, String? status}) async =>
      ((await _dio.get('/platform-admin/societies', queryParameters: {'limit': 200, if (q != null && q.isNotEmpty) 'q': q, if (status != null) 'status': status})).data as List)
          .map((e) => PlatformSociety.fromJson(e as Map<String, dynamic>))
          .toList();

  Future<PlatformSociety> society(String id) async => PlatformSociety.fromJson((await _dio.get('/platform-admin/societies/$id')).data as Map<String, dynamic>);

  Future<List<PlatformEvent>> activity() async =>
      ((await _dio.get('/platform-admin/activity', queryParameters: {'limit': 100})).data as List).map((e) => PlatformEvent.fromJson(e as Map<String, dynamic>)).toList();

  Future<void> extendTrial(String id, int days) => _dio.post('/platform-admin/societies/$id/extend-trial', data: {'extend_days': days});
  Future<void> suspend(String id, String reason) => _dio.post('/platform-admin/societies/$id/suspend', data: {'reason': reason});
  Future<void> activate(String id, String plan, DateTime? expiresOn) =>
      _dio.post('/platform-admin/societies/$id/activate', data: {'plan': plan, if (expiresOn != null) 'expires_on': apiDay(expiresOn)});
  Future<void> setLimits(String id, int users, int flats, int storageMb) =>
      _dio.put('/platform-admin/societies/$id/limits', data: {'allowed_users': users, 'allowed_flats': flats, 'allowed_storage_mb': storageMb});
}
