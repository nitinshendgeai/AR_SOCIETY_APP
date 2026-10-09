import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/utils/server_time.dart';

class AutomationRun {
  final String status; // ok | error | running
  final String? summary;
  final bool manual;
  final DateTime? at;
  AutomationRun.fromJson(Map<String, dynamic> j)
      : status = j['status'] as String? ?? 'ok',
        summary = j['summary'] as String?,
        manual = j['manual'] as bool? ?? false,
        at = parseStampOrNull(j['ran_at']);
}

class AutomationJob {
  final String key, title, description, schedule;
  final bool enabled;
  final AutomationRun? lastRun;
  AutomationJob.fromJson(Map<String, dynamic> j)
      : key = j['key'] as String,
        title = j['title'] as String,
        description = j['description'] as String? ?? '',
        schedule = j['schedule'] as String? ?? 'daily',
        enabled = j['enabled'] as bool? ?? false,
        lastRun = j['last_run'] == null ? null : AutomationRun.fromJson(j['last_run'] as Map<String, dynamic>);
}

class AutomationOverview {
  final List<AutomationJob> jobs;
  final int reminderEveryDays, reminderMinMonths;
  AutomationOverview.fromJson(Map<String, dynamic> j)
      : jobs = [for (final x in (j['jobs'] as List)) AutomationJob.fromJson(x as Map<String, dynamic>)],
        reminderEveryDays = ((j['settings'] as Map)['reminder_every_days'] as num?)?.toInt() ?? 7,
        reminderMinMonths = ((j['settings'] as Map)['reminder_min_months'] as num?)?.toInt() ?? 1;
}

class AutomationApi {
  final Dio _dio;
  AutomationApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<AutomationOverview> get(String societyId) async =>
      AutomationOverview.fromJson((await _dio.get('/automation/$societyId')).data as Map<String, dynamic>);

  Future<AutomationOverview> update(String societyId, Map<String, dynamic> changes) async =>
      AutomationOverview.fromJson((await _dio.put('/automation/$societyId', data: changes)).data as Map<String, dynamic>);

  Future<String> runNow(String societyId, String job) async {
    final r = await _dio.post('/automation/$societyId/run', data: {'job': job});
    return (r.data as Map<String, dynamic>)['summary'] as String? ?? 'Done';
  }
}

final automationApiProvider = Provider<AutomationApi>((_) => AutomationApi());

final automationProvider = FutureProvider.autoDispose.family<AutomationOverview, String>(
  (ref, societyId) => ref.watch(automationApiProvider).get(societyId),
);
