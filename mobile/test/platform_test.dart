import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/platform/data/platform_api.dart';

void main() {
  Map<String, dynamic> society(Map<String, dynamic> o) => {
        'id': 's1', 'name': 'Ganesh Residency', 'society_code': 'GNR01', 'city': 'Pune', 'account_status': 'TRIAL',
        'trial_end_date': '2026-11-20', 'trial_days_remaining': 12, 'trial_ended': false, 'user_count': 18, 'flat_count': 40,
        'allowed_users': 50, 'allowed_flats': 100, 'setup_completion_percentage': 60, ...o,
      };

  test('a society says where it stands with us', () {
    final trial = PlatformSociety.fromJson(society({}));
    expect(trial.standing, contains('Trial ends'));
    expect(trial.standing, contains('12 days'));
    final ended = PlatformSociety.fromJson(society({'trial_ended': true, 'trial_days_remaining': 0}));
    expect(ended.standing, startsWith('Trial ended'));
    final paid = PlatformSociety.fromJson(society({'account_status': 'ACTIVE', 'subscription_plan': 'growth', 'subscription_expiry_date': '2027-03-31'}));
    expect(paid.standing, startsWith('Growth plan until'));
    final shut = PlatformSociety.fromJson(society({'account_status': 'SUSPENDED'}));
    expect(shut.suspended, isTrue);
    expect(shut.standing, 'Locked out');
  });

  test('usage and limits are read from the list row', () {
    final s = PlatformSociety.fromJson(society({}));
    expect(s.users, 18);
    expect(s.allowedUsers, 50);
    expect(s.flats, 40);
    expect(s.setupPct, 60);
    expect(statusLabel('ACTIVE'), 'Paid');
    expect(statusLabel('CANCELLED'), 'Closed');
  });

  test('a society detail carries its admins and what has been done to it', () {
    final s = PlatformSociety.fromJson(society({
      'admins': [{'name': 'Asha Admin', 'email': 'asha@x.in', 'last_login': '2026-10-08T05:00:00'}],
      'history': [
        {'at': '2026-10-01T10:00:00', 'by': 'Ops', 'event': 'society_suspended', 'details': {'reason': 'Unpaid'}},
        {'at': '2026-10-02T10:00:00', 'by': 'Ops', 'event': 'limits_changed', 'details': {'old': {'users': 50, 'flats': 100}, 'new': {'users': 80, 'flats': 150}}},
      ],
      'wings': 3,
    }));
    expect(s.admins.single.name, 'Asha Admin');
    expect(s.wings, 3);
    expect(eventLabel(s.history[0].event), 'Suspended');
    expect(eventDetail(s.history[0].event, s.history[0].details), 'Reason: Unpaid');
    expect(eventDetail(s.history[1].event, s.history[1].details), 'Users 50 → 80, flats 100 → 150');
  });

  test('the platform stats read the headline numbers', () {
    final st = PlatformStats.fromJson({'total_societies': 9, 'trial_societies': 4, 'active_societies': 3, 'expired_societies': 1, 'suspended_societies': 1, 'expiring_soon': 2, 'trial_ended_not_marked': 1, 'total_users': 300, 'total_flats': 520});
    expect(st.societies, 9);
    expect(st.endedNotMarked, 1);
    expect(st.users, 300);
  });

  test('"ago" says how long since a sign-in', () {
    expect(ago(null), 'never');
    expect(ago(DateTime.now()), 'today');
    expect(ago(DateTime.now().subtract(const Duration(days: 1, hours: 2))), 'yesterday');
    expect(ago(DateTime.now().subtract(const Duration(days: 9))), '9 days ago');
  });
}
