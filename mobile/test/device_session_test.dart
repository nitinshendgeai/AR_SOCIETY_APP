import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/auth/domain/entities/device_session.dart';

void main() {
  group('a signed-in device from the server', () {
    final json = {
      'id': 's1', 'device': 'Chrome on Windows', 'ip_address': '203.0.113.7',
      'signed_in_at': '2026-10-05T04:30:00', 'last_seen_at': '2026-10-05T05:00:00', 'current': true,
    };

    test('times arrive as UTC without a zone marker and are read as UTC', () {
      final s = DeviceSession.fromJson(json);
      expect(s.signedInAt.toUtc(), DateTime.utc(2026, 10, 5, 4, 30));
      expect(s.lastSeenAt!.toUtc(), DateTime.utc(2026, 10, 5, 5, 0));
      expect(s.current, isTrue);
      expect(s.device, 'Chrome on Windows');
    });

    test('a time that already says Z is not given a second one', () {
      final s = DeviceSession.fromJson({...json, 'signed_in_at': '2026-10-05T04:30:00Z'});
      expect(s.signedInAt.toUtc(), DateTime.utc(2026, 10, 5, 4, 30));
    });

    test('a missing device name or last-seen time is tolerated', () {
      final s = DeviceSession.fromJson({...json, 'device': null, 'last_seen_at': null, 'current': null});
      expect(s.device, 'Unknown device');
      expect(s.lastSeenAt, isNull);
      expect(s.current, isFalse);
    });
  });

  group('how long ago', () {
    final now = DateTime(2026, 10, 5, 12, 0);
    test('minutes, hours, days', () {
      expect(sinceLabel(now.subtract(const Duration(seconds: 20)), now: now), 'just now');
      expect(sinceLabel(now.subtract(const Duration(minutes: 1)), now: now), '1 minute ago');
      expect(sinceLabel(now.subtract(const Duration(minutes: 45)), now: now), '45 minutes ago');
      expect(sinceLabel(now.subtract(const Duration(hours: 1)), now: now), '1 hour ago');
      expect(sinceLabel(now.subtract(const Duration(hours: 5)), now: now), '5 hours ago');
      expect(sinceLabel(now.subtract(const Duration(days: 1)), now: now), 'yesterday');
      expect(sinceLabel(now.subtract(const Duration(days: 3)), now: now), '3 days ago');
    });

    test('older than a week gives the date; nothing gives nothing', () {
      expect(sinceLabel(DateTime(2026, 9, 21), now: now), '21 Sep');
      expect(sinceLabel(null, now: now), '');
    });
  });
}
