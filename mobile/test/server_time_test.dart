import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/utils/server_time.dart';

void main() {
  final moment = DateTime.utc(2026, 10, 9, 4, 1, 2);

  test('a time with Z is the same moment, shown on the local clock', () {
    final d = parseStamp('2026-10-09T04:01:02Z');
    expect(d.isAtSameMomentAs(moment), isTrue);
    expect(d.isUtc, isFalse);
  });

  test('a time without a zone is taken as UTC, not as local', () {
    expect(parseStamp('2026-10-09T04:01:02').isAtSameMomentAs(moment), isTrue);
    expect(parseStamp('2026-10-09T04:01:02.250000').isAtSameMomentAs(moment.add(const Duration(milliseconds: 250))), isTrue);
  });

  test('an explicit offset is respected', () {
    expect(parseStamp('2026-10-09T09:31:02+05:30').isAtSameMomentAs(moment), isTrue);
  });

  test('null and empty give null', () {
    expect(parseStampOrNull(null), isNull);
    expect(parseStampOrNull(''), isNull);
    expect(parseStampOrNull('not a time'), isNull);
  });
}
