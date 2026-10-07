import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/notices/data/notices_api.dart';

void main() {
  test('a notice that asks for confirmation is waiting until it is acknowledged', () {
    final n = NoticeItem.fromJson({
      'id': 'n1', 'title': 'Water off', 'content': 'Sunday', 'category': 'water_shutdown', 'priority': 'high',
      'status': 'published', 'acknowledgement_required': true, 'audience_type': 'all', 'acknowledged': false,
      'total_audience': 40, 'acknowledgement_count': 12,
    });
    expect(n.needsAck, isTrue);
    expect(n.isPublished, isTrue);
    expect(noticeCategoryLabel(n.category), 'Water shutdown');
    expect(audienceLabel(n.audience), 'Everyone');
  });

  test('a notice that does not ask is never waiting, and a draft is a draft', () {
    final n = NoticeItem.fromJson({
      'id': 'n2', 'title': 'AGM', 'content': 'Nov 15', 'category': 'events', 'priority': 'normal', 'status': 'draft',
      'acknowledgement_required': false, 'audience_type': 'specific_wings', 'target_wing_ids': ['w1', 'w2'],
    });
    expect(n.needsAck, isFalse);
    expect(n.isDraft, isTrue);
    expect(n.wingIds, ['w1', 'w2']);
    expect(n.acknowledged, isNull);
  });

  test('the acknowledgement report lists who has and has not read it', () {
    final r = AckReport.fromJson({
      'total_audience': 3, 'acknowledged': 1, 'pending': 2, 'rate_pct': 33.3,
      'acknowledgers': [{'name': 'Omkar', 'flat': 'A / 101', 'ack_at': '2026-10-07T05:00:00'}],
      'pending_people': [{'name': 'Tara', 'flat': 'A / 102'}, {'name': 'Bhaskar', 'flat': 'B / 201'}],
    });
    expect(r.ratePct, 33.3);
    expect(r.acknowledgers.single.name, 'Omkar');
    expect(r.pendingPeople.map((p) => p.flat), ['A / 102', 'B / 201']);
  });

  test('an alert in force carries what the banner shows', () {
    final a = EmergencyAlertItem.fromJson({
      'id': 'a1', 'alert_type': 'fire', 'status': 'active', 'title': 'Fire in Wing B basement',
      'location': 'Wing B parking', 'triggered_at': '2026-10-07T04:01:00Z', 'triggered_by_name': 'Asha', 'reached': 6,
    });
    expect(a.active, isTrue);
    expect(a.reached, 6);
    expect(alertTypeLabel(a.type), 'Fire');
    expect(a.triggeredAt.isUtc, isTrue);
  });
}
