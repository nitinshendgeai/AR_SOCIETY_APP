import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';

/// Today's gate figures from `GET /dashboard/security/{societyId}`: counts only, worked out by the server.
/// A figure is null when the server could not work it out (or the Visitors service is switched off); the
/// dashboard then shows it as unavailable, never as 0.
class GateSummary {
  final int? visitorsToday, checkedInToday, inside;
  final bool failed;

  const GateSummary({this.visitorsToday, this.checkedInToday, this.inside, this.failed = false});

  factory GateSummary.fromJson(Map<String, dynamic> j) {
    final today = j['today'] as Map?;
    final errors = {for (final e in (j['errors'] as List? ?? const [])) '$e'};
    int? n(String key) => (today?[key] as num?)?.toInt();
    return GateSummary(
      visitorsToday: n('visitors_today'),
      checkedInToday: n('checked_in_today'),
      inside: n('visitors_inside'),
      failed: errors.contains('today'),
    );
  }
}

final gateSummaryProvider = FutureProvider.autoDispose.family<GateSummary, String>((ref, societyId) async {
  final r = await ApiClient.instance.get('/dashboard/security/$societyId');
  return GateSummary.fromJson(r.data as Map<String, dynamic>);
});
